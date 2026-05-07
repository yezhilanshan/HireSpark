import json
import re
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional


COMMON_KEYWORD_HINTS = [
    "java", "spring", "spring boot", "mysql", "redis", "rabbitmq", "kafka", "docker",
    "kubernetes", "linux", "git", "grpc", "elasticsearch", "mongodb", "vue", "react",
    "typescript", "javascript", "python", "go", "微服务", "高并发", "缓存", "消息队列",
    "系统设计", "性能优化", "容灾", "监控", "测试", "接口设计", "数据结构", "算法",
]


class ResumeOptimizer:
    """轻量版简历优化服务：JD 关键词抽取 + 最近短板注入 + 受控改写 + 前后对比。"""

    def __init__(self, *, db_manager, llm_manager=None, logger=None):
        self.db_manager = db_manager
        self.llm_manager = llm_manager
        self.logger = logger

    def optimize(
        self,
        *,
        user_id: str = "default",
        latest_resume: Optional[Dict[str, Any]] = None,
        profile_form: Optional[Dict[str, Any]] = None,
        job_description: str = "",
        strategy: str = "keywords",
    ) -> Dict[str, Any]:
        current_snapshot = self._build_snapshot(profile_form or {}, latest_resume or {})
        keywords = self._extract_job_keywords(job_description)
        recent_gap_profile = self._collect_recent_gap_profile(user_id=user_id)
        match_before = self._compute_match_score(current_snapshot, keywords)

        optimized_payload = self._build_fallback_optimization(
            current_snapshot=current_snapshot,
            keywords=keywords,
            strategy=strategy,
            recent_gap_profile=recent_gap_profile,
        )

        llm_result = None
        llm_project_result = None
        if strategy == "full":
            llm_result = self._generate_llm_optimization(
                current_snapshot=current_snapshot,
                keywords=keywords,
                job_description=job_description,
                strategy=strategy,
                recent_gap_profile=recent_gap_profile,
            )
            llm_project_result = self._generate_llm_project_rewrite(
                current_snapshot=current_snapshot,
                keywords=keywords,
                job_description=job_description,
                recent_gap_profile=recent_gap_profile,
            )
        if llm_result:
            optimized_payload = self._merge_payloads(optimized_payload, llm_result)
        if llm_project_result:
            optimized_payload = self._merge_payloads(optimized_payload, llm_project_result)

        optimized_snapshot = optimized_payload.get("optimized_snapshot") or deepcopy(current_snapshot)
        project_bullet_diffs = self._normalize_project_bullet_diffs(
            optimized_payload.get("project_bullet_diffs") or [],
            current_snapshot=current_snapshot,
            keywords=keywords,
            recent_gap_profile=recent_gap_profile,
        )
        if strategy == "full":
            optimized_snapshot = self._apply_full_project_rewrite(
                current_snapshot=current_snapshot,
                optimized_snapshot=optimized_snapshot,
                project_bullet_diffs=project_bullet_diffs,
            )

        detailed_changes = self._normalize_changes(
            self._ensure_full_mode_change_records(
                changes=optimized_payload.get("detailed_changes") or [],
                current_snapshot=current_snapshot,
                optimized_snapshot=optimized_snapshot,
                project_bullet_diffs=project_bullet_diffs,
                strategy=strategy,
            ),
            current_snapshot=current_snapshot,
            optimized_snapshot=optimized_snapshot,
        )
        section_suggestions = self._normalize_section_suggestions(
            self._ensure_full_mode_section_suggestions(
                suggestions=optimized_payload.get("section_suggestions") or [],
                current_snapshot=current_snapshot,
                project_bullet_diffs=project_bullet_diffs,
                recent_gap_profile=recent_gap_profile,
                strategy=strategy,
            )
        )
        suggestions = self._normalize_string_list(optimized_payload.get("suggestions") or [], max_items=6)
        risks = self._normalize_string_list(optimized_payload.get("risks") or [], max_items=4)
        injected_keywords = self._collect_injected_keywords(current_snapshot, optimized_snapshot, keywords)
        remaining_missing_keywords = self._compute_missing_keywords(optimized_snapshot, keywords)
        match_after = self._compute_match_score(optimized_snapshot, keywords)

        result = {
            "optimization_id": f"resume_opt_{uuid.uuid4().hex[:12]}",
            "generated_at": datetime.now().isoformat(),
            "strategy": strategy,
            "target_role": current_snapshot.get("target_role", ""),
            "job_description": str(job_description or "").strip(),
            "match_before": match_before,
            "match_after": match_after,
            "keywords_extracted": keywords,
            "missing_keywords_before": self._compute_missing_keywords(current_snapshot, keywords),
            "remaining_missing_keywords": remaining_missing_keywords,
            "injected_keywords": injected_keywords,
            "before_snapshot": current_snapshot,
            "after_snapshot": optimized_snapshot,
            "detailed_changes": detailed_changes,
            "section_suggestions": section_suggestions,
            "project_bullet_diffs": project_bullet_diffs,
            "recent_gap_profile": recent_gap_profile,
            "suggestions": suggestions,
            "risks": risks,
            "summary": str(optimized_payload.get("summary") or "").strip(),
            "resume_id": latest_resume.get("id") if isinstance(latest_resume, dict) else None,
        }

        save_result = self.db_manager.save_resume_optimization({
            "optimization_id": result["optimization_id"],
            "user_id": user_id,
            "resume_id": result.get("resume_id"),
            "target_role": result.get("target_role"),
            "strategy": strategy,
            "job_description": result.get("job_description"),
            "match_before": match_before,
            "match_after": match_after,
            "result": result,
        })
        if not save_result.get("success") and self.logger:
            self.logger.warning(f"保存简历优化历史失败：{save_result.get('error')}")
        return result

    def _build_snapshot(self, profile_form: Dict[str, Any], latest_resume: Dict[str, Any]) -> Dict[str, Any]:
        parsed = latest_resume.get("parsed_data") if isinstance(latest_resume, dict) else {}
        basic = parsed.get("basic_info") if isinstance(parsed, dict) else {}

        skills_text = str(profile_form.get("skills") or "").strip()
        skills = [item.strip() for item in re.split(r"[,\n，、]", skills_text) if item.strip()]
        if not skills and isinstance(parsed.get("skills"), list):
            skills = [str(item).strip() for item in parsed.get("skills", []) if str(item).strip()]

        return {
            "nickname": str(profile_form.get("nickname") or basic.get("name") or "").strip(),
            "target_role": str(profile_form.get("targetRole") or basic.get("target_role") or "").strip(),
            "years_of_experience": str(profile_form.get("yearsOfExperience") or basic.get("years_of_experience") or "").strip(),
            "summary": str(profile_form.get("intro") or basic.get("summary") or "").strip(),
            "skills": skills,
            "education": str(profile_form.get("educationHistory") or "").strip(),
            "work_experiences": str(profile_form.get("workExperiences") or "").strip(),
            "project_experiences": str(profile_form.get("projectExperiences") or "").strip(),
        }

    def _extract_job_keywords(self, job_description: str) -> Dict[str, List[str]]:
        text = str(job_description or "").strip()
        if not text:
            return {
                "required_skills": [],
                "preferred_skills": [],
                "keywords": [],
                "key_responsibilities": [],
            }

        llm_keywords = self._extract_keywords_with_llm(text)
        if llm_keywords:
            return llm_keywords

        normalized = text.lower()
        found = []
        for keyword in COMMON_KEYWORD_HINTS:
            if keyword.lower() in normalized and keyword not in found:
                found.append(keyword)

        responsibilities = []
        for line in [item.strip(" -•\t") for item in text.splitlines() if item.strip()]:
            if len(line) >= 8 and len(responsibilities) < 5:
                responsibilities.append(line[:80])

        return {
            "required_skills": found[:8],
            "preferred_skills": found[8:12],
            "keywords": found[:12],
            "key_responsibilities": responsibilities,
        }

    def _extract_keywords_with_llm(self, job_description: str) -> Optional[Dict[str, List[str]]]:
        if self.llm_manager is None:
            return None
        system_prompt = (
            "你是岗位 JD 分析助手。请从岗位描述中提取 required_skills、preferred_skills、"
            "keywords、key_responsibilities，并且只返回 JSON。不要编造，没有就返回空数组。"
        )
        user_prompt = (
            "请分析下面的岗位描述，输出 JSON：\n"
            "{\n"
            '  "required_skills": ["..."],\n'
            '  "preferred_skills": ["..."],\n'
            '  "keywords": ["..."],\n'
            '  "key_responsibilities": ["..."]\n'
            "}\n\n"
            f"岗位描述：\n{job_description}"
        )
        result = self.llm_manager.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1200,
        )
        if not result.get("success"):
            return None
        payload = result.get("data") or {}
        return {
            "required_skills": self._normalize_string_list(payload.get("required_skills") or [], max_items=10),
            "preferred_skills": self._normalize_string_list(payload.get("preferred_skills") or [], max_items=10),
            "keywords": self._normalize_string_list(payload.get("keywords") or [], max_items=15),
            "key_responsibilities": self._normalize_string_list(payload.get("key_responsibilities") or [], max_items=6),
        }

    def _generate_llm_optimization(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        job_description: str,
        strategy: str,
        recent_gap_profile: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if self.llm_manager is None:
            return None

        system_prompt = (
            "你是求职简历优化助手。你必须严格遵守真实约束：只能改写候选人已经提供的信息，"
            "不允许新增不存在的经历、项目、公司、时间、学历、指标或技术。"
            "你可以优化表达、强调已有技术点、重组描述顺序、补充更清楚的结果导向表达。"
            "请只返回 JSON，不要输出解释性前缀。"
        )
        user_prompt = (
            "请基于当前简历快照和目标岗位描述，生成一份轻量但实用的优化结果。\n"
            f"优化策略：{strategy}\n"
            "允许优化的字段：summary、skills、work_experiences、project_experiences。\n"
            "禁止改动事实身份字段，如姓名、邮箱、手机号、学校名称、公司名称、任职时间。\n"
            "如果工作经历/项目经历不适合直接改写，也请至少给出该区块的定向优化建议和一条示例改写。\n"
            "项目经历请尽量返回逐条 bullet 改写建议，而不是整段泛泛润色。\n"
            "请返回 JSON：\n"
            "{\n"
            '  "summary": "一句话总结本次优化重点",\n'
            '  "optimized_snapshot": {\n'
            '    "summary": "...",\n'
            '    "skills": ["..."],\n'
            '    "education": "...",\n'
            '    "work_experiences": "...",\n'
            '    "project_experiences": "..."\n'
            "  },\n"
            '  "detailed_changes": [\n'
            '    {"section":"项目经历","field_label":"项目描述","before":"...","after":"...","reason":"...","impact":"..."}\n'
            "  ],\n"
            '  "section_suggestions": [\n'
            '    {"section":"项目经历","issue":"...","suggestion":"...","sample_rewrite":"..."}\n'
            "  ],\n"
            '  "project_bullet_diffs": [\n'
            '    {"project_title":"...","focus_hint":"...","reason":"...","before_bullets":["..."],"after_bullets":["..."]}\n'
            "  ],\n"
            '  "suggestions": ["..."],\n'
            '  "risks": ["..."]\n'
            "}\n\n"
            f"当前简历快照：\n{json.dumps(self._condense_snapshot_for_prompt(current_snapshot), ensure_ascii=False, indent=2)}\n\n"
            f"岗位关键词：\n{json.dumps(keywords, ensure_ascii=False, indent=2)}\n\n"
            f"最近面试短板（用于决定优先改哪一块）：\n{json.dumps(recent_gap_profile, ensure_ascii=False, indent=2)}\n\n"
            f"岗位描述：\n{job_description}"
        )
        result = self.llm_manager.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1500,
        )
        if not result.get("success"):
            if self.logger:
                self.logger.warning(f"LLM 简历优化失败，将退回规则优化：{result.get('message')}")
            return None
        return result.get("data")

    def _generate_llm_project_rewrite(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        job_description: str,
        recent_gap_profile: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if self.llm_manager is None:
            return None

        project_blocks = self._extract_project_blocks(str(current_snapshot.get("project_experiences") or ""))
        if not project_blocks:
            return None

        keyword_focus = self._dedupe_preserve_order(
            (keywords.get("required_skills") or []) + (keywords.get("keywords") or [])
        )[:8]

        system_prompt = (
            "你是资深技术简历优化顾问，专门负责把项目经历改写成适合技术岗位筛选和面试追问的 bullet。"
            "你必须严格遵守真实约束：不能新增候选人没有提供的项目、技术、结果、指标或职责。"
            "你可以重组表达、突出职责边界、补足方案与结果的表达骨架。"
            "请只返回 JSON。"
        )
        user_prompt = (
            "请仅针对下面的项目经历做逐项目 bullet 重写。\n"
            "要求：\n"
            "1. 每个项目输出 3 到 5 条 after_bullets。\n"
            "2. after_bullets 要尽量像可以直接写回简历的项目 bullet，而不是提示语。\n"
            "3. 如果原文没有量化结果，不要编造数字，但可以保留“建议补充结果”类的事实安全表达。\n"
            "4. focus_hint 说明这次重写优先补的能力面，例如项目深挖、技术细节、架构权衡、结果表达。\n"
            "5. reason 说明为什么这样改更贴合岗位与面试追问。\n"
            "请返回 JSON：\n"
            "{\n"
            '  "project_bullet_diffs": [\n'
            '    {\n'
            '      "project_title": "...",\n'
            '      "focus_hint": "...",\n'
            '      "reason": "...",\n'
            '      "before_bullets": ["..."],\n'
            '      "after_bullets": ["..."]\n'
            "    }\n"
            "  ],\n"
            '  "section_suggestions": [\n'
            '    {"section":"项目经历","issue":"...","suggestion":"...","sample_rewrite":"..."}\n'
            "  ],\n"
            '  "suggestions": ["..."]\n'
            "}\n\n"
            f"目标岗位：{current_snapshot.get('target_role') or ''}\n\n"
            f"岗位描述：\n{job_description or '未提供，主要依据目标岗位与简历内容优化。'}\n\n"
            f"岗位关键词：\n{json.dumps(keyword_focus, ensure_ascii=False)}\n\n"
            f"最近面试短板：\n{json.dumps(recent_gap_profile, ensure_ascii=False, indent=2)}\n\n"
            f"项目经历原文块：\n{json.dumps(project_blocks[:4], ensure_ascii=False, indent=2)}"
        )
        result = self.llm_manager.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.25,
            max_tokens=1800,
        )
        if not result.get("success"):
            if self.logger:
                self.logger.warning(f"LLM 项目逐条改写失败，将回退到规则改写：{result.get('message')}")
            return None
        return result.get("data")

    def _apply_full_project_rewrite(
        self,
        *,
        current_snapshot: Dict[str, Any],
        optimized_snapshot: Dict[str, Any],
        project_bullet_diffs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not project_bullet_diffs:
            return optimized_snapshot

        rendered = self._render_project_experiences_from_diffs(project_bullet_diffs)
        if not rendered:
            return optimized_snapshot

        rewritten_snapshot = deepcopy(optimized_snapshot)
        rewritten_snapshot["project_experiences"] = rendered
        return rewritten_snapshot

    def _ensure_full_mode_change_records(
        self,
        *,
        changes: List[Dict[str, Any]],
        current_snapshot: Dict[str, Any],
        optimized_snapshot: Dict[str, Any],
        project_bullet_diffs: List[Dict[str, Any]],
        strategy: str,
    ) -> List[Dict[str, Any]]:
        merged_changes = list(changes or [])
        if strategy != "full":
            return merged_changes

        before_project = str(current_snapshot.get("project_experiences") or "").strip()
        after_project = str(optimized_snapshot.get("project_experiences") or "").strip()
        if before_project and after_project and before_project != after_project:
            has_project_change = any("项目经历" in str(item.get("section") or "") for item in merged_changes)
            if not has_project_change:
                focus_hint = str(project_bullet_diffs[0].get("focus_hint") or "").strip() if project_bullet_diffs else ""
                merged_changes.insert(0, {
                    "section": "项目经历",
                    "field_label": "项目 bullet 重写",
                    "before": before_project,
                    "after": after_project,
                    "reason": focus_hint or "把项目经历改写成更适合岗位筛选与面试追问的项目 bullet，重点突出你的职责、方案、技术细节和结果。",
                    "impact": "提升项目深挖支撑力",
                })
        return merged_changes

    def _ensure_full_mode_section_suggestions(
        self,
        *,
        suggestions: List[Dict[str, Any]],
        current_snapshot: Dict[str, Any],
        project_bullet_diffs: List[Dict[str, Any]],
        recent_gap_profile: Dict[str, Any],
        strategy: str,
    ) -> List[Dict[str, Any]]:
        merged_suggestions = list(suggestions or [])
        if strategy != "full":
            return merged_suggestions

        has_project_suggestion = any(str(item.get("section") or "").strip() == "项目经历" for item in merged_suggestions)
        if has_project_suggestion or not project_bullet_diffs:
            return merged_suggestions

        focus_hint = str(project_bullet_diffs[0].get("focus_hint") or "").strip()
        sample_rewrite = "；".join(project_bullet_diffs[0].get("after_bullets") or []).strip()
        shortfalls = list(recent_gap_profile.get("top_shortfalls") or [])
        merged_suggestions.insert(0, {
            "section": "项目经历",
            "issue": (
                f"最近面试里反复暴露出“{shortfalls[0]}”的短板，现有项目描述还不足以支撑你在面试中把这个点讲透。"
                if shortfalls
                else "当前项目经历更像背景介绍，缺少足够支撑面试追问的职责、方案和结果表达。"
            ),
            "suggestion": focus_hint or "优先把项目经历改成 3 到 5 条结果导向的 bullet，每条都尽量回答“我负责了什么、怎么做的、为什么这样做、最终带来了什么”。",
            "sample_rewrite": sample_rewrite or "建议把项目经历改成更具体的职责、方案和结果表达。",
        })
        return merged_suggestions

    def _build_fallback_optimization(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        strategy: str,
        recent_gap_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        optimized = deepcopy(current_snapshot)
        current_summary = str(current_snapshot.get("summary") or "").strip()
        target_role = str(current_snapshot.get("target_role") or "").strip()
        existing_skills = list(current_snapshot.get("skills") or [])
        missing_keywords = self._compute_missing_keywords(current_snapshot, keywords)
        safe_keywords = self._pick_safe_keywords_for_fallback(current_snapshot, missing_keywords)
        section_suggestions = self._build_section_suggestions(
            current_snapshot=current_snapshot,
            keywords=keywords,
            missing_keywords=missing_keywords,
            recent_gap_profile=recent_gap_profile,
        )
        project_bullet_diffs = self._build_project_bullet_diffs(
            current_snapshot=current_snapshot,
            keywords=keywords,
            recent_gap_profile=recent_gap_profile,
        )

        if strategy in {"keywords", "full"} and safe_keywords:
            merged_skills = existing_skills[:]
            for keyword in safe_keywords:
                if keyword not in merged_skills:
                    merged_skills.append(keyword)
            optimized["skills"] = merged_skills

        summary_bits = []
        if target_role:
            summary_bits.append(f"面向{target_role}岗位")
        if existing_skills:
            summary_bits.append(f"具备{', '.join(existing_skills[:5])}等技术基础")
        if safe_keywords:
            summary_bits.append(f"可重点强化{', '.join(safe_keywords[:3])}相关表达")
        if recent_gap_profile.get("focus_section") == "project_experiences":
            summary_bits.append("后续可优先围绕项目职责、技术方案与结果表达补强简历")

        optimized["summary"] = "，".join(summary_bits) + "。" if summary_bits else current_summary
        if current_summary:
            optimized["summary"] = f"{current_summary}\n\n{optimized['summary']}".strip()

        changes = []
        if optimized["summary"] != current_snapshot.get("summary", ""):
            changes.append({
                "section": "个人介绍",
                "field_label": "摘要表达",
                "before": str(current_snapshot.get("summary") or ""),
                "after": str(optimized.get("summary") or ""),
                "reason": "把目标岗位、现有技术栈和最近需要补强的方向显式写进摘要，方便招聘方和面试官快速形成正确预期。",
                "impact": "提升岗位匹配度",
            })
        if optimized.get("skills") != existing_skills:
            changes.append({
                "section": "核心技能",
                "field_label": "关键词增强",
                "before": ", ".join(existing_skills),
                "after": ", ".join(optimized.get("skills") or []),
                "reason": "补入简历文本中已出现、且与目标岗位更相关的技能关键词。",
                "impact": "提升关键词覆盖率",
            })

        return {
            "summary": "这版优化先用 JD 关键词和最近面试短板一起决定重点：如果短板集中在项目深挖，就优先把项目经历写成更能支撑追问的样子。",
            "optimized_snapshot": optimized,
            "detailed_changes": changes,
            "section_suggestions": section_suggestions,
            "project_bullet_diffs": project_bullet_diffs,
            "suggestions": [
                "优先把与你目标岗位最相关的项目放在最前面，并在首句写清业务场景。",
                "每段项目经历尽量补成“场景、职责、关键方案、结果”四段式。",
                "如果最近项目面总暴露“项目深挖不够”，优先补充你亲自负责的模块、方案权衡和结果指标。",
            ],
            "risks": [
                "规则优化不会编造经历，但也不会自动补出你没有提供的量化结果。",
                "如果要进一步提升匹配度，建议提供真实岗位 JD 并补充项目中的真实指标与收益。",
            ],
        }

    def _merge_payloads(self, base_payload: Dict[str, Any], llm_payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(base_payload)
        llm_snapshot = llm_payload.get("optimized_snapshot")
        if isinstance(llm_snapshot, dict):
            merged_snapshot = deepcopy(merged.get("optimized_snapshot") or {})
            for key, value in llm_snapshot.items():
                if value not in (None, "", []):
                    merged_snapshot[key] = value
            merged["optimized_snapshot"] = merged_snapshot

        if str(llm_payload.get("summary") or "").strip():
            merged["summary"] = str(llm_payload.get("summary")).strip()
        merged["detailed_changes"] = (llm_payload.get("detailed_changes") or []) + (merged.get("detailed_changes") or [])
        merged["section_suggestions"] = (llm_payload.get("section_suggestions") or []) + (merged.get("section_suggestions") or [])
        merged["project_bullet_diffs"] = (llm_payload.get("project_bullet_diffs") or []) + (merged.get("project_bullet_diffs") or [])
        merged["suggestions"] = (llm_payload.get("suggestions") or []) + (merged.get("suggestions") or [])
        merged["risks"] = (llm_payload.get("risks") or []) + (merged.get("risks") or [])
        return merged

    def _compute_match_score(self, snapshot: Dict[str, Any], keywords: Dict[str, List[str]]) -> float:
        expected_keywords = []
        for key in ("required_skills", "preferred_skills", "keywords"):
            expected_keywords.extend(keywords.get(key) or [])
        expected_keywords = self._dedupe_preserve_order(expected_keywords)
        if not expected_keywords:
            return 0.0
        missing = self._compute_missing_keywords(snapshot, keywords)
        matched_count = max(len(expected_keywords) - len(missing), 0)
        return round((matched_count / len(expected_keywords)) * 100, 1)

    def _compute_missing_keywords(self, snapshot: Dict[str, Any], keywords: Dict[str, List[str]]) -> List[str]:
        all_keywords = self._dedupe_preserve_order(
            (keywords.get("required_skills") or [])
            + (keywords.get("preferred_skills") or [])
            + (keywords.get("keywords") or [])
        )
        text = self._flatten_snapshot(snapshot).lower()
        missing = []
        for keyword in all_keywords:
            if not self._keyword_in_text(keyword, text):
                missing.append(keyword)
        return missing

    def _collect_injected_keywords(
        self,
        before_snapshot: Dict[str, Any],
        after_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
    ) -> List[str]:
        before_text = self._flatten_snapshot(before_snapshot).lower()
        after_text = self._flatten_snapshot(after_snapshot).lower()
        added = []
        all_keywords = self._dedupe_preserve_order(
            (keywords.get("required_skills") or [])
            + (keywords.get("preferred_skills") or [])
            + (keywords.get("keywords") or [])
        )
        for keyword in all_keywords:
            if not self._keyword_in_text(keyword, before_text) and self._keyword_in_text(keyword, after_text):
                added.append(keyword)
        return added

    def _normalize_changes(
        self,
        changes: List[Dict[str, Any]],
        *,
        current_snapshot: Dict[str, Any],
        optimized_snapshot: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        normalized = []
        seen_pairs = set()
        for item in changes[:10]:
            section = str(item.get("section") or "").strip() or "简历内容"
            field_label = str(item.get("field_label") or "").strip() or section
            before = str(item.get("before") or "").strip()
            after = str(item.get("after") or "").strip()
            reason = str(item.get("reason") or "").strip()
            impact = str(item.get("impact") or "").strip()
            pair_key = (section, field_label, before, after)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            if before or after:
                normalized.append({
                    "section": section,
                    "field_label": field_label,
                    "before": before,
                    "after": after,
                    "reason": reason or "让这部分表达更贴近目标岗位要求。",
                    "impact": impact or "提高岗位匹配度",
                })

        if normalized:
            return normalized

        fallback_fields = [
            ("个人介绍", "摘要表达", current_snapshot.get("summary"), optimized_snapshot.get("summary")),
            ("核心技能", "技能关键词", ", ".join(current_snapshot.get("skills") or []), ", ".join(optimized_snapshot.get("skills") or [])),
            ("工作经历", "工作经历描述", current_snapshot.get("work_experiences"), optimized_snapshot.get("work_experiences")),
            ("项目经历", "项目经历描述", current_snapshot.get("project_experiences"), optimized_snapshot.get("project_experiences")),
        ]
        for section, field_label, before, after in fallback_fields:
            if str(before or "").strip() != str(after or "").strip():
                normalized.append({
                    "section": section,
                    "field_label": field_label,
                    "before": str(before or "").strip(),
                    "after": str(after or "").strip(),
                    "reason": "增强这部分与目标岗位的相关表达。",
                    "impact": "提升可读性与匹配度",
                })
        return normalized[:8]

    def _flatten_snapshot(self, snapshot: Dict[str, Any]) -> str:
        parts = [
            str(snapshot.get("target_role") or ""),
            str(snapshot.get("summary") or ""),
            str(snapshot.get("education") or ""),
            str(snapshot.get("work_experiences") or ""),
            str(snapshot.get("project_experiences") or ""),
            ", ".join(snapshot.get("skills") or []),
        ]
        return "\n".join(parts)

    def _condense_snapshot_for_prompt(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "target_role": snapshot.get("target_role"),
            "years_of_experience": snapshot.get("years_of_experience"),
            "summary": str(snapshot.get("summary") or "")[:500],
            "skills": list(snapshot.get("skills") or [])[:20],
            "education": str(snapshot.get("education") or "")[:400],
            "work_experiences": str(snapshot.get("work_experiences") or "")[:1200],
            "project_experiences": str(snapshot.get("project_experiences") or "")[:1200],
        }

    def _build_section_suggestions(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        missing_keywords: List[str],
        recent_gap_profile: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        suggestions: List[Dict[str, str]] = []
        summary = str(current_snapshot.get("summary") or "").strip()
        skills = list(current_snapshot.get("skills") or [])
        work = str(current_snapshot.get("work_experiences") or "").strip()
        project = str(current_snapshot.get("project_experiences") or "").strip()
        target_role = str(current_snapshot.get("target_role") or "").strip()
        keyword_focus = self._dedupe_preserve_order(
            (keywords.get("required_skills") or []) + (keywords.get("keywords") or [])
        )[:6]
        focus_section = str(recent_gap_profile.get("focus_section") or "").strip()
        focus_themes = list(recent_gap_profile.get("focus_themes") or [])
        shortfalls = list(recent_gap_profile.get("top_shortfalls") or [])
        project_priority = focus_section == "project_experiences" or any(
            theme in {"project_depth", "ownership", "technical_depth", "architecture_tradeoff", "result_expression"}
            for theme in focus_themes
        )
        summary_priority = focus_section == "summary" or any(
            theme in {"summary_clarity", "expression_clarity"} for theme in focus_themes
        )

        if (target_role and target_role not in summary) or summary_priority:
            summary_issue = "摘要里还没有把目标岗位和优势方向明确说出来。"
            if summary_priority and shortfalls:
                summary_issue = f"最近面试反复暴露出“{shortfalls[0]}”的问题，但摘要里还没有主动把你的定位和关键优势说清楚。"
            suggestions.append({
                "section": "个人介绍",
                "issue": summary_issue,
                "suggestion": f"开头一句直接点明你面向{target_role or '目标岗位'}，并补上最核心的 3-4 个技术关键词。",
                "sample_rewrite": f"面向{target_role or '目标岗位'}，具备{', '.join((skills or keyword_focus)[:4])}等经验，擅长围绕真实业务场景推进开发与优化。",
            })

        if missing_keywords:
            suggestions.append({
                "section": "核心技能",
                "issue": "技能区和目标 JD 的关键词对齐还不够，招聘方可能看不到你的相关性。",
                "suggestion": f"优先检查这些关键词是否确实做过：{', '.join(missing_keywords[:5])}。做过的放进技能区，没做过不要硬加。",
                "sample_rewrite": f"建议把技能区改成“语言 / 框架 / 中间件 / 数据库 / 工程实践”分组，并把 {', '.join((skills or keyword_focus)[:4])} 放到最前面。",
            })

        if work:
            work_has_metric = self._contains_metric(work)
            suggestions.append({
                "section": "工作经历",
                "issue": "工作经历更像职责罗列，结果导向和岗位相关性还不够强。" if not work_has_metric else "工作经历已有基础内容，但还可以进一步强化业务场景和技术权衡。",
                "suggestion": "每段工作经历都尽量补成“场景-动作-结果”结构，尤其写清你负责的模块、关键技术和业务价值。",
                "sample_rewrite": "建议把工作经历第一句改成“在 XX 业务场景下，负责 XX 模块设计与开发，使用 XX 技术解决 XX 问题，并带来 XX 结果”。",
            })

        if project:
            project_has_metric = self._contains_metric(project)
            project_issue = (
                "项目经历没有充分体现你亲自做了什么，或者和目标岗位的高频考点连接不够。"
                if not project_has_metric else
                "项目经历里有内容，但还缺少更像面试回答的技术展开和结果说明。"
            )
            if project_priority and shortfalls:
                project_issue = f"最近项目/系统设计类面试里反复暴露出“{shortfalls[0]}”的短板，但简历项目描述还不足以支撑你在面试中把这些点讲清楚。"
            suggestions.append({
                "section": "项目经历",
                "issue": project_issue,
                "suggestion": (
                    f"优先把与你目标岗位最贴近的项目放在最前面，并主动补上与 "
                    f"{', '.join(keyword_focus[:3]) or '岗位关键词'} 相关的设计/优化动作。"
                    "如果最近短板集中在项目深挖，就先补“我亲自做了什么、为什么这样做、结果如何”。"
                ),
                "sample_rewrite": (
                    "建议每个项目至少包含 4 个点：业务场景、你的职责、关键技术方案、结果或收益。"
                    "如果你最近暴露的短板是项目深挖不够，就把“模块负责范围、方案权衡、实际效果”写得更显式。"
                ),
            })

        return suggestions[:6]

    def _build_project_bullet_diffs(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        recent_gap_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        project_text = str(current_snapshot.get("project_experiences") or "").strip()
        if not project_text:
            return []

        blocks = [block.strip() for block in re.split(r"\n\s*\n", project_text) if block.strip()]
        focus_themes = list(recent_gap_profile.get("focus_themes") or [])
        shortfalls = list(recent_gap_profile.get("top_shortfalls") or [])
        keyword_focus = self._dedupe_preserve_order(
            (keywords.get("required_skills") or []) + (keywords.get("keywords") or [])
        )[:4]

        diffs = []
        for block in blocks[:4]:
            lines = [line.strip(" -•\t") for line in block.splitlines() if line.strip()]
            if not lines:
                continue

            project_title = lines[0]
            detail_lines = lines[1:]
            tech_line = next((line for line in detail_lines if "技术栈" in line), "")
            description_line = next((line for line in detail_lines if "项目描述" in line), detail_lines[0] if detail_lines else "")
            responsibility_line = next((line for line in detail_lines if "职责" in line or "负责" in line), "")

            after_bullets = []
            if tech_line:
                after_bullets.append(f"技术栈：{tech_line.split('：', 1)[-1].strip()}")
            if description_line:
                after_bullets.append(f"业务场景：{description_line.split('：', 1)[-1].strip()}")
            if responsibility_line:
                after_bullets.append(f"个人职责：{responsibility_line.split('：', 1)[-1].strip()}")
            elif detail_lines:
                after_bullets.append("个人职责：建议把你亲自负责的模块、接口或功能点单独写成一条，避免只有项目背景。")

            focus_hint = "优先补充项目深挖、模块 ownership 和结果表达。"
            if "architecture_tradeoff" in focus_themes:
                focus_hint = "优先补充方案权衡、扩展性设计和为什么这样选。"
            elif "technical_depth" in focus_themes:
                focus_hint = "优先补充关键技术方案、难点和你亲自处理的技术细节。"
            elif "result_expression" in focus_themes:
                focus_hint = "优先补充性能、效率、稳定性或业务收益等结果数据。"
            if shortfalls:
                focus_hint = f"结合最近面试短板“{shortfalls[0]}”，建议把这一条写成更能支撑追问的项目 bullet。"

            if keyword_focus:
                after_bullets.append(f"建议补点：围绕 {', '.join(keyword_focus[:3])} 写清你做过的设计、优化或排障动作。")
            else:
                after_bullets.append("建议补点：写清你做过的设计、优化、排障动作，以及最终结果。")

            diffs.append({
                "project_title": project_title,
                "focus_hint": focus_hint,
                "reason": "把项目描述改成更像面试追问支撑材料的 bullet，可以同时提升岗位匹配度和项目面可展开性。",
                "before_bullets": lines[:6],
                "after_bullets": after_bullets[:6],
            })
        return diffs

    def _extract_project_blocks(self, project_text: str) -> List[Dict[str, Any]]:
        text = str(project_text or "").strip()
        if not text:
            return []

        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        parsed_blocks = []
        for block in blocks:
            lines = [line.strip(" -•\t") for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            parsed_blocks.append({
                "title": lines[0],
                "lines": lines,
                "detail_lines": lines[1:],
                "raw_block": block,
            })
        return parsed_blocks

    def _strip_field_prefix(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        return re.sub(r"^[^:：]{1,12}[:：]\s*", "", value).strip()

    def _render_project_experiences_from_diffs(self, items: List[Dict[str, Any]]) -> str:
        rendered_blocks = []
        for item in items:
            title = str(item.get("project_title") or "").strip()
            bullets = self._normalize_string_list(item.get("after_bullets") or [], max_items=6)
            if not title or not bullets:
                continue
            block_lines = [title] + [f"- {bullet}" for bullet in bullets]
            rendered_blocks.append("\n".join(block_lines))
        return "\n\n".join(rendered_blocks).strip()

    def _build_project_bullet_diffs(
        self,
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        recent_gap_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        project_blocks = self._extract_project_blocks(str(current_snapshot.get("project_experiences") or ""))
        if not project_blocks:
            return []

        focus_themes = list(recent_gap_profile.get("focus_themes") or [])
        shortfalls = list(recent_gap_profile.get("top_shortfalls") or [])
        keyword_focus = self._dedupe_preserve_order(
            (keywords.get("required_skills") or []) + (keywords.get("keywords") or [])
        )[:4]

        diffs = []
        for block in project_blocks[:4]:
            project_title = str(block.get("title") or "").strip()
            detail_lines = list(block.get("detail_lines") or [])
            before_bullets = list(block.get("lines") or [])[:6]

            tech_line = next((line for line in detail_lines if any(token in line for token in ("技术栈", "技术", "Tech"))), "")
            description_line = next((line for line in detail_lines if any(token in line for token in ("项目描述", "描述", "背景", "场景"))), detail_lines[0] if detail_lines else "")
            responsibility_line = next((line for line in detail_lines if any(token in line for token in ("职责", "负责", "工作内容", "我做了"))), "")

            description_value = self._strip_field_prefix(description_line)
            tech_value = self._strip_field_prefix(tech_line)
            responsibility_value = self._strip_field_prefix(responsibility_line)

            after_bullets = []
            if description_value:
                after_bullets.append(f"围绕{description_value}场景推进项目实现，先交代业务目标，再自然引出你负责的模块与方案。")
            if responsibility_value:
                after_bullets.append(f"重点写清你本人负责的部分：{responsibility_value}，避免只写团队整体工作。")
            elif detail_lines:
                after_bullets.append("把你亲自负责的模块、接口、核心功能或排障动作单独拆成一条，突出 ownership。")
            if tech_value:
                after_bullets.append(f"结合{tech_value}说明关键技术动作，尽量补足为什么这样设计、遇到什么难点、如何解决。")

            focus_hint = "优先补充项目深挖、模块 ownership 和结果表达。"
            if "architecture_tradeoff" in focus_themes:
                focus_hint = "优先补充方案权衡、扩展性设计和为什么这样选。"
            elif "technical_depth" in focus_themes:
                focus_hint = "优先补充关键技术方案、难点和你亲自处理的技术细节。"
            elif "result_expression" in focus_themes:
                focus_hint = "优先补充性能、效率、稳定性或业务收益等结果数据。"
            if shortfalls:
                focus_hint = f"结合最近面试短板“{shortfalls[0]}”，建议把这一条写成更能支撑追问的项目 bullet。"

            if keyword_focus:
                after_bullets.append(f"围绕{', '.join(keyword_focus[:3])}补充你做过的设计、优化或排障动作，让项目内容更贴近目标岗位高频考点。")
            else:
                after_bullets.append("补上一条结果或收益表达：哪怕暂时没有精确数字，也要说明性能、效率、稳定性或业务价值层面的改善。")
            if not self._contains_metric('\n'.join(detail_lines)):
                after_bullets.append("如果你手里有真实数据，建议再补一条结果表达，例如响应时间、成功率、效率提升或业务影响。")

            diffs.append({
                "project_title": project_title,
                "focus_hint": focus_hint,
                "reason": "把项目描述改成更像面试追问支撑材料的 bullet，可以同时提升岗位匹配度和项目面可展开性。",
                "before_bullets": before_bullets,
                "after_bullets": after_bullets[:6],
            })
        return diffs

    def _normalize_section_suggestions(self, items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalized = []
        seen = set()
        for item in items[:8]:
            section = str(item.get("section") or "").strip() or "简历内容"
            issue = str(item.get("issue") or "").strip()
            suggestion = str(item.get("suggestion") or "").strip()
            sample_rewrite = str(item.get("sample_rewrite") or "").strip()
            key = (section, issue, suggestion, sample_rewrite)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({
                "section": section,
                "issue": issue or "这部分还可以进一步贴近岗位要求。",
                "suggestion": suggestion or "建议补充更具体的动作、结果和关键词。",
                "sample_rewrite": sample_rewrite or "可把这部分改成更结构化、结果导向的表达。",
            })
        return normalized

    def _normalize_project_bullet_diffs(
        self,
        items: List[Dict[str, Any]],
        *,
        current_snapshot: Dict[str, Any],
        keywords: Dict[str, List[str]],
        recent_gap_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        normalized = []
        seen = set()
        for item in items[:6]:
            title = str(item.get("project_title") or "").strip()
            focus_hint = str(item.get("focus_hint") or "").strip()
            reason = str(item.get("reason") or "").strip()
            before_bullets = self._normalize_string_list(item.get("before_bullets") or [], max_items=8)
            after_bullets = self._normalize_string_list(item.get("after_bullets") or [], max_items=8)
            key = (title, tuple(before_bullets), tuple(after_bullets))
            if key in seen or not title:
                continue
            seen.add(key)
            normalized.append({
                "project_title": title,
                "focus_hint": focus_hint or "建议把这一条改成更能支撑项目深挖的 bullet。",
                "reason": reason or "让项目经历更贴近目标岗位和真实面试追问。",
                "before_bullets": before_bullets,
                "after_bullets": after_bullets,
            })
        if normalized:
            return normalized
        return self._build_project_bullet_diffs(
            current_snapshot=current_snapshot,
            keywords=keywords,
            recent_gap_profile=recent_gap_profile,
        )[:4]

    def _contains_metric(self, text: str) -> bool:
        value = str(text or "")
        return bool(re.search(r"\d+[%万千百次ms秒h小时个条名TBGBMBQPSTPS]", value, re.IGNORECASE))

    def _pick_safe_keywords_for_fallback(self, snapshot: Dict[str, Any], missing_keywords: List[str]) -> List[str]:
        raw_text = self._flatten_snapshot(snapshot).lower()
        safe = []
        for keyword in missing_keywords:
            lowered = str(keyword or "").strip().lower()
            if lowered and lowered in raw_text and keyword not in safe:
                safe.append(keyword)
        return safe[:6]

    def _keyword_in_text(self, keyword: str, text: str) -> bool:
        token = str(keyword or "").strip().lower()
        if not token:
            return False
        if re.search(r"[a-z0-9]", token):
            pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
            return re.search(pattern, text) is not None
        return token in text

    def _normalize_string_list(self, values: List[Any], *, max_items: int = 10) -> List[str]:
        items = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in items:
                items.append(text)
            if len(items) >= max_items:
                break
        return items

    def _dedupe_preserve_order(self, values: List[str]) -> List[str]:
        result = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def _collect_recent_gap_profile(self, *, user_id: str) -> Dict[str, Any]:
        interviews = []
        if hasattr(self.db_manager, "get_interviews"):
            interviews = self.db_manager.get_interviews(limit=8) or []

        theme_counter: Dict[str, int] = {}
        shortfall_counter: Dict[str, int] = {}
        round_counter: Dict[str, int] = {}

        for interview in interviews[:8]:
            interview_id = str((interview or {}).get("interview_id") or "").strip()
            if not interview_id or not hasattr(self.db_manager, "get_interview_evaluations"):
                continue
            raw_rows = self.db_manager.get_interview_evaluations(interview_id=interview_id) or []
            for row in raw_rows[:20]:
                status = str(row.get("status") or "").strip().lower()
                if status not in {"ok", "partial_ok"}:
                    continue

                round_type = str(row.get("round_type") or "").strip()
                if round_type:
                    round_counter[round_type] = round_counter.get(round_type, 0) + 1

                layer2 = self._safe_json_load(row.get("layer2_json"))
                summary = layer2.get("summary") or {}
                final_dims = layer2.get("final_dimension_scores") or layer2.get("dimension_scores") or {}

                for weakness in (summary.get("weaknesses") or []):
                    text = str(weakness or "").strip()
                    if text:
                        shortfall_counter[text] = shortfall_counter.get(text, 0) + 1
                        for theme in self._map_gap_text_to_themes(text, round_type=round_type):
                            theme_counter[theme] = theme_counter.get(theme, 0) + 1

                for action in (summary.get("next_actions") or []):
                    text = str(action or "").strip()
                    if text:
                        for theme in self._map_gap_text_to_themes(text, round_type=round_type):
                            theme_counter[theme] = theme_counter.get(theme, 0) + 1

                for dim_key, dim_payload in (final_dims or {}).items():
                    score = float((dim_payload or {}).get("score") or 0.0)
                    if score > 65:
                        continue
                    dim_text = " ".join(
                        [
                            str(dim_key or ""),
                            str((dim_payload or {}).get("label") or ""),
                            str((dim_payload or {}).get("reason") or ""),
                        ]
                    ).strip()
                    for theme in self._map_gap_text_to_themes(dim_text, round_type=round_type):
                        theme_counter[theme] = theme_counter.get(theme, 0) + 1

        focus_themes = [item[0] for item in sorted(theme_counter.items(), key=lambda pair: pair[1], reverse=True)[:4]]
        top_shortfalls = [item[0] for item in sorted(shortfall_counter.items(), key=lambda pair: pair[1], reverse=True)[:3]]
        focus_section = self._determine_focus_section(focus_themes)
        return {
            "focus_section": focus_section,
            "focus_themes": focus_themes,
            "top_shortfalls": top_shortfalls,
            "recent_rounds": [item[0] for item in sorted(round_counter.items(), key=lambda pair: pair[1], reverse=True)[:3]],
            "user_id": user_id,
        }

    def _safe_json_load(self, raw_value: Any) -> Dict[str, Any]:
        if not raw_value:
            return {}
        if isinstance(raw_value, dict):
            return raw_value
        try:
            return json.loads(raw_value)
        except Exception:
            return {}

    def _map_gap_text_to_themes(self, text: str, *, round_type: str = "") -> List[str]:
        normalized = str(text or "").strip().lower()
        if not normalized:
            return []

        themes = []
        if any(token in normalized for token in ("项目", "负责", "职责", "深挖", "追问", "ownership", "reflection")):
            themes.append("project_depth")
        if any(token in normalized for token in ("owner", "ownership", "主导", "个人贡献", "负责范围")):
            themes.append("ownership")
        if any(token in normalized for token in ("技术深度", "原理", "底层", "设计细节", "technical_depth", "authenticity")):
            themes.append("technical_depth")
        if any(token in normalized for token in ("结果", "收益", "量化", "指标", "impact", "%", "ms", "提升")):
            themes.append("result_expression")
        if any(token in normalized for token in ("表达", "清晰", "结构", "逻辑", "clarity", "communication")):
            themes.append("summary_clarity")
        if any(token in normalized for token in ("架构", "扩展", "权衡", "tradeoff", "scalability", "architecture")):
            themes.append("architecture_tradeoff")

        round_text = str(round_type or "").strip().lower()
        if "project" in round_text:
            themes.extend(["project_depth", "ownership"])
        if "system" in round_text or "design" in round_text:
            themes.append("architecture_tradeoff")
        return self._dedupe_preserve_order(themes)

    def _determine_focus_section(self, focus_themes: List[str]) -> str:
        if any(theme in {"project_depth", "ownership", "technical_depth", "architecture_tradeoff", "result_expression"} for theme in focus_themes):
            return "project_experiences"
        if any(theme in {"summary_clarity", "expression_clarity"} for theme in focus_themes):
            return "summary"
        return "skills"
