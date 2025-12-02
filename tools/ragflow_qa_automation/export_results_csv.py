#!/usr/bin/env python3
"""
合并飞书与 RAGFlow 的测评结果，输出为 CSV，便于后续报告或核对。

默认输入：
    --feishu  feishu-test-results.json      (飞书 Knowledge AI 测试结果或评估结果)
    --ragflow test_output/test_results.json (RAGFlow 测试结果，run_test.py 生成)
输出：
    --output  test_output/combined_results.csv
"""
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple


COLUMNS = [
    "index",
    "question",
    "feishu_answer",
    "feishu_status",
    "feishu_duration_ms",
    "feishu_start",
    "feishu_end",
    "feishu_overall_score",
    "ragflow_answer",
    "ragflow_success",
    "ragflow_response_time_s",
    "ragflow_accuracy",
    "ragflow_relevance",
    "ragflow_completeness",
    "ragflow_citation_quality",
    "ragflow_overall_score",
    "ragflow_error",
]


def _clean_feishu_answer(answer: str, fallback_status: str) -> Tuple[str, str]:
    """从飞书答案中尽量拆出 status，并清理掉夹带的状态片段。"""
    status = fallback_status
    if not isinstance(answer, str):
        return "", status

    match = re.search(r'"?status"?\s*:\s*"([^"]+)"', answer)
    if match:
        status = match.group(1)
        answer = re.sub(r',?\s*"?status"?\s*:\s*"[^"]+"', "", answer)

    # 去掉可能的尾部逗号或多余引号
    answer = answer.strip().rstrip(",").strip('"').strip()
    return answer, status


def load_feishu(path: Path) -> Dict[str, Dict[str, Any]]:
    """读取飞书结果，返回按问题文本归一化后的映射。"""
    if not path.exists():
        print(f"[warn] Feishu file not found: {path}")
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = {}
    for item in data.get("results", []):
        question = (item.get("question") or "").strip()
        key = question

        status = item.get("status", "unknown")
        answer_raw = item.get("answer", "")
        answer_clean, status = _clean_feishu_answer(answer_raw, status)

        evaluation = item.get("evaluation", {})  # evaluate_feishu.py 生成

        results[key] = {
            "index": item.get("index"),
            "question": question,
            "answer": answer_clean,
            "status": status,
            "duration_ms": item.get("duration"),
            "start": item.get("startTime"),
            "end": item.get("endTime"),
            "overall_score": evaluation.get("overall_score"),
        }
    return results


def load_ragflow(path: Path) -> Dict[str, Dict[str, Any]]:
    """读取 RAGFlow 结果，返回按问题文本归一化后的映射。"""
    if not path.exists():
        print(f"[warn] RAGFlow file not found: {path}")
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = {}
    for item in data.get("results", []):
        question = (item.get("question") or "").strip()
        key = question
        evaluation = item.get("evaluation", {})

        results[key] = {
            "index": item.get("question_id"),
            "question": question,
            "answer": item.get("answer", ""),
            "success": item.get("success"),
            "response_time_s": item.get("response_time"),
            "accuracy": evaluation.get("accuracy"),
            "relevance": evaluation.get("relevance"),
            "completeness": evaluation.get("completeness"),
            "citation_quality": evaluation.get("citation_quality"),
            "overall_score": evaluation.get("overall_score"),
            "error": item.get("error"),
        }
    return results


def merge_and_write(feishu: Dict[str, Dict[str, Any]], ragflow: Dict[str, Dict[str, Any]], output: Path):
    """合并结果并写出 CSV。"""
    output.parent.mkdir(parents=True, exist_ok=True)

    all_questions = sorted(set(feishu.keys()) | set(ragflow.keys()))
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for q in all_questions:
            f_item = feishu.get(q, {})
            r_item = ragflow.get(q, {})

            row = {
                "index": f_item.get("index") or r_item.get("index"),
                "question": q,
                "feishu_answer": f_item.get("answer"),
                "feishu_status": f_item.get("status"),
                "feishu_duration_ms": f_item.get("duration_ms"),
                "feishu_start": f_item.get("start"),
                "feishu_end": f_item.get("end"),
                "feishu_overall_score": f_item.get("overall_score"),
                "ragflow_answer": r_item.get("answer"),
                "ragflow_success": r_item.get("success"),
                "ragflow_response_time_s": r_item.get("response_time_s"),
                "ragflow_accuracy": r_item.get("accuracy"),
                "ragflow_relevance": r_item.get("relevance"),
                "ragflow_completeness": r_item.get("completeness"),
                "ragflow_citation_quality": r_item.get("citation_quality"),
                "ragflow_overall_score": r_item.get("overall_score"),
                "ragflow_error": r_item.get("error"),
            }
            writer.writerow(row)

    print(f"[ok] CSV written to: {output}")
    print(f"     Questions merged: {len(all_questions)} "
          f"(Feishu: {len(feishu)}, RAGFlow: {len(ragflow)})")


def main():
    parser = argparse.ArgumentParser(description="导出合并后的飞书/RAGFlow测试结果 CSV")
    parser.add_argument("--feishu", type=str, default="feishu-test-results.json", help="飞书结果文件")
    parser.add_argument("--ragflow", type=str, default="test_output/test_results.json", help="RAGFlow结果文件")
    parser.add_argument("--output", type=str, default="test_output/combined_results.csv", help="输出CSV路径")
    args = parser.parse_args()

    base = Path(__file__).parent

    feishu_path = Path(args.feishu)
    if not feishu_path.is_absolute():
        feishu_path = base / feishu_path

    ragflow_path = Path(args.ragflow)
    if not ragflow_path.is_absolute():
        ragflow_path = base / ragflow_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = base / output_path

    feishu = load_feishu(feishu_path)
    ragflow = load_ragflow(ragflow_path)
    merge_and_write(feishu, ragflow, output_path)


if __name__ == "__main__":
    main()
