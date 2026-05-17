"""
大模型管理器 - 集成阿里通义 Qwen
用于面试官实时对话与追问
支持 4 轮面试：技术基础、项目深度、系统设计、HR 综合
"""
import os
import json
import time
import re
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
- 只允许给一句非常短的提示，不能直接给定义、结论、完整示例、示范代码或标准答案
- 输出必须保持“面试官提问”姿态，提示之后要立刻落到一个明确问题上，不能进入教学讲解模式
- 禁止出现“你觉得这个例子清晰吗”“如果有问题我再解释”这类授课式收尾
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
- 每次输出都必须以明确问题结尾，且只能提问或极短提示后追问
- 不要直接解释概念，不要给标准答案，不要写示例代码
- 如果候选人回答不理想，只能重述、缩小问题或继续追问，不能切换成讲课模式
- 切换话题时，先简要点评上一题回答，再自然引出新问题，避免机械过渡"""
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
- 关注候选人的技术深度和思考能力
- 切换话题时，先简要点评上一题回答，再自然引出新问题，避免机械过渡"""
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
- 关注设计思路而非标准答案
- 切换话题时，先简要点评上一题回答，再自然引出新问题，避免机械过渡"""
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
- 给予候选人充分表达空间
- 切换话题时，先简要点评上一题回答，再自然引出新问题，避免机械过渡"""
    }
}


