#!/usr/bin/env python
"""
RAG 综合测试脚本 - 全面评估检索质量
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.service import rag_service


# 综合测试用例 - 包含不同难度和类型的查询
TEST_CASES = [
    # ========== 基础概念类 ==========
    {
        "query": "Attention 为什么要除以 dk",
        "position": "大模型算法工程师",
        "expected_id": "llm_001",
        "expected_keywords": ["attention", "dk", "softmax"],
        "category": "基础概念",
    },
    {
        "query": "Transformer 注意力机制公式",
        "position": "大模型算法工程师",
        "expected_id": "llm_001",
        "expected_keywords": ["attention", "transformer"],
        "category": "同义改写",
    },
    
    # ========== RLHF/对齐类 ==========
    {
        "query": "PPO 和 DPO 有什么区别",
        "position": "大模型算法工程师",
        "expected_id": "llm_002",
        "expected_keywords": ["ppo", "dpo", "rlhf"],
        "category": "对比类",
    },
    {
        "query": "DPO 不需要奖励模型吗",
        "position": "大模型算法工程师",
        "expected_id": "llm_002",
        "expected_keywords": ["dpo", "奖励模型"],
        "category": "疑问句式",
    },
    {
        "query": "PPO 的 ratio 和 advantage 怎么理解",
        "position": "大模型算法工程师",
        "expected_id": "llm_003",
        "expected_keywords": ["ppo", "ratio", "advantage"],
        "category": "具体概念",
    },
    {
        "query": "强化学习 PPO 损失函数",
        "position": "大模型算法工程师",
        "expected_id": "llm_003",
        "expected_keywords": ["ppo", "损失函数"],
        "category": "关键词组合",
    },
    
    # ========== 优化器类 ==========
    {
        "query": "Adam 优化器原理",
        "position": "大模型算法工程师",
        "expected_id": "llm_004",
        "expected_keywords": ["adam", "优化器", "梯度"],
        "category": "基础概念",
    },
    {
        "query": "Adam 和 SGD 的区别是什么",
        "position": "大模型算法工程师",
        "expected_id": "llm_004",
        "expected_keywords": ["adam", "sgd"],
        "category": "对比类",
    },
    
    # ========== Attention 变体类 ==========
    {
        "query": "MHA MQA GQA 区别",
        "position": "大模型算法工程师",
        "expected_id": "llm_005",
        "expected_keywords": ["mha", "mqa", "gqa"],
        "category": "缩写查询",
    },
    {
        "query": "多头注意力机制优化",
        "position": "大模型算法工程师",
        "expected_id": "llm_005",
        "expected_keywords": ["注意力", "mha"],
        "category": "中文描述",
    },
    
    # ========== 损失函数类 ==========
    {
        "query": "交叉熵损失函数怎么写",
        "position": "大模型算法工程师",
        "expected_id": "llm_006",
        "expected_keywords": ["交叉熵", "损失函数"],
        "category": "基础概念",
    },
    {
        "query": "手写 CrossEntropy Loss",
        "position": "大模型算法工程师",
        "expected_id": "llm_006",
        "expected_keywords": ["crossentropy", "损失函数"],
        "category": "中英混合",
    },
    
    # ========== 位置编码类 ==========
    {
        "query": "RoPE 的原理是什么",
        "position": "大模型算法工程师",
        "expected_id": "llm_007",
        "expected_keywords": ["rope", "位置编码"],
        "category": "基础概念",
    },
    {
        "query": "旋转位置编码外推性",
        "position": "大模型算法工程师",
        "expected_id": "llm_007",
        "expected_keywords": ["rope", "外推"],
        "category": "特性查询",
    },
    {
        "query": "大模型位置编码有哪些",
        "position": "大模型算法工程师",
        "expected_id": "base_001",
        "expected_keywords": ["位置编码", "rope", "alibi"],
        "category": "分类查询",
    },
    
    # ========== 强化学习细节类 ==========
    {
        "query": "GAE 优势函数估计",
        "position": "大模型算法工程师",
        "expected_id": "llm_008",
        "expected_keywords": ["gae", "优势函数"],
        "category": "专业术语",
    },
    {
        "query": "PPO 的 returns 怎么计算",
        "position": "大模型算法工程师",
        "expected_id": "llm_009",
        "expected_keywords": ["ppo", "returns"],
        "category": "具体概念",
    },
    
    # ========== 视觉/多模态类 ==========
    {
        "query": "ViT 位置编码方式",
        "position": "多模态算法工程师",
        "expected_id": "llm_010",
        "expected_keywords": ["vit", "位置编码"],
        "category": "视觉类",
    },
    
    # ========== 算法题类 ==========
    {
        "query": "最长有效括号",
        "position": "算法工程师",
        "expected_id": "code_001",
        "expected_keywords": ["括号", "栈"],
        "category": "算法题",
    },
    {
        "query": "搜索旋转排序数组",
        "position": "算法工程师",
        "expected_id": "code_002",
        "expected_keywords": ["旋转数组", "二分"],
        "category": "算法题",
    },
    
    # ========== 项目/开放类 ==========
    {
        "query": "介绍大模型项目经验",
        "position": "大模型算法工程师",
        "expected_id": "proj_001",
        "expected_keywords": ["项目", "大模型"],
        "category": "开放问题",
    },
]


def match_expected(item: Dict, expected_keywords: List[str]) -> Dict[str, List[str]]:
    """检查期望关键词是否命中"""
    metadata = item.get("metadata", {}) or {}
    haystack = " ".join([
        item.get("question", "") or "",
        metadata.get("answer_summary", "") or "",
        metadata.get("category", "") or "",
        metadata.get("subcategory", "") or "",
        " ".join(str(k) for k in metadata.get("keywords", []) or []),
        " ".join(str(t) for t in metadata.get("tags", []) or []),
    ]).lower()
    
    hits = [kw for kw in expected_keywords if kw.lower() in haystack]
    return {"hits": hits, "misses": [kw for kw in expected_keywords if kw not in hits]}


def run_comprehensive_test(top_k: int = 5) -> Dict:
    """运行综合测试"""
    
    if not rag_service.ensure_ready():
        return {"error": "RAG not ready", "cases": []}
    
    results = []
    category_stats = {}
    
    for case in TEST_CASES:
        # 执行检索
        retrieved = rag_service.retrieve(
            query=case["query"],
            position=case["position"],
            top_k=top_k
        )
        
        # 分析结果
        top1_hit = False
        topk_hit = False
        expected_rank = None
        
        for rank, item in enumerate(retrieved, start=1):
            # 新架构使用双视图索引，ID格式为 "llm_001#question" 或 "llm_001#rubric"
            item_id = item.get("id", "")
            base_id = item_id.split("#")[0] if "#" in item_id else item_id
            if base_id == case["expected_id"]:
                if rank == 1:
                    top1_hit = True
                topk_hit = True
                expected_rank = rank
                break
        
        # 关键词匹配分析
        if retrieved:
            keyword_match = match_expected(retrieved[0], case["expected_keywords"])
        else:
            keyword_match = {"hits": [], "misses": case["expected_keywords"]}
        
        result = {
            "query": case["query"],
            "category": case["category"],
            "expected_id": case["expected_id"],
            "top1_hit": top1_hit,
            "topk_hit": topk_hit,
            "expected_rank": expected_rank,
            "keyword_hits": keyword_match["hits"],
            "keyword_misses": keyword_match["misses"],
            "results_count": len(retrieved),
        }
        
        # 添加 Top-3 结果详情
        if retrieved:
            result["top3_results"] = [
                {
                    "rank": i+1,
                    "id": r.get("id"),
                    "base_id": r.get("id", "").split("#")[0] if "#" in r.get("id", "") else r.get("id", ""),
                    "question": r.get("question", "")[:60] + "..." if len(r.get("question", "")) > 60 else r.get("question", ""),
                    "similarity": round(float(r.get("similarity", 0)), 4),
                    "lexical_score": round(float(r.get("lexical_score", 0)), 4),
                    "rerank_score": round(float(r.get("rerank_score", 0)), 4),
                }
                for i, r in enumerate(retrieved[:3])
            ]
        
        results.append(result)
        
        # 分类统计
        cat = case["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "top1_hits": 0, "topk_hits": 0}
        category_stats[cat]["total"] += 1
        if top1_hit:
            category_stats[cat]["top1_hits"] += 1
        if topk_hit:
            category_stats[cat]["topk_hits"] += 1
    
    # 计算总体统计
    total = len(TEST_CASES)
    top1_hits = sum(1 for r in results if r["top1_hit"])
    topk_hits = sum(1 for r in results if r["topk_hit"])
    
    return {
        "summary": {
            "total_cases": total,
            "top1_hit_rate": round(top1_hits / total, 4),
            "topk_hit_rate": round(topk_hits / total, 4),
            "top1_hits": top1_hits,
            "topk_hits": topk_hits,
        },
        "category_stats": category_stats,
        "cases": results,
        "rag_status": rag_service.status(),
    }


def print_report(report: Dict):
    """打印测试报告"""
    print("=" * 80)
    print("RAG 综合测试报告")
    print("=" * 80)
    
    if "error" in report:
        print(f"\n错误: {report['error']}")
        return
    
    # 总体统计
    summary = report["summary"]
    print(f"\n【总体统计】")
    print(f"  测试用例总数: {summary['total_cases']}")
    print(f"  Top-1 命中率: {summary['top1_hit_rate']*100:.1f}% ({summary['top1_hits']}/{summary['total_cases']})")
    print(f"  Top-K 命中率: {summary['topk_hit_rate']*100:.1f}% ({summary['topk_hits']}/{summary['total_cases']})")
    
    # 分类统计
    print(f"\n【分类统计】")
    for cat, stats in sorted(report["category_stats"].items()):
        top1_rate = stats["top1_hits"] / stats["total"] * 100
        topk_rate = stats["topk_hits"] / stats["total"] * 100
        print(f"  {cat:12s}: Top-1 {top1_rate:5.1f}% | Top-K {topk_rate:5.1f}% ({stats['total']} 例)")
    
    # 失败案例分析
    failures = [c for c in report["cases"] if not c["topk_hit"]]
    if failures:
        print(f"\n【失败案例】({len(failures)} 个)")
        for case in failures:
            print(f"\n  查询: {case['query']}")
            print(f"  期望: {case['expected_id']}")
            print(f"  分类: {case['category']}")
            if case.get("top3_results"):
                print(f"  实际返回:")
                for r in case["top3_results"]:
                    print(f"    [{r['rank']}] {r['id']}: {r['question'][:50]}...")
    
    # 详细结果
    print(f"\n【详细结果】")
    for case in report["cases"]:
        status = "✓" if case["top1_hit"] else ("○" if case["topk_hit"] else "✗")
        rank_info = f"(Rank {case['expected_rank']})" if case["expected_rank"] else "(未命中)"
        print(f"\n  {status} [{case['category']:10s}] {case['query'][:40]:40s} -> {case['expected_id']} {rank_info}")
        if case.get("top3_results"):
            for r in case["top3_results"][:2]:
                match_mark = " <--" if r["base_id"] == case["expected_id"] else ""
                print(f"      [{r['rank']}] {r['id']:20s} sim={r['similarity']:.3f} lex={r['lexical_score']:.3f} rerank={r['rerank_score']:.3f}{match_mark}")
    
    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="RAG 综合测试")
    parser.add_argument("--top-k", type=int, default=5, help="检索结果数量")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    
    report = run_comprehensive_test(top_k=args.top_k)
    
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    
    # 返回退出码
    if "error" in report:
        return 1
    top1_rate = report["summary"]["top1_hit_rate"]
    return 0 if top1_rate >= 0.7 else 1  # Top-1 命中率低于 70% 返回错误


if __name__ == "__main__":
    raise SystemExit(main())
