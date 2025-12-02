#!/usr/bin/env python3
"""
使用OpenRouter LLM评估RAGFlow中文测试结果，并生成和飞书的对比报告
"""
import json
import logging
import time
import sys
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OpenRouterEvaluator:
    """使用OpenRouter LLM评估答案质量"""
    
    def __init__(self, api_key: str, model: str = "minimax/minimax-01"):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = model
    
    def evaluate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """评估单个答案"""
        if not answer or answer.strip() == "":
            return {
                "accuracy": 0,
                "relevance": 0,
                "completeness": 0,
                "citation_quality": 0,
                "overall_score": 0,
                "evaluation_text": "答案为空"
            }
        
        prompt = f"""请评估以下RAG系统的回答质量，按1-5分评分：

问题：{question}

回答：{answer[:2000]}

评分标准：
1. **准确性(accuracy)**: 答案是否事实正确？
2. **相关性(relevance)**: 答案是否直接回答了问题？
3. **完整性(completeness)**: 答案是否涵盖了问题的所有方面？
4. **引用质量(citation_quality)**: 是否提供了参考来源？

请以JSON格式返回评估结果：
{{"accuracy": <1-5>, "relevance": <1-5>, "completeness": <1-5>, "citation_quality": <1-5>, "overall": <平均分>, "comments": "<简短评价>"}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的RAG系统评估专家。请客观评估答案质量。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            eval_text = response.choices[0].message.content
            scores = self._parse_scores(eval_text)
            
            return {
                "accuracy": scores.get("accuracy", 0),
                "relevance": scores.get("relevance", 0),
                "completeness": scores.get("completeness", 0),
                "citation_quality": scores.get("citation_quality", 0),
                "overall_score": scores.get("overall", 0),
                "evaluation_text": eval_text
            }
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {
                "accuracy": 0,
                "relevance": 0,
                "completeness": 0,
                "citation_quality": 0,
                "overall_score": 0,
                "evaluation_text": f"评估错误: {str(e)}"
            }
    
    def _parse_scores(self, text: str) -> Dict[str, float]:
        """解析评分结果"""
        import re
        
        scores = {"accuracy": 0, "relevance": 0, "completeness": 0, "citation_quality": 0, "overall": 0}
        
        # 尝试提取JSON
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                for key in scores:
                    if key in parsed:
                        scores[key] = float(parsed[key])
            except json.JSONDecodeError:
                pass
        
        # 计算overall如果没有
        if scores["overall"] == 0:
            vals = [scores["accuracy"], scores["relevance"], scores["completeness"], scores["citation_quality"]]
            scores["overall"] = sum(vals) / len(vals) if any(vals) else 0
        
        return scores


def evaluate_ragflow_results(ragflow_file: str, output_file: str, api_key: str, model: str, start_from: int = 1):
    """评估RAGFlow结果"""
    
    # 加载RAGFlow结果
    with open(ragflow_file, 'r', encoding='utf-8') as f:
        ragflow_data = json.load(f)
    
    results = ragflow_data.get("results", [])
    logger.info(f"Loaded {len(results)} RAGFlow results")
    
    evaluator = OpenRouterEvaluator(api_key, model)
    
    # 加载已有评估结果
    output_path = Path(output_file)
    evaluated_results = []
    if output_path.exists() and start_from > 1:
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            evaluated_results = existing.get("results", [])
            logger.info(f"Loaded {len(evaluated_results)} existing evaluations")
    
    for result in results:
        idx = result.get("index", 0)
        
        # 跳过已评估的
        if idx < start_from:
            continue
        
        # 检查是否已在evaluated_results中
        if any(r.get("index") == idx for r in evaluated_results):
            continue
        
        question = result.get("question", "")
        answer = result.get("answer", "")
        
        logger.info(f"[{idx}/{len(results)}] Evaluating: {question[:40]}...")
        
        evaluation = evaluator.evaluate_answer(question, answer)
        
        evaluated_result = {
            **result,
            "evaluation": evaluation
        }
        evaluated_results.append(evaluated_result)
        
        # 每5个保存一次
        if idx % 5 == 0:
            _save_results(evaluated_results, ragflow_data["metadata"], output_file)
            logger.info(f"Progress saved at Q{idx}")
        
        time.sleep(0.5)  # 避免限流
    
    # 最终保存
    _save_results(evaluated_results, ragflow_data["metadata"], output_file)
    logger.info(f"✓ Evaluation completed. Results saved to {output_file}")
    
    return evaluated_results


def _save_results(results: list, metadata: dict, output_file: str):
    """保存评估结果"""
    output_data = {
        "metadata": {
            **metadata,
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "results": sorted(results, key=lambda x: x.get("index", 0))
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def generate_comparison_report(ragflow_file: str, feishu_file: str, output_file: str):
    """生成RAGFlow和飞书的对比报告"""
    
    # 加载数据
    with open(ragflow_file, 'r', encoding='utf-8') as f:
        ragflow_data = json.load(f)
    
    with open(feishu_file, 'r', encoding='utf-8') as f:
        feishu_data = json.load(f)
    
    ragflow_results = {r["index"]: r for r in ragflow_data.get("results", [])}
    feishu_results = {r["index"]: r for r in feishu_data.get("results", [])}
    
    # 统计
    ragflow_scores = []
    feishu_scores = []
    comparisons = []
    
    all_indices = sorted(set(ragflow_results.keys()) | set(feishu_results.keys()))
    
    for idx in all_indices:
        rag = ragflow_results.get(idx, {})
        fei = feishu_results.get(idx, {})
        
        rag_score = rag.get("evaluation", {}).get("overall_score", 0)
        fei_score = fei.get("evaluation", {}).get("overall_score", 0)
        
        if rag_score > 0:
            ragflow_scores.append(rag_score)
        if fei_score > 0:
            feishu_scores.append(fei_score)
        
        comparisons.append({
            "index": idx,
            "question": rag.get("question") or fei.get("question", ""),
            "ragflow_answer": rag.get("answer", "N/A"),
            "ragflow_score": rag_score,
            "feishu_answer": fei.get("answer", "N/A"),
            "feishu_score": fei_score,
            "winner": "RAGFlow" if rag_score > fei_score + 0.5 else ("飞书" if fei_score > rag_score + 0.5 else "平手")
        })
    
    # 生成HTML报告
    avg_rag = sum(ragflow_scores) / len(ragflow_scores) if ragflow_scores else 0
    avg_fei = sum(feishu_scores) / len(feishu_scores) if feishu_scores else 0
    
    rag_wins = sum(1 for c in comparisons if c["winner"] == "RAGFlow")
    fei_wins = sum(1 for c in comparisons if c["winner"] == "飞书")
    ties = sum(1 for c in comparisons if c["winner"] == "平手")
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow vs 飞书 Knowledge AI 对比报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #333; text-align: center; }}
        .summary {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .stats {{ display: flex; justify-content: space-around; flex-wrap: wrap; }}
        .stat-box {{ text-align: center; padding: 15px; min-width: 150px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2196F3; }}
        .stat-label {{ color: #666; }}
        .winner-rag {{ color: #4CAF50; }}
        .winner-fei {{ color: #FF9800; }}
        table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; vertical-align: top; }}
        th {{ background: #2196F3; color: white; }}
        .answer {{ max-height: 200px; overflow-y: auto; white-space: pre-wrap; font-size: 12px; }}
        .score {{ font-weight: bold; text-align: center; }}
        .score-high {{ color: #4CAF50; }}
        .score-mid {{ color: #FF9800; }}
        .score-low {{ color: #f44336; }}
        .winner-cell {{ text-align: center; font-weight: bold; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🤖 RAGFlow vs 飞书 Knowledge AI 对比报告</h1>
    
    <div class="summary">
        <h2>📊 总体统计</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{len(comparisons)}</div>
                <div class="stat-label">总问题数</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{avg_rag:.2f}</div>
                <div class="stat-label">RAGFlow 平均分</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{avg_fei:.2f}</div>
                <div class="stat-label">飞书 平均分</div>
            </div>
            <div class="stat-box">
                <div class="stat-value winner-rag">{rag_wins}</div>
                <div class="stat-label">RAGFlow 胜出</div>
            </div>
            <div class="stat-box">
                <div class="stat-value winner-fei">{fei_wins}</div>
                <div class="stat-label">飞书 胜出</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{ties}</div>
                <div class="stat-label">平手</div>
            </div>
        </div>
        <h3 style="text-align:center; margin-top:20px;">
            🏆 总体优胜者: <span style="color: {'#4CAF50' if avg_rag > avg_fei else '#FF9800'}">
            {'RAGFlow' if avg_rag > avg_fei else '飞书'}</span> 
            (差距: {abs(avg_rag - avg_fei):.2f}分)
        </h3>
    </div>
    
    <h2>📝 详细对比</h2>
    <table>
        <thead>
            <tr>
                <th style="width:5%">#</th>
                <th style="width:20%">问题</th>
                <th style="width:30%">RAGFlow 回答</th>
                <th style="width:5%">分数</th>
                <th style="width:30%">飞书 回答</th>
                <th style="width:5%">分数</th>
                <th style="width:5%">胜出</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for comp in comparisons:
        rag_score_class = "score-high" if comp["ragflow_score"] >= 4 else ("score-mid" if comp["ragflow_score"] >= 3 else "score-low")
        fei_score_class = "score-high" if comp["feishu_score"] >= 4 else ("score-mid" if comp["feishu_score"] >= 3 else "score-low")
        winner_class = "winner-rag" if comp["winner"] == "RAGFlow" else ("winner-fei" if comp["winner"] == "飞书" else "")
        
        # 截断过长的答案
        rag_ans = comp["ragflow_answer"][:500] + "..." if len(comp["ragflow_answer"]) > 500 else comp["ragflow_answer"]
        fei_ans = comp["feishu_answer"][:500] + "..." if len(comp["feishu_answer"]) > 500 else comp["feishu_answer"]
        
        html += f"""
            <tr>
                <td>{comp["index"]}</td>
                <td>{comp["question"]}</td>
                <td><div class="answer">{rag_ans}</div></td>
                <td class="score {rag_score_class}">{comp["ragflow_score"]:.1f}</td>
                <td><div class="answer">{fei_ans}</div></td>
                <td class="score {fei_score_class}">{comp["feishu_score"]:.1f}</td>
                <td class="winner-cell {winner_class}">{comp["winner"]}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