class LLMManager:
    """大模型管理器 - 处理与 Qwen 的交互"""
    _QUESTION_LINE_PATTERNS = (
        r"(?:优先问题|候选题|问题)\s*[:：]\s*(.+)",
    )
    _META_QUESTION_PATTERNS = (
        "你觉得这个例子清晰吗",
        "如果有任何问题",
        "需要进一步解释的地方",
        "我可以继续解释",
        "我再给你解释",
    )
    _TEACHING_PATTERNS = (
        "在这个例子中",
        "假设我们有一个",
        "请看下面的代码",
        "这就是",
        "我们来具体看一下",
        "下面这个例子",
    )
    
    def __init__(self):
        """初始化 LLM 管理器"""
        self.enabled = config.get('llm.enabled', False)
        self.provider = (
            str(os.environ.get('LLM_PROVIDER', '')).strip().lower()
            or config.get('llm.provider', 'qwen')
            or 'qwen'
        )
        self.model = (
            str(os.environ.get('LLM_MODEL', '')).strip()
            or config.get('llm.model', 'qwen-max')
            or 'qwen-max'
        )
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
- 输出必须是面试官口吻，最终落在一个明确问题上
- 不要直接解释概念、不要给标准答案、不要写示例代码
- 如果候选人回答不理想，可以缩小范围继续追问，但不要变成教学讲解
- 切换话题时，先用一句话简要点评候选人刚才的回答，再自然引出新问题，像真人面试官一样自然衔接""")

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

    @staticmethod
    def _dedupe_text_list(items: Optional[List[Any]], limit: int = 8) -> List[str]:
        results: List[str] = []
        seen = set()
        for item in items or []:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(text)
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _parse_json_object_from_text(text: str) -> Dict[str, Any]:
        """从模型输出中提取第一个完整 JSON 对象，避免贪婪正则吞入多余文本。"""
        source = str(text or "").strip()
        if source.startswith("```"):
            source = re.sub(r"^```(?:json)?\s*", "", source, flags=re.IGNORECASE)
            source = re.sub(r"\s*```$", "", source)

        decoder = json.JSONDecoder()
        for index, char in enumerate(source):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(source[index:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        # 常见模型小错误：对象/数组尾逗号。
        compact = re.sub(r",\s*([}\]])", r"\1", source)
        for index, char in enumerate(compact):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(compact[index:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        raise ValueError("未找到可解析的完整 JSON 对象")

    @classmethod
    def _extract_question_from_context(cls, text: Optional[str]) -> str:
        source = str(text or "").strip()
        if not source:
            return ""

        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for pattern in cls._QUESTION_LINE_PATTERNS:
                matched = re.search(pattern, line)
                if not matched:
                    continue
                candidate = str(matched.group(1) or "").strip().strip("。")
                if candidate:
                    return candidate if candidate.endswith(("？", "?")) else f"{candidate}？"
        return ""

    @classmethod
    def _extract_primary_question(cls, text: Optional[str]) -> str:
        source = re.sub(r"\s+", " ", str(text or "").strip())
        if not source:
            return ""

        parts = re.split(r"(?<=[？?])\s*", source)
        for part in parts:
            candidate = part.strip()
            if not candidate or ("？" not in candidate and "?" not in candidate):
                continue
            if any(pattern in candidate for pattern in cls._META_QUESTION_PATTERNS):
                continue
            if len(candidate) < 6:
                continue
            return candidate
        return ""

    @classmethod
    def _looks_like_teaching_response(cls, text: Optional[str]) -> bool:
        source = re.sub(r"\s+", " ", str(text or "").strip())
        if not source:
            return True
        if any(pattern in source for pattern in cls._META_QUESTION_PATTERNS):
            return True
        teaching_hits = sum(1 for pattern in cls._TEACHING_PATTERNS if pattern in source)
        if teaching_hits >= 1 and len(source) >= 40:
            return True
        if ("示例" in source or "代码" in source) and len(source) >= 30:
            return True
        return False

    @classmethod
    def _fallback_interviewer_question(
        cls,
        *,
        round_type: str,
        current_question: str = "",
        rag_context: Optional[str] = None,
        user_answer: str = "",
        reference_question: str = "",
    ) -> str:
        normalized_reference = re.sub(r"\s+", " ", str(reference_question or "").strip())
        if normalized_reference:
            if normalized_reference.endswith(("？", "?")):
                return normalized_reference
            return f"{normalized_reference}？"

        context_question = cls._extract_question_from_context(rag_context)
        if context_question:
            return context_question

        normalized_current = str(current_question or "").strip()
        normalized_answer = re.sub(r"\s+", " ", str(user_answer or "").strip())
        if normalized_current and normalized_answer:
            followup_map = {
                "technical": "你刚才讲的是概括层面。请继续往下展开一层，具体说明它的底层机制、关键约束，以及实际使用时最容易出错的点？",
                "project": "你刚才更多是在讲结果。请具体拆一下当时你的个人职责、关键决策，以及你最终怎么验证方案有效？",
                "system_design": "你刚才先给了总体说法。请继续展开核心模块划分、关键数据流，以及你会优先防哪类瓶颈？",
                "hr": "你刚才说到了结论。请再具体补充一下当时你的行动、判断依据，以及这件事对你的影响？",
            }
            return followup_map.get(round_type, followup_map["technical"])

        generic_map = {
            "technical": "请你直接说明这个技术点的定义、核心机制，以及一个实际使用场景？",
            "project": "请你结合你的项目经历，挑一个关键技术决策讲一下为什么这样做？",
            "system_design": "请你先给出整体方案，再说明核心模块划分和关键权衡？",
            "hr": "请你结合一段真实经历，说明你当时是怎么思考和处理的？",
        }
        return generic_map.get(round_type, generic_map["technical"])

    @classmethod
    def _sanitize_interviewer_output(
        cls,
        text: Optional[str],
        *,
        round_type: str,
        current_question: str = "",
        rag_context: Optional[str] = None,
        user_answer: str = "",
        reference_question: str = "",
    ) -> str:
        source = re.sub(r"\s+", " ", str(text or "").strip())
        if not source:
            return cls._fallback_interviewer_question(
                round_type=round_type,
                current_question=current_question,
                rag_context=rag_context,
                user_answer=user_answer,
                reference_question=reference_question,
            )

        primary_question = cls._extract_primary_question(source)
        if primary_question and not cls._looks_like_teaching_response(source):
            return primary_question

        if source.endswith(("？", "?")) and not cls._looks_like_teaching_response(source):
            return source

        return cls._fallback_interviewer_question(
            round_type=round_type,
            current_question=current_question,
            rag_context=rag_context,
            user_answer=user_answer,
            reference_question=reference_question,
        )

    def _build_position_profile(
        self,
        position: str,
        round_type: str,
        layer1_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_position = "".join(str(position or "").strip().lower().split())
        competency = self._dedupe_text_list((layer1_result or {}).get("competency") or [], limit=6)
        position_profile = dict((layer1_result or {}).get("position_profile") or {})
        question_keywords = self._dedupe_text_list(position_profile.get("keywords") or [], limit=8)

        role_hints_map = {
            "java_backend": [
                "后端工程实践",
                "Java 生态与框架使用",
                "数据库与缓存",
                "接口设计与稳定性",
                "排障与性能优化",
            ],
            "java后端": [
                "后端工程实践",
                "Java 生态与框架使用",
                "数据库与缓存",
                "接口设计与稳定性",
                "排障与性能优化",
            ],
            "frontend": [
                "前端工程化",
                "组件设计与状态管理",
                "浏览器与性能优化",
                "交互体验",
                "联调与问题排查",
            ],
            "frontend_engineer": [
                "前端工程化",
                "组件设计与状态管理",
                "浏览器与性能优化",
                "交互体验",
                "联调与问题排查",
            ],
            "算法工程师": [
                "模型理解与训练调优",
                "数据与评估设计",
                "工程落地能力",
                "问题分析与实验闭环",
                "业务场景适配",
            ],
            "algorithm_engineer": [
                "模型理解与训练调优",
                "数据与评估设计",
                "工程落地能力",
                "问题分析与实验闭环",
                "业务场景适配",
            ],
            "产品经理": [
                "需求分析与优先级判断",
                "用户洞察与场景抽象",
                "跨团队协作与推动落地",
                "数据分析与效果复盘",
                "产品规划与商业判断",
            ],
            "product_manager": [
                "需求分析与优先级判断",
                "用户洞察与场景抽象",
                "跨团队协作与推动落地",
                "数据分析与效果复盘",
                "产品规划与商业判断",
            ],
        }

        role_hints: List[str] = []
        for key, hints in role_hints_map.items():
            if key in normalized_position:
                role_hints = hints[:]
                break

        if not role_hints:
            role_hints = [
                "岗位核心技能是否匹配",
                "回答是否贴近真实工作场景",
                "是否体现岗位需要的工程判断",
            ]

        resume_data = self.resume_data if isinstance(self.resume_data, dict) else {}
        resume_skills = self._dedupe_text_list((resume_data or {}).get("skills") or [], limit=10)

        return {
            "position": str(position or "").strip(),
            "round_type": str(round_type or "").strip(),
            "target_competency": competency,
            "question_keywords": question_keywords,
            "role_hints": role_hints,
            "resume_skills": resume_skills,
            "question_intent": str(position_profile.get("question_intent") or "").strip(),
            "question_type": str(position_profile.get("question_type") or "").strip(),
        }
    
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
        rag_context: Optional[str] = None,
        reference_question: Optional[str] = None,
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
            if reference_question and str(reference_question).strip():
                prompt += (
                    f"RAG候选题（必须优先参考）：{str(reference_question).strip()}\n"
                    "要求：可改写措辞，但必须保持同一能力点和场景边界，不要发散为泛泛提问。\n"
                )
            prompt += "参考知识只用于帮助你选题，不允许直接复述成答案、示例或讲解。请直接给出一个面试问题，不要多余解释。"
            
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
                return self._sanitize_interviewer_output(
                    question,
                    round_type=self.current_round,
                    rag_context=rag_context,
                    reference_question=str(reference_question or ""),
                )
            else:
                logger.error(f"✗ API 错误: {response.message}")
                return self._fallback_interviewer_question(
                    round_type=self.current_round,
                    rag_context=rag_context,
                    reference_question=str(reference_question or ""),
                )
        
        except Exception as e:
            logger.error(f"✗ 生成面试问题失败: {str(e)}")
            return self._fallback_interviewer_question(
                round_type=self.current_round,
                rag_context=rag_context,
                reference_question=str(reference_question or ""),
            )
    
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
                return self._sanitize_interviewer_output(
                    feedback,
                    round_type=self.current_round,
                    current_question=current_question,
                    user_answer=user_answer,
                )
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
        基于 rubric 输出结构化评分结果与维度级证据链。
        """
        if not self.check_enabled():
            return {"error": "LLM_NOT_READY", "message": "LLM 未启用"}

        round_dimensions = {
            "technical": ["technical_accuracy", "knowledge_depth", "completeness", "logic", "job_match"],
            "project": ["authenticity", "ownership", "technical_depth", "reflection"],
            "system_design": ["architecture_reasoning", "tradeoff_awareness", "scalability", "logic"],
            "hr": ["clarity", "relevance", "self_awareness", "communication", "confidence"],
        }
        dimensions = round_dimensions.get(round_type, round_dimensions["technical"])

        rubric_text = json.dumps(scoring_rubric or {}, ensure_ascii=False, indent=2)
        layer1_text = json.dumps(layer1_result or {}, ensure_ascii=False, indent=2)
        speech_text = json.dumps(speech_context or {}, ensure_ascii=False, indent=2)
        position_profile = self._build_position_profile(position, round_type, layer1_result)
        position_profile_text = json.dumps(position_profile, ensure_ascii=False, indent=2)

        dim_schema = ", ".join(
            (
                f'"{name}": {{'
                '"score": 0-100, '
                '"reason": "...", '
                '"evidence": {'
                '"hit_rubric_points": ["..."], '
                '"missed_rubric_points": ["..."], '
                '"source_quotes": ["..."], '
                '"deduction_rationale": "..."'
                '}'
                '}}'
            )
            for name in dimensions
        )

        system_prompt = (
            "You are an interview grading assistant. "
            "Return valid compact JSON only. "
            "Your dimension scores must be text-semantic base scores derived from the answer content, rubric, and layer1 evidence. "
            "For every dimension, you must also return structured evidence. "
            "Do not apply speech weighting inside dimension scores or overall_score. "
            "If speech_context is present, you may reference it only in reasons and summary wording. "
            "Keep scores calibrated to 0-100 and ensure reasons are concise, evidence is concrete, and quotes come from the candidate answer. "
            "When `scoring_rubric.atomic_points` is present, treat the LLM task as point-level evidence judgement: classify every point independently before giving narrative dimension comments. "
            "For `job_match`, score role alignment instead of repeating technical correctness: judge whether the answer reflects the target role's core competency, engineering context, and scenario relevance. "
            "For HR round `confidence`, score professional confidence from the semantics of the answer: whether the candidate shows stable judgment, clear ownership, and appropriately bounded self-belief. "
            "Do not confuse confidence with extroversion, speaking volume, aggression, or refusal to admit uncertainty."
        )
        user_prompt = (
            f"prompt_version: {prompt_version}\n"
            f"position: {position}\n"
            f"round_type: {round_type}\n"
            f"question: {question}\n"
            f"candidate_answer: {user_answer}\n\n"
            f"position_profile:\n{position_profile_text}\n\n"
            f"scoring_rubric:\n{rubric_text}\n\n"
            f"layer1_result:\n{layer1_text}\n\n"
            f"speech_context:\n{speech_text}\n\n"
            "Scoring rules:\n"
            "1. `dimension_scores` must be text-base scores only.\n"
            "2. `overall_score` should be the mean of the text-base dimension scores.\n"
            "3. `rubric_eval` should reflect rubric alignment.\n"
            "4. `summary` can mention speaking strengths/weaknesses only if supported by speech_context.\n"
            "5. Every dimension must include `evidence.hit_rubric_points`, `evidence.missed_rubric_points`, `evidence.source_quotes`, and `evidence.deduction_rationale`.\n"
            "6. `source_quotes` must quote the candidate answer verbatim when possible; use short excerpts only.\n\n"
            "7. If `scoring_rubric.atomic_points` exists, return one `point_judgements` item for every atomic point id. "
            "`status` must be one of `hit`, `partial`, `miss`, or `contradict`; for `hit`, `partial`, and `contradict`, `quote` must be a short exact excerpt copied from candidate_answer. "
            "Use `contradict` when the answer states something opposite to a core rubric point, not merely when it omits the point.\n"
            "8. Dimension scores may be semantic baselines, but final deterministic scoring will be computed by the rules layer from `point_judgements`.\n\n"
            "9. When scoring `job_match`, prioritize these signals in order:\n"
            "   - whether the answer reflects role-specific competency from `position_profile.target_competency`\n"
            "   - whether the answer uses role-relevant scenarios / technologies / engineering trade-offs\n"
            "   - whether the answer goes beyond generic correctness and shows practical fit for the target role\n"
            "   - do not simply mirror `technical_accuracy`; a technically correct but generic answer can have only moderate `job_match`\n"
            "10. When scoring HR `confidence`, prioritize these signals in order:\n"
            "   - whether the candidate expresses clear judgments, choices, and reasons instead of repeated hedging\n"
            "   - whether the candidate shows stable ownership of actions, outcomes, strengths, and weaknesses\n"
            "   - whether the answer stays composed and coherent when discussing pressure, failure, trade-offs, or self-evaluation\n"
            "   - whether the confidence is appropriately bounded: admitting uncertainty can still score well if the stance remains honest and stable\n"
            "   - do not reward aggression, exaggerated self-praise, or mere verbosity; do not punish introversion or calm tone\n\n"
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
            '  "point_judgements": [\n'
            '    {"point_id": "...", "status": "hit|partial|miss|contradict", "confidence": 0.0, "quote": "...", "reason": "..."}\n'
            "  ],\n"
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
                max_tokens=2200,
                timeout=self.timeout
            )

            if response.status_code != 200:
                return {"error": "API_ERROR", "message": response.message}

            raw_text = str(response.output.text or "").strip()
            try:
                parsed = self._parse_json_object_from_text(raw_text)
            except Exception as parse_error:
                return {
                    "error": "INVALID_JSON",
                    "message": str(parse_error),
                    "raw_text": raw_text[:4000],
                }
            rubric_eval = parsed.get("rubric_eval", {}) or {}
            point_judgements = parsed.get("point_judgements", []) or []
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

            normalized_point_judgements = []
            raw_point_items = point_judgements.values() if isinstance(point_judgements, dict) else point_judgements
            for item in raw_point_items or []:
                if not isinstance(item, dict):
                    continue
                point_id = str(item.get("point_id") or item.get("id") or "").strip()
                if not point_id:
                    continue
                status = str(item.get("status") or item.get("judgement") or "miss").strip().lower()
                if status not in {"hit", "partial", "miss", "contradict"}:
                    status = "miss"
                try:
                    point_confidence = round(max(0.0, min(1.0, float(item.get("confidence", 0.65)))), 4)
                except Exception:
                    point_confidence = 0.65
                normalized_point_judgements.append({
                    "point_id": point_id,
                    "status": status,
                    "confidence": point_confidence,
                    "quote": str(item.get("quote") or item.get("source_quote") or "").strip()[:160],
                    "reason": str(item.get("reason") or item.get("rationale") or "").strip()[:240],
                })

            normalized_dimensions = {}
            normalized_dimension_evidence = {}
            for dim in dimensions:
                dim_payload = dimension_scores.get(dim, {}) or {}
                evidence = dim_payload.get("evidence") if isinstance(dim_payload.get("evidence"), dict) else {}
                reason = str(dim_payload.get("reason", "")).strip()
                normalized_dimensions[dim] = {
                    "score": _clamp_100(dim_payload.get("score", 0)),
                    "reason": reason,
                    "evidence": {
                        "hit_rubric_points": [str(x).strip() for x in (evidence.get("hit_rubric_points") or []) if str(x).strip()][:5],
                        "missed_rubric_points": [str(x).strip() for x in (evidence.get("missed_rubric_points") or []) if str(x).strip()][:5],
                        "source_quotes": [str(x).strip() for x in (evidence.get("source_quotes") or []) if str(x).strip()][:3],
                        "deduction_rationale": str(evidence.get("deduction_rationale") or reason).strip(),
                    },
                }
                normalized_dimension_evidence[dim] = normalized_dimensions[dim]["evidence"]

            overall_score = parsed.get("overall_score")
            if overall_score is None:
                scores = [item["score"] for item in normalized_dimensions.values()]
                overall_score = sum(scores) / len(scores) if scores else 0.0

            normalized = {
                "rubric_eval": normalized_rubric_eval,
                "point_judgements": normalized_point_judgements,
                "dimension_scores": normalized_dimensions,
                "dimension_evidence": normalized_dimension_evidence,
                "overall_score": _clamp_100(overall_score),
                "summary": {
                    "strengths": [str(x) for x in (summary.get("strengths", []) or [])][:5],
                    "weaknesses": [str(x) for x in (summary.get("weaknesses", []) or [])][:5],
                    "next_actions": [str(x) for x in (summary.get("next_actions", []) or [])][:5],
                }
            }
            return normalized
        except Exception as e:
            logger.error(f"rubric 评分失败: {str(e)}")
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
        rag_context: Optional[str] = None,
        reference_question: Optional[str] = None
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
        prompt += "\n参考知识只用于帮助你选题，不允许直接复述成答案、示例或讲解。请直接给出一个面试问题，不要多余解释。"
        if reference_question and str(reference_question).strip():
            prompt += (
                f"\nRAG候选题（必须优先参考）：{str(reference_question).strip()}\n"
                "要求：可改写措辞，但必须保持同一能力点和场景边界，不要发散为泛泛提问。"
            )
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
        try:
            response = Generation.call(model=self.model, messages=messages, top_p=0.7, top_k=50, temperature=0.7, max_tokens=500, timeout=self.timeout)
            if response.status_code == 200:
                question = response.output.text
                logger.info(f"✓ 生成{round_info['name']}问题 - 职位：{position}")
                return self._sanitize_interviewer_output(
                    question,
                    round_type=round_type,
                    rag_context=rag_context,
                    reference_question=str(reference_question or ""),
                )
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return self._fallback_interviewer_question(
                    round_type=round_type,
                    rag_context=rag_context,
                    reference_question=str(reference_question or ""),
                )
        except Exception as e:
            logger.error(f"✗ 生成问题失败：{e}")
            return self._fallback_interviewer_question(
                round_type=round_type,
                rag_context=rag_context,
                reference_question=str(reference_question or ""),
            )

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
                "以下是与当前问题相关的参考知识，请优先基于这些知识判断候选人回答质量，并据此生成追问。\n"
                "这些内容只用于判断和设计追问，禁止直接把参考知识讲给候选人听，禁止直接给出标准答案、完整例子或示范代码：\n"
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
                return self._sanitize_interviewer_output(
                    feedback,
                    round_type=round_type,
                    current_question=current_question,
                    rag_context=rag_context,
                    user_answer=user_answer,
                )
            else:
                logger.error(f"✗ API 错误：{response.message}")
                return ""
        except Exception as e:
            logger.error(f"✗ 处理回答失败：{e}")
            return ""

    def generate_targeted_followup_question(
        self,
        *,
        current_question: str,
        user_answer: str,
        position: str,
        round_type: str,
        followup_style: str = "detail_probe",
        followup_hint: str = "",
        rag_context: Optional[str] = None,
    ) -> str:
        """Generate one natural follow-up focused on detail, tradeoff, or scale."""
        fallback_templates = {
            "detail_probe": "你刚才提到了一部分关键点，但还比较概括。请继续展开：{hint}",
            "tradeoff_probe": "如果继续往下追问，你为什么会这么选？请重点讲讲方案取舍：{hint}",
            "scale_probe": "如果把这个场景放到更大的线上规模，你认为最先出现的问题会是什么？请结合落地展开：{hint}",
        }
        fallback_hint = str(followup_hint or current_question or "").strip() or "请你把刚才那部分继续讲具体一点。"
        fallback_question = fallback_templates.get(
            followup_style,
            fallback_templates["detail_probe"],
        ).format(hint=fallback_hint)

        if not self.check_enabled():
            return fallback_question

        resume_data = self.resume_data if isinstance(self.resume_data, dict) else None
        self.set_interview_round(round_type, resume_data)
        style_instruction_map = {
            "detail_probe": "追问目标是补细节，逼近候选人刚才没讲清楚的技术细节、职责边界或关键依据。",
            "tradeoff_probe": "追问目标是问取舍，逼近为什么这么选、放弃了什么、代价是什么。",
            "scale_probe": "追问目标是问落地与规模化，逼近线上量级扩大、故障、瓶颈、扩展性与稳定性。",
        }
        prompt = (
            "你现在是一位经验丰富的中文技术面试官。请基于当前题目、候选人刚才的回答，以及给定的追问目标，"
            "只输出一句自然、连续、像真人面试官会说的后续提问。不要输出点评，不要列点，不要解释。\n\n"
            f"目标岗位：{position}\n"
            f"面试轮次：{round_type}\n"
            f"当前题目：{current_question}\n"
            f"候选人刚才的回答：{user_answer}\n"
            f"追问目标：{style_instruction_map.get(followup_style, style_instruction_map['detail_probe'])}\n"
            f"优先追问线索：{fallback_hint}\n"
        )
        if rag_context:
            prompt += (
                "\n参考考点（只用于帮助你找追问角度，禁止直接复述成答案或讲解）：\n"
                f"{rag_context}\n"
            )
        prompt += "\n请直接输出下一句追问。"
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.7,
                top_k=40,
                temperature=0.55,
                max_tokens=180,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                question = response.output.text
                return self._sanitize_interviewer_output(
                    question,
                    round_type=round_type,
                    current_question=current_question,
                    rag_context=rag_context,
                    user_answer=user_answer,
                ) or fallback_question
        except Exception as e:
            logger.error(f"✗ 生成追问失败：{e}")
        return fallback_question

    def generate_natural_transition(
        self,
        *,
        previous_question: str,
        user_answer: str,
        next_question: str,
        transition_type: str,
        position: str,
        round_type: str,
        chat_history: Optional[list] = None,
    ) -> str:
        """生成自然过渡语：简要点评上一题回答，再自然引出下一题。"""
        fallback = next_question
        if not self.check_enabled():
            return fallback

        resume_data = self.resume_data if isinstance(self.resume_data, dict) else None
        self.set_interview_round(round_type, resume_data)
        transition_hint = "候选人回答得不错，需要提升难度" if transition_type == 'raise_difficulty' else "需要切换到新的话题"
        prompt = (
            "你现在是一位经验丰富的中文技术面试官。候选人刚刚回答完一个问题，你现在要过渡到下一个问题。\n"
            "请用 1-2 句话自然衔接，要求：\n"
            "1. 先用一句话简要点评候选人刚才的回答（可以是肯定、总结或指出不足）\n"
            "2. 然后自然引出下一个问题，不要说'我们换一个方向'这类机械表达\n"
            "3. 整体要像真人面试官的口头表达，自然、专业、不生硬\n"
            "4. 直接输出面试官的发言文本，包含下一题的完整内容，不要分段输出\n\n"
            f"目标岗位：{position}\n"
            f"面试轮次：{round_type}\n"
            f"过渡原因：{transition_hint}\n"
            f"上一个问题是：{previous_question}\n"
            f"候选人的回答：{user_answer}\n"
            f"下一个问题是：{next_question}\n"
        )
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                top_p=0.7,
                top_k=40,
                temperature=0.6,
                max_tokens=250,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                text = str(response.output.text or "").strip()
                if text and len(text) > 10:
                    logger.info("✓ 生成自然过渡成功")
                    return text
        except Exception as e:
            logger.error(f"✗ 生成自然过渡失败：{e}")
        return fallback

    def generate_coach_followup(
        self,
        user_answer: str,
        current_question: str,
        next_question: str,
        position: str,
        round_type: str,
        analysis_result: Optional[Dict] = None,
        followup_decision: Optional[Dict] = None,
        rag_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成“点评 + 改进建议 + 参考骨架 + 下一问”的教练式反馈。"""
        fallback_question = str(next_question or current_question or "").strip() or "请你继续展开一下刚才的关键点。"
        fallback_summary = "这一轮你已经触达了部分关键点，但结构和展开还不够稳定。"
        fallback_tip = "下一次先给整体结论，再补关键依据、方案取舍和落地细节。"
        fallback_outline = [
            "先用一句话给出整体判断或方案结论",
            "补充两到三个关键依据或核心设计点",
            "说明取舍、风险或边界条件",
            "最后总结结果与落地方式",
        ]

        if not self.check_enabled():
            return {
                "summary_feedback": fallback_summary,
                "improvement_tip": fallback_tip,
                "reference_outline": fallback_outline,
                "next_question": fallback_question,
                "spoken_summary": f"先提醒你一个关键改进点：{fallback_tip}。接下来请你回答：{fallback_question}",
            }

        resume_data = self.resume_data if isinstance(self.resume_data, dict) else None
        self.set_interview_round(round_type, resume_data)
        resume_context = self._build_resume_context(resume_data) if isinstance(resume_data, dict) else ""
        analysis_text = json.dumps(analysis_result or {}, ensure_ascii=False, indent=2)
        decision_text = json.dumps(followup_decision or {}, ensure_ascii=False, indent=2)
        prompt = (
            "你现在不是普通面试官，而是“边练边改”的面试教练。"
            "请根据候选人刚刚的回答，先给出简短、具体、可执行的点评，再抛出下一问。"
            "不要使用表格，不要输出 Markdown 代码块，不要长篇讲解。"
            "请严格返回 JSON。"
            "\n\n输出要求："
            "\n1. summary_feedback：1-2 句，总结刚才回答哪里还不够好。"
            "\n2. improvement_tip：只给 1 条最重要的改进建议。"
            "\n3. reference_outline：返回 3-5 条中文短句，作为更优回答骨架，不要写完整标准答案。"
            "\n4. next_question：直接给出下一问，像真实面试官一样提问。"
            "\n5. spoken_summary：用于语音播报，长度控制在 2 句内，先提改进点，再自然过渡到下一问。"
            "\n\n如果参考知识不足，也要基于当前问题和回答给出务实建议，但不要编造具体事实。"
            f"\n\n目标岗位：{position}"
            f"\n面试轮次：{round_type}"
            f"\n当前问题：{current_question}"
            f"\n候选人回答：{user_answer}"
            f"\n建议中的下一问：{fallback_question}"
        )
        if resume_context:
            prompt += f"\n\n候选人简历摘要：\n{resume_context}"
        if rag_context:
            prompt += f"\n\n参考知识与考点：\n{rag_context}"
        if analysis_result:
            prompt += f"\n\n结构化分析：\n{analysis_text}"
        if followup_decision:
            prompt += f"\n\n追问决策参考：\n{decision_text}"
        prompt += (
            "\n\n返回 JSON schema："
            '\n{'
            '\n  "summary_feedback": "...",'
            '\n  "improvement_tip": "...",'
            '\n  "reference_outline": ["...", "..."],'
            '\n  "next_question": "...",'
            '\n  "spoken_summary": "..."'
            '\n}'
        )

        try:
            response = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                top_p=0.6,
                top_k=40,
                temperature=0.3,
                max_tokens=900,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                logger.error(f"✗ 教练点评 API 错误：{response.message}")
                raise RuntimeError(response.message)

            raw_text = str(response.output.text or "").strip()
            json_match = re.search(r"\{.*\}", raw_text, re.S)
            if not json_match:
                raise ValueError("coach response missing json object")

            parsed = json.loads(json_match.group(0))
            summary_feedback = str(parsed.get("summary_feedback") or "").strip() or fallback_summary
            improvement_tip = str(parsed.get("improvement_tip") or "").strip() or fallback_tip
            reference_outline = [
                str(item).strip()
                for item in (parsed.get("reference_outline") or [])
                if str(item).strip()
            ][:5] or fallback_outline
            resolved_next_question = str(parsed.get("next_question") or "").strip() or fallback_question
            spoken_summary = str(parsed.get("spoken_summary") or "").strip()
            if not spoken_summary:
                spoken_summary = f"先提醒你一个关键改进点：{improvement_tip}。接下来请你回答：{resolved_next_question}"

            return {
                "summary_feedback": summary_feedback,
                "improvement_tip": improvement_tip,
                "reference_outline": reference_outline,
                "next_question": resolved_next_question,
                "spoken_summary": spoken_summary,
            }
        except Exception as e:
            logger.error(f"✗ 生成教练式反馈失败：{e}")
            return {
                "summary_feedback": fallback_summary,
                "improvement_tip": fallback_tip,
                "reference_outline": fallback_outline,
                "next_question": fallback_question,
                "spoken_summary": f"先提醒你一个关键改进点：{fallback_tip}。接下来请你回答：{fallback_question}",
            }

# 创建全局 LLM 管理器实例
llm_manager = LLMManager()
