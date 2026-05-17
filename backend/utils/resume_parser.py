"""
简历解析器 - 使用视觉模型识别简历内容
支持 PDF/DOC/DOCX 格式，提取项目经历、实习经历、学历、技术栈等信息
"""
import os
import json
import base64
import tempfile
import dashscope
from typing import Dict, List, Optional
from pathlib import Path
from dashscope import Generation, MultiModalConversation
from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)


class ResumeParser:
    """
    简历解析器 - 使用 Qwen 视觉模型识别简历内容

    功能：
    - 支持 PDF/DOC/DOCX 格式简历
    - 提取项目经历、实习经历、学历、技术栈等信息
    - 解析结果持久化到数据库
    """

    def __init__(self):
        """初始化简历解析器"""
        self.enabled = config.get('llm.enabled', False)
        self.model = (
            str(os.environ.get('RESUME_PARSER_MODEL', '')).strip()
            or 'qwen3-vl-flash'
        )
        self.api_key = self._resolve_api_key(config.get('llm.api_key'))
        self.timeout = config.get('llm.timeout', 60)  # 简历解析需要更长时间

        # 初始化 API Key
        if self.api_key:
            dashscope.api_key = self.api_key
            Generation.api_key = self.api_key
            logger.info(f"简历解析器初始化成功 - 模型：{self.model}")
        else:
            logger.warning("未配置 API Key，简历解析功能不可用")
            self.enabled = False

        # 解析提示词
        self.system_prompt = """你是一个专业的简历信息提取助手。请从简历图片中提取以下信息：

    0. 基础信息：姓名、邮箱、手机号、所在城市、目标岗位、工作年限、个人简介（如有）

1. 项目经历：包括项目名称、使用的技术栈、项目描述、个人职责
2. 实习/工作经历：包括公司名称、职位、工作时间、工作内容
3. 学历信息：包括学校名称、专业、学历、起止时间（支持多个，如本科、硕士、博士等）
4. 技术栈：包括候选人掌握的所有技术技能

请返回 JSON 格式的结果，格式如下：
{
    "basic_info": {
        "name": "姓名",
        "email": "邮箱",
        "phone": "手机号",
        "city": "所在城市",
        "target_role": "目标岗位",
        "years_of_experience": "工作年限",
        "summary": "个人简介"
    },
    "projects": [
        {
            "name": "项目名称",
            "technologies": ["技术 1", "技术 2"],
            "description": "项目描述",
            "responsibilities": "个人职责"
        }
    ],
    "experiences": [
        {
            "company": "公司名称",
            "position": "职位",
            "duration": "工作时间",
            "description": "工作内容"
        }
    ],
    "education": [
        {
            "school": "学校名称",
            "major": "专业",
            "degree": "学历",
            "start_date": "开始时间",
            "end_date": "结束时间"
        }
    ],
    "skills": ["技能 1", "技能 2", "技能 3"]
}

注意：
- 如果某项信息在简历中不存在，对应字段留空或返回空数组
- 项目名称、公司名称等保持原文
- 技术栈要尽可能详细提取"""

    @staticmethod
    def _resolve_api_key(config_value: Optional[str]) -> Optional[str]:
        """解析 API Key：优先环境变量，其次配置值"""
        env_key = (
            os.environ.get('DASHSCOPE_API_KEY')
            or os.environ.get('BAILIAN_API_KEY')
        )
        if env_key:
            return env_key.strip()

        if isinstance(config_value, str):
            value = config_value.strip()
            if value and not (value.startswith('${') and value.endswith('}')):
                return value

        return None

    def parse_file(self, file_path: str) -> Dict:
        """
        解析简历文件

        Args:
            file_path: 简历文件路径（PDF/DOC/DOCX）

        Returns:
            Dict: 解析后的简历信息
        """
        if not self.enabled:
            logger.error("简历解析器未启用")
            return {"error": "简历解析器未启用"}

        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在：{file_path}")
                return {"error": f"文件不存在：{file_path}"}

            # 将文件转换为图片（对于 PDF/DOC 需要转换）
            image_paths = self._convert_to_images(file_path)

            if not image_paths:
                logger.error("文件转换失败")
                return {"error": "文件转换失败，无法提取内容"}

            # 对每张图片进行 OCR 和内容提取
            all_results = []
            failed_pages = []
            for idx, img_path in enumerate(image_paths, start=1):
                result = self._parse_image(img_path)
                if result and not result.get('error'):
                    all_results.append(result)
                else:
                    failed_pages.append({
                        'page': idx,
                        'file': img_path,
                        'error': (result or {}).get('error', 'unknown parse error')
                    })

            # 合并多页结果
            if all_results:
                return self._merge_results(all_results)
            else:
                logger.error(f"未能从简历中提取到有效内容，失败详情：{failed_pages}")
                return {
                    "error": "未能从简历中提取到有效内容",
                    "details": failed_pages
                }

        except Exception as e:
            logger.error(f"解析简历失败：{e}", exc_info=True)
            return {"error": str(e)}

        finally:
            # 清理临时文件
            self._cleanup_temp_files(file_path)

    def _convert_to_images(self, file_path: str) -> List[str]:
        """
        将 PDF/DOC/DOCX 文件转换为图片

        Args:
            file_path: 输入文件路径

        Returns:
            List[str]: 转换后的图片路径列表
        """
        temp_dir = tempfile.mkdtemp(prefix='resume_parse_')
        image_paths = []

        try:
            file_ext = Path(file_path).suffix.lower()

            if file_ext == '.pdf':
                # 优先直接提取 PDF 文本，避免视觉接口对本地图片 URL 校验失败。
                # 对于可提取文本的电子简历，这条链路更稳定。
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(file_path)
                    text_parts = []
                    for page in reader.pages:
                        text_parts.append((page.extract_text() or '').strip())

                    text_content = '\n'.join([t for t in text_parts if t])
                    if text_content and len(text_content) > 80:
                        txt_path = os.path.join(temp_dir, 'content_from_pdf.txt')
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        image_paths.append(txt_path)
                        logger.info("PDF 文本提取成功，使用文本解析链路")
                        return image_paths
                except Exception as e:
                    logger.warning(f"PDF 文本提取失败，回退到图片解析：{e}")

                # 回退：使用 pdf2image 转换 PDF 为图片
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(file_path, dpi=200)
                    for i, img in enumerate(images):
                        img_path = os.path.join(temp_dir, f'page_{i+1}.png')
                        img.save(img_path, 'PNG')
                        image_paths.append(img_path)
                    logger.info(f"PDF 转换为 {len(image_paths)} 页图片")
                except ImportError:
                    logger.error("pdf2image 未安装，请运行：pip install pdf2image")
                    return []
                except Exception as e:
                    logger.error(f"PDF 转换失败：{e}")
                    return []

            elif file_ext in ['.doc', '.docx']:
                # DOC/DOCX 转换为 PDF 再转图片
                # 注意：这需要先安装 LibreOffice 或使用 python-docx 提取文本
                try:
                    import docx
                    # 对于 DOCX，我们提取文本然后创建简单的图片
                    doc = docx.Document(file_path)
                    text_content = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])

                    if text_content:
                        # 创建文本文件作为备选方案
                        txt_path = os.path.join(temp_dir, 'content.txt')
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(text_content)
                        # 标记使用文本解析
                        image_paths.append(txt_path)
                        logger.info("DOCX 文件已提取文本内容")
                except ImportError:
                    logger.error("python-docx 未安装")
                    return []
                except Exception as e:
                    logger.error(f"DOCX 解析失败：{e}")
                    return []

            elif file_ext in ['.png', '.jpg', '.jpeg']:
                # 已经是图片，直接使用
                image_paths.append(file_path)

            else:
                logger.error(f"不支持的文件格式：{file_ext}")
                return []

        except Exception as e:
            logger.error(f"文件转换失败：{e}")
            return []

        return image_paths

    def _parse_image(self, image_path: str) -> Dict:
        """
        解析单张图片

        Args:
            image_path: 图片路径

        Returns:
            Dict: 解析结果
        """
        try:
            # 检查是否是文本文件（DOCX 提取的情况）
            if image_path.endswith('.txt'):
                with open(image_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                return self._parse_text(text_content)

            # 使用多模态接口解析图片
            # 百炼 API 不支持 file:// URI，需要使用 base64 data URL 格式
            image_data_url = self._build_image_data_url(image_path)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": image_data_url
                        },
                        {
                            "text": self.system_prompt
                        }
                    ]
                }
            ]

            response = MultiModalConversation.call(
                model=self.model,
                messages=messages,
                temperature=0.1,  # 降低温度以获得更稳定的提取结果
                max_tokens=2000,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result_text = self._extract_response_text(response)
                logger.info(f"✓ 简历页面解析成功")
                return self._parse_result_text(result_text)
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return {"error": f"API 错误：{response.message}"}

        except Exception as e:
            logger.error(f"图片解析失败：{e}")
            return {"error": str(e)}

    def _build_image_data_url(self, image_path: str) -> str:
        """
        构建 data URL（data:image/...;base64,...）供视觉模型输入。

        Args:
            image_path: 图片路径

        Returns:
            str: data URL
        """
        suffix = Path(image_path).suffix.lower()
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp'
        }
        mime_type = mime_map.get(suffix, 'image/png')

        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{encoded}"

    def _extract_response_text(self, response) -> str:
        """
        兼容不同 DashScope 响应结构，提取模型文本。
        """
        # 结构1：Generation 风格
        output_text = getattr(getattr(response, 'output', None), 'text', None)
        if output_text:
            return output_text

        # 结构2：choices/message/content 风格
        output = getattr(response, 'output', None)
        choices = getattr(output, 'choices', None) if output else None
        if choices and isinstance(choices, list):
            first = choices[0]
            message = first.get('message', {}) if isinstance(first, dict) else {}
            content = message.get('content', []) if isinstance(message, dict) else []

            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        txt = item.get('text')
                        if txt:
                            parts.append(txt)
                    elif isinstance(item, str):
                        parts.append(item)
                if parts:
                    return '\n'.join(parts)

        return ''

    def _parse_text(self, text_content: str) -> Dict:
        """
        解析纯文本内容

        Args:
            text_content: 文本内容

        Returns:
            Dict: 解析结果
        """
        try:
            # 使用多模态接口处理纯文本（qwen3-vl-flash 支持）
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "text": f"请从以下简历文本中提取信息：\n\n{text_content}"
                        }
                    ]
                }
            ]

            response = MultiModalConversation.call(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result_text = self._extract_response_text(response)
                logger.info("✓ 简历文本解析成功")
                return self._parse_result_text(result_text)
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return {"error": f"API 错误：{response.message}"}

        except Exception as e:
            logger.error(f"文本解析失败：{e}")
            return {"error": str(e)}

    def _parse_result_text(self, text: str) -> Dict:
        """
        解析模型返回的文本，提取 JSON 结果

        Args:
            text: 模型返回的文本

        Returns:
            Dict: 解析后的 JSON 数据
        """
        import re

        try:
            # 尝试直接解析 JSON
            result = json.loads(text)
            return self._normalize_parsed_result(result)
        except json.JSONDecodeError:
            pass

        try:
            # 尝试提取 JSON 内容
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return self._normalize_parsed_result(result)
        except Exception as e:
            logger.error(f"JSON 解析失败：{e}")

        # 如果都失败，返回原始文本
        return {
            "raw_text": text,
            "parse_error": "无法解析为 JSON 格式"
        }

    def _normalize_parsed_result(self, result: Dict) -> Dict:
        """统一解析结果结构，避免前后端字段不一致。"""
        if not isinstance(result, dict):
            return {
                "basic_info": {},
                "projects": [],
                "experiences": [],
                "education": [],
                "skills": []
            }

        normalized = dict(result)

        basic_info = normalized.get('basic_info')
        normalized['basic_info'] = basic_info if isinstance(basic_info, dict) else {}

        for key in ['projects', 'experiences', 'skills']:
            value = normalized.get(key)
            normalized[key] = value if isinstance(value, list) else []

        education = normalized.get('education')
        if isinstance(education, list):
            normalized['education'] = education
        elif isinstance(education, dict):
            normalized['education'] = [education] if education else []
        else:
            normalized['education'] = []

        return normalized

    def _merge_results(self, results: List[Dict]) -> Dict:
        """
        合并多页解析结果

        Args:
            results: 每页的解析结果列表

        Returns:
            Dict: 合并后的结果
        """
        merged = {
            "basic_info": {
                "name": "",
                "email": "",
                "phone": "",
                "city": "",
                "target_role": "",
                "years_of_experience": "",
                "summary": ""
            },
            "projects": [],
            "experiences": [],
            "education": [],
            "skills": [],
            "source_pages": len(results)
        }

        for result in results:
            normalized_result = self._normalize_parsed_result(result)

            # 合并基础信息（优先使用先出现的非空值）
            basic_info = normalized_result.get("basic_info", {})
            for field in ["name", "email", "phone", "city", "target_role", "years_of_experience", "summary"]:
                if not merged["basic_info"].get(field) and basic_info.get(field):
                    merged["basic_info"][field] = str(basic_info.get(field)).strip()

            # 合并项目经历
            if normalized_result["projects"]:
                merged["projects"].extend(normalized_result["projects"])

            # 合并工作经历
            if normalized_result["experiences"]:
                merged["experiences"].extend(normalized_result["experiences"])

            # 合并教育信息
            if normalized_result["education"]:
                merged["education"].extend(normalized_result["education"])

            # 合并技能（去重）
            if normalized_result["skills"]:
                for skill in normalized_result["skills"]:
                    if skill and skill not in merged["skills"]:
                        merged["skills"].append(skill)

        logger.info(f"✓ 合并完成，共 {len(results)} 页")
        return merged

    def _cleanup_temp_files(self, original_file: str):
        """清理临时文件"""
        try:
            # 只清理我们创建的临时目录中的文件
            temp_dirs = list(Path(tempfile.gettempdir()).glob('resume_parse_*'))
            for temp_dir in temp_dirs:
                if temp_dir.is_dir():
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.debug(f"清理临时目录：{temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败：{e}")

    def check_enabled(self) -> bool:
        """检查解析器是否可用"""
        return self.enabled


# 创建全局解析器实例
resume_parser = ResumeParser()
