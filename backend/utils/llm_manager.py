"""
大模型管理器 - 集成阿里通义 Qwen
用于面试官实时对话与追问
支持 4 轮面试：技术基础、项目深度、系统设计、HR 综合
"""
import os
import json
import dashscope
from typing import Optional, Dict, List
from dashscope import Generation
from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)

# 面试轮次配置
INTERVIEW_ROUNDS = {
    'technical': {
        'name': '技术基础面',
        'description': '考察基础知识、编码能力、语言特性、框架原理',
        'system_prompt': """你是一面技术面试官，重点考察候选人的技术基础。

考察重点：
1. 基础知识扎实程度（数据结构、算法、语言特性）
2. 编码规范和代码理解深度
3. 对常用框架的原理理解
4. 计算机基础（网络、操作系统、数据库）

提问风格：
- 由浅入深，循序渐进
- 注重基础概念和理解深度
- 适当追问底层原理
- 每次只问一个问题，问题要清晰具体

回答要求：
- 字数控制在 200 字以内
- 语言专业但不生硬
- 如果候选人回答不理想，可以给予提示或追问更深层的知识点"""
    },
    'project': {
        'name': '项目深度面',
        'description': '考察项目经验、技术深度、问题解决能力',
        'system_prompt': """你是二面项目面试官，重点考察候选人的项目经验和技术深度。

考察重点：
1. 简历中项目的真实性和参与深度
2. 技术选型理由和替代方案思考
3. 遇到的技术难点和解决思路
4. 项目中的个人贡献和成长

提问风格：
- 结合候选人的项目经历进行追问
- 关注"为什么这么做"而不是"做了什么"
- 深入技术细节，验证真实性
- 考察解决复杂问题的思路

回答要求：
- 每次只提一个问题，问题要具体
- 字数控制在 200 字以内
- 对于模糊的回答要追问细节
- 关注候选人的技术深度和思考能力"""
    },
    'system_design': {
        'name': '系统设计面',
        'description': '考察架构能力、全局思维、技术权衡能力',
        'system_prompt': """你是三面系统设计面试官，重点考察候选人的架构设计能力。

考察重点：
1. 系统设计能力和架构思维
2. 高并发、高可用、高扩展场景的处理
3. 技术选型的权衡能力（trade-off）
4. 对分布式系统的理解

提问风格：
- 给出实际场景题，让候选人设计方案
- 关注系统边界和模块划分
- 追问性能瓶颈和解决方案
- 考察技术选型的理由

回答要求：
- 问题要描述清晰的场景和需求
- 字数控制在 300 字以内
- 引导候选人思考扩展性问题
- 关注设计思路而非标准答案"""
    },
    'hr': {
        'name': 'HR 综合面',
        'description': '考察软技能、文化匹配、职业规划',
        'system_prompt': """你是四面 HR 面试官，重点考察候选人的综合素质。

考察重点：
1. 职业规划清晰度和自我认知
2. 沟通表达能力和逻辑思维
3. 团队协作和领导力潜质
4. 文化匹配度和稳定性
5. 离职动机和求职期望

提问风格：
- 开放性问题为主
- 了解候选人的价值观和动机
- 适当的压力面试（可选）
- 关注软技能和潜力

回答要求：
- 问题要开放但有边界
- 字数控制在 200 字以内
- 语言友好但保持专业性
- 给予候选人充分表达空间"""
    }
}


