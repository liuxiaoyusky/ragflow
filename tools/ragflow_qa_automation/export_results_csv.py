#!/usr/bin/env python3
"""
合并飞书与 RAGFlow 的测评结果，输出为 CSV，便于后续报告或核对。

默认输入（使用评估后的最新数据）：
    --feishu  test/pdf_chat_test/test_output/feishu_evaluated.json
    --ragflow test/pdf_chat_test/test_output/ragflow_cn_retested.json
输出：
    --output  test/pdf_chat_test/test_output/full_comparison.csv
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


COLUMNS = [
    "index",
    "question",
    # 飞书数据
    "feishu_answer",
    "feishu_response_time_s",
    "feishu_accuracy",
    "feishu_relevance",
    "feishu_completeness",
    "feishu_overall_score",
    # RAGFlow数据
    "ragflow_answer",
    "ragflow_response_time_s",
    "ragflow_success",
    "ragflow_accuracy",
    "ragflow_relevance",
    "ragflow_completeness",
    "ragflow_citation_quality",
    "ragflow_overall_score",
    # 对比结果
    "winner",
    "score_diff",
]


def load_feishu(path: Path) -> Dict[int, Dict[str, Any]]:
    """读取飞书评估结果，返回按 index 索引的映射。"""
    if not path.exists():
        print(f"[warn] Feishu file not found: {path}")
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = {}
    for item in data.get("results", []):
        idx = item.get("index")
        if idx is None:
            continue

        evaluation = item.get("evaluation", {})
        # 使用清洗后的答案（如果有）
        answer = evaluation.get("cleaned_answer") or item.get("answer", "")
        # 时长从毫秒转秒
        duration_ms = item.get("duration", 0)
        response_time_s = duration_ms / 1000 if duration_ms else 0

        results[idx] = {
            "index": idx,
            "question": item.get("question", ""),
            "answer": answer,
            "response_time_s": round(response_time_s, 2),
            "accuracy": evaluation.get("accuracy"),
            "relevance": evaluation.get("relevance"),
            "completeness": evaluation.get("completeness"),
            "overall_score": evaluation.get("overall_score"),
        }
    return results


def load_ragflow(path: Path) -> Dict[int, Dict[str, Any]]:
    """读取 RAGFlow 评估结果，返回按 index 索引的映射。优先使用重测后的数据。"""
    if not path.exists():
        print(f"[warn] RAGFlow file not found: {path}")
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = {}
    for item in data.get("results", []):
        idx = item.get("index")
        if idx is None:
            continue

        evaluation = item.get("evaluation", {})
        
        # 优先使用重测后的答案和响应时间
        answer = item.get("retest_answer") or item.get("answer", "")
        response_time = item.get("retest_response_time") or item.get("response_time", 0)
        success = item.get("retest_success") if item.get("retest_success") is not None else item.get("success")

        results[idx] = {
            "index": idx,
            "question": item.get("question", ""),
            "answer": answer,
            "response_time_s": round(response_time, 2) if response_time else 0,
            "success": success,
            "accuracy": evaluation.get("accuracy"),
            "relevance": evaluation.get("relevance"),
            "completeness": evaluation.get("completeness"),
            "citation_quality": evaluation.get("citation_quality"),
            "overall_score": evaluation.get("overall_score"),
        }
    return results


def determine_winner(rag_score: float, fei_score: float) -> Tuple[str, float]:
    """确定胜者和分差。"""
    if rag_score is None:
        rag_score = 0
    if fei_score is None:
        fei_score = 0
    
    diff = round(rag_score - fei_score, 2)
    
    if diff > 0.5:
        return "RAGFlow", diff
    elif diff < -0.5:
        return "Feishu", diff
    else:
        return "Tie", diff


def truncate_answer(answer: str, max_length: int = 500) -> str:
    """截断答案以便CSV可读。"""
    if not answer:
        return ""
    answer = answer.replace("\n", " ").replace("\r", " ")
    if len(answer) > max_length:
        return answer[:max_length] + "..."
    return answer


def merge_and_write(
    feishu: Dict[int, Dict[str, Any]],
    ragflow: Dict[int, Dict[str, Any]],
    output: Path,
    full_answer: bool = False
):
    """合并结果并写出 CSV。"""
    output.parent.mkdir(parents=True, exist_ok=True)

    # 合并所有索引
    all_indices = sorted(set(feishu.keys()) | set(ragflow.keys()))
    
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        stats = {"ragflow_wins": 0, "feishu_wins": 0, "ties": 0}

        for idx in all_indices:
            f_item = feishu.get(idx, {})
            r_item = ragflow.get(idx, {})

            rag_score = r_item.get("overall_score", 0) or 0
            fei_score = f_item.get("overall_score", 0) or 0
            winner, score_diff = determine_winner(rag_score, fei_score)

            if winner == "RAGFlow":
                stats["ragflow_wins"] += 1
            elif winner == "Feishu":
                stats["feishu_wins"] += 1
            else:
                stats["ties"] += 1

            # 处理答案
            max_len = 10000 if full_answer else 500
            fei_answer = truncate_answer(f_item.get("answer", ""), max_len)
            rag_answer = truncate_answer(r_item.get("answer", ""), max_len)

            row = {
                "index": idx,
                "question": f_item.get("question") or r_item.get("question", ""),
                # 飞书数据
                "feishu_answer": fei_answer,
                "feishu_response_time_s": f_item.get("response_time_s"),
                "feishu_accuracy": f_item.get("accuracy"),
                "feishu_relevance": f_item.get("relevance"),
                "feishu_completeness": f_item.get("completeness"),
                "feishu_overall_score": f_item.get("overall_score"),
                # RAGFlow数据
                "ragflow_answer": rag_answer,
                "ragflow_response_time_s": r_item.get("response_time_s"),
                "ragflow_success": r_item.get("success"),
                "ragflow_accuracy": r_item.get("accuracy"),
                "ragflow_relevance": r_item.get("relevance"),
                "ragflow_completeness": r_item.get("completeness"),
                "ragflow_citation_quality": r_item.get("citation_quality"),
                "ragflow_overall_score": r_item.get("overall_score"),
                # 对比结果
                "winner": winner,
                "score_diff": score_diff,
            }
            writer.writerow(row)

    print(f"\n[ok] CSV written to: {output}")
    print(f"     Total questions: {len(all_indices)}")
    print(f"     Feishu: {len(feishu)} | RAGFlow: {len(ragflow)}")
    print(f"\n📊 Summary:")
    print(f"     RAGFlow wins: {stats['ragflow_wins']}")
    print(f"     Feishu wins:  {stats['feishu_wins']}")
    print(f"     Ties:         {stats['ties']}")


def main():
    parser = argparse.ArgumentParser(description="导出合并后的飞书/RAGFlow测试结果 CSV")
    parser.add_argument(
        "--feishu",
        type=str,
        default="test/pdf_chat_test/test_output/feishu_evaluated.json",
        help="飞书评估结果文件"
    )
    parser.add_argument(
        "--ragflow",
        type=str,
        default="test/pdf_chat_test/test_output/ragflow_cn_retested.json",
        help="RAGFlow评估/重测结果文件"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test/pdf_chat_test/test_output/full_comparison.csv",
        help="输出CSV路径"
    )
    parser.add_argument(
        "--full-answer",
        action="store_true",
        help="保留完整答案（不截断）"
    )
    args = parser.parse_args()

    # 找到项目根目录
    base = Path(__file__).parent.parent.parent  # ragflow_qa_automation -> tools -> ragflow

    feishu_path = Path(args.feishu)
    if not feishu_path.is_absolute():
        feishu_path = base / feishu_path

    ragflow_path = Path(args.ragflow)
    if not ragflow_path.is_absolute():
        ragflow_path = base / ragflow_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = base / output_path

    print(f"📥 Loading Feishu data from: {feishu_path}")
    print(f"📥 Loading RAGFlow data from: {ragflow_path}")

    feishu = load_feishu(feishu_path)
    ragflow = load_ragflow(ragflow_path)
    merge_and_write(feishu, ragflow, output_path, args.full_answer)


if __name__ == "__main__":
    main()
