import json
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from neo4j import GraphDatabase
    neo4j_import_error = None
except Exception as exc:  # pragma: no cover - optional dependency
    GraphDatabase = None
    neo4j_import_error = str(exc)


CAPABILITY_LABELS = {
    'technical_accuracy': '技术准确性',
    'knowledge_depth': '知识深度',
    'completeness': '回答完整度',
    'logic': '逻辑严谨性',
    'job_match': '岗位匹配度',
    'authenticity': '项目真实性',
    'ownership': '项目 ownership',
    'technical_depth': '项目技术深度',
    'reflection': '复盘反思',
    'architecture_reasoning': '架构推理',
    'tradeoff_awareness': '权衡意识',
    'scalability': '扩展性设计',
    'clarity': '表达清晰度',
    'relevance': '回答相关性',
    'self_awareness': '自我认知',
    'communication': '沟通表现',
}

CAPABILITY_FIELD_MAP = {
    'technical_accuracy': 'technical_accuracy_score',
    'knowledge_depth': 'knowledge_depth_score',
    'completeness': 'completeness_score',
    'logic': 'logic_score',
    'job_match': 'job_match_score',
    'authenticity': 'authenticity_score',
    'ownership': 'ownership_score',
    'technical_depth': 'technical_depth_score',
    'reflection': 'reflection_score',
    'architecture_reasoning': 'architecture_reasoning_score',
    'tradeoff_awareness': 'tradeoff_awareness_score',
    'scalability': 'scalability_score',
    'clarity': 'clarity_score',
    'relevance': 'relevance_score',
    'self_awareness': 'self_awareness_score',
    'communication': 'communication_score',
}

GROUP_ORDER = {
    'user': 0,
    'position': 1,
    'resume': 1,
    'project': 1,
    'skill': 2,
    'capability': 3,
    'weakness': 4,
    'training': 4,
    'interview': 5,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _compact_text(value: Any, limit: int = 96) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _slug(value: Any) -> str:
    text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', str(value or '').strip().lower())
    text = re.sub(r'-+', '-', text).strip('-')
    return text or 'item'


def _normalize_user_id(value: Any) -> str:
    return str(value or 'default').strip().lower() or 'default'


def _parse_json(value: Any, default: Any) -> Any:
    if value in (None, ''):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _extract_numeric_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ('score', 'value', 'overall_score'):
            if value.get(key) is not None:
                return _safe_float(value.get(key), 0.0)
        return None
    return _safe_float(value, 0.0)


def _extract_capability_score(row: Dict[str, Any], capability_key: str, field_name: str) -> Optional[float]:
    direct_score = _extract_numeric_score(row.get(field_name))
    if direct_score is not None:
        return direct_score

    for source_key in ('fusion', 'layer2', 'text_layer', 'scoring_snapshot'):
        source = row.get(source_key)
        if not isinstance(source, dict):
            continue
        dimension_scores = (
            source.get('final_dimension_scores')
            or source.get('dimension_scores')
            or {}
        )
        if not isinstance(dimension_scores, dict):
            continue
        nested_score = _extract_numeric_score(dimension_scores.get(capability_key))
        if nested_score is not None:
            return nested_score

    return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or '').strip()
    if not text:
        return None
    normalized = text.replace('Z', '+00:00')
    for candidate in (normalized, normalized.replace(' ', 'T')):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            continue
    return None


def _format_time(value: Any) -> str:
    dt = _parse_datetime(value)
    if not dt:
        return str(value or '')
    return dt.strftime('%Y-%m-%d %H:%M')


