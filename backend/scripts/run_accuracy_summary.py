from pathlib import Path
import sys

root = Path('d:/mianshi/tianshuzhimian-main')
sys.path.insert(0, str(root / 'backend'))
sys.path.insert(0, str(root))

from scripts import test_interview_knowledge_rag as tir

report = tir.run_test(
    source_path='backend/interview_knowledge',
    top_k=5,
    limit=30,
    position_filter=None,
    rebuild_first=False,
    modes=['exact'],
)

print('top1_hit_rate:', report['summary']['question_view']['exact']['top1_hit_rate'])
print('topk_hit_rate:', report['summary']['question_view']['exact']['topk_hit_rate'])
print('avg_top1_similarity:', report['summary']['question_view']['exact']['avg_top1_similarity'])
print('rubric_top1_hit_rate:', report['summary']['rubric_view']['top1_hit_rate'])
print('rubric_topk_hit_rate:', report['summary']['rubric_view']['topk_hit_rate'])
print('rubric_avg_top1_similarity:', report['summary']['rubric_view']['avg_top1_similarity'])