class LLMManager:
    """大模型管理器 - 处理与 Qwen 的交互"""
    
    def __init__(self):
        """初始化 LLM 管理器"""
        self.enabled = config.get('llm.enabled', False)
        self.provider = config.get('llm.provider', 'qwen')
        self.model = config.get('llm.model', 'qwen-max')
        self.api_key = self._resolve_api_key(config.get('llm.api_key'))
        self.timeout = config.get('llm.timeout', 30)
        self.current_round = 'technical'
        self.resume_data: Optional[Dict] = None
        
        # 初始化 API Key
        if self.api_key:
            # DashScope SDK 在不同调用路径中可能读取 dashscope.api_key，
            # 这里同时设置两个入口，避免“配置了但仍提示 No api key provided”。
            dashscope.api_key = self.api_key
            Generation.api_key = self.api_key
            logger.info(f"LLM 管理器初始化成功 - 模型: {self.model}")
        else:
            logger.warning("未配置 DASHSCOPE_API_KEY/BAILIAN_API_KEY，LLM 功能不可用")
            self.enabled = False
        
        # 面试官系统提示词
        self.system_prompt = """你是一位专业的互联网大厂的技术面试官，具有多年招聘经验。

你的职责：
1. 根据候选人的回答提出相关问题或追问
2. 评估候选人的技术水平、思维能力和表达能力
3. 提问应该循序渐进，难度逐步提升
4. 对于不清楚或不完整的回答，要求进一步解释

回答要求：
- 每次只提一个问题，问题要清晰具体
- 字数控制在 100 字以内
- 语言专业但不生硬，要体现面试官的专业性
- 如果候选人回答不理想，可以提出改进建议或追问更深层的知识点"""

    @staticmethod
    def _resolve_api_key(config_value: Optional[str]) -> Optional[str]:
        """解析 API Key：优先环境变量，其次配置值，并过滤占位符。"""
        env_key = (
            os.environ.get('DASHSCOPE_API_KEY')
            or os.environ.get('BAILIAN_API_KEY')
        )
        if env_key:
            return env_key.strip()

        if isinstance(config_value, str):
            value = config_value.strip()
            # 过滤 config.yaml 中类似 ${BAILIAN_API_KEY} 的占位符文本
            if value and not (value.startswith('${') and value.endswith('}')):
                return value

        return None
    
    def check_enabled(self) -> bool:
        """检查 LLM 是否启用"""
        if not self.enabled:
            logger.warning("LLM 功能未启用或 API Key 未配置")
            return False
        return True
    
    def generate_interview_question(
        self,
        position: str,
        difficulty: str = "medium",
        context: Optional[str] = None
    ) -> str:
        """
        生成面试问题
        
        Args:
            position: 职位名称，如 "Java后端工程师"
            difficulty: 难度等级 "easy", "medium", "hard"
            context: 上下文信息，如之前的问答历史
        
        Returns:
            生成的面试问题
        """
        if not self.check_enabled():
            return ""
        
        try:
            difficulty_map = {
                "easy": "基础",
                "medium": "中等",
                "hard": "高级"
            }
            
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": (
                        f"请为【{position}】职位生成一个【{difficulty_map.get(difficulty, '中等')}】难度的面试问题。"
                        f"{f'背景信息：{context}' if context else ''}\n"
                        f"请直接给出问题，不要多余的解释。"
                    )
                }
            ]
            
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.7,
                top_k=50,
                temperature=0.7,
                max_tokens=500,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                question = response.output.text
                logger.info(f"✓ 生成面试问题 - 职位: {position}, 难度: {difficulty}")
                return question
            else:
                logger.error(f"✗ API 错误: {response.message}")
                return ""
        
        except Exception as e:
            logger.error(f"✗ 生成面试问题失败: {str(e)}")
            return ""
    
    def process_answer(
        self,
        user_answer: str,
        current_question: str,
        position: str,
        chat_history: Optional[list] = None
    ) -> str:
        """
        处理用户回答，生成追问或下一个问题
        
        Args:
            user_answer: 用户的回答文本
            current_question: 当前的问题
            position: 职位名称
            chat_history: 对话历史
        
        Returns:
            面试官的反馈和下一个问题
        """
        if not self.check_enabled():
            return ""
        
        try:
            # 构建上下文
            history_context = ""
            if chat_history:
                for item in chat_history[-3:]:  # 只保留最近3条对话
                    if "role" in item and "content" in item:
                        history_context += f"{item['role']}: {item['content']}\n"
            
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            
            # 添加历史对话
            if chat_history:
                for item in chat_history[-4:]:  # 最近4条历史
                    if "role" in item and "content" in item:
                        messages.append(item)
            
            # 添加用户答案
            messages.append({
                "role": "user",
                "content": f"当前问题: {current_question}\n\n我的回答: {user_answer}"
            })
            
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.7,
                top_k=50,
                temperature=0.7,
                max_tokens=500,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                feedback = response.output.text
                logger.info(f"✓ 处理回答 - 职位: {position}")
                return feedback
            else:
                logger.error(f"✗ API 错误: {response.message}")
                return ""
        
        except Exception as e:
            logger.error(f"✗ 处理回答失败: {str(e)}")
            return ""
    
    def evaluate_answer(
        self,
        user_answer: str,
        question: str,
        position: str
    ) -> dict:
        """
        评估用户回答的质量
        
        Args:
            user_answer: 用户的回答
            question: 对应的问题
            position: 职位名称
        
        Returns:
            包含评分和评价的字典
        """
        if not self.check_enabled():
            return {"score": 0, "feedback": "LLM 功能未启用"}
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一位资深面试官，需要评估候选人的回答质量。"
                        "请返回 JSON 格式的评估结果，包含: score(1-10分), strengths(优点), "
                        "weaknesses(缺点), suggestions(建议)"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"职位: {position}\n"
                        f"原问题: {question}\n"
                        f"候选人回答: {user_answer}\n"
                        f"\n请评估这个回答，返回 JSON 格式结果。"
                    )
                }
            ]
            
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.5,
                top_k=50,
                temperature=0.3,  # 降低温度以获得更一致的评分
                max_tokens=500,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    # 尝试解析 JSON
                    result_text = response.output.text
                    # 查找 JSON 内容
                    import re
                    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                except:
                    # 如果解析失败，返回原始文本
                    return {
                        "score": 5,
                        "feedback": response.output.text
                    }
            
            return {"score": 0, "error": f"API 错误: {response.message}"}
        
        except Exception as e:
            logger.error(f"✗ 评估回答失败: {str(e)}")
            return {"score": 0, "error": str(e)}

    def set_interview_round(self, round_type: str, resume_data: Optional[Dict] = None):
        """设置面试轮次"""
        if round_type in INTERVIEW_ROUNDS:
            self.current_round = round_type
            self.system_prompt = INTERVIEW_ROUNDS[round_type]['system_prompt']
            self.resume_data = resume_data if isinstance(resume_data, dict) else None
            if self.resume_data:
                resume_context = self._build_resume_context(resume_data)
                self.system_prompt += "\n\n" + resume_context
            logger.info(f"设置面试轮次：{round_type}")
            return True
        return False

    def _build_resume_context(self, resume_data: Dict) -> str:
        """构建简历上下文字符串"""
        lines = ["\n候选人简历信息："]
        if resume_data.get('skills'):
            skills = resume_data['skills'][:15]
            lines.append(f"技术栈：{', '.join(skills)}")
        for exp in resume_data.get('experiences', [])[:2]:
            company = exp.get('company', '')
            position = exp.get('position', '')
            lines.append(f"工作经历：{company} - {position}")
        for proj in resume_data.get('projects', [])[:2]:
            name = proj.get('name', '')
            techs = proj.get('technologies', [])
            lines.append(f"项目：{name}（技术：{', '.join(techs[:5])}）")
        education = resume_data.get('education', [])
        if isinstance(education, list) and len(education) > 0:
            for edu in education[:3]:
                school = edu.get('school', '')
                degree = edu.get('degree', '')
                major = edu.get('major', '')
                lines.append(f"教育：{school} - {degree} - {major}")
        elif isinstance(education, dict) and education.get('school'):
            lines.append(f"教育：{education.get('school')} - {education.get('degree')}")
        return "\n".join(lines)

    def load_resume_data(self, user_id: str = "default") -> Optional[Dict]:
        """从数据库加载用户简历数据"""
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            resume = db.get_latest_resume(user_id)
            if resume and resume.get('parsed_data'):
                return {
                    'projects': resume['parsed_data'].get('projects', []),
                    'experiences': resume['parsed_data'].get('experiences', []),
                    'education': resume['parsed_data'].get('education', []),
                    'skills': resume['parsed_data'].get('skills', [])
                }
        except Exception as e:
            logger.error(f"加载简历数据失败：{e}")
        return None

    def generate_round_question(self, round_type: str, position: str, difficulty: str = "medium", context: Optional[str] = None) -> str:
        """根据面试轮次生成问题"""
        if not self.check_enabled():
            return ""
        resume_data = self.resume_data if isinstance(self.resume_data, dict) else None
        self.set_interview_round(round_type, resume_data)
        difficulty_map = {"easy": "基础", "medium": "中等", "hard": "高级"}
        round_info = INTERVIEW_ROUNDS.get(round_type, INTERVIEW_ROUNDS['technical'])
        prompt = f"请为【{position}】职位生成一个【{difficulty_map.get(difficulty, '中等')}】难度的{round_info['name']}问题。"
        if context:
            prompt += f"\n背景信息：{context}"
        if round_type == 'project' and resume_data:
            projects = resume_data.get('projects', [])
            if projects:
                prompt += f"\n候选人项目：{projects[0].get('name', '')}"
        prompt += "\n请直接给出问题，不要多余的解释。"
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
        try:
            response = Generation.call(model=self.model, messages=messages, top_p=0.7, top_k=50, temperature=0.7, max_tokens=500, timeout=self.timeout)
            if response.status_code == 200:
                question = response.output.text
                logger.info(f"✓ 生成{round_info['name']}问题 - 职位：{position}")
                return question
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return ""
        except Exception as e:
            logger.error(f"✗ 生成问题失败：{e}")
            return ""

    def process_answer_with_round(self, user_answer: str, current_question: str, position: str, round_type: str, chat_history: Optional[list] = None) -> str:
        """处理用户回答，根据轮次生成追问"""
        if not self.check_enabled():
            return ""
        resume_data = self.resume_data if isinstance(self.resume_data, dict) else None
        self.set_interview_round(round_type, resume_data)
        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_history:
            for item in chat_history[-4:]:
                if "role" in item and "content" in item:
                    # 转换角色名：interviewer -> assistant, candidate -> user
                    role = item["role"]
                    if role == 'interviewer':
                        role = 'assistant'
                    elif role == 'candidate':
                        role = 'user'
                    messages.append({"role": role, "content": item["content"]})
        messages.append({"role": "user", "content": f"当前问题：{current_question}\n\n候选人回答：{user_answer}"})
        """此时message中包含了前面4次历史对话，方便模型根据上下文进行追问（处理核心逻辑）"""
        try:
            response = Generation.call(model=self.model, messages=messages, top_p=0.7, top_k=50, temperature=0.7, max_tokens=500, timeout=self.timeout)
            if response.status_code == 200:
                feedback = response.output.text
                logger.info(f"✓ 处理回答 - 轮次：{round_type}, 职位：{position}")
                return feedback
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return ""
        except Exception as e:
            logger.error(f"✗ 处理回答失败：{e}")
            return ""

# 创建全局 LLM 管理器实例
llm_manager = LLMManager()
