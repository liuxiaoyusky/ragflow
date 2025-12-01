#!/usr/bin/env python3
"""
用LLM评估飞书Knowledge AI答案质量，并生成与RAGFlow的对比报告
"""
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FeishuEvaluator:
    """评估飞书Knowledge AI答案质量"""
    
    def __init__(self, config_path: str = None):
        # 从config加载LLM配置
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from config import TestConfig
        
        self.config = TestConfig()
        
        # 初始化LLM客户端
        self.llm_client = OpenAI(
            api_key=self.config.eval_llm_api_key,
            base_url=self.config.eval_llm_base_url
        )
        self.model = self.config.eval_llm_model
        
    def clean_answer(self, answer: str, question: str) -> str:
        """清洗飞书答案，移除无关内容"""
        if not answer:
            return ""
        
        # 移除飞书来源标记
        cleaned = re.sub(r'\s*\(From Feishu Knowledge AI \| https://ask\.feishu\.cn\)', '', answer)
        
        # 移除JSON格式残留
        cleaned = re.sub(r'",\s*\n?"status":\s*"success"?', '', cleaned)
        cleaned = re.sub(r'"\s*\n?"status":\s*"success"?', '', cleaned)
        
        # 移除"Deep thinking completed"标记
        cleaned = re.sub(r'Deep thinking completed\s*‍?\s*', '', cleaned)
        
        # 移除定时任务推荐
        patterns = [
            r'‍?\s*要不要我帮你设个定时任务.*?你觉得呢？',
            r'‍?\s*我可以每.*?需要创建.*?定时任务吗？',
            r'‍?\s*需要我帮你建个定时任务吗？.*?',
            r'Monthly on the \d+th at \d+:\d+',
            r'Annually on \w+ \d+ at \d+:\d+',
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
        
        return cleaned.strip()
    
    def evaluate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """用LLM评估单个答案"""
        cleaned_answer = self.clean_answer(answer, question)
        
        if not cleaned_answer:
            return {
                "accuracy": 0,
                "relevance": 0,
                "completeness": 0,
                "overall_score": 0,
                "evaluation_text": "答案为空",
                "cleaned_answer": cleaned_answer
            }
        
        prompt = f"""你是一个专业的金融分析师，正在评估一个知识库AI助手对金融问题的回答质量。

问题: {question}

AI回答: {cleaned_answer}

请从以下维度评估回答质量（1-5分）：

1. **准确性 (Accuracy)**: 回答是否提供了具体、正确的数据或信息？是否直接回答了问题？
   - 5分: 提供了精确的数值/信息，完全正确
   - 4分: 基本正确，有具体数据
   - 3分: 部分正确，但有些模糊
   - 2分: 回答不准确或答非所问
   - 1分: 完全错误或未回答

2. **相关性 (Relevance)**: 回答是否针对问题？是否包含无关内容？
   - 5分: 完全针对问题，无多余内容
   - 4分: 主要针对问题，略有偏题
   - 3分: 部分相关，有不少无关内容
   - 2分: 大部分不相关
   - 1分: 完全不相关

3. **完整性 (Completeness)**: 回答是否全面？是否遗漏重要信息？
   - 5分: 非常全面，提供了详细信息
   - 4分: 较完整，覆盖主要方面
   - 3分: 基本回答，但缺少细节
   - 2分: 不完整，遗漏重要信息
   - 1分: 极度不完整

请用JSON格式返回评估结果：
{{
    "accuracy": <1-5>,
    "relevance": <1-5>,
    "completeness": <1-5>,
    "overall": <平均分>,
    "comments": "<简要评语，20字以内>"
}}"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融知识问答评估专家。请严格按照JSON格式返回评估结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            eval_text = response.choices[0].message.content
            scores = self._parse_evaluation(eval_text)
            
            return {
                "accuracy": scores.get("accuracy", 0),
                "relevance": scores.get("relevance", 0),
                "completeness": scores.get("completeness", 0),
                "overall_score": scores.get("overall", 0),
                "evaluation_text": scores.get("comments", ""),
                "cleaned_answer": cleaned_answer
            }
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {
                "accuracy": 0,
                "relevance": 0,
                "completeness": 0,
                "overall_score": 0,
                "evaluation_text": f"评估错误: {str(e)}",
                "cleaned_answer": cleaned_answer
            }
    
    def _parse_evaluation(self, text: str) -> Dict[str, Any]:
        """解析LLM评估结果"""
        scores = {"accuracy": 0, "relevance": 0, "completeness": 0, "overall": 0, "comments": ""}
        
        # 尝试提取JSON
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                scores["accuracy"] = int(parsed.get("accuracy", 0))
                scores["relevance"] = int(parsed.get("relevance", 0))
                scores["completeness"] = int(parsed.get("completeness", 0))
                scores["overall"] = float(parsed.get("overall", 0))
                scores["comments"] = parsed.get("comments", "")
            except (json.JSONDecodeError, ValueError):
                # 正则提取
                for key in ["accuracy", "relevance", "completeness", "overall"]:
                    match = re.search(rf'"{key}":\s*(\d+(?:\.\d+)?)', text)
                    if match:
                        scores[key] = float(match.group(1))
        
        # 计算平均分
        if scores["overall"] == 0:
            vals = [scores["accuracy"], scores["relevance"], scores["completeness"]]
            if any(vals):
                scores["overall"] = sum(vals) / 3
        
        return scores
    
    def evaluate_all(self, feishu_results: List[Dict]) -> List[Dict]:
        """评估所有飞书答案"""
        evaluated = []
        total = len(feishu_results)
        
        for i, result in enumerate(feishu_results, 1):
            question = result.get("question", "")
            answer = result.get("answer", "")
            
            logger.info(f"[{i}/{total}] 评估问题: {question[:40]}...")
            
            evaluation = self.evaluate_answer(question, answer)
            
            result["evaluation"] = evaluation
            evaluated.append(result)
            
            # 避免API限流
            time.sleep(0.5)
        
        return evaluated


class ComparisonReportGenerator:
    """生成RAGFlow与飞书的对比报告"""
    
    def __init__(self, ragflow_file: str, feishu_file: str, output_dir: str):
        self.ragflow_file = ragflow_file
        self.feishu_file = feishu_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_data(self):
        """加载数据"""
        with open(self.ragflow_file, "r", encoding="utf-8") as f:
            self.ragflow_data = json.load(f)
        with open(self.feishu_file, "r", encoding="utf-8") as f:
            self.feishu_data = json.load(f)
    
    def calculate_stats(self, results: List[Dict], source: str) -> Dict[str, Any]:
        """计算统计信息"""
        scores = {"accuracy": [], "relevance": [], "completeness": [], "overall": []}
        times = []
        
        for r in results:
            eval_data = r.get("evaluation", {})
            if eval_data:
                for key in ["accuracy", "relevance", "completeness"]:
                    val = eval_data.get(key, 0)
                    if val > 0:
                        scores[key].append(val)
                overall = eval_data.get("overall_score", eval_data.get("overall", 0))
                if overall > 0:
                    scores["overall"].append(overall)
            
            # 响应时间
            if source == "feishu":
                times.append(r.get("duration", 0) / 1000)
            else:
                times.append(r.get("response_time", 0))
        
        def avg(lst): return sum(lst) / len(lst) if lst else 0
        
        overall_scores = scores["overall"]
        return {
            "total": len(results),
            "evaluated": len(overall_scores),
            "avg_accuracy": avg(scores["accuracy"]),
            "avg_relevance": avg(scores["relevance"]),
            "avg_completeness": avg(scores["completeness"]),
            "avg_overall": avg(overall_scores),
            "avg_time": avg(times),
            "excellent": sum(1 for s in overall_scores if s >= 4.5),
            "good": sum(1 for s in overall_scores if 3.5 <= s < 4.5),
            "fair": sum(1 for s in overall_scores if 2.5 <= s < 3.5),
            "poor": sum(1 for s in overall_scores if s < 2.5 and s > 0),
        }
    
    def generate_report(self) -> str:
        """生成对比报告"""
        self.load_data()
        
        ragflow_results = self.ragflow_data.get("results", [])
        feishu_results = self.feishu_data.get("results", [])
        
        ragflow_stats = self.calculate_stats(ragflow_results, "ragflow")
        feishu_stats = self.calculate_stats(feishu_results, "feishu")
        
        # 生成HTML
        html = self._generate_html(ragflow_stats, feishu_stats, ragflow_results, feishu_results)
        
        # 保存
        html_file = self.output_dir / "comparison_report.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML saved to: {html_file}")
        
        # 转换PDF
        pdf_file = self.output_dir / "comparison_report.pdf"
        try:
            from weasyprint import HTML
            HTML(filename=str(html_file)).write_pdf(str(pdf_file))
            logger.info(f"PDF saved to: {pdf_file}")
            print(f"✓ 对比报告已保存到: {pdf_file}")
            return str(pdf_file)
        except ImportError:
            print(f"✓ HTML报告已保存到: {html_file}")
            return str(html_file)
    
    def _generate_html(self, ragflow_stats: Dict, feishu_stats: Dict, 
                       ragflow_results: List, feishu_results: List) -> str:
        """生成HTML内容"""
        
        # 创建飞书问题索引
        feishu_by_question = {r.get("question", ""): r for r in feishu_results}
        
        # 计算对比数量
        compared = min(len(ragflow_results), len(feishu_results))
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow vs 飞书Knowledge AI 对比报告</title>
    <style>
        @page {{ size: A4; margin: 1.2cm; }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif;
            font-size: 9px;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 12px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            font-size: 22px;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 12px;
            margin-bottom: 20px;
        }}
        h2 {{
            color: #2c3e50;
            font-size: 14px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
            margin: 20px 0 12px 0;
        }}
        
        /* 总体对比卡片 */
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }}
        .stat-card.ragflow {{ border-top: 4px solid #3498db; }}
        .stat-card.feishu {{ border-top: 4px solid #00d4aa; }}
        .stat-card h3 {{
            margin: 0 0 12px 0;
            font-size: 13px;
        }}
        .stat-card.ragflow h3 {{ color: #3498db; }}
        .stat-card.feishu h3 {{ color: #00d4aa; }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }}
        .stat-row:last-child {{ border: none; }}
        .stat-label {{ color: #666; }}
        .stat-value {{ font-weight: bold; }}
        
        /* 评分分布 */
        .score-dist {{
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }}
        .score-bar {{
            flex: 1;
            text-align: center;
            padding: 4px;
            border-radius: 4px;
            font-size: 8px;
        }}
        .score-bar.excellent {{ background: #d4edda; color: #155724; }}
        .score-bar.good {{ background: #cce5ff; color: #004085; }}
        .score-bar.fair {{ background: #fff3cd; color: #856404; }}
        .score-bar.poor {{ background: #f8d7da; color: #721c24; }}
        
        /* 对比结论 */
        .conclusion {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .conclusion h3 {{ margin: 0 0 10px 0; font-size: 12px; }}
        .conclusion ul {{ margin: 5px 0; padding-left: 18px; }}
        .conclusion li {{ margin: 4px 0; }}
        
        /* 逐题对比 */
        .qa-item {{
            background: white;
            margin: 10px 0;
            border-radius: 8px;
            overflow: hidden;
            page-break-inside: avoid;
        }}
        .qa-header {{
            background: #34495e;
            color: white;
            padding: 8px 12px;
            display: flex;
            justify-content: space-between;
            font-size: 10px;
        }}
        .qa-question {{
            padding: 8px 12px;
            background: #f8f9fa;
            font-weight: bold;
            border-bottom: 1px solid #eee;
        }}
        .qa-answers {{
            display: grid;
            grid-template-columns: 1fr 1fr;
        }}
        .answer-box {{
            padding: 10px;
            font-size: 9px;
        }}
        .answer-box.ragflow {{ background: #f0f7ff; border-right: 1px solid #e0e0e0; }}
        .answer-box.feishu {{ background: #f0fff7; }}
        .answer-box h4 {{
            margin: 0 0 6px 0;
            font-size: 10px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .answer-box.ragflow h4 {{ color: #3498db; }}
        .answer-box.feishu h4 {{ color: #00d4aa; }}
        .answer-content {{
            max-height: 150px;
            overflow: hidden;
            line-height: 1.5;
            color: #444;
        }}
        
        .score-pill {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 9px;
            font-weight: bold;
        }}
        .score-pill.excellent {{ background: #d4edda; color: #155724; }}
        .score-pill.good {{ background: #cce5ff; color: #004085; }}
        .score-pill.fair {{ background: #fff3cd; color: #856404; }}
        .score-pill.poor {{ background: #f8d7da; color: #721c24; }}
        
        .winner {{ 
            background: gold; 
            color: #333; 
            padding: 1px 5px; 
            border-radius: 3px; 
            font-size: 8px;
            margin-left: 4px;
        }}
        
        .metadata {{
            text-align: center;
            color: #888;
            font-size: 8px;
            margin-top: 20px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <h1>RAGFlow vs 飞书Knowledge AI 对比报告</h1>
    
    <h2>第一部分：总体评分对比</h2>
    
    <div class="stats-grid">
        <div class="stat-card ragflow">
            <h3>📊 RAGFlow</h3>
            <div class="stat-row">
                <span class="stat-label">测试问题数</span>
                <span class="stat-value">{ragflow_stats['total']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均准确性</span>
                <span class="stat-value">{ragflow_stats['avg_accuracy']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均相关性</span>
                <span class="stat-value">{ragflow_stats['avg_relevance']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均完整性</span>
                <span class="stat-value">{ragflow_stats['avg_completeness']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">综合评分</span>
                <span class="stat-value" style="color:#3498db;font-size:12px;">{ragflow_stats['avg_overall']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均响应时间</span>
                <span class="stat-value">{ragflow_stats['avg_time']:.1f}s</span>
            </div>
            <div class="score-dist">
                <div class="score-bar excellent">优秀 {ragflow_stats['excellent']}</div>
                <div class="score-bar good">良好 {ragflow_stats['good']}</div>
                <div class="score-bar fair">一般 {ragflow_stats['fair']}</div>
                <div class="score-bar poor">较差 {ragflow_stats['poor']}</div>
            </div>
        </div>
        
        <div class="stat-card feishu">
            <h3>📊 飞书 Knowledge AI</h3>
            <div class="stat-row">
                <span class="stat-label">测试问题数</span>
                <span class="stat-value">{feishu_stats['total']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均准确性</span>
                <span class="stat-value">{feishu_stats['avg_accuracy']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均相关性</span>
                <span class="stat-value">{feishu_stats['avg_relevance']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均完整性</span>
                <span class="stat-value">{feishu_stats['avg_completeness']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">综合评分</span>
                <span class="stat-value" style="color:#00d4aa;font-size:12px;">{feishu_stats['avg_overall']:.2f}/5</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均响应时间</span>
                <span class="stat-value">{feishu_stats['avg_time']:.1f}s</span>
            </div>
            <div class="score-dist">
                <div class="score-bar excellent">优秀 {feishu_stats['excellent']}</div>
                <div class="score-bar good">良好 {feishu_stats['good']}</div>
                <div class="score-bar fair">一般 {feishu_stats['fair']}</div>
                <div class="score-bar poor">较差 {feishu_stats['poor']}</div>
            </div>
        </div>
    </div>
    
    <div class="conclusion">
        <h3>📋 对比结论</h3>
        <ul>
            <li><strong>综合评分</strong>：RAGFlow {ragflow_stats['avg_overall']:.2f} vs 飞书 {feishu_stats['avg_overall']:.2f} 
                {"(RAGFlow胜出)" if ragflow_stats['avg_overall'] > feishu_stats['avg_overall'] else "(飞书胜出)" if feishu_stats['avg_overall'] > ragflow_stats['avg_overall'] else "(持平)"}</li>
            <li><strong>准确性</strong>：RAGFlow {ragflow_stats['avg_accuracy']:.2f} vs 飞书 {feishu_stats['avg_accuracy']:.2f}</li>
            <li><strong>响应速度</strong>：RAGFlow {ragflow_stats['avg_time']:.1f}s vs 飞书 {feishu_stats['avg_time']:.1f}s 
                {"(RAGFlow更快)" if ragflow_stats['avg_time'] < feishu_stats['avg_time'] else "(飞书更快)"}</li>
            <li><strong>优秀回答比例</strong>：RAGFlow {ragflow_stats['excellent']}/{ragflow_stats['evaluated']} vs 飞书 {feishu_stats['excellent']}/{feishu_stats['evaluated']}</li>
        </ul>
    </div>
    
    <h2>第二部分：逐题对比（共{compared}题）</h2>
"""
        
        # 逐题对比
        for i, ragflow_r in enumerate(ragflow_results[:compared], 1):
            question = ragflow_r.get("question", "")
            
            # RAGFlow数据
            ragflow_answer = ragflow_r.get("answer", "")[:400]
            ragflow_eval = ragflow_r.get("evaluation", {})
            ragflow_score = ragflow_eval.get("overall_score", 0)
            
            # 飞书数据
            feishu_r = feishu_by_question.get(question, {})
            feishu_eval = feishu_r.get("evaluation", {})
            feishu_answer = feishu_eval.get("cleaned_answer", feishu_r.get("answer", ""))[:400]
            feishu_score = feishu_eval.get("overall_score", 0)
            
            # 评分样式
            def get_score_class(s):
                if s >= 4.5: return "excellent"
                if s >= 3.5: return "good"
                if s >= 2.5: return "fair"
                return "poor"
            
            ragflow_class = get_score_class(ragflow_score)
            feishu_class = get_score_class(feishu_score)
            
            # 胜出标记
            ragflow_winner = '<span class="winner">胜</span>' if ragflow_score > feishu_score + 0.3 else ""
            feishu_winner = '<span class="winner">胜</span>' if feishu_score > ragflow_score + 0.3 else ""
            
            html += f"""
    <div class="qa-item">
        <div class="qa-header">
            <span>问题 {i}</span>
            <span>RAGFlow: {ragflow_score:.1f} | 飞书: {feishu_score:.1f}</span>
        </div>
        <div class="qa-question">Q: {question}</div>
        <div class="qa-answers">
            <div class="answer-box ragflow">
                <h4>RAGFlow <span class="score-pill {ragflow_class}">{ragflow_score:.1f}</span>{ragflow_winner}</h4>
                <div class="answer-content">{ragflow_answer}{"..." if len(ragflow_r.get("answer", "")) > 400 else ""}</div>
            </div>
            <div class="answer-box feishu">
                <h4>飞书 <span class="score-pill {feishu_class}">{feishu_score:.1f}</span>{feishu_winner}</h4>
                <div class="answer-content">{feishu_answer}{"..." if len(feishu_answer) > 400 else ""}</div>
            </div>
        </div>
    </div>
"""
        
        html += f"""
    <div class="metadata">
        生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        RAGFlow: {ragflow_stats['total']}题 | 飞书: {feishu_stats['total']}题 |
        对比: {compared}题
    </div>
</body>
</html>
"""
        return html


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="评估飞书答案并生成对比报告")
    parser.add_argument("--feishu", type=str, default="../../feishu-test-results.json",
                        help="飞书测试结果文件")
    parser.add_argument("--ragflow", type=str, default="test_output/test_results.json",
                        help="RAGFlow测试结果文件")
    parser.add_argument("--output", type=str, default="test_output",
                        help="输出目录")
    parser.add_argument("--skip-eval", action="store_true",
                        help="跳过评估，直接生成报告")
    
    args = parser.parse_args()
    
    feishu_path = Path(__file__).parent / args.feishu
    ragflow_path = Path(__file__).parent / args.ragflow
    output_path = Path(__file__).parent / args.output
    
    # 加载飞书数据
    with open(feishu_path, "r", encoding="utf-8") as f:
        feishu_data = json.load(f)
    
    feishu_results = feishu_data.get("results", [])
    logger.info(f"加载了 {len(feishu_results)} 个飞书测试结果")
    
    # 评估飞书答案
    if not args.skip_eval:
        evaluator = FeishuEvaluator()
        logger.info("开始用LLM评估飞书答案...")
        evaluated_results = evaluator.evaluate_all(feishu_results)
        
        # 保存评估结果
        feishu_data["results"] = evaluated_results
        evaluated_file = output_path / "feishu_evaluated.json"
        with open(evaluated_file, "w", encoding="utf-8") as f:
            json.dump(feishu_data, f, ensure_ascii=False, indent=2)
        logger.info(f"评估结果已保存到: {evaluated_file}")
        
        feishu_path = evaluated_file
    
    # 生成对比报告
    logger.info("生成对比报告...")
    generator = ComparisonReportGenerator(str(ragflow_path), str(feishu_path), str(output_path))
    generator.generate_report()


if __name__ == "__main__":
    main()

