"""
大模型管理器 - 集成阿里通义 Qwen
用于面试官实时对话与追问
支持 4 轮面试：技术基础、项目深度、系统设计、HR 综合
"""
import os
import json
import time
import dashscope
from typing import Any, Optional, Dict, List
from dashscope import Generation
from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)

VOICE_SAFE_OUTPUT_RULES = """

语音播报约束：
- 输出必须是适合语音播报的自然中文纯文本
- 不要使用 Markdown、反引号、代码块、项目符号、链接、表格或特殊格式
- 提到类名、方法名或英文术语时，不要包裹特殊符号
"""

INTERVIEWER_STRUGGLE_RESPONSE_RULES = """

当候选人回答明显不完整、偏弱、卡住或答不上来时，遵守以下反应规则：
- 不要立刻否定、下结论或表现出不耐烦，更不要使用羞辱、讽刺、阴阳怪气的表达
- 先判断是没听清、太紧张，还是确实不会；必要时可以重述问题、换一种更清楚的说法，或把问题拆小一点
- 先给很小的引导，不要直接给标准答案，例如让候选人先说大致思路、先说一个可行方案、先结合项目经验分析
- 如果对方仍然回答不好，优先降一级继续评估基础能力，而不是持续在同一点上施压
- 重点观察候选人的逻辑、真实性、应变和情绪稳定性；允许候选人承认“不确定”，不要逼迫其乱答
- 如果当前题继续深挖价值不大，应自然切换到相关但更容易发挥的问题
- 整体语气保持尊重、专业、克制，既有面试官判断力，也给候选人基本体面
"""

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
        self.system_prompt = self._compose_system_prompt("""你是一位专业的互联网大厂的技术面试官，具有多年招聘经验。

你的职责：
1. 根据候选人的回答提出相关问题或追问
2. 评估候选人的技术水平、思维能力和表达能力
3. 提问应该循序渐进，难度逐步提升
4. 对于不清楚或不完整的回答，要求进一步解释

回答要求：
- 每次只提一个问题，问题要清晰具体
- 字数控制在 100 字以内
- 语言专业但不生硬，要体现面试官的专业性
- 如果候选人回答不理想，可以提出改进建议或追问更深层的知识点""")

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

    def _compose_system_prompt(self, base_prompt: str, resume_data: Optional[Dict] = None) -> str:
        prompt = (
            f"{base_prompt.rstrip()}"
            f"{INTERVIEWER_STRUGGLE_RESPONSE_RULES}"
            f"{VOICE_SAFE_OUTPUT_RULES}"
        )
        if resume_data:
            prompt += "\n\n" + self._build_resume_context(resume_data)
        return prompt
    
    def check_enabled(self) -> bool:
        """检查 LLM 是否启用"""
        if not self.enabled:
            logger.warning("LLM 功能未启用或 API Key 未配置")
            return False
        return True

    def warmup(self) -> Dict[str, Any]:
        """执行一次轻量 LLM 预热请求，降低首轮调用冷启动延迟。"""
        result: Dict[str, Any] = {
            "enabled": bool(self.enabled),
            "success": False,
            "model": self.model,
            "latency_ms": 0.0,
            "error": "",
        }
        if not self.check_enabled():
            result["error"] = "LLM not enabled"
            return result

        messages = [
            {"role": "system", "content": "You are a health checker. Reply with OK only."},
            {"role": "user", "content": "ping"},
        ]
        started_at = time.time()
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.1,
                top_k=10,
                temperature=0.0,
                max_tokens=8,
                timeout=min(float(self.timeout or 30), 15.0),
            )
            latency_ms = round((time.time() - started_at) * 1000.0, 2)
            result["latency_ms"] = latency_ms
            if getattr(response, "status_code", None) == 200:
                reply_text = str(getattr(getattr(response, "output", None), "text", "") or "").strip()
                result["success"] = True
                result["reply_preview"] = reply_text[:48]
                logger.info(f"[LLM] 预热完成 - latency={latency_ms}ms")
                return result

            result["error"] = str(getattr(response, "message", "") or getattr(response, "code", "") or "unknown_error")
            logger.warning(f"[LLM] 预热失败 - {result['error']}")
            return result
        except Exception as exc:
            result["latency_ms"] = round((time.time() - started_at) * 1000.0, 2)
            result["error"] = str(exc)[:240]
            logger.warning(f"[LLM] 预热异常 - {result['error']}")
            return result

    def generate_structured_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: Optional[str] = None,
        top_p: float = 0.4,
        top_k: int = 40,
        temperature: float = 0.2,
        max_tokens: int = 1800,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """通用结构化 JSON 生成接口（支持 model 覆盖用于复盘链路）。"""
        if not self.check_enabled():
            return {"success": False, "error": "LLM_NOT_READY", "message": "LLM not enabled"}

        target_model = str(model or self.model or "").strip()
        if not target_model:
            return {"success": False, "error": "INVALID_MODEL", "message": "model is empty"}

        try:
            response = Generation.call(
                model=target_model,
                messages=[
                    {"role": "system", "content": str(system_prompt or "")},
                    {"role": "user", "content": str(user_prompt or "")},
                ],
                top_p=top_p,
                top_k=top_k,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=(timeout if timeout is not None else self.timeout),
            )
            if getattr(response, "status_code", None) != 200:
                return {
                    "success": False,
                    "error": "API_ERROR",
                    "message": str(getattr(response, "message", "") or getattr(response, "code", "") or "unknown_error"),
                }

            raw_text = str(getattr(getattr(response, "output", None), "text", "") or "").strip()
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not json_match:
                return {"success": False, "error": "INVALID_JSON", "message": "json not found", "raw_text": raw_text}
            parsed = json.loads(json_match.group())
            return {"success": True, "model": target_model, "data": parsed, "raw_text": raw_text}
        except Exception as e:
            logger.error(f"结构化 JSON 生成失败: {e}")
            return {"success": False, "error": "GENERATION_EXCEPTION", "message": str(e)}
    
    def generate_interview_question(
        self,
        position: str,
        difficulty: str = "medium",
        context: Optional[str] = None,
        rag_context: Optional[str] = None
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
            prompt = (
                f"请为【{position}】职位生成一个【{difficulty_map.get(difficulty, '中等')}】难度的面试问题。\n"
            )
            if context:
                prompt += f"背景信息：{context}\n"
            if rag_context:
                prompt += f"参考知识：\n{rag_context}\n"
            prompt += "请直接给出问题，不要多余的解释。"
            
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
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
    
    def evaluate_answer_with_rubric(
        self,
        user_answer: str,
        question: str,
        position: str,
        round_type: str,
        scoring_rubric: Optional[Dict] = None,
        layer1_result: Optional[Dict] = None,
        prompt_version: str = "v1",
        speech_context: Optional[Dict] = None
    ) -> Dict:
        """
        ??????????????rubric?????????????????? JSON?
        """
        if not self.check_enabled():
            return {"error": "LLM_NOT_READY", "message": "LLM ?????"}

        round_dimensions = {
            "technical": ["technical_accuracy", "knowledge_depth", "completeness", "logic", "job_match"],
            "project": ["authenticity", "ownership", "technical_depth", "reflection"],
            "system_design": ["architecture_reasoning", "tradeoff_awareness", "scalability", "logic"],
            "hr": ["clarity", "relevance", "self_awareness", "communication"],
        }
        dimensions = round_dimensions.get(round_type, round_dimensions["technical"])

        rubric_text = json.dumps(scoring_rubric or {}, ensure_ascii=False, indent=2)
        layer1_text = json.dumps(layer1_result or {}, ensure_ascii=False, indent=2)
        speech_text = json.dumps(speech_context or {}, ensure_ascii=False, indent=2)

        dim_schema = ", ".join(
            f'"{name}": {{"score": 0-100, "reason": "..."}}'
            for name in dimensions
        )

        system_prompt = (
            "You are an interview grading assistant. "
            "Return valid JSON only. "
            "Your dimension scores must be text-semantic base scores derived from the answer content, rubric, and layer1 evidence. "
            "Do not apply speech weighting inside dimension scores or overall_score. "
            "If speech_context is present, you may reference it only in reasons and summary wording. "
            "Keep scores calibrated to 0-100 and ensure reasons are concise."
        )
        user_prompt = (
            f"prompt_version: {prompt_version}\n"
            f"position: {position}\n"
            f"round_type: {round_type}\n"
            f"question: {question}\n"
            f"candidate_answer: {user_answer}\n\n"
            f"scoring_rubric:\n{rubric_text}\n\n"
            f"layer1_result:\n{layer1_text}\n\n"
            f"speech_context:\n{speech_text}\n\n"
            "Scoring rules:\n"
            "1. `dimension_scores` must be text-base scores only.\n"
            "2. `overall_score` should be the mean of the text-base dimension scores.\n"
            "3. `rubric_eval` should reflect rubric alignment.\n"
            "4. `summary` can mention speaking strengths/weaknesses only if supported by speech_context.\n\n"
            "Return JSON with this schema:\n"
            "{\n"
            '  "rubric_eval": {\n'
            '    "basic_match": 0,\n'
            '    "good_match": 0,\n'
            '    "excellent_match": 0,\n'
            '    "final_level": "basic|good|excellent",\n'
            '    "confidence": 0.0,\n'
            '    "reason": "..."\n'
            "  },\n"
            '  "dimension_scores": {\n'
            f"    {dim_schema}\n"
            "  },\n"
            '  "overall_score": 0,\n'
            '  "summary": {\n'
            '    "strengths": ["..."],\n'
            '    "weaknesses": ["..."],\n'
            '    "next_actions": ["..."]\n'
            "  }\n"
            "}\n"
            "All score fields except confidence must be between 0 and 100."
        )

        try:
            response = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                top_p=0.5,
                top_k=50,
                temperature=0.2,
                max_tokens=1200,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return {"error": "API_ERROR", "message": response.message}

            raw_text = str(response.output.text or "").strip()
            import re
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not json_match:
                return {"error": "INVALID_JSON", "message": "????? JSON", "raw_text": raw_text}

            parsed = json.loads(json_match.group())
            rubric_eval = parsed.get("rubric_eval", {}) or {}
            dimension_scores = parsed.get("dimension_scores", {}) or {}
            summary = parsed.get("summary", {}) or {}

            def _clamp_100(value, default=0.0):
                try:
                    return round(max(0.0, min(100.0, float(value))), 2)
                except Exception:
                    return round(float(default), 2)

            normalized_rubric_eval = {
                "basic_match": _clamp_100(rubric_eval.get("basic_match", 0)),
                "good_match": _clamp_100(rubric_eval.get("good_match", 0)),
                "excellent_match": _clamp_100(rubric_eval.get("excellent_match", 0)),
                "final_level": str(rubric_eval.get("final_level", "basic")).strip().lower() or "basic",
                "confidence": round(max(0.0, min(1.0, float(rubric_eval.get("confidence", 0.5)))), 4),
                "reason": str(rubric_eval.get("reason", "")).strip(),
            }
            if normalized_rubric_eval["final_level"] not in {"basic", "good", "excellent"}:
                normalized_rubric_eval["final_level"] = "basic"

            normalized_dimensions = {}
            for dim in dimensions:
                dim_payload = dimension_scores.get(dim, {}) or {}
                normalized_dimensions[dim] = {
                    "score": _clamp_100(dim_payload.get("score", 0)),
                    "reason": str(dim_payload.get("reason", "")).strip(),
                }

            overall_score = parsed.get("overall_score")
            if overall_score is None:
                scores = [item["score"] for item in normalized_dimensions.values()]
                overall_score = sum(scores) / len(scores) if scores else 0.0

            normalized = {
                "rubric_eval": normalized_rubric_eval,
                "dimension_scores": normalized_dimensions,
                "overall_score": _clamp_100(overall_score),
                "summary": {
                    "strengths": [str(x) for x in (summary.get("strengths", []) or [])][:5],
                    "weaknesses": [str(x) for x in (summary.get("weaknesses", []) or [])][:5],
                    "next_actions": [str(x) for x in (summary.get("next_actions", []) or [])][:5],
                }
            }
            return normalized
        except Exception as e:
            logger.error(f"??? rubric ????: {str(e)}")
            return {"error": "EVALUATION_EXCEPTION", "message": str(e)}

    def set_interview_round(self, round_type: str, resume_data: Optional[Dict] = None):
        """设置面试轮次"""
        if round_type in INTERVIEW_ROUNDS:
            self.current_round = round_type
            self.resume_data = resume_data if isinstance(resume_data, dict) else None
            self.system_prompt = self._compose_system_prompt(
                INTERVIEW_ROUNDS[round_type]['system_prompt'],
                self.resume_data
            )
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

    def generate_round_question(
        self,
        round_type: str,
        position: str,
        difficulty: str = "medium",
        context: Optional[str] = None,
        rag_context: Optional[str] = None
    ) -> str:
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
        if rag_context:
            prompt += f"\n参考知识：\n{rag_context}"
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

    def process_answer_with_round(
        self,
        user_answer: str,
        current_question: str,
        position: str,
        round_type: str,
        chat_history: Optional[list] = None,
        rag_context: Optional[str] = None
    ) -> str:
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
        user_content = []
        if rag_context:
            user_content.append(
                "以下是与当前问题相关的参考知识，请优先基于这些知识判断候选人回答质量，并据此生成追问：\n"
                f"{rag_context}"
            )
        user_content.append(f"当前问题：{current_question}\n\n候选人回答：{user_answer}")
        messages.append({"role": "user", "content": "\n\n".join(user_content)})
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