def _decode_evaluation_rows(raw_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    decoded: List[Dict[str, Any]] = []
    for row in raw_rows or []:
        item = dict(row)
        for key in (
            'layer1_json',
            'layer2_json',
            'text_layer_json',
            'speech_layer_json',
            'video_layer_json',
            'fusion_json',
            'scoring_snapshot_json',
        ):
            item[key.replace('_json', '')] = _parse_json(item.get(key), {})
        decoded.append(item)
    return decoded


def _extract_projects(resume: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_projects = resume.get('projects') or []
    parsed_data = resume.get('parsed_data') or {}
    if not raw_projects and isinstance(parsed_data, dict):
        raw_projects = parsed_data.get('projects') or []

    projects: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_projects):
        if isinstance(item, str):
            projects.append({
                'name': item.strip() or f'项目 {index + 1}',
                'description': '',
                'tech_stack': [],
            })
            continue
        if not isinstance(item, dict):
            continue
        name = (
            item.get('name')
            or item.get('project_name')
            or item.get('title')
            or item.get('project')
            or f'项目 {index + 1}'
        )
        tech_stack = item.get('tech_stack') or item.get('technologies') or item.get('skills') or []
        if isinstance(tech_stack, str):
            tech_stack = re.split(r'[、,，/| ]+', tech_stack)
        projects.append({
            'name': str(name).strip() or f'项目 {index + 1}',
            'description': str(item.get('description') or item.get('summary') or '').strip(),
            'tech_stack': [str(tag).strip() for tag in tech_stack if str(tag).strip()],
        })
    return projects


def _extract_resume_skills(resume: Dict[str, Any], projects: List[Dict[str, Any]]) -> List[str]:
    raw_skills = resume.get('skills') or []
    parsed_data = resume.get('parsed_data') or {}
    if not raw_skills and isinstance(parsed_data, dict):
        raw_skills = parsed_data.get('skills') or []

    counter: Counter[str] = Counter()

    for item in raw_skills:
        if isinstance(item, str):
            for part in re.split(r'[、,，/| ]+', item):
                normalized = str(part).strip()
                if normalized:
                    counter[normalized] += 1
            continue
        if not isinstance(item, dict):
            continue
        values = item.get('items') or item.get('skills') or item.get('value') or item.get('name') or []
        if isinstance(values, str):
            values = re.split(r'[、,，/| ]+', values)
        if not isinstance(values, list):
            values = [values]
        for value in values:
            normalized = str(value).strip()
            if normalized:
                counter[normalized] += 1

    for project in projects:
        for tag in project.get('tech_stack') or []:
            normalized = str(tag).strip()
            if normalized:
                counter[normalized] += 2

    return [item for item, _count in counter.most_common(10)]


def _knowledge_status(score: float) -> str:
    score_value = _safe_float(score, 0.0)
    if score_value >= 78:
        return 'mastered'
    if score_value >= 60:
        return 'familiar'
    return 'weak'


class KnowledgeGraphService:
    def __init__(self, db_manager, logger=None):
        self.db = db_manager
        self.logger = logger
        self.neo4j_uri = str(os.environ.get('KG_NEO4J_URI', '') or '').strip()
        self.neo4j_user = str(os.environ.get('KG_NEO4J_USERNAME', '') or '').strip()
        self.neo4j_password = str(os.environ.get('KG_NEO4J_PASSWORD', '') or '').strip()
        self.neo4j_database = str(os.environ.get('KG_NEO4J_DATABASE', 'neo4j') or 'neo4j').strip() or 'neo4j'

    def health(self) -> Dict[str, Any]:
        neo4j_configured = bool(self.neo4j_uri and self.neo4j_user and self.neo4j_password)
        neo4j_available = neo4j_configured and GraphDatabase is not None
        return {
            'enabled': True,
            'mode': 'local_graph_with_optional_neo4j_sync',
            'neo4j': {
                'configured': neo4j_configured,
                'available': neo4j_available,
                'database': self.neo4j_database if neo4j_configured else '',
                'import_error': None if GraphDatabase is not None else neo4j_import_error,
            },
        }

    def _collect_interviews(self, user_id: str, limit: int = 18) -> List[Dict[str, Any]]:
        interviews = self.db.get_interviews(limit=max(limit * 2, 30), offset=0, risk_level=None) or []
        normalized_user_id = _normalize_user_id(user_id)
        filtered: List[Dict[str, Any]] = []
        user_specific_hits = 0

        for row in interviews:
            item = dict(row)
            row_user_id = _normalize_user_id(item.get('user_id'))
            if row_user_id != 'default':
                if row_user_id == normalized_user_id:
                    filtered.append(item)
                    user_specific_hits += 1
                continue
            filtered.append(item)

        if user_specific_hits == 0:
            filtered = [dict(row) for row in interviews]

        filtered.sort(
            key=lambda item: _parse_datetime(item.get('start_time')) or datetime.min,
            reverse=True,
        )
        return filtered[:limit]

    def _extract_capability_scores(
        self,
        evaluation_rows: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Dict[str, Any]], Counter[str], Counter[str]]:
        capability_agg: Dict[str, Dict[str, Any]] = {}
        position_counter: Counter[str] = Counter()
        round_counter: Counter[str] = Counter()

        for row in evaluation_rows:
            status = str(row.get('status') or '').strip().lower()
            if status and status not in {'ok', 'partial_ok'}:
                continue

            position = str(row.get('position') or '').strip()
            round_type = str(row.get('round_type') or '').strip()
            if position:
                position_counter[position] += 1
            if round_type:
                round_counter[round_type] += 1

            for capability_key, field_name in CAPABILITY_FIELD_MAP.items():
                score = _extract_capability_score(row, capability_key, field_name)
                if score is None:
                    continue

                bucket = capability_agg.setdefault(
                    capability_key,
                    {
                        'key': capability_key,
                        'label': CAPABILITY_LABELS.get(capability_key, capability_key),
                        'total_score': 0.0,
                        'count': 0,
                        'min_score': 100.0,
                        'max_score': 0.0,
                        'positions': Counter(),
                        'rounds': Counter(),
                    },
                )
                bucket['total_score'] += score
                bucket['count'] += 1
                bucket['min_score'] = min(float(bucket['min_score']), score)
                bucket['max_score'] = max(float(bucket['max_score']), score)
                if position:
                    bucket['positions'][position] += 1
                if round_type:
                    bucket['rounds'][round_type] += 1

        return capability_agg, position_counter, round_counter

    def build_user_graph(self, user_id: str = 'default') -> Dict[str, Any]:
        normalized_user_id = _normalize_user_id(user_id)
        resume = self.db.get_latest_resume(user_id=normalized_user_id) or self.db.get_latest_resume()
        resume = dict(resume or {})
        projects = _extract_projects(resume)
        resume_skills = _extract_resume_skills(resume, projects)
        interviews = self._collect_interviews(normalized_user_id)

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids = set()
        edge_ids = set()

        def add_node(node: Dict[str, Any]) -> None:
            node_id = str(node.get('id') or '').strip()
            if not node_id or node_id in node_ids:
                return
            node_ids.add(node_id)
            nodes.append(node)

        def add_edge(edge: Dict[str, Any]) -> None:
            edge_id = str(edge.get('id') or '').strip()
            if not edge_id or edge_id in edge_ids:
                return
            edge_ids.add(edge_id)
            edges.append(edge)

        user_label = str(resume.get('user_id') or normalized_user_id or 'default').strip() or 'default'
        user_name = (
            str(resume.get('name') or '').strip()
            or str(resume.get('file_name') or '').strip()
            or normalized_user_id
        )
        user_node_id = f"user:{user_label}"
        add_node({
            'id': user_node_id,
            'label': _compact_text(user_name, 24),
            'type': 'user',
            'group': 'user',
            'status': 'stable',
            'score': None,
            'description': '当前登录用户的能力图谱中心节点。',
            'meta': {
                'user_id': user_label,
                'resume_attached': bool(resume),
            },
        })

        resume_node_id = ''
        if resume:
            resume_node_id = f"resume:{_slug(resume.get('id') or resume.get('file_name') or normalized_user_id)}"
            add_node({
                'id': resume_node_id,
                'label': _compact_text(str(resume.get('file_name') or '当前简历').strip() or '当前简历', 20),
                'type': 'resume',
                'group': 'resume',
                'status': 'stable',
                'score': None,
                'description': '用户当前绑定的简历信息，是个性化提问和能力图谱的基础证据来源。',
                'meta': {
                    'updated_at': resume.get('updated_at') or resume.get('created_at'),
                    'project_count': len(projects),
                    'skill_count': len(resume_skills),
                },
            })
            add_edge({
                'id': f"edge:{user_node_id}:{resume_node_id}",
                'source': user_node_id,
                'target': resume_node_id,
                'label': '当前简历',
                'type': 'HAS_RESUME',
            })

        evaluation_rows: List[Dict[str, Any]] = []
        project_counter: Counter[str] = Counter()
        interview_evidence: List[Dict[str, Any]] = []
        skill_mentions: Counter[str] = Counter()
        skill_interview_hits: Dict[str, int] = Counter()
        skill_interview_scores: Dict[str, List[float]] = {}
        project_interview_scores: Dict[str, List[float]] = {}

        for interview in interviews:
            interview_id = str(interview.get('interview_id') or '').strip()
            if not interview_id:
                continue
            rows = _decode_evaluation_rows(self.db.get_interview_evaluations(interview_id=interview_id) or [])
            evaluation_rows.extend(rows)

            dominant_round = str(interview.get('dominant_round') or '').strip() or (
                str(rows[0].get('round_type') or '').strip() if rows else ''
            )
            overall_score = interview.get('overall_score')
            if overall_score is None and rows:
                scores = [_safe_float(row.get('overall_score')) for row in rows if row.get('overall_score') is not None]
                overall_score = round(sum(scores) / len(scores), 1) if scores else None

            interview_evidence.append({
                'interview_id': interview_id,
                'round_type': dominant_round or '综合面',
                'score': round(_safe_float(overall_score), 1) if overall_score is not None else None,
                'time': _format_time(interview.get('start_time')),
                'risk_level': interview.get('risk_level'),
            })

            dialogues = self.db.get_interview_dialogues(interview_id=interview_id) or []
            merged_text = ' '.join(
                str(item.get('answer') or '') for item in dialogues if str(item.get('answer') or '').strip()
            ).lower()
            for project in projects:
                project_name = str(project.get('name') or '').strip().lower()
                if project_name and project_name in merged_text:
                    project_counter[project.get('name') or ''] += 1
                    if overall_score is not None:
                        project_interview_scores.setdefault(project.get('name') or '', []).append(_safe_float(overall_score))
            for skill_name in resume_skills:
                normalized_skill = str(skill_name or '').strip().lower()
                if not normalized_skill:
                    continue
                hits = merged_text.count(normalized_skill)
                if hits <= 0:
                    continue
                skill_mentions[skill_name] += hits
                skill_interview_hits[skill_name] += 1
                if overall_score is not None:
                    skill_interview_scores.setdefault(skill_name, []).append(_safe_float(overall_score))

        capability_agg, position_counter, round_counter = self._extract_capability_scores(evaluation_rows)

        target_position = ''
        if position_counter:
            target_position = position_counter.most_common(1)[0][0]
        elif resume.get('parsed_data') and isinstance(resume.get('parsed_data'), dict):
            parsed_target = resume.get('parsed_data', {}).get('target_position') or resume.get('parsed_data', {}).get('position')
            target_position = str(parsed_target or '').strip()

        if target_position:
            position_node_id = f"position:{_slug(target_position)}"
            add_node({
                'id': position_node_id,
                'label': target_position,
                'type': 'position',
                'group': 'position',
                'status': 'stable',
                'score': None,
                'description': '当前主要求职目标岗位，决定能力图谱中的重点评价维度。',
                'meta': {
                    'evidence_count': position_counter.get(target_position, 0),
                },
            })
            add_edge({
                'id': f"edge:{user_node_id}:{position_node_id}",
                'source': user_node_id,
                'target': position_node_id,
                'label': '目标岗位',
                'type': 'TARGETS',
            })
        else:
            position_node_id = ''

        top_projects = projects[:5]
        for project in top_projects:
            project_name = str(project.get('name') or '').strip()
            if not project_name:
                continue
            project_node_id = f"project:{_slug(project_name)}"
            related_scores = project_interview_scores.get(project_name) or []
            project_score = round(sum(related_scores) / len(related_scores), 1) if related_scores else None
            add_node({
                'id': project_node_id,
                'label': _compact_text(project_name, 18),
                'type': 'project',
                'group': 'project',
                'status': 'stable' if project_counter.get(project_name, 0) > 0 else 'neutral',
                'score': project_score,
                'description': _compact_text(project.get('description') or '来自简历项目经历。', 96),
                'meta': {
                    'mentioned_in_interviews': project_counter.get(project_name, 0),
                    'tech_stack': project.get('tech_stack') or [],
                },
            })
            if resume_node_id:
                add_edge({
                    'id': f"edge:{resume_node_id}:{project_node_id}",
                    'source': resume_node_id,
                    'target': project_node_id,
                    'label': '项目经历',
                    'type': 'INCLUDES_PROJECT',
                })

        capability_items: List[Dict[str, Any]] = []
        for capability_key, bucket in capability_agg.items():
            count = max(1, _safe_int(bucket.get('count'), 1))
            avg_score = round(_safe_float(bucket.get('total_score')) / count, 1)
            capability_items.append({
                'key': capability_key,
                'label': bucket.get('label') or CAPABILITY_LABELS.get(capability_key, capability_key),
                'score': avg_score,
                'status': 'strength' if avg_score >= 75 else ('developing' if avg_score >= 60 else 'risk'),
                'count': count,
                'rounds': list((bucket.get('rounds') or Counter()).keys()),
                'positions': list((bucket.get('positions') or Counter()).keys()),
            })

        capability_items.sort(key=lambda item: float(item.get('score') or 0.0), reverse=True)
        capability_map = {item['key']: item for item in capability_items}
        capability_nodes: List[Dict[str, Any]] = []
        for item in capability_items:
            capability_node_id = f"capability:{item['key']}"
            capability_node = {
                'id': capability_node_id,
                'label': item['label'],
                'type': 'capability',
                'group': 'capability',
                'status': item['status'],
                'score': item['score'],
                'description': f"{item['label']} 是从近期结构化评估聚合出的能力维度，当前均值 {item['score']} 分，样本数 {item['count']}。",
                'meta': {
                    'capability_key': item['key'],
                    'sample_count': item['count'],
                    'rounds': item.get('rounds') or [],
                    'positions': item.get('positions') or [],
                },
            }
            capability_nodes.append(capability_node)
            add_node(capability_node)
            add_edge({
                'id': f"edge:{user_node_id}:{capability_node_id}",
                'source': user_node_id,
                'target': capability_node_id,
                'label': '能力维度',
                'type': 'HAS_CAPABILITY',
            })
            if target_position and position_node_id:
                add_edge({
                    'id': f"edge:{position_node_id}:{capability_node_id}",
                    'source': position_node_id,
                    'target': capability_node_id,
                    'label': '岗位要求',
                    'type': 'REQUIRES_CAPABILITY',
                })

        knowledge_points: List[Dict[str, Any]] = []
        for skill_name in resume_skills[:14]:
            skill_node_id = f"skill:{_slug(skill_name)}"
            related_project_count = sum(
                1
                for project in top_projects
                if skill_name in (project.get('tech_stack') or [])
            )
            interview_hit_count = _safe_int(skill_interview_hits.get(skill_name), 0)
            mentions = _safe_int(skill_mentions.get(skill_name), 0)
            interview_scores = skill_interview_scores.get(skill_name) or []
            avg_related_score = round(sum(interview_scores) / len(interview_scores), 1) if interview_scores else None

            if avg_related_score is not None:
                mastery_score = (
                    avg_related_score * 0.72
                    + min(100.0, 42.0 + related_project_count * 14.0) * 0.18
                    + min(100.0, 38.0 + mentions * 7.0) * 0.10
                )
            elif related_project_count > 0:
                mastery_score = 46.0 + min(22.0, related_project_count * 8.0) + min(12.0, mentions * 2.0)
            else:
                mastery_score = 36.0 + min(10.0, mentions * 2.0)

            mastery_score = round(max(15.0, min(96.0, mastery_score)), 1)
            mastery_status = _knowledge_status(mastery_score)
            status_text = {
                'mastered': '已形成较稳定掌握',
                'familiar': '具备基础掌握，但还需要更多证据',
                'weak': '在近期面试里缺少足够展开或证据支撑',
            }[mastery_status]

            related_projects = [
                str(project.get('name') or '').strip()
                for project in top_projects
                if skill_name in (project.get('tech_stack') or [])
            ]

            knowledge_points.append({
                'id': skill_node_id,
                'label': skill_name,
                'type': 'knowledge',
                'group': 'skill',
                'status': mastery_status,
                'score': mastery_score,
                'description': f"{skill_name} 当前为“{status_text}”。评分会综合简历项目关联、近期面试是否主动提及，以及相关回答的整体表现。",
                'meta': {
                    'mastery_level': mastery_status,
                    'evidence_count': interview_hit_count,
                    'mention_count': mentions,
                    'related_projects': related_projects,
                    'avg_related_interview_score': avg_related_score if avg_related_score is not None else '暂无',
                },
            })

            add_node({
                **knowledge_points[-1],
            })
            for related_project_name in related_projects:
                add_edge({
                    'id': f"edge:project:{_slug(related_project_name)}:{skill_node_id}",
                    'source': f"project:{_slug(related_project_name)}",
                    'target': skill_node_id,
                    'label': '涉及知识点',
                    'type': 'USES_SKILL',
                })

        risk_capabilities = sorted(
            [item for item in capability_items if item['status'] == 'risk'],
            key=lambda item: float(item.get('score') or 0.0),
        )[:3]
        weakness_nodes: List[Dict[str, Any]] = []
        for item in risk_capabilities:
            weakness_node_id = f"weakness:{item['key']}"
            weakness_node = {
                'id': weakness_node_id,
                'label': item['label'],
                'type': 'weakness',
                'group': 'weakness',
                'status': 'risk',
                'score': item['score'],
                'description': f"这是从最近结构化评估里反复出现的弱项维度，当前均值 {item['score']} 分，适合作为知识点补练时的优先方向。",
                'meta': {
                    'capability_key': item['key'],
                    'sample_count': item['count'],
                },
            }
            weakness_nodes.append(weakness_node)
            add_node(weakness_node)
            add_edge({
                'id': f"edge:{user_node_id}:{weakness_node_id}",
                'source': user_node_id,
                'target': weakness_node_id,
                'label': '当前短板',
                'type': 'HAS_WEAKNESS',
            })
            capability_node_id = f"capability:{item['key']}"
            if capability_node_id in node_ids:
                add_edge({
                    'id': f"edge:{capability_node_id}:{weakness_node_id}",
                    'source': capability_node_id,
                    'target': weakness_node_id,
                    'label': '风险聚合',
                    'type': 'HAS_RISK',
                })

        today = datetime.now().date()
        monday = today.replace(day=today.day)  # placeholder to keep mypy calm
        monday = today.fromordinal(today.toordinal() - today.weekday())
        bundle = self.db.get_training_plan_bundle(user_id=normalized_user_id, week_start_date=monday.isoformat())
        tasks = list((bundle or {}).get('tasks') or [])
        active_tasks = [
            item for item in tasks
            if str(item.get('status') or '').strip().lower() not in {'completed', 'rolled_over'}
        ][:4]
        for task in active_tasks:
            task_title = str(task.get('title') or task.get('focus_label') or '训练任务').strip() or '训练任务'
            task_node_id = f"training:{_slug(task.get('task_id') or task_title)}"
            add_node({
                'id': task_node_id,
                'label': _compact_text(task_title, 18),
                'type': 'training',
                'group': 'training',
                'status': 'developing',
                'score': None,
                'description': _compact_text(task.get('description') or task.get('goal') or '来自当前周训练计划。', 96),
                'meta': {
                    'status': task.get('status'),
                    'deadline': task.get('due_date'),
                },
            })
            add_edge({
                'id': f"edge:{user_node_id}:{task_node_id}",
                'source': user_node_id,
                'target': task_node_id,
                'label': '当前训练',
                'type': 'TRAINS',
            })

            task_text = f"{task_title} {task.get('description') or ''} {task.get('focus_label') or ''}".lower()
            for item in risk_capabilities:
                capability_label = str(item.get('label') or '').lower()
                if capability_label and capability_label in task_text:
                    add_edge({
                        'id': f"edge:{task_node_id}:weakness:{item['key']}",
                        'source': task_node_id,
                        'target': f"weakness:{item['key']}",
                        'label': '针对补练',
                        'type': 'IMPROVES',
                    })

        strengths = sorted(
            [item for item in knowledge_points if item['status'] == 'mastered']
            + [item for item in capability_nodes if item['status'] == 'strength'],
            key=lambda item: float(item.get('score') or 0.0),
            reverse=True,
        )[:5]
        risk_nodes = sorted(
            [item for item in knowledge_points if item['status'] == 'weak'] + weakness_nodes,
            key=lambda item: float(item.get('score') or 0.0),
        )[:5]
        warnings = risk_capabilities
        dominant_rounds = [{'round': key, 'count': count} for key, count in round_counter.most_common(4)]
        scored_interview_evidence = [
            item
            for item in interview_evidence
            if isinstance(item.get('score'), (int, float)) and 0 <= float(item.get('score') or 0) <= 100
        ]

        if not nodes:
            add_node({
                'id': user_node_id,
                'label': '当前用户',
                'type': 'user',
                'group': 'user',
                'status': 'neutral',
                'score': None,
                'description': '暂无可展示的能力画像数据。',
                'meta': {},
            })

        summary = {
            'user_name': user_name,
            'user_id': user_label,
            'target_position': target_position or '待补充岗位目标',
            'resume_attached': bool(resume),
            'project_count': len(projects),
            'resume_skill_count': len(resume_skills),
            'interviews_analyzed': len(interviews),
            'evaluations_analyzed': len(evaluation_rows),
            'capability_count': len(knowledge_points),
            'graph_node_count': len(nodes),
            'strength_count': len(strengths),
            'risk_count': len(risk_nodes),
            'active_task_count': len(active_tasks),
            'last_interview_at': scored_interview_evidence[0]['time'] if scored_interview_evidence else '',
            'dominant_rounds': dominant_rounds,
            'top_strengths': strengths,
            'top_risks': risk_nodes,
            'top_capability_risks': warnings,
            'recent_interviews': scored_interview_evidence[:6],
        }

        nodes.sort(key=lambda item: (GROUP_ORDER.get(str(item.get('group') or ''), 99), str(item.get('label') or '')))
        edges.sort(key=lambda item: str(item.get('id') or ''))

        return {
            'summary': summary,
            'nodes': nodes,
            'edges': edges,
            'meta': self.health(),
        }

    def _get_driver(self):
        if GraphDatabase is None:
            raise RuntimeError(neo4j_import_error or 'neo4j driver is not installed')
        if not (self.neo4j_uri and self.neo4j_user and self.neo4j_password):
            raise RuntimeError('Neo4j connection is not configured. Please set KG_NEO4J_URI/KG_NEO4J_USERNAME/KG_NEO4J_PASSWORD.')
        return GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))

    def sync_user_graph(self, user_id: str = 'default') -> Dict[str, Any]:
        graph_payload = self.build_user_graph(user_id=user_id)
        driver = self._get_driver()
        try:
            with driver.session(database=self.neo4j_database) as session:
                for node in graph_payload['nodes']:
                    props = {
                        'id': node.get('id'),
                        'label': node.get('label'),
                        'type': node.get('type'),
                        'group': node.get('group'),
                        'status': node.get('status'),
                        'score': node.get('score'),
                        'description': node.get('description'),
                        'meta_json': json.dumps(node.get('meta') or {}, ensure_ascii=False),
                        'user_id': graph_payload['summary']['user_id'],
                    }
                    session.run(
                        '''
                        MERGE (n:CapabilityNode {id: $id})
                        SET n += $props
                        ''',
                        {'id': props['id'], 'props': props},
                    )

                for edge in graph_payload['edges']:
                    session.run(
                        '''
                        MATCH (a:CapabilityNode {id: $source}), (b:CapabilityNode {id: $target})
                        MERGE (a)-[r:CAPABILITY_EDGE {id: $id}]->(b)
                        SET r.type = $type,
                            r.label = $label,
                            r.user_id = $user_id
                        ''',
                        {
                            'id': edge.get('id'),
                            'source': edge.get('source'),
                            'target': edge.get('target'),
                            'type': edge.get('type'),
                            'label': edge.get('label'),
                            'user_id': graph_payload['summary']['user_id'],
                        },
                    )
        finally:
            driver.close()

        return {
            'synced': True,
            'node_count': len(graph_payload['nodes']),
            'edge_count': len(graph_payload['edges']),
            'database': self.neo4j_database,
        }
