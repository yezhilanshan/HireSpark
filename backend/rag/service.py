"""
RAG service - configuration, indexing and retrieval entrypoint.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embedding import TextEmbedder
from .chroma_db import KnowledgeStore
from .retriever import KnowledgeRetriever, QuestionRetriever, RubricRetriever
from .state import InterviewState

try:
    from utils.config_loader import config
    from utils.logger import get_logger
except ImportError:  # pragma: no cover - compatibility for root-level scripts
    from backend.utils.config_loader import config
    from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_EMBEDDING_MODEL = "shibing624/text2vec-base-chinese"
OPENAI_EMBEDDING_MODELS = {
    "text-embedding-3-small",
    "text-embedding-3-large",
}

# 第一层匹配默认同义词（当题库未配置 aliases 时作为兜底）
DEFAULT_KEY_POINT_ALIASES = {
    "数组": ["哈希桶", "桶数组", "bucket array"],
    "链表": ["链地址法", "拉链法", "链式冲突处理"],
    "红黑树": ["treeify", "树化", "rbtree"],
    "哈希冲突": ["冲突处理", "碰撞处理", "collision"],
    "扩容机制": ["resize", "容量翻倍", "rehash", "阈值触发扩容"],
    "负载因子": ["load factor", "装载因子", "阈值"],
    "索引计算": ["hash定位", "下标计算", "index calc"],
    "线程": ["并发", "多线程", "thread"],
    "事务": ["transaction", "acID", "隔离级别"],
    "性能优化": ["调优", "优化", "benchmark"],
}

POSITION_ALIASES = {
    "java_backend": ["java_backend", "java后端", "java后端工程师", "java后端开发工程师", "后端", "后端工程师", "backend"],
    "frontend": ["frontend", "frontend_engineer", "前端", "前端工程师", "前端开发", "web前端工程师", "web前端开发工程师", "qianduan"],
    "algorithm": ["algorithm", "algorithm_engineer", "算法", "算法工程师"],
    "test_engineer": [
        "test_engineer", "software_test", "software_test_engineer", "qa", "qa_engineer",
        "测试", "测试工程师", "软件测试", "软件测试工程师", "质量保障",
        "fullstack", "全栈", "全栈工程师"
    ],
    "agent_developer": [
        "agent_developer", "agentdeveloper", "agent开发", "agent开发工程师", "agent工程师", "智能体开发", "智能体工程师",
        "data_engineer", "数据工程师", "dataengineer", "agent", "agent developer"
    ],
    "devops": ["devops", "devops工程师", "运维开发", "运维工程师"],
    "product_manager": ["product_manager", "productmanager", "产品经理", "产品", "chanpin", "pm"],
}


class RAGService:
    """Shared RAG service used by scripts and runtime handlers."""

    def __init__(self):
        self.backend_root = Path(__file__).resolve().parents[1]
        self.enabled = bool(config.get("rag.enabled", False))
        self.requested_store_type = str(
            config.get("rag.store", config.get("rag.vector_db", "chroma"))
        ).lower()
        self.store_type = self._normalize_store_type(self.requested_store_type)
        self.embedding_model = self._normalize_embedding_model(
            config.get("rag.embedding_model", DEFAULT_EMBEDDING_MODEL)
        )
        self.collection_name = config.get("rag.collection_name", "interview_questions")
        self.persist_dir = self._resolve_backend_path(
            config.get("rag.persist_dir", "rag_data")
        )
        self.knowledge_path = self._resolve_backend_path(
            config.get("rag.knowledge_path", "knowledge/llm_questions.json")
        )
        self.additional_knowledge_paths = self._resolve_backend_paths(
            config.get("rag.additional_knowledge_paths", [])
        )
        self.top_k = int(config.get("rag.top_k", 5))
        self.min_similarity = float(config.get("rag.min_similarity", 0.55))
        self.max_context_results = int(config.get("rag.max_context_results", 2))
        self.max_similarity_gap = float(config.get("rag.max_similarity_gap", 0.08))
        self.min_lexical_score = float(config.get("rag.min_lexical_score", 0.10))
        self.question_candidate_pool_size = max(
            8,
            int(config.get("rag.question_candidate_pool_size", 12) or 12),
        )
        self.question_selection_pool_size = max(
            3,
            int(config.get("rag.question_selection_pool_size", 5) or 5),
        )
        self.question_randomness = max(
            0.0,
            min(1.0, float(config.get("rag.question_randomness", 0.35) or 0.35)),
        )
        self.auto_build = bool(config.get("rag.auto_build_on_start", False))

        self.embedder: Optional[TextEmbedder] = None
        self.store: Optional[KnowledgeStore] = None
        self.retriever: Optional[KnowledgeRetriever] = None
        self.question_retriever: Optional[QuestionRetriever] = None
        self.rubric_retriever: Optional[RubricRetriever] = None
        self._initialized = False
        self._build_attempted = False

        if self.enabled and self.auto_build:
            self.ensure_ready()

    def _resolve_backend_path(self, value: Optional[str]) -> str:
        if not value:
            return str(self.backend_root)

        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((self.backend_root / path).resolve())

    def _resolve_backend_paths(self, values: Any) -> List[str]:
        if not values:
            return []
        if isinstance(values, (str, Path)):
            values = [values]

        resolved: List[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            resolved.append(self._resolve_backend_path(text))
        return resolved

    def _normalize_store_type(self, value: str) -> str:
        normalized = (value or "chroma").strip().lower()
        if normalized == "faiss":
            logger.warning("当前仅实现 ChromaDB 存储，配置中的 faiss 将回退为 chroma")
            return "chroma"
        if normalized not in {"chroma", "local"}:
            logger.warning(f"未知的 RAG 存储类型：{value}，将回退为 chroma")
            return "chroma"
        return normalized

    def _normalize_embedding_model(self, value: Optional[str]) -> str:
        model_name = (value or DEFAULT_EMBEDDING_MODEL).strip()
        if model_name in OPENAI_EMBEDDING_MODELS:
            logger.warning(
                "当前 RAG 实现使用本地 sentence-transformers，"
                f"配置中的 {model_name} 将回退为 {DEFAULT_EMBEDDING_MODEL}"
            )
            return DEFAULT_EMBEDDING_MODEL
        return model_name

    def _init_runtime(self):
        if self._initialized:
            return

        if not self.enabled:
            logger.info("RAG 当前未启用，跳过初始化")
            self._initialized = True
            return

        self.embedder = TextEmbedder(model_name=self.embedding_model)
        persist_dir = None if self.store_type == "local" else self.persist_dir
        self.store = KnowledgeStore(
            collection_name=self.collection_name,
            persist_dir=persist_dir,
            embedder=self.embedder
        )
        self.question_retriever = QuestionRetriever(self.store, self.embedder)
        self.rubric_retriever = RubricRetriever(self.store, self.embedder)
        self.retriever = KnowledgeRetriever(self.store, self.embedder)
        self._initialized = True

    def ensure_ready(self) -> bool:
        if not self.enabled:
            return False

        self._init_runtime()

        if (
            self.store is None
            or self.retriever is None
            or self.question_retriever is None
            or self.rubric_retriever is None
        ):
            return False

        if self.store.count() > 0:
            if self._has_dual_view_index():
                return True
            if not self._build_attempted:
                logger.info("检测到旧版单索引 RAG，开始自动重建为双视图索引")
                self.build_index(rebuild=True)
            return self._has_dual_view_index()

        if not self._build_attempted:
            self.build_index()

        return self._has_dual_view_index()

    def _has_dual_view_index(self) -> bool:
        if self.store is None:
            return False
        try:
            return (
                self.store.count({"view_type": "question"}) > 0
                and self.store.count({"view_type": "rubric"}) > 0
            )
        except Exception:
            return False

    def _load_records(self, source_path: Optional[str] = None) -> List[Dict[str, Any]]:
        source_paths: List[str]
        if source_path is None:
            source_paths = [self.knowledge_path, *self.additional_knowledge_paths]
        elif isinstance(source_path, (list, tuple, set)):
            source_paths = [str(item) for item in source_path if str(item or "").strip()]
        else:
            source_paths = [str(source_path)]

        if len(source_paths) > 1:
            records: List[Dict[str, Any]] = []
            for item in source_paths:
                records.extend(self._load_records(source_path=item))
            return records

        path = Path(source_paths[0] or self.knowledge_path)
        if path.is_dir():
            records: List[Dict[str, Any]] = []
            supported_files = [
                item for item in sorted(path.iterdir())
                if item.is_file() and item.suffix.lower() in {".json", ".jsonl", ".md"}
            ]
            if not supported_files:
                raise FileNotFoundError(f"知识库目录中没有可用文件: {path}")
            for item in supported_files:
                try:
                    records.extend(self._load_records_from_file(item))
                except ValueError as exc:
                    logger.warning(f"跳过无法解析为结构化知识的文件 {item}: {exc}")
                    continue
            if not records:
                raise ValueError(f"目录中未解析到可用知识记录: {path}")
            return records

        if not path.exists():
            fallback_candidates = [
                path.with_name("llm_questions_v2.json"),
                path.with_name("llm_questions.json"),
                path.with_suffix(".jsonl"),
            ]
            for candidate in fallback_candidates:
                if candidate.exists():
                    logger.warning(f"知识库文件 {path} 不存在，回退使用 {candidate}")
                    path = candidate
                    break
            else:
                raise FileNotFoundError(
                    f"知识库文件不存在: {path}。可用候选: "
                    + ", ".join(str(candidate) for candidate in fallback_candidates)
                )

        return self._load_records_from_file(path)

    def _load_records_from_file(self, path: Path) -> List[Dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return self._load_markdown_records(path)

        if path.suffix.lower() == ".jsonl":
            records: List[Dict[str, Any]] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    records.append(json.loads(line))
            return records

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("llm_interview_questions", "questions", "items", "records"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise ValueError(f"无法识别的知识库数据格式: {path}")

    @staticmethod
    def _load_markdown_records(path: Path) -> List[Dict[str, Any]]:
        text = path.read_text(encoding="utf-8")
        records: List[Dict[str, Any]] = []
        buffer: List[str] = []
        capturing = False
        depth = 0
        in_string = False
        escape = False

        for char in text:
            if not capturing:
                if char == "{":
                    capturing = True
                    depth = 1
                    in_string = False
                    escape = False
                    buffer = [char]
                continue

            buffer.append(char)

            if escape:
                escape = False
                continue

            if char == "\\":
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1
                continue

            if char != "}":
                continue

            depth -= 1
            if depth > 0:
                continue

            chunk = "".join(buffer).strip()
            capturing = False
            buffer = []

            if not chunk:
                continue

            parsed: Any = None
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(chunk)
                except Exception:
                    continue

            if isinstance(parsed, dict):
                records.append(parsed)
            elif isinstance(parsed, list):
                records.extend(item for item in parsed if isinstance(item, dict))

        if records:
            return records

        fallback_records = RAGService._extract_question_records_from_plain_markdown(path, text)
        if fallback_records:
            logger.info(
                "Markdown 未命中 JSON 结构，已回退为纯文本题目抽取: %s (count=%s)",
                path,
                len(fallback_records),
            )
            return fallback_records

        raise ValueError(f"Markdown 文件中未解析到 JSON 记录: {path}")

    @staticmethod
    def _infer_role_from_markdown_path(path: Path) -> str:
        stem = str(path.stem or "").strip().lower()
        if any(token in stem for token in ("frontend", "qianduan", "fe")):
            return "前端工程师"
        if any(token in stem for token in ("java", "backend")):
            return "Java后端工程师"
        if any(token in stem for token in ("test", "qa", "ceshi", "测试")):
            return "软件测试工程师"
        if any(token in stem for token in ("chanpin", "product", "pm")):
            return "产品经理"
        if any(token in stem for token in ("agent", "智能体", "zhinengti")):
            return "Agent开发工程师"
        if any(token in stem for token in ("algorithm", "mianjing")):
            return "算法工程师"
        return "通用岗位"

    @staticmethod
    def _extract_question_candidates_from_plain_markdown(text: str) -> List[str]:
        chinese_cues = (
            "为什么",
            "如何",
            "怎么",
            "是什么",
            "区别",
            "哪些",
            "哪种",
            "原理",
            "流程",
            "思路",
            "设计",
            "优化",
        )
        english_cues = ("why", "how", "what", "difference", "compare", "design", "explain")

        candidates: List[str] = []
        for raw_line in (text or "").splitlines():
            line = str(raw_line or "").strip()
            if not line or line.startswith("```"):
                continue

            # 清理常见 markdown / 列表前缀
            line = re.sub(r"^[#>\-\*\+\s]+", "", line)
            line = re.sub(r"^\d+[\.\)\、]\s*", "", line)
            line = re.sub(r"^[（(]?\d+[）)]\s*", "", line)
            line = re.sub(r"\s+", " ", line).strip(" \t-_")
            if len(line) < 8 or len(line) > 160:
                continue

            lower = line.lower()
            has_question_mark = ("?" in line) or ("？" in line)
            has_chinese_cue = any(cue in line for cue in chinese_cues)
            has_english_cue = any(cue in lower for cue in english_cues)
            if not (has_question_mark or has_chinese_cue or has_english_cue):
                continue

            cleaned = line.rstrip("。；;,，、")
            if cleaned:
                candidates.append(cleaned)

        deduped: List[str] = []
        seen = set()
        for question in candidates:
            key = question.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(question)
        return deduped

    @staticmethod
    def _extract_question_records_from_plain_markdown(path: Path, text: str) -> List[Dict[str, Any]]:
        questions = RAGService._extract_question_candidates_from_plain_markdown(text)
        if not questions:
            return []

        role = RAGService._infer_role_from_markdown_path(path)
        records: List[Dict[str, Any]] = []
        for index, question in enumerate(questions, start=1):
            records.append(
                {
                    "id": f"{path.stem}_plain_{index:03d}",
                    "role": role,
                    "position": role,
                    "question": question,
                    "category": "面经整理",
                    "subcategory": str(path.stem),
                    "competency": [],
                    "difficulty": "medium",
                    "question_type": "经验问答",
                    "round_type": "technical",
                    "question_intent": "screening",
                    "keywords": [],
                    "tags": ["plain_markdown", "auto_extracted", str(path.stem)],
                    "answer_summary": "",
                    "key_points": [],
                    "optional_points": [],
                    "expected_answer_signals": [],
                    "common_mistakes": [],
                    "scoring_rubric": {"basic": [], "good": [], "excellent": []},
                    "followups": [],
                    "retrieval_text": question,
                    "source": str(path.name),
                    "source_type": "auto_markdown_extraction",
                }
            )
        return records

    def _normalize_record(self, raw: Dict[str, Any], index: int) -> Dict[str, Any]:
        record_id = str(raw.get("id") or f"rag_{index:04d}")
        role_or_position = str(raw.get("position") or raw.get("role") or "").strip()
        canonical_position = self._normalize_position(role_or_position)
        question = str(
            raw.get("question")
            or raw.get("title")
            or raw.get("content")
            or ""
        ).strip()
        if not question:
            raise ValueError(f"记录缺少 question/title/content 字段: {record_id}")

        answer = str(
            raw.get("answer")
            or raw.get("answer_summary")
            or raw.get("content")
            or ""
        ).strip()
        keywords = self._ensure_list(raw.get("keywords"))
        tags = self._ensure_list(raw.get("tags"))
        competency = self._ensure_list(raw.get("competency"))
        expected_answer_signals = self._ensure_list(
            raw.get("expected_answer_signals")
        ) or keywords[:]
        return {
            "id": record_id,
            "role": role_or_position,
            "position": canonical_position or role_or_position,
            "question": question,
            "category": raw.get("category", ""),
            "subcategory": raw.get("subcategory") or raw.get("title", ""),
            "competency": competency,
            "difficulty": raw.get("difficulty", ""),
            "question_type": raw.get("question_type") or raw.get("doc_type", ""),
            "round_type": raw.get("round_type", "technical"),
            "question_intent": raw.get("question_intent", "screening"),
            "keywords": keywords,
            "answer_summary": answer,
            "key_points": raw.get("key_points", []),
            "optional_points": raw.get("optional_points", []),
            "expected_answer_signals": expected_answer_signals,
            "common_mistakes": raw.get("common_mistakes", []),
            "scoring_rubric": raw.get("scoring_rubric", {}),
            "aliases": raw.get("aliases", {}),
            "rubric_version": raw.get("rubric_version", "unknown"),
            "followups": self._normalize_followups(raw.get("followups", []), keywords),
            "retrieval_text": raw.get("retrieval_text", "") or answer or question,
            "source": raw.get("source", ""),
            "source_type": raw.get("source_type", ""),
            "chunk_id": raw.get("chunk_id", ""),
            "doc_type": raw.get("doc_type", ""),
            "tags": tags,
            "answer": answer,
        }

    @staticmethod
    def _ensure_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _normalize_followups(
        followups: Any,
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        normalized = []
        default_signals = [
            str(keyword).strip()
            for keyword in (keywords or [])
            if str(keyword).strip()
        ][:3]

        for entry in RAGService._ensure_list(followups):
            if isinstance(entry, dict):
                question = str(entry.get("question", "")).strip()
                if not question:
                    continue
                trigger_signals = [
                    str(signal).strip()
                    for signal in RAGService._ensure_list(
                        entry.get("trigger_signals")
                    )
                    if str(signal).strip()
                ]
                normalized.append({
                    "question": question,
                    "trigger_type": str(
                        entry.get("trigger_type") or "missing_detail"
                    ).strip() or "missing_detail",
                    "trigger_signals": trigger_signals or default_signals
                })
                continue

            question = str(entry).strip()
            if not question:
                continue
            normalized.append({
                "question": question,
                "trigger_type": "missing_detail",
                "trigger_signals": default_signals
            })

        return normalized

    def _ensure_unique_record_ids(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保记录 ID 全局唯一，避免向量库写入失败。"""
        seen_counts: Dict[str, int] = {}
        unique_items: List[Dict[str, Any]] = []

        for item in items:
            base_id = str(item.get("id") or "").strip()
            if not base_id:
                unique_items.append(item)
                continue

            seen_counts[base_id] = seen_counts.get(base_id, 0) + 1
            if seen_counts[base_id] == 1:
                unique_items.append(item)
                continue

            dedup_id = f"{base_id}__dup{seen_counts[base_id]}"
            logger.warning(f"检测到重复题目ID：{base_id}，已自动改写为 {dedup_id}")
            updated = dict(item)
            updated["id"] = dedup_id
            updated["original_id"] = base_id
            unique_items.append(updated)

        return unique_items

    def build_index(self, source_path: Optional[str] = None, rebuild: bool = False) -> int:
        if not self.enabled:
            logger.info("RAG 未启用，跳过建库")
            return 0

        self._init_runtime()
        self._build_attempted = True

        if self.store is None:
            return 0

        raw_records = self._load_records(source_path=source_path)
        items = [
            self._normalize_record(record, idx)
            for idx, record in enumerate(raw_records, start=1)
        ]
        items = self._ensure_unique_record_ids(items)

        if rebuild:
            self.store.reset()
        elif self.store.count() > 0:
            if not self._has_dual_view_index():
                logger.info("检测到旧版单索引，重建为 question/rubric 双视图索引")
                self.store.reset()
            else:
                logger.info(f"RAG 索引已存在，共 {self.store.count()} 条，跳过重复建库")
                return self.store.count()

        self.store.add_questions_batch(items)
        self.store.save()
        logger.info(f"RAG 建库完成，共 {self.store.count()} 条")
        return self.store.count()

    def build_indexes(self, source_path: Optional[str] = None, rebuild: bool = False) -> int:
        """构建双视图索引的兼容入口。"""
        return self.build_index(source_path=source_path, rebuild=rebuild)

    def create_interview_state(
        self,
        role: str,
        round_type: str = "technical",
        difficulty: str = "medium",
        session_id: str = "",
    ) -> Dict[str, Any]:
        state = InterviewState(
            session_id=session_id,
            role=role,
            target_round_type=round_type or "technical",
            target_difficulty=difficulty or "medium",
        )
        return state.to_dict()

    def _coerce_interview_state(
        self,
        session_state: Optional[Any],
        role: Optional[str] = None,
        round_type: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> InterviewState:
        if isinstance(session_state, InterviewState):
            state = session_state
        elif isinstance(session_state, dict):
            state = InterviewState.from_dict(session_state)
        else:
            state = InterviewState()

        if role and not state.role:
            state.role = role
        if round_type:
            state.target_round_type = round_type
        if difficulty:
            state.target_difficulty = difficulty
        return state

    @staticmethod
    def _dedupe_terms(values: List[Any], limit: int) -> List[str]:
        terms: List[str] = []
        seen = set()
        for value in values:
            text = str(value or "").strip()
            if len(text) < 2:
                continue
            normalized = re.sub(r"\s+", "", text).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            terms.append(text)
            if len(terms) >= limit:
                break
        return terms

    def _extract_resume_hints(self, resume_data: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
        if not isinstance(resume_data, dict):
            return {"skills": [], "projects": [], "keywords": []}

        raw_skills = resume_data.get("skills", []) or []
        raw_projects = resume_data.get("projects", []) or []
        raw_experiences = resume_data.get("experiences", []) or []

        skills = self._dedupe_terms(raw_skills, limit=8)

        project_names: List[str] = []
        project_terms: List[str] = []
        for project in raw_projects[:4]:
            if not isinstance(project, dict):
                continue
            project_names.append(project.get("name", ""))
            project_terms.extend(project.get("technologies", []) or [])

        experience_terms: List[str] = []
        for experience in raw_experiences[:3]:
            if not isinstance(experience, dict):
                continue
            experience_terms.append(experience.get("position", ""))

        projects = self._dedupe_terms(project_names, limit=4)
        keywords = self._dedupe_terms(project_terms + skills + experience_terms + projects, limit=10)
        return {
            "skills": skills,
            "projects": projects,
            "keywords": keywords,
        }

    def attach_resume_to_state(
        self,
        session_state: Optional[Any],
        resume_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = self._coerce_interview_state(session_state)
        hints = self._extract_resume_hints(resume_data)
        state.resume_skills = hints["skills"]
        state.resume_projects = hints["projects"]
        state.resume_keywords = hints["keywords"]
        return state.to_dict()

    def _get_resume_weight_profile(self, round_type: str) -> Dict[str, Any]:
        normalized = str(round_type or "technical").strip().lower()
        profiles = {
            "project": {
                "project_limit": 4,
                "keyword_limit": 5,
                "skill_limit": 3,
                "base_hit_boost": 0.10,
                "max_hit_boost": 0.40,
                "project_bonus": 0.14,
                "skill_bonus": 0.06,
                "enabled": True,
            },
            "system_design": {
                "project_limit": 3,
                "keyword_limit": 4,
                "skill_limit": 3,
                "base_hit_boost": 0.08,
                "max_hit_boost": 0.32,
                "project_bonus": 0.10,
                "skill_bonus": 0.05,
                "enabled": True,
            },
            "technical": {
                "project_limit": 1,
                "keyword_limit": 3,
                "skill_limit": 3,
                "base_hit_boost": 0.04,
                "max_hit_boost": 0.18,
                "project_bonus": 0.02,
                "skill_bonus": 0.05,
                "enabled": True,
            },
            "hr": {
                "project_limit": 0,
                "keyword_limit": 0,
                "skill_limit": 0,
                "base_hit_boost": 0.0,
                "max_hit_boost": 0.0,
                "project_bonus": 0.0,
                "skill_bonus": 0.0,
                "enabled": False,
            },
        }
        return profiles.get(normalized, profiles["technical"])

    def _select_resume_query_terms(self, state: InterviewState) -> List[str]:
        profile = self._get_resume_weight_profile(state.target_round_type)
        if not profile.get("enabled", True):
            return []

        candidates = (
            state.resume_projects[: profile["project_limit"]]
            + state.resume_keywords[: profile["keyword_limit"]]
            + state.resume_skills[: profile["skill_limit"]]
        )
        return self._dedupe_terms(candidates, limit=6)

    def _build_question_query(
        self,
        state: InterviewState,
        context: Optional[str] = None,
    ) -> str:
        query_parts: List[str] = [
            state.role,
            state.target_round_type,
            state.target_difficulty,
        ]
        if state.current_topic:
            query_parts.append(state.current_topic)
        query_parts.extend(state.weak_competencies[:3])
        query_parts.extend(self._select_resume_query_terms(state))
        if context:
            query_parts.append(context)
        return " ".join(part for part in query_parts if part)

    def _score_question_for_state(
        self,
        item: Dict[str, Any],
        state: InterviewState,
    ) -> float:
        metadata = item.get("metadata", {}) or {}
        competencies = [
            str(entry).strip()
            for entry in metadata.get("competency", []) or []
            if str(entry).strip()
        ]
        covered = set(state.covered_competencies)
        weak = set(state.weak_competencies)

        score = float(item.get("rerank_score", item.get("similarity", 0.0)))
        uncovered_gain = sum(1 for entry in competencies if entry not in covered)
        weak_gain = sum(1 for entry in competencies if entry in weak)
        score += min(uncovered_gain * 0.08, 0.24)
        score += min(weak_gain * 0.05, 0.15)

        current_topic = (state.current_topic or "").strip()
        item_topic = str(metadata.get("subcategory") or metadata.get("category") or "").strip()
        if current_topic and item_topic and current_topic == item_topic:
            score += 0.04
        target_round = str(state.target_round_type or "").strip().lower()
        item_round = str(metadata.get("round_type") or "").strip().lower()
        if target_round and item_round:
            if item_round == target_round:
                score += 0.20
            else:
                score -= 0.18
        round_keyword_hints = {
            "system_design": ["系统设计", "架构", "扩展", "高并发", "可用性", "一致性", "分布式", "容量", "限流", "降级"],
            "project": ["项目", "落地", "负责", "复盘", "协作", "推进", "实践", "交付"],
            "hr": ["自我介绍", "职业规划", "优缺点", "冲突", "沟通", "团队", "压力", "动机"],
            "technical": ["原理", "机制", "实现", "复杂度", "优化", "底层", "源码", "算法"],
        }
        if target_round in round_keyword_hints:
            round_haystack = " ".join(
                [
                    str(item.get("question", "")).strip(),
                    str(metadata.get("category", "")).strip(),
                    str(metadata.get("subcategory", "")).strip(),
                    " ".join(str(entry) for entry in metadata.get("keywords", []) or []),
                ]
            )
            hint_hits = sum(
                1 for token in round_keyword_hints[target_round] if token and token in round_haystack
            )
            if hint_hits:
                score += min(0.22, hint_hits * 0.05)

        target_difficulty = str(state.target_difficulty or "").strip().lower()
        item_difficulty = str(metadata.get("difficulty") or "").strip().lower()
        if target_difficulty and item_difficulty:
            if item_difficulty == target_difficulty:
                score += 0.08
            else:
                adjacent = {
                    "easy": {"medium"},
                    "medium": {"easy", "hard"},
                    "hard": {"medium"},
                }
                score += 0.02 if item_difficulty in adjacent.get(target_difficulty, set()) else -0.06

        resume_terms = self._select_resume_query_terms(state)
        resume_profile = self._get_resume_weight_profile(state.target_round_type)
        if resume_terms:
            haystack = re.sub(
                r"\s+",
                "",
                " ".join([
                    str(item.get("question", "")).strip(),
                    str(metadata.get("category", "")).strip(),
                    str(metadata.get("subcategory", "")).strip(),
                    " ".join(str(entry) for entry in metadata.get("keywords", []) or []),
                ]).lower(),
            )
            resume_hits = [
                term for term in resume_terms
                if re.sub(r"\s+", "", str(term).lower()) in haystack
            ]
            if resume_hits:
                score += min(
                    len(resume_hits) * float(resume_profile.get("base_hit_boost", 0.0)),
                    float(resume_profile.get("max_hit_boost", 0.0)),
                )
                if any(
                    term in set(state.resume_projects) for term in resume_hits
                ) and float(resume_profile.get("project_bonus", 0.0)) > 0:
                    score += float(resume_profile.get("project_bonus", 0.0))
                if any(
                    term in set(state.resume_skills) for term in resume_hits
                ) and float(resume_profile.get("skill_bonus", 0.0)) > 0:
                    score += float(resume_profile.get("skill_bonus", 0.0))

        is_first_question = not (state.asked_question_ids or [])
        question_type = str(metadata.get("question_type") or "").strip().lower()
        question_intent = str(metadata.get("question_intent") or "").strip().lower()
        if is_first_question:
            if target_round == "project":
                if any(token in question_type for token in ["项目", "场景", "实战"]) or question_intent == "deep_dive":
                    score += 0.18
                if any(token in question_type for token in ["基础", "定义"]) or question_intent == "screening":
                    score -= 0.14
            elif target_round == "system_design":
                if any(token in question_type for token in ["系统设计", "场景", "架构"]) or question_intent == "deep_dive":
                    score += 0.20
                if any(token in question_type for token in ["基础", "技术基础"]) or question_intent == "screening":
                    score -= 0.16

        return round(score, 4)

    def _question_selection_seed(
        self,
        state: InterviewState,
        context: Optional[str] = None,
    ) -> int:
        seed_text = "|".join(
            [
                str(state.session_id or ""),
                str(state.role or ""),
                str(state.target_round_type or ""),
                str(state.target_difficulty or ""),
                str(len(state.asked_question_ids or [])),
                str(context or ""),
            ]
        )
        digest = hashlib.sha1(seed_text.encode("utf-8", errors="ignore")).hexdigest()
        return int(digest[:12], 16)

    def _select_question_from_ranked_pool(
        self,
        candidates: List[Dict[str, Any]],
        state: InterviewState,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None

        target_round = str(state.target_round_type or "").strip().lower()
        is_first_question = not (state.asked_question_ids or [])
        pool_size = max(1, min(self.question_selection_pool_size, len(candidates)))
        effective_randomness = self.question_randomness
        if is_first_question and target_round in {"project", "system_design"}:
            pool_size = max(pool_size, min(len(candidates), self.question_selection_pool_size + 2))
            effective_randomness = max(
                self.question_randomness,
                0.58 if target_round == "project" else 0.5,
            )
        pool = candidates[:pool_size]
        if len(pool) == 1 or effective_randomness <= 0:
            return pool[0]

        max_score = max(float(item.get("score", 0.0) or 0.0) for item in pool)
        min_score = min(float(item.get("score", 0.0) or 0.0) for item in pool)
        spread = max(max_score - min_score, 0.0001)

        weights: List[float] = []
        for rank, item in enumerate(pool):
            normalized = (float(item.get("score", 0.0) or 0.0) - min_score) / spread
            rank_bias = max(0.18, 1.0 - rank * 0.14)
            weights.append(max(0.05, (0.65 + normalized) * rank_bias))

        if random.Random(self._question_selection_seed(state, context=context)).random() > effective_randomness:
            return pool[0]

        chooser = random.Random(self._question_selection_seed(state, context=context) + 17)
        return chooser.choices(pool, weights=weights, k=1)[0]

    @staticmethod
    def _move_selected_question_first(
        candidates: List[Dict[str, Any]],
        selected: Optional[Dict[str, Any]],
        max_items: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not selected:
            return candidates
        selected_id = str(selected.get("id") or "").strip()
        ordered = [selected]
        ordered.extend(
            item for item in candidates
            if str(item.get("id") or "").strip() != selected_id
        )
        if max_items is not None:
            return ordered[:max(1, max_items)]
        return ordered

    def get_next_question(
        self,
        session_state: Optional[Any],
        context: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        state = self._coerce_interview_state(session_state)
        if not state.role:
            return {
                "target_competency": [],
                "round_type": state.target_round_type,
                "difficulty_target": state.target_difficulty,
                "candidate_questions": [],
                "selection_reason": "缺少岗位信息，无法规划下一题",
            }

        query = self._build_question_query(state, context=context)
        resume_focus_terms = self._select_resume_query_terms(state)
        visible_limit = max(top_k or self.max_context_results, self.max_context_results)
        candidate_limit = max(
            self.question_candidate_pool_size,
            visible_limit * 3,
            self.top_k,
        )
        round_filter = {"round_type": state.target_round_type} if state.target_round_type else None
        relaxed_similarity = max(0.42, float(self.min_similarity) - 0.10)
        short_query = " ".join(
            part for part in [state.role, state.target_round_type, state.target_difficulty] if part
        ).strip() or query

        retrieval_plans = [
            {
                "query": query,
                "position": state.role,
                "min_similarity": self.min_similarity,
                "metadata_filters": round_filter,
            },
            {
                "query": short_query,
                "position": state.role,
                "min_similarity": relaxed_similarity,
                "metadata_filters": round_filter,
            },
            {
                "query": short_query,
                "position": None,
                "min_similarity": relaxed_similarity,
                "metadata_filters": round_filter,
            },
            {
                "query": short_query,
                "position": state.role,
                "min_similarity": relaxed_similarity,
                "metadata_filters": None,
            },
            {
                "query": short_query,
                "position": None,
                "min_similarity": relaxed_similarity,
                "metadata_filters": None,
            },
        ]
        items: List[Dict[str, Any]] = []
        for plan in retrieval_plans:
            items = self.retrieve_questions(
                query=plan["query"],
                position=plan["position"],
                top_k=candidate_limit,
                min_similarity=plan["min_similarity"],
                metadata_filters=plan["metadata_filters"],
            )
            if items:
                break

        asked_ids = set(state.asked_question_ids)
        candidate_questions = []
        seen_ids = set()
        for item in items:
            metadata = item.get("metadata", {}) or {}
            source_id = str(metadata.get("source_id") or item.get("id") or "").split("#")[0]
            if not source_id or source_id in asked_ids or source_id in seen_ids:
                continue
            seen_ids.add(source_id)

            competencies = [
                str(entry).strip()
                for entry in metadata.get("competency", []) or []
                if str(entry).strip()
            ]
            candidate_questions.append({
                "id": source_id,
                "question": item.get("question", ""),
                "category": metadata.get("category", ""),
                "subcategory": metadata.get("subcategory", ""),
                "competency": competencies,
                "difficulty": metadata.get("difficulty", ""),
                "question_type": metadata.get("question_type", ""),
                "round_type": metadata.get("round_type", ""),
                "score": self._score_question_for_state(item, state),
            })

        candidate_questions.sort(key=lambda entry: float(entry.get("score", 0)), reverse=True)
        candidate_questions = candidate_questions[:candidate_limit]
        selected_question = self._select_question_from_ranked_pool(
            candidate_questions,
            state,
            context=context,
        )
        candidate_questions = self._move_selected_question_first(
            candidate_questions[:visible_limit],
            selected_question,
            max_items=visible_limit,
        )

        target_competency = []
        if candidate_questions:
            top_question = candidate_questions[0]
            target_competency = [
                entry for entry in top_question.get("competency", [])
                if entry not in state.covered_competencies
            ] or top_question.get("competency", [])

        if candidate_questions:
            reason = "优先补齐未覆盖能力，并避开本轮已问题目"
            if state.current_topic:
                reason += f"，当前主题延续为 {state.current_topic}"
            if resume_focus_terms:
                reason += f"，并参考简历线索 {', '.join(resume_focus_terms[:3])}"
        else:
            reason = "未找到满足条件的新题目候选"

        return {
            "target_competency": target_competency[:2],
            "round_type": state.target_round_type,
            "difficulty_target": state.target_difficulty,
            "resume_focus_terms": resume_focus_terms[:4],
            "candidate_questions": candidate_questions,
            "selection_reason": reason,
            "selection_strategy": {
                "mode": "weighted_top_pool",
                "candidate_pool_size": candidate_limit,
                "selection_pool_size": min(self.question_selection_pool_size, len(candidate_questions)),
                "randomness": self.question_randomness,
                "selected_question_id": str((candidate_questions[0] or {}).get("id", "")) if candidate_questions else "",
            },
        }

    def format_question_plan(self, question_plan: Optional[Dict[str, Any]]) -> str:
        if not question_plan:
            return ""

        candidates = question_plan.get("candidate_questions", []) or []
        if not candidates:
            return ""

        parts = []
        target_competency = question_plan.get("target_competency") or []
        if target_competency:
            parts.append(f"目标能力：{', '.join(str(item) for item in target_competency)}")
        resume_focus_terms = question_plan.get("resume_focus_terms") or []
        if resume_focus_terms:
            parts.append(f"简历线索：{', '.join(str(item) for item in resume_focus_terms[:4])}")
        selection_reason = str(question_plan.get("selection_reason", "")).strip()
        if selection_reason:
            parts.append(f"选择依据：{selection_reason}")

        for index, item in enumerate(candidates, start=1):
            lines = [f"{index}. 候选题：{item.get('question', '')}"]
            category = str(item.get("category", "")).strip()
            subcategory = str(item.get("subcategory", "")).strip()
            if category or subcategory:
                lines.append(f"分类：{category} / {subcategory}".strip(" /"))
            competency = item.get("competency") or []
            if competency:
                lines.append(f"能力点：{', '.join(str(entry) for entry in competency[:3])}")
            difficulty = str(item.get("difficulty", "")).strip()
            if difficulty:
                lines.append(f"难度：{difficulty}")
            lines.append(f"规划分数：{item.get('score', 0)}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    def mark_question_asked(
        self,
        session_state: Optional[Any],
        question_plan: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = self._coerce_interview_state(session_state)
        candidates = (question_plan or {}).get("candidate_questions", []) or []
        if not candidates:
            return state.to_dict()

        selected = candidates[0]
        source_id = str(selected.get("id", "")).strip()
        if source_id and source_id not in state.asked_question_ids:
            state.asked_question_ids.append(source_id)

        topic = str(selected.get("subcategory") or selected.get("category") or "").strip()
        if topic:
            state.current_topic = topic

        state.followup_depth = 0
        question_count = max(len(state.asked_question_ids), 1)
        state.round_goal_progress = round(min(question_count / 3.0, 1.0), 4)
        return state.to_dict()

    def retrieve(
        self,
        query: str,
        position: Optional[str] = None,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        view_type: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        if not self.ensure_ready():
            return []

        combined_filters = dict(metadata_filters or {})
        if view_type:
            combined_filters["view_type"] = view_type

        retriever = self._get_retriever_for_view(view_type)
        if retriever is None:
            return []

        results = retriever.retrieve(
            query=query,
            top_k=top_k or self.top_k,
            min_similarity=min_similarity if min_similarity is not None else self.min_similarity,
            strong_filter=True,
            max_similarity_gap=self.max_similarity_gap,
            min_lexical_score=self.min_lexical_score,
            metadata_filters=combined_filters or None
        )

        if not position:
            return results

        position = self._normalize_position(position)
        filtered = []
        for item in results:
            item_position = self._normalize_position(
                str(item.get("metadata", {}).get("position", ""))
            )
            if not item_position or item_position == position:
                filtered.append(item)
        return filtered

    def _get_retriever_for_view(
        self,
        view_type: Optional[str]
    ) -> Optional[Any]:
        if view_type == "rubric":
            return self.rubric_retriever
        if view_type == "question":
            return self.question_retriever
        return self.retriever

    def retrieve_questions(
        self,
        query: str,
        position: Optional[str] = None,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.retrieve(
            query=query,
            position=position,
            top_k=top_k,
            min_similarity=min_similarity,
            view_type="question",
            metadata_filters=metadata_filters,
        )

    def retrieve_rubrics(
        self,
        query: str,
        position: Optional[str] = None,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.retrieve(
            query=query,
            position=position,
            top_k=top_k,
            min_similarity=min_similarity,
            view_type="rubric",
            metadata_filters=metadata_filters,
        )

    @staticmethod
    def _normalize_position(position: str) -> str:
        normalized = "".join((position or "").strip().lower().split())
        if not normalized:
            return ""

        for canonical, aliases in POSITION_ALIASES.items():
            normalized_aliases = {
                "".join(str(alias or "").strip().lower().split())
                for alias in aliases
            }
            if normalized == canonical or normalized in normalized_aliases:
                return canonical

        return normalized

    def _format_context(self, items: List[Dict[str, Any]]) -> str:
        parts = []
        for index, item in enumerate(items, start=1):
            metadata = item.get("metadata", {})
            answer = metadata.get("answer", "") or metadata.get("answer_summary", "")
            if not answer:
                answer = ""
            followups = metadata.get("followups") or []
            if isinstance(followups, list):
                normalized_followups = []
                for entry in followups:
                    if isinstance(entry, dict):
                        question = str(entry.get("question", "")).strip()
                        if question:
                            normalized_followups.append(question)
                    else:
                        text = str(entry).strip()
                        if text:
                            normalized_followups.append(text)
                followups = normalized_followups
            else:
                followups = []

            part_lines = [f"{index}. 问题：{item.get('question', '')}"]
            category = str(metadata.get("category", "")).strip()
            if category:
                part_lines.append(f"分类：{category}")
            difficulty = str(metadata.get("difficulty", "")).strip()
            if difficulty:
                part_lines.append(f"难度：{difficulty}")
            source = str(metadata.get("source", "")).strip()
            if source:
                part_lines.append(f"来源：{source}")
            if answer:
                part_lines.append(f"参考答案：{answer}")
            if followups:
                part_lines.append(f"可追问：{'；'.join(followups[:2])}")

            parts.append("\n".join(part_lines))

        return "\n\n".join(parts)

    def build_question_context(
        self,
        position: str,
        difficulty: str = "medium",
        round_type: Optional[str] = None,
        context: Optional[str] = None,
        interview_state: Optional[Any] = None,
    ) -> str:
        if interview_state is not None:
            state = self._coerce_interview_state(
                interview_state,
                role=position,
                round_type=round_type,
                difficulty=difficulty,
            )
            return self.format_question_plan(
                self.get_next_question(state, context=context, top_k=self.max_context_results)
            )

        query_parts = [position, difficulty]
        if round_type:
            query_parts.append(round_type)
        if context:
            query_parts.append(context)

        items = self.retrieve_questions(
            " ".join(part for part in query_parts if part),
            position=position,
            top_k=self.max_context_results,
            metadata_filters={"round_type": round_type} if round_type else None
        )
        return self._format_context(items)

    def build_answer_context(
        self,
        position: str,
        current_question: str,
        user_answer: Optional[str] = None,
        round_type: Optional[str] = None,
    ) -> str:
        query_parts = [position, current_question]
        if round_type:
            query_parts.append(round_type)
        if user_answer:
            query_parts.append(user_answer)

        items = self.retrieve_rubrics(
            " ".join(part for part in query_parts if part),
            position=position,
            top_k=self.max_context_results,
            metadata_filters={"round_type": round_type} if round_type else None
        )
        return self._format_context(items)

    @staticmethod
    def _normalize_analysis_text(text: Any) -> str:
        return re.sub(r"\s+", "", str(text or "").lower())

    @classmethod
    def _extract_analysis_terms(cls, text: Any) -> List[str]:
        normalized = cls._normalize_analysis_text(text)
        if not normalized:
            return []
        terms = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-./+]*|[\u4e00-\u9fff]{2,}", normalized)
        return list(dict.fromkeys(term for term in terms if term))

    @classmethod
    def _matches_answer_entry(cls, answer: str, entry: Any) -> bool:
        normalized_answer = cls._normalize_analysis_text(answer)
        normalized_entry = cls._normalize_analysis_text(entry)
        if not normalized_answer or not normalized_entry:
            return False
        if normalized_entry in normalized_answer:
            return True

        answer_terms = set(cls._extract_analysis_terms(answer))
        entry_terms = set(cls._extract_analysis_terms(entry))
        if not answer_terms or not entry_terms:
            return False

        overlap = answer_terms & entry_terms
        overlap_ratio = len(overlap) / max(len(entry_terms), 1)
        return len(overlap) >= 2 or overlap_ratio >= 0.6

    @classmethod
    def _collect_matched_entries(
        cls,
        answer: str,
        entries: Optional[List[Any]],
        limit: Optional[int] = None,
    ) -> List[str]:
        matched = []
        for entry in entries or []:
            text = str(entry).strip()
            if not text:
                continue
            if cls._matches_answer_entry(answer, text):
                matched.append(text)
            if limit is not None and len(matched) >= limit:
                break
        return matched

    @classmethod
    def _compute_match_ratio(cls, answer: str, entries: Optional[List[Any]]) -> float:
        normalized_entries = [
            str(entry).strip()
            for entry in entries or []
            if str(entry).strip()
        ]
        if not normalized_entries:
            return 0.0
        matched = cls._collect_matched_entries(answer, normalized_entries)
        return round(len(matched) / len(normalized_entries), 4)

    def _resolve_rubric_profile(
        self,
        question_id: Optional[str] = None,
        current_question: Optional[str] = None,
        candidate_answer: Optional[str] = None,
        position: Optional[str] = None,
        round_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if question_id:
            rubric = self.get_rubric(question_id)
            if rubric:
                return rubric

        query_variants = []
        long_query_parts = [position, current_question, candidate_answer, round_type]
        long_query = " ".join(str(part).strip() for part in long_query_parts if str(part).strip())
        if long_query:
            query_variants.append(long_query)

        question_with_round = " ".join(
            str(part).strip() for part in [position, current_question, round_type] if str(part).strip()
        )
        if question_with_round:
            query_variants.append(question_with_round)

        question_only = str(current_question or "").strip()
        if question_only:
            query_variants.append(question_only)

        answer_only = str(candidate_answer or "").strip()
        if answer_only:
            query_variants.append(answer_only)

        # 去重保序
        query_variants = list(dict.fromkeys(query_variants))
        if not query_variants:
            query_variants = [""]

        # 先走严格过滤（round_type + position），未命中时逐级放宽，避免整场评估被 skipped。
        retrieval_strategies = [
            {
                "position": position,
                "metadata_filters": {"round_type": round_type} if round_type else None,
            },
            {
                "position": position,
                "metadata_filters": None,
            },
            {
                "position": None,
                "metadata_filters": {"round_type": round_type} if round_type else None,
            },
            {
                "position": None,
                "metadata_filters": None,
            },
        ]

        items = []
        for query_text in query_variants:
            for strategy in retrieval_strategies:
                items = self.retrieve_rubrics(
                    query=query_text,
                    position=strategy["position"],
                    top_k=1,
                    metadata_filters=strategy["metadata_filters"],
                )
                if items:
                    break
            if items:
                break

        if not items:
            return None

        item = items[0]
        metadata = item.get("metadata", {}) or {}
        return {
            "id": item.get("id"),
            "source_id": metadata.get("source_id"),
            "question": item.get("question", ""),
            **metadata,
        }

    @staticmethod
    def _vector_cosine_similarity(vec_a: Any, vec_b: Any) -> float:
        if vec_a is None or vec_b is None:
            return 0.0
        if hasattr(vec_a, "tolist"):
            vec_a = vec_a.tolist()
        if hasattr(vec_b, "tolist"):
            vec_b = vec_b.tolist()
        if not isinstance(vec_a, list) or not isinstance(vec_b, list):
            return 0.0
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            fa = float(a)
            fb = float(b)
            dot += fa * fb
            norm_a += fa * fa
            norm_b += fb * fb
        if norm_a <= 0.0 or norm_b <= 0.0:
            return 0.0
        return float(dot / ((norm_a ** 0.5) * (norm_b ** 0.5) + 1e-8))

    @staticmethod
    def _default_aliases_for_point(point: str) -> List[str]:
        point_text = str(point or "").strip()
        if not point_text:
            return []
        aliases: List[str] = []
        for seed, candidates in DEFAULT_KEY_POINT_ALIASES.items():
            if seed in point_text:
                aliases.extend(candidates)
        # 去重保序
        return list(dict.fromkeys(str(item).strip() for item in aliases if str(item).strip()))

    def _build_aliases_for_key_point(
        self,
        key_point: str,
        aliases_data: Any,
    ) -> List[str]:
        aliases: List[str] = []
        if isinstance(aliases_data, dict):
            aliases.extend(self._ensure_list(aliases_data.get(key_point)))
            # 容错：按“包含关系”匹配字典键
            for alias_key, alias_values in aliases_data.items():
                key = str(alias_key or "").strip()
                if key and (key in key_point or key_point in key):
                    aliases.extend(self._ensure_list(alias_values))
        elif isinstance(aliases_data, list):
            aliases.extend(aliases_data)
        elif aliases_data:
            aliases.append(aliases_data)

        aliases.extend(self._default_aliases_for_point(key_point))
        normalized = [
            str(item).strip()
            for item in aliases
            if str(item).strip()
        ]
        return list(dict.fromkeys(normalized))

    def _semantic_match_entries(
        self,
        answer_text: str,
        entries: List[str],
        threshold: float = 0.74,
        limit: int = 4,
    ) -> List[str]:
        if not answer_text or not entries or self.embedder is None:
            return []
        try:
            answer_vector = self.embedder.encode(answer_text)
        except Exception:
            return []
        if answer_vector is None:
            return []

        matched: List[str] = []
        for entry in entries:
            candidate = str(entry).strip()
            if not candidate:
                continue
            try:
                candidate_vector = self.embedder.encode(candidate)
            except Exception:
                continue
            sim = self._vector_cosine_similarity(answer_vector, candidate_vector)
            if sim >= threshold:
                matched.append(candidate)
            if len(matched) >= limit:
                break
        return matched

    def evaluate_layer1(
        self,
        question_id: Optional[str],
        candidate_answer: str,
        current_question: Optional[str] = None,
        position: Optional[str] = None,
        round_type: Optional[str] = None,
        semantic_threshold: float = 0.74,
    ) -> Dict[str, Any]:
        """
        第一层评估：原词匹配 + 同义词匹配 + 轻量语义匹配。
        """
        answer_text = str(candidate_answer or "").strip()
        rubric = self._resolve_rubric_profile(
            question_id=question_id,
            current_question=current_question,
            candidate_answer=answer_text,
            position=position,
            round_type=round_type
        )
        if not rubric:
            return {
                "status": "skipped",
                "error_code": "RUBRIC_NOT_FOUND",
                "question_id": str(question_id or "").strip(),
                "matched_rubric_id": "",
                "rubric_version": "unknown",
                "key_points": {"covered": [], "missing": [], "coverage_ratio": 0.0},
                "rubric_match": {"basic": 0.0, "good": 0.0, "excellent": 0.0},
                "signals": {"hit": [], "red_flags": []},
                "competency": [],
                "position_profile": {
                    "role": str(position or "").strip(),
                    "question_intent": str(round_type or "").strip(),
                },
            }

        key_points = [
            str(entry).strip()
            for entry in rubric.get("key_points", []) or []
            if str(entry).strip()
        ]
        aliases_data = rubric.get("aliases", {}) or {}
        expected_signals = [
            str(entry).strip()
            for entry in rubric.get("expected_answer_signals", []) or []
            if str(entry).strip()
        ]
        common_mistakes = [
            str(entry).strip()
            for entry in rubric.get("common_mistakes", []) or []
            if str(entry).strip()
        ]
        competencies = [
            str(entry).strip()
            for entry in rubric.get("competency", []) or []
            if str(entry).strip()
        ]
        scoring_rubric = rubric.get("scoring_rubric", {}) or {}

        covered: List[Dict[str, Any]] = []
        missing: List[str] = []
        covered_set: List[str] = []

        for key_point in key_points:
            aliases = self._build_aliases_for_key_point(key_point, aliases_data)
            direct_hit = self._matches_answer_entry(answer_text, key_point)
            alias_hits = [
                alias for alias in aliases
                if self._matches_answer_entry(answer_text, alias)
            ]
            semantic_hits = self._semantic_match_entries(
                answer_text,
                [key_point] + aliases,
                threshold=semantic_threshold,
                limit=3,
            )

            strategies: List[str] = []
            if direct_hit:
                strategies.append("exact")
            if alias_hits:
                strategies.append("alias")
            if semantic_hits:
                strategies.append("semantic")

            if strategies:
                covered.append({
                    "point": key_point,
                    "strategies": strategies,
                    "matched_aliases": alias_hits[:3],
                    "semantic_hits": [entry for entry in semantic_hits if entry != key_point][:3],
                })
                covered_set.append(key_point)
            else:
                missing.append(key_point)

        def _rubric_level_match(level_key: str) -> float:
            entries = [
                str(item).strip()
                for item in scoring_rubric.get(level_key, []) or []
                if str(item).strip()
            ]
            if not entries:
                if level_key == "basic":
                    entries = key_points[:2]
                elif level_key == "good":
                    entries = key_points
                else:
                    entries = []
            if not entries:
                return 0.0
            hits = 0
            for entry in entries:
                direct_hit = self._matches_answer_entry(answer_text, entry)
                semantic_hits = self._semantic_match_entries(
                    answer_text,
                    [entry],
                    threshold=semantic_threshold,
                    limit=1,
                )
                if direct_hit or semantic_hits:
                    hits += 1
            return round(hits / len(entries), 4)

        hit_signals = self._collect_matched_entries(answer_text, expected_signals, limit=6)
        red_flags = self._collect_matched_entries(answer_text, common_mistakes, limit=4)
        coverage_ratio = round((len(covered_set) / len(key_points)), 4) if key_points else 0.0

        return {
            "status": "ok",
            "error_code": "",
            "question_id": str(rubric.get("source_id") or question_id or "").strip(),
            "matched_rubric_id": str(rubric.get("id") or "").strip(),
            "rubric_version": str(rubric.get("rubric_version", "unknown") or "unknown").strip(),
            "scoring_rubric": scoring_rubric,
            "key_points": {
                "covered": covered,
                "missing": missing,
                "coverage_ratio": coverage_ratio,
            },
            "rubric_match": {
                "basic": _rubric_level_match("basic"),
                "good": _rubric_level_match("good"),
                "excellent": _rubric_level_match("excellent"),
            },
            "signals": {
                "hit": hit_signals,
                "red_flags": red_flags,
            },
            "competency": competencies,
            "position_profile": {
                "role": str(rubric.get("position") or position or "").strip(),
                "question_intent": str(rubric.get("question_intent") or "").strip(),
                "question_type": str(rubric.get("question_type") or "").strip(),
                "keywords": [
                    str(entry).strip()
                    for entry in rubric.get("keywords", []) or []
                    if str(entry).strip()
                ][:8],
            },
            "metadata": {
                "semantic_threshold": semantic_threshold,
                "alias_enabled": True,
            },
        }

    def analyze_answer(
        self,
        question_id: Optional[str],
        candidate_answer: str,
        session_state: Optional[Any] = None,
        current_question: Optional[str] = None,
        position: Optional[str] = None,
        round_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        answer_text = str(candidate_answer or "").strip()
        state = self._coerce_interview_state(
            session_state,
            role=position,
            round_type=round_type,
        )
        rubric = self._resolve_rubric_profile(
            question_id=question_id,
            current_question=current_question,
            candidate_answer=answer_text,
            position=position or state.role,
            round_type=round_type or state.target_round_type,
        )
        if not rubric:
            return {
                "question_id": question_id or "",
                "matched_rubric_id": "",
                "coverage": {"basic": 0.0, "good": 0.0, "excellent": 0.0},
                "correctness": 0.0,
                "depth": 0.0,
                "confidence": 0.0,
                "covered_points": [],
                "missed_points": [],
                "hit_signals": [],
                "red_flags": [],
                "suggested_followup_type": "switch_question",
                "recommended_followup_ids": [],
                "competency": [],
                "followups": [],
            }

        key_points = [
            str(entry).strip()
            for entry in rubric.get("key_points", []) or []
            if str(entry).strip()
        ]
        optional_points = [
            str(entry).strip()
            for entry in rubric.get("optional_points", []) or []
            if str(entry).strip()
        ]
        expected_signals = [
            str(entry).strip()
            for entry in rubric.get("expected_answer_signals", []) or []
            if str(entry).strip()
        ]
        common_mistakes = [
            str(entry).strip()
            for entry in rubric.get("common_mistakes", []) or []
            if str(entry).strip()
        ]
        scoring_rubric = rubric.get("scoring_rubric", {}) or {}
        followups = self._normalize_followups(rubric.get("followups"))
        competencies = [
            str(entry).strip()
            for entry in rubric.get("competency", []) or []
            if str(entry).strip()
        ]

        covered_points = self._collect_matched_entries(answer_text, key_points, limit=6)
        optional_hits = self._collect_matched_entries(answer_text, optional_points, limit=4)
        hit_signals = self._collect_matched_entries(answer_text, expected_signals, limit=6)
        red_flags = self._collect_matched_entries(answer_text, common_mistakes, limit=4)

        coverage = {
            "basic": self._compute_match_ratio(answer_text, scoring_rubric.get("basic", []) or key_points[:2]),
            "good": self._compute_match_ratio(answer_text, scoring_rubric.get("good", []) or key_points),
            "excellent": self._compute_match_ratio(
                answer_text,
                scoring_rubric.get("excellent", []) or optional_points,
            ),
        }

        key_point_ratio = self._compute_match_ratio(answer_text, key_points)
        optional_ratio = self._compute_match_ratio(answer_text, optional_points)
        signal_ratio = self._compute_match_ratio(answer_text, expected_signals)
        mistake_ratio = self._compute_match_ratio(answer_text, common_mistakes)

        correctness = max(
            0.0,
            min(
                1.0,
                0.35
                + coverage["basic"] * 0.35
                + coverage["good"] * 0.20
                + signal_ratio * 0.15
                - mistake_ratio * 0.30,
            ),
        )
        depth = max(
            0.0,
            min(
                1.0,
                0.15
                + coverage["good"] * 0.35
                + coverage["excellent"] * 0.35
                + optional_ratio * 0.15,
            ),
        )
        confidence = max(
            0.0,
            min(
                1.0,
                0.25
                + key_point_ratio * 0.30
                + signal_ratio * 0.20
                + max(len(answer_text), 20) / 400.0
                - mistake_ratio * 0.15,
            ),
        )

        missed_points = [
            point for point in key_points
            if point not in covered_points
        ][:4]

        suggested_followup_type = "switch_question"
        if red_flags:
            suggested_followup_type = "correct_mistake"
        elif missed_points:
            suggested_followup_type = "missing_explanation"
        elif depth < 0.55:
            suggested_followup_type = "deepen_topic"

        recommended_followup_ids = []
        normalized_answer = self._normalize_analysis_text(answer_text)
        normalized_missed = self._normalize_analysis_text(" ".join(missed_points))
        for index, followup in enumerate(followups, start=1):
            trigger_type = str(followup.get("trigger_type", "")).strip()
            trigger_signals = [
                self._normalize_analysis_text(signal)
                for signal in followup.get("trigger_signals", []) or []
                if self._normalize_analysis_text(signal)
            ]

            matched = False
            if trigger_type and trigger_type == suggested_followup_type:
                matched = True
            elif trigger_signals and any(
                signal in normalized_missed or signal in normalized_answer
                for signal in trigger_signals
            ):
                matched = True

            if matched:
                recommended_followup_ids.append(index)

        return {
            "question_id": str(rubric.get("source_id") or question_id or "").strip(),
            "matched_rubric_id": str(rubric.get("id") or "").strip(),
            "coverage": {
                "basic": round(coverage["basic"], 4),
                "good": round(coverage["good"], 4),
                "excellent": round(coverage["excellent"], 4),
            },
            "correctness": round(correctness, 4),
            "depth": round(depth, 4),
            "confidence": round(confidence, 4),
            "covered_points": covered_points[:4],
            "missed_points": missed_points,
            "hit_signals": hit_signals[:5],
            "red_flags": red_flags[:3],
            "suggested_followup_type": suggested_followup_type,
            "recommended_followup_ids": recommended_followup_ids[:2],
            "competency": competencies,
            "followups": followups,
        }

    def format_analysis_result(self, analysis_result: Optional[Dict[str, Any]]) -> str:
        if not analysis_result:
            return ""

        parts = [
            "以下是当前回答的结构化分析，请优先依据这些判断生成反馈或追问。",
        ]
        coverage = analysis_result.get("coverage", {}) or {}
        parts.append(
            "覆盖度："
            f"basic={coverage.get('basic', 0)}, "
            f"good={coverage.get('good', 0)}, "
            f"excellent={coverage.get('excellent', 0)}"
        )
        parts.append(
            "质量评分："
            f"correctness={analysis_result.get('correctness', 0)}, "
            f"depth={analysis_result.get('depth', 0)}, "
            f"confidence={analysis_result.get('confidence', 0)}"
        )

        competency = analysis_result.get("competency") or []
        if competency:
            parts.append(f"当前能力点：{', '.join(str(entry) for entry in competency[:3])}")
        covered_points = analysis_result.get("covered_points") or []
        if covered_points:
            parts.append(f"已覆盖要点：{'；'.join(str(entry) for entry in covered_points[:4])}")
        missed_points = analysis_result.get("missed_points") or []
        if missed_points:
            parts.append(f"遗漏要点：{'；'.join(str(entry) for entry in missed_points[:4])}")
        red_flags = analysis_result.get("red_flags") or []
        if red_flags:
            parts.append(f"潜在错误：{'；'.join(str(entry) for entry in red_flags[:3])}")

        suggested_followup_type = str(
            analysis_result.get("suggested_followup_type", "")
        ).strip()
        if suggested_followup_type:
            parts.append(f"建议动作：{suggested_followup_type}")

        followups = analysis_result.get("followups") or []
        recommended_ids = set(analysis_result.get("recommended_followup_ids") or [])
        recommended_questions = [
            str(item.get("question", "")).strip()
            for index, item in enumerate(followups, start=1)
            if index in recommended_ids and str(item.get("question", "")).strip()
        ]
        if recommended_questions:
            parts.append(f"优先追问：{'；'.join(recommended_questions[:2])}")

        return "\n".join(parts)

    def update_interview_state_from_analysis(
        self,
        session_state: Optional[Any],
        analysis_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        state = self._coerce_interview_state(session_state)
        if not analysis_result:
            return state.to_dict()

        competency = [
            str(entry).strip()
            for entry in analysis_result.get("competency", []) or []
            if str(entry).strip()
        ]
        coverage = analysis_result.get("coverage", {}) or {}
        correctness = float(analysis_result.get("correctness", 0.0) or 0.0)
        missed_points = analysis_result.get("missed_points", []) or []
        recommended_followup_ids = analysis_result.get("recommended_followup_ids", []) or []

        if correctness >= 0.7 and float(coverage.get("basic", 0.0) or 0.0) >= 0.6:
            for item in competency:
                if item not in state.covered_competencies:
                    state.covered_competencies.append(item)

        if correctness < 0.6 or missed_points:
            for item in competency:
                if item not in state.weak_competencies:
                    state.weak_competencies.append(item)

        if correctness >= 0.7:
            state.weak_competencies = [
                item for item in state.weak_competencies
                if item not in set(state.covered_competencies)
            ]

        state.followup_depth = min(
            state.followup_depth + (1 if recommended_followup_ids else 0),
            3,
        )
        if not recommended_followup_ids:
            state.followup_depth = 0

        return state.to_dict()

    @staticmethod
    def _raise_difficulty_target(current_difficulty: str) -> str:
        difficulty_order = ["easy", "medium", "hard"]
        normalized = str(current_difficulty or "medium").strip().lower()
        if normalized not in difficulty_order:
            return "hard"
        current_index = difficulty_order.index(normalized)
        return difficulty_order[min(current_index + 1, len(difficulty_order) - 1)]

    def _infer_followup_style(
        self,
        state: InterviewState,
        analysis_result: Optional[Dict[str, Any]],
        followup_question: str = "",
    ) -> str:
        normalized_round = str(state.target_round_type or "").strip().lower()
        if not analysis_result:
            return "detail_probe"

        depth = float(analysis_result.get("depth", 0.0) or 0.0)
        correctness = float(analysis_result.get("correctness", 0.0) or 0.0)
        coverage = analysis_result.get("coverage", {}) or {}
        partial_coverage = float(coverage.get("partial", 0.0) or 0.0)
        poor_coverage = float(coverage.get("poor", 0.0) or 0.0)
        style_hint = str(analysis_result.get("suggested_followup_type", "") or "").strip().lower()

        if any(token in style_hint for token in ["tradeoff", "权衡", "取舍"]):
            return "tradeoff_probe"
        if any(token in style_hint for token in ["scale", "扩容", "容量", "稳定性", "高并发"]):
            return "scale_probe"

        if normalized_round in {"project", "system_design"}:
            if depth < 0.58 or partial_coverage + poor_coverage >= 0.55:
                return "detail_probe"
            if normalized_round == "system_design" and correctness >= 0.55:
                return "tradeoff_probe"
            return "scale_probe"

        if depth < 0.55 or partial_coverage >= 0.35:
            return "detail_probe"
        if correctness >= 0.7 and followup_question:
            return "tradeoff_probe"
        return "detail_probe"

    def decide_followup(
        self,
        question_id: Optional[str],
        analysis_result: Optional[Dict[str, Any]],
        session_state: Optional[Any] = None,
    ) -> Dict[str, Any]:
        state = self._coerce_interview_state(session_state)
        if not analysis_result:
            return {
                "question_id": question_id or "",
                "next_action": "switch_question",
                "followup_type": "",
                "followup_question": "",
                "recommended_followup_ids": [],
                "difficulty_target": state.target_difficulty,
                "followup_style": "detail_probe",
                "reason": "缺少结构化分析结果，切换到下一题更稳妥",
            }

        correctness = float(analysis_result.get("correctness", 0.0) or 0.0)
        depth = float(analysis_result.get("depth", 0.0) or 0.0)
        coverage = analysis_result.get("coverage", {}) or {}
        followup_type = str(analysis_result.get("suggested_followup_type", "")).strip()
        followups = analysis_result.get("followups", []) or []
        recommended_ids = [
            int(item)
            for item in analysis_result.get("recommended_followup_ids", []) or []
            if str(item).strip().isdigit()
        ]
        followup_depth = int(state.followup_depth or 0)

        followup_question = ""
        for index in recommended_ids:
            if 1 <= index <= len(followups):
                candidate = str(followups[index - 1].get("question", "")).strip()
                if candidate:
                    followup_question = candidate
                    break
        followup_style = self._infer_followup_style(state, analysis_result, followup_question)

        if (
            followup_question
            and followup_depth < 2
            and correctness < 0.82
        ):
            return {
                "question_id": analysis_result.get("question_id", question_id or ""),
                "next_action": "ask_followup",
                "followup_type": followup_type or "targeted_followup",
                "followup_question": followup_question,
                "recommended_followup_ids": recommended_ids[:2],
                "difficulty_target": state.target_difficulty,
                "followup_style": followup_style,
                "reason": "当前回答仍有明显遗漏点，优先沿当前题继续追问",
            }

        if (
            correctness >= 0.82
            and depth >= 0.68
            and float(coverage.get("good", 0.0) or 0.0) >= 0.6
        ):
            next_difficulty = self._raise_difficulty_target(state.target_difficulty)
            return {
                "question_id": analysis_result.get("question_id", question_id or ""),
                "next_action": "raise_difficulty",
                "followup_type": "advance_topic",
                "followup_question": "",
                "recommended_followup_ids": [],
                "difficulty_target": next_difficulty,
                "followup_style": "scale_probe" if state.target_round_type == "system_design" else "tradeoff_probe",
                "reason": "当前回答覆盖较完整，可以提升难度进入下一题",
            }

        if followup_depth >= 2 or correctness < 0.45:
            return {
                "question_id": analysis_result.get("question_id", question_id or ""),
                "next_action": "switch_question",
                "followup_type": followup_type or "switch_topic",
                "followup_question": "",
                "recommended_followup_ids": recommended_ids[:2],
                "difficulty_target": state.target_difficulty,
                "followup_style": followup_style,
                "reason": "当前题继续深挖收益有限，切换题目更合适",
            }

        if followup_question:
            return {
                "question_id": analysis_result.get("question_id", question_id or ""),
                "next_action": "ask_followup",
                "followup_type": followup_type or "targeted_followup",
                "followup_question": followup_question,
                "recommended_followup_ids": recommended_ids[:2],
                "difficulty_target": state.target_difficulty,
                "followup_style": followup_style,
                "reason": "存在可执行的结构化追问，继续验证当前能力点",
            }

        return {
            "question_id": analysis_result.get("question_id", question_id or ""),
            "next_action": "switch_question",
            "followup_type": followup_type or "switch_topic",
            "followup_question": "",
            "recommended_followup_ids": [],
            "difficulty_target": state.target_difficulty,
            "followup_style": followup_style,
            "reason": "未命中合适追问，进入下一题",
        }

    def format_followup_decision(self, decision: Optional[Dict[str, Any]]) -> str:
        if not decision:
            return ""

        next_action = str(decision.get("next_action", "")).strip()
        if not next_action:
            return ""

        parts = [f"策略决策：{next_action}"]
        followup_type = str(decision.get("followup_type", "")).strip()
        if followup_type:
            parts.append(f"追问类型：{followup_type}")
        followup_style = str(decision.get("followup_style", "")).strip()
        if followup_style:
            parts.append(f"追问风格：{followup_style}")
        followup_question = str(decision.get("followup_question", "")).strip()
        if followup_question:
            parts.append(f"优先问题：{followup_question}")
        difficulty_target = str(decision.get("difficulty_target", "")).strip()
        if difficulty_target:
            parts.append(f"目标难度：{difficulty_target}")
        reason = str(decision.get("reason", "")).strip()
        if reason:
            parts.append(f"原因：{reason}")

        if next_action == "ask_followup":
            parts.append("请基于当前题继续追问，不要切到新题。")
        elif next_action in {"switch_question", "raise_difficulty"}:
            parts.append("请进入下一题，不要继续围绕当前题展开。")

        return "\n".join(parts)

    def get_rubric(self, question_id: str) -> Optional[Dict[str, Any]]:
        if not question_id or not self.ensure_ready() or self.store is None:
            return None

        items = self.store.get_by_metadata(
            {"view_type": "rubric", "source_id": question_id},
            limit=1
        )
        if not items:
            return None
        item = items[0]
        return {
            "id": item.get("id"),
            "source_id": item.get("metadata", {}).get("source_id"),
            "question": item.get("question", ""),
            **(item.get("metadata", {}) or {}),
        }

    def status(self) -> Dict[str, Any]:
        count = 0
        question_count = 0
        rubric_count = 0
        if self.store is not None:
            try:
                count = self.store.count()
                question_count = self.store.count({"view_type": "question"})
                rubric_count = self.store.count({"view_type": "rubric"})
            except Exception:
                count = 0
                question_count = 0
                rubric_count = 0

        return {
            "enabled": self.enabled,
            "requested_store_type": self.requested_store_type,
            "store_type": self.store_type,
            "embedding_model": self.embedding_model,
            "knowledge_path": self.knowledge_path,
            "persist_dir": self.persist_dir,
            "count": count,
            "question_count": question_count,
            "rubric_count": rubric_count,
            "dual_index_ready": bool(question_count and rubric_count),
            "top_k": self.top_k,
            "min_similarity": self.min_similarity,
            "max_context_results": self.max_context_results,
            "max_similarity_gap": self.max_similarity_gap,
            "min_lexical_score": self.min_lexical_score,
        }


rag_service = RAGService()