</div>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logger.info(f"✓ Comparison report saved to {output_file}")
    
    # 打印总结
    print("\n" + "="*60)
    print("对比结果总结")
    print("="*60)
    print(f"总问题数: {len(comparisons)}")
    print(f"RAGFlow 平均分: {avg_rag:.2f}")
    print(f"飞书 平均分: {avg_fei:.2f}")
    print(f"RAGFlow 胜出: {rag_wins} 题")
    print(f"飞书 胜出: {fei_wins} 题")
    print(f"平手: {ties} 题")
    print(f"\n🏆 总体优胜者: {'RAGFlow' if avg_rag > avg_fei else '飞书'} (差距: {abs(avg_rag - avg_fei):.2f}分)")
    print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate RAGFlow results and compare with Feishu")
    parser.add_argument("--ragflow", type=str, default="test_output/ragflow_cn_results.json")
    parser.add_argument("--feishu", type=str, default="test_output/feishu_evaluated.json")
    parser.add_argument("--output", type=str, default="test_output/ragflow_cn_evaluated.json")
    parser.add_argument("--report", type=str, default="test_output/comparison_report_cn.html")
    parser.add_argument("--api-key", type=str, required=True)
    parser.add_argument("--model", type=str, default="minimax/minimax-01")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--skip-eval", action="store_true", help="Skip evaluation, only generate report")
    args = parser.parse_args()
    
    if not args.skip_eval:
        evaluate_ragflow_results(args.ragflow, args.output, args.api_key, args.model, args.start)
    
    generate_comparison_report(args.output, args.feishu, args.report)


if __name__ == "__main__":
    main()

