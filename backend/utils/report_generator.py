"""
PDF 报告生成模块
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import REPORT_OUTPUT_DIR


class ReportGenerator:
    """
    PDF 报告生成器
    """
    
    def __init__(self):
        """初始化报告生成器"""
        # 确保输出目录存在
        self.output_dir = os.path.abspath(REPORT_OUTPUT_DIR)
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                print(f"Created reports directory: {self.output_dir}")
            else:
                print(f"Reports directory exists: {self.output_dir}")
        except Exception as e:
            print(f"Error creating reports directory: {e}")
            # 使用备用目录
            self.output_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"Using fallback directory: {self.output_dir}")
        
        # 尝试注册中文字体（可选）
        try:
            font_path = "C:\\Windows\\Fonts\\msyh.ttc"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                self.chinese_font_available = True
            else:
                self.chinese_font_available = False
        except:
            self.chinese_font_available = False
    
    def _generate_assessment_text(self, max_prob: float, total_events: int, 
                                  gaze_count: int, mouth_count: int, 
                                  multi_person_count: int, off_screen_ratio: float) -> str:
        """
        基于实际检测数据生成智能综合评估文本（中文）
        
        Args:
            max_prob: 最高作弊概率
            total_events: 总事件数
            gaze_count: 眼神偏离次数
            mouth_count: 异常张嘴次数
            multi_person_count: 多人出现次数
            off_screen_ratio: 屏幕外注视时间占比
            
        Returns:
            str: 综合评估文本
        """
        assessment_parts = []
        
        # 基础风险判定
        if max_prob >= 60:
            assessment_parts.append("本次面试检测到高度可疑行为")
            urgency = "建议立即审查面试录像"
        elif max_prob >= 30:
            assessment_parts.append("本次面试检测到中等程度的可疑行为")
            urgency = "建议结合其他评估指标综合判断"
        else:
            assessment_parts.append("本次面试未检测到明显的作弊迹象")
            urgency = "面试者行为表现正常"
        
        # 事件分析
        if total_events == 0:
            assessment_parts.append("，全程无异常事件记录")
        else:
            event_desc = f"，共记录 {total_events} 个异常事件"
            
            # 详细事件分类
            event_details = []
            if gaze_count > 0:
                if gaze_count >= 8:
                    event_details.append(f"眼神偏离频繁（{gaze_count}次）")
                elif gaze_count >= 4:
                    event_details.append(f"眼神偏离较多（{gaze_count}次）")
                else:
                    event_details.append(f"眼神偏离{gaze_count}次")
            
            if mouth_count > 0:
                if mouth_count >= 5:
                    event_details.append(f"异常张嘴频繁（{mouth_count}次）")
                else:
                    event_details.append(f"异常张嘴{mouth_count}次")
            
            if multi_person_count > 0:
                event_details.append(f"检测到多人出现{multi_person_count}次")
            
            if event_details:
                event_desc += "，包括：" + "、".join(event_details)
            
            assessment_parts.append(event_desc)
        
        # 屏幕外注视分析
        if off_screen_ratio > 20:
            assessment_parts.append(f"。注意到面试者屏幕外注视时间占比较高（{off_screen_ratio:.1f}%），可能存在查看其他资料的行为")
        elif off_screen_ratio > 10:
            assessment_parts.append(f"。屏幕外注视时间占比为{off_screen_ratio:.1f}%，略高于正常水平")
        
        # 主要问题识别
        if max_prob >= 30:
            assessment_parts.append("。")
            
            # 识别主要异常类型
            if multi_person_count > 0:
                assessment_parts.append("主要风险点为检测到其他人员出现，严重违反面试规则")
            elif gaze_count > mouth_count and gaze_count >= 5:
                assessment_parts.append("主要问题为频繁的眼神偏离，可能在查看屏幕外资料")
            elif mouth_count >= 3:
                assessment_parts.append("主要问题为多次异常张嘴行为，可能存在与他人交流的情况")
            elif off_screen_ratio > 15:
                assessment_parts.append("主要问题为注意力不集中，频繁看向屏幕外")
            else:
                assessment_parts.append("存在多种异常行为模式")
        else:
            assessment_parts.append("。")
        
        # 添加处理建议
        assessment_parts.append(urgency)
        
        # 具体建议
        if max_prob >= 60:
            if multi_person_count > 0:
                assessment_parts.append("，重点核查多人出现的时间段")
            elif gaze_count >= 8:
                assessment_parts.append("，重点关注眼神偏离时段的行为")
            else:
                assessment_parts.append("，建议人工复核关键时段")
        elif max_prob >= 30:
            if total_events > 8:
                assessment_parts.append("，可疑事件频率较高，需要进一步确认")
            else:
                assessment_parts.append("，建议对比同批次其他面试者的表现")
        else:
            if total_events <= 2:
                assessment_parts.append("，仅有轻微异常可忽略")
            else:
                assessment_parts.append("，偶发异常属于正常范围")
        
        return "".join(assessment_parts) + "。"
    
    def _generate_suggestions(self, max_prob: float, total_events: int,
                             gaze_count: int, mouth_count: int,
                             multi_person_count: int, off_screen_ratio: float) -> str:
        """
        基于检测数据生成详细的面试者建议
        
        Args:
            max_prob: 最高作弊概率
            total_events: 总事件数
            gaze_count: 眼神偏离次数
            mouth_count: 异常张嘴次数
            multi_person_count: 多人出现次数
            off_screen_ratio: 屏幕外注视时间占比
            
        Returns:
            str: 面试者建议文本
        """
        suggestions = []
        
        # 开场语
        if max_prob >= 60:
            suggestions.append("本次面试检测到较多异常行为，为确保未来面试的顺利进行，请重点关注以下建议：\n\n")
        elif max_prob >= 30:
            suggestions.append("本次面试表现尚可，但仍有改进空间，建议注意以下几点：\n\n")
        else:
            suggestions.append("本次面试表现良好，以下建议可帮助您在未来面试中表现得更加出色：\n\n")
        
        suggestion_items = []
        
        # 针对眼神偏离的建议
        if gaze_count > 0:
            if gaze_count >= 8:
                suggestion_items.append(
                    "【视线管理 - 重点改进】\n"
                    "检测到您在面试过程中频繁移开视线。建议：\n"
                    "• 将摄像头放置在与眼睛平行的位置，保持自然的视线接触\n"
                    "• 面试时专注看向摄像头，想象在与面试官进行眼神交流\n"
                    "• 避免频繁查看屏幕其他区域或周围环境\n"
                    "• 如需思考，可短暂看向上方（不超过2-3秒），但避免左右张望\n"
                    "• 准备充分的面试材料，避免临时查找资料\n"
                )
            elif gaze_count >= 4:
                suggestion_items.append(
                    "【视线管理 - 需要注意】\n"
                    "您的视线有时会偏离摄像头。建议：\n"
                    "• 保持与摄像头的自然视线接触，这能传达自信和专注\n"
                    "• 调整摄像头位置，确保无需移动头部即可看到面试官\n"
                    "• 思考时可适当停顿，无需频繁转移视线\n"
                )
            else:
                suggestion_items.append(
                    "【视线管理 - 保持良好】\n"
                    "整体视线管理较好，继续保持与摄像头的自然交流即可。偶尔的视线移动属于正常情况。\n"
                )
        
        # 针对异常张嘴的建议
        if mouth_count > 0:
            if mouth_count >= 5:
                suggestion_items.append(
                    "【沟通规范 - 重点改进】\n"
                    "检测到您在面试中有多次异常交流行为。建议：\n"
                    "• 确保面试环境安静独立，避免他人打扰\n"
                    "• 回答问题前可先在心中组织语言，避免过多的口头语或停顿\n"
                    "• 如需时间思考，可礼貌告知面试官：'请让我思考一下'\n"
                    "• 保持专业的面试状态，避免与他人交谈或自言自语\n"
                    "• 关闭所有通讯设备和软件的通知功能\n"
                )
            elif mouth_count >= 2:
                suggestion_items.append(
                    "【沟通规范 - 需要注意】\n"
                    "您在面试中的表达状态良好，但建议：\n"
                    "• 回答问题时保持清晰、简洁的表达\n"
                    "• 减少不必要的口头语（如'嗯'、'啊'、'那个'等）\n"
                    "• 确保环境无他人干扰，维持专业的面试氛围\n"
                )
        
        # 针对多人出现的建议
        if multi_person_count > 0:
            suggestion_items.append(
                "【环境要求 - 严重违规】\n"
                "检测到面试过程中有其他人员出现，这严重违反面试规则。必须改进：\n"
                "• 选择独立、封闭的房间进行面试，确保全程无他人出现\n"
                "• 面试前告知家人或室友，避免在面试期间进入房间\n"
                "• 在门上张贴'面试中，请勿打扰'的提示\n"
                "• 如使用共享空间，提前预约独立时段\n"
                "• 面试开始前检查摄像头范围内无他人可能出现的区域\n"
                "• 这是面试的基本要求，必须严格遵守！\n"
            )
        
        # 针对屏幕外注视时间占比的建议
        if off_screen_ratio > 20:
            suggestion_items.append(
                "【专注度管理 - 重点改进】\n"
                "您在面试中的注意力较为分散。建议：\n"
                "• 移除桌面和视野范围内的所有干扰物品（手机、书籍、笔记等）\n"
                "• 关闭电脑上所有与面试无关的应用程序和网页\n"
                "• 将面试问题的关键点记在心中，而非依赖外部资料\n"
                "• 提前熟悉常见面试问题，减少现场查找资料的需求\n"
                "• 专心聆听面试官的问题，展现您的专注和重视\n"
            )
        elif off_screen_ratio > 10:
            suggestion_items.append(
                "【专注度管理 - 需要注意】\n"
                "建议进一步提高面试专注度：\n"
                "• 清理桌面，保持视野整洁\n"
                "• 将简历和重要信息提前熟记，无需频繁查看\n"
                "• 面试时全神贯注于对话本身\n"
            )
        
        # 通用面试技巧建议
        general_tips = []
        
        if max_prob < 30 and total_events <= 3:
            # 表现良好的情况
            general_tips.append(
                "【整体表现 - 优秀】\n"
                "您本次面试的技术操作和行为规范都表现出色！以下建议可帮助您更上一层楼：\n"
            )
        
        general_tips.extend([
            "【环境准备建议】\n"
            "• 选择光线充足、背景整洁的环境\n"
            "• 确保网络连接稳定，提前测试设备\n"
            "• 调整摄像头角度，让面部完整清晰地出现在画面中\n"
            "• 保持环境安静，避免背景噪音\n",
            
            "【仪态姿势建议】\n"
            "• 保持端正的坐姿，展现专业形象\n"
            "• 面部表情自然放松，适时微笑\n"
            "• 双手可自然放在桌面上，偶尔配合手势强调重点\n"
            "• 避免频繁调整坐姿或触摸面部\n",
            
            "【内容准备建议】\n"
            "• 提前研究公司和岗位信息\n"
            "• 准备好自我介绍和常见问题的回答框架\n"
            "• 梳理个人经历，准备具体的案例和数据\n"
            "• 准备2-3个向面试官提问的问题\n",
            
            "【沟通技巧建议】\n"
            "• 回答问题时保持逻辑清晰，先说结论再展开\n"
            "• 使用STAR法则（情境、任务、行动、结果）描述经历\n"
            "• 控制回答时长，避免过于冗长或过于简短\n"
            "• 认真倾听问题，必要时可礼貌地要求面试官重复或澄清\n",
            
            "【心态调整建议】\n"
            "• 面试前做深呼吸放松，保持自信心态\n"
            "• 将面试视为展示自己的机会，而非单纯的考核\n"
            "• 对不确定的问题，诚实表达并展示学习意愿\n"
            "• 面试结束后及时复盘，总结经验教训\n"
        ])
        
        # 组装建议内容
        if suggestion_items:
            suggestions.append("\n".join(suggestion_items))
            suggestions.append("\n")
        
        suggestions.append("\n".join(general_tips))
        
        # 结束语
        if max_prob >= 60:
            suggestions.append(
                "\n【重要提醒】\n"
                "本次面试检测到较多不规范行为，请务必重视并改进。"
                "严格遵守面试规则不仅是对面试官的尊重，也是展现个人职业素养的重要方式。"
                "相信通过认真准备和改进，您一定能在下次面试中表现得更好！"
            )
        elif max_prob >= 30:
            suggestions.append(
                "\n【温馨提示】\n"
                "您已经有不错的基础，通过以上建议的改进，相信您能在面试中展现更专业的一面。"
                "祝您面试顺利，取得满意的结果！"
            )
        else:
            suggestions.append(
                "\n【鼓励寄语】\n"
                "您的面试表现已经很出色！继续保持专业态度和良好习惯，"
                "在未来的职业道路上，您一定能够取得更大的成功。加油！"
            )
        
        return "".join(suggestions)
            
    def generate_report(self, data: Dict, filename: Optional[str] = None) -> str:
        """
        生成面试报告
        
        Args:
            data: 面试数据
            filename: 输出文件名（不含扩展名），如果为 None 则自动生成
            
        Returns:
            str: 生成的 PDF 文件路径
        """
        try:
            # 生成文件名
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"interview_report_{timestamp}"
            
            filepath = os.path.join(self.output_dir, f"{filename}.pdf")
            print(f"Generating report at: {filepath}")
        
            # 创建 PDF 文档
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            story = []
            
            # 样式
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#2C3E50'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#34495E'),
                spaceAfter=12,
                spaceBefore=12
            )
            
            # 标题
            story.append(Paragraph("Interview Anti-Cheating Report", title_style))
            story.append(Spacer(1, 0.3 * inch))
            
            # 基本信息
            summary = data['summary']
            story.append(Paragraph("Basic Information", heading_style))
            
            basic_info_data = [
                ['Interview Start Time:', summary.get('start_time_str', 'N/A')],
                ['Interview End Time:', summary.get('end_time_str', 'N/A')],
                ['Total Duration:', summary.get('duration_str', '0s')],
                ['Frames Processed:', str(summary.get('frames_processed', 0))],
            ]
            
            basic_info_table = Table(basic_info_data, colWidths=[2.5*inch, 4*inch])
            basic_info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(basic_info_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # 统计数据
            story.append(Paragraph("Statistics", heading_style))
            statistics = data['statistics']
            
            # 风险等级
            max_prob = statistics.get('max_probability', 0)
            if max_prob < 30:
                risk_level = "LOW RISK"
                risk_color = colors.green
            elif max_prob < 60:
                risk_level = "MEDIUM RISK"
                risk_color = colors.orange
            else:
                risk_level = "HIGH RISK"
                risk_color = colors.red
            
            stats_data = [
                ['Maximum Cheating Probability:', f"{max_prob:.2f}%"],
                ['Average Cheating Probability:', f"{statistics.get('avg_probability', 0):.2f}%"],
                ['Risk Level:', risk_level],
                ['Total Gaze Deviations:', str(statistics.get('total_deviations', 0))],
                ['Total Abnormal Mouth Opens:', str(statistics.get('total_mouth_open', 0))],
                ['Multiple Persons Detected:', 'Yes' if statistics.get('multi_person_detected', False) else 'No'],
                ['Off-Screen Time Ratio:', f"{statistics.get('off_screen_ratio', 0):.2f}%"],
            ]
            
            stats_table = Table(stats_data, colWidths=[3*inch, 3.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('TEXTCOLOR', (1, 2), (1, 2), risk_color),
                ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),
            ]))
            story.append(stats_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # 异常事件列表
            story.append(Paragraph("Abnormal Events", heading_style))
            
            all_events = data['events']
            if len(all_events) > 0:
                # 限制显示最多20个事件
                events_to_show = all_events[:20]
                
                events_data = [['No.', 'Type', 'Time', 'Details']]
                for idx, event in enumerate(events_to_show, 1):
                    event_type = event.get('type', 'Unknown')
                    event_time = event.get('datetime', 'N/A')
                    
                    # 详情
                    if event_type == 'gaze_deviation':
                        details = f"Direction: {event.get('direction', 'N/A')}, Duration: {event.get('duration', 0):.1f}s"
                    elif event_type == 'mouth_open':
                        details = f"Duration: {event.get('duration', 0):.1f}s"
                    elif event_type == 'multi_person':
                        details = f"Faces: {event.get('num_faces', 0)}"
                    else:
                        details = "N/A"
                    
                    events_data.append([str(idx), event_type, event_time, details])
                
                events_table = Table(events_data, colWidths=[0.5*inch, 1.5*inch, 2*inch, 2.5*inch])
                events_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
                ]))
                story.append(events_table)
                
                if len(all_events) > 20:
                    story.append(Spacer(1, 0.1 * inch))
                    story.append(Paragraph(f"... and {len(all_events) - 20} more events", styles['Normal']))
            else:
                story.append(Paragraph("No abnormal events detected.", styles['Normal']))
            
            story.append(Spacer(1, 0.3 * inch))
            
            # 统计各类事件数量（用于生成评估）- 使用已定义的all_events
            gaze_events_list = [e for e in all_events if e.get('type') == 'gaze_deviation']
            mouth_events_list = [e for e in all_events if e.get('type') == 'mouth_open']
            multi_person_events_list = [e for e in all_events if e.get('type') == 'multi_person']
            
            # 生成智能综合评估（中文）
            assessment_zh = self._generate_assessment_text(
                max_prob, len(all_events), len(gaze_events_list), 
                len(mouth_events_list), len(multi_person_events_list),
                statistics.get('off_screen_ratio', 0)
            )
            
            # 生成面试者建议（中文）
            suggestions_zh = self._generate_suggestions(
                max_prob, len(all_events), len(gaze_events_list),
                len(mouth_events_list), len(multi_person_events_list),
                statistics.get('off_screen_ratio', 0)
            )
            
            print(f"Generated assessment text: {assessment_zh[:100]}...")  # 调试信息
            print(f"Generated suggestions text: {len(suggestions_zh)} chars")  # 调试信息
            
            # 综合评估（英文版用于PDF）
            story.append(Paragraph("Overall Assessment", heading_style))
            
            if max_prob < 30:
                assessment_en = "The interviewee showed normal behavior throughout the interview. No significant signs of cheating were detected."
            elif max_prob < 60:
                assessment_en = "The interviewee showed some suspicious behaviors during the interview. Moderate risk of cheating detected. Further review recommended."
            else:
                assessment_en = "The interviewee showed highly suspicious behaviors during the interview. High risk of cheating detected. Immediate review required."
            
            story.append(Paragraph(assessment_en, styles['Normal']))
            
            # 页脚
            story.append(Spacer(1, 0.5 * inch))
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
            story.append(Paragraph("Interview Anti-Cheating System v1.0", footer_style))
            
            # 生成 PDF
            doc.build(story)
            
            # 保存元数据到JSON文件
            metadata_path = os.path.join(self.output_dir, f"{filename}.json")
            
            print(f"Saving metadata with assessment_text length: {len(assessment_zh)} chars")  # 调试信息
            
            metadata = {
                'filename': f"{filename}.pdf",
                'timestamp': summary.get('end_time_str', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'duration': summary.get('duration_str', 'N/A'),
                'max_probability': statistics.get('max_probability', 0),
                'avg_probability': statistics.get('avg_probability', 0),
                'risk_level': risk_level,
                'events_count': len(all_events),
                'assessment_text': assessment_zh,  # 智能生成的综合评估文本
                'suggestions_text': suggestions_zh,  # 智能生成的面试者建议
                'statistics': {
                    'total_deviations': len(gaze_events_list),
                    'total_mouth_open': len(mouth_events_list),
                    'total_multi_person': len(multi_person_events_list),
                    'multi_person_detected': statistics.get('multi_person_detected', False),
                    'off_screen_ratio': statistics.get('off_screen_ratio', 0),
                    'frames_processed': summary.get('frames_processed', 0)
                },
                'content_summary': {
                    'has_basic_info': True,
                    'has_statistics': True,
                    'has_events': len(all_events) > 0,
                    'has_assessment': True,
                    'events_details': {
                        'gaze_deviation_count': len(gaze_events_list),
                        'mouth_open_count': len(mouth_events_list),
                        'multi_person_count': len(multi_person_events_list)
                    }
                }
            }
            
            try:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print(f"Metadata saved: {metadata_path}")
            except Exception as e:
                print(f"Warning: Failed to save metadata: {e}")
            
            print(f"Report generated successfully: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error generating report: {e}")
            import traceback
            traceback.print_exc()
            raise
