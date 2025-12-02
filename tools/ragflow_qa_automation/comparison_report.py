#!/usr/bin/env python3
"""
RAGFlow vs 飞书Knowledge AI 对比报告生成器
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import markdown

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComparisonReportGenerator:
    """生成RAGFlow与飞书Knowledge AI的对比报告"""
    
    def __init__(self, ragflow_results_file: str, feishu_results_file: str, output_dir: str = "test_output"):
        self.ragflow_file = ragflow_results_file
        self.feishu_file = feishu_results_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_ragflow_results(self) -> Dict[str, Any]:
        """加载RAGFlow测试结果"""
        with open(self.ragflow_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    
    def load_feishu_results(self) -> Dict[str, Any]:
        """加载飞书测试结果"""
        with open(self.feishu_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    
    def clean_feishu_answer(self, answer: str, question: str) -> str:
        """清洗飞书答案，移除重复问题和无关内容"""
        if not answer:
            return "(无回答)"
        
        # 移除答案开头重复的问题文本
        cleaned = answer
        
        # 移除 "Deep thinking completed" 标记
        cleaned = re.sub(r'Deep thinking completed\s*', '', cleaned)
        
        # 移除定时任务推荐文本
        patterns = [
            r'‍\s*要不要我帮你设个定时任务.*?你觉得呢？',
            r'‍\s*我可以每.*?需要创建.*?定时任务吗？',
            r'‍\s*需要我帮你建个定时任务吗？.*?你觉得.*?',
            r'‍\s*如果你需要，我可以.*?定时任务.*?',
            r'Monthly on the \d+th at \d+:\d+',
            r'Annually on \w+ \d+ at \d+:\d+',
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)
        
        # 移除开头重复的问题
        if question in cleaned:
            # 只移除开头的问题重复
            if cleaned.startswith(question):
                cleaned = cleaned[len(question):].strip()
            # 移除结尾的问题重复
            if cleaned.endswith(question):
                cleaned = cleaned[:-len(question)].strip()
        
        # 清理多余空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned if cleaned else "(无有效回答)"
    
    def calculate_stats(self, ragflow_data: Dict, feishu_data: Dict) -> Dict[str, Any]:
        """计算对比统计信息"""
        ragflow_results = ragflow_data.get("results", [])
        feishu_results = feishu_data.get("results", [])
        
        # RAGFlow统计
        ragflow_success = sum(1 for r in ragflow_results if r.get("success", False))
        ragflow_scores = [r.get("evaluation", {}).get("overall_score", 0) 
                         for r in ragflow_results if r.get("success") and r.get("evaluation", {}).get("overall_score", 0) > 0]
        ragflow_times = [r.get("response_time", 0) for r in ragflow_results if r.get("success")]
        
        # 飞书统计
        feishu_success = sum(1 for r in feishu_results if r.get("status") == "success")
        feishu_empty = sum(1 for r in feishu_results if r.get("status") == "empty")
        feishu_times = [r.get("duration", 0) / 1000 for r in feishu_results if r.get("status") == "success"]
        
        return {
            "ragflow": {
                "total": len(ragflow_results),
                "success": ragflow_success,
                "success_rate": ragflow_success / len(ragflow_results) * 100 if ragflow_results else 0,
                "avg_score": sum(ragflow_scores) / len(ragflow_scores) if ragflow_scores else 0,
                "avg_time": sum(ragflow_times) / len(ragflow_times) if ragflow_times else 0,
            },
            "feishu": {
                "total": len(feishu_results),
                "success": feishu_success,
                "empty": feishu_empty,
                "success_rate": feishu_success / len(feishu_results) * 100 if feishu_results else 0,
                "avg_time": sum(feishu_times) / len(feishu_times) if feishu_times else 0,
            },
            "compared_count": min(len(ragflow_results), len(feishu_results))
        }
    
    def generate(self) -> str:
        """生成对比报告"""
        logger.info("Loading test results...")
        ragflow_data = self.load_ragflow_results()
        feishu_data = self.load_feishu_results()
        
        ragflow_results = ragflow_data.get("results", [])
        feishu_results = feishu_data.get("results", [])
        
        # 计算统计
        stats = self.calculate_stats(ragflow_data, feishu_data)
        
        logger.info(f"RAGFlow: {stats['ragflow']['total']} questions, Feishu: {stats['feishu']['total']} questions")
        
        # 生成HTML
        html = self._generate_html(stats, ragflow_results, feishu_results)
        
        # 保存HTML
        html_file = self.output_dir / "comparison_report.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML report saved to: {html_file}")
        
        # 转换为PDF
        pdf_file = self.output_dir / "comparison_report.pdf"
        try:
            from weasyprint import HTML
            HTML(filename=str(html_file)).write_pdf(str(pdf_file))
            logger.info(f"PDF report saved to: {pdf_file}")
            print(f"✓ 对比报告已保存到: {pdf_file}")
            return str(pdf_file)
        except ImportError:
            logger.warning("weasyprint not installed, HTML report saved instead")
            print(f"✓ HTML报告已保存到: {html_file}")
            return str(html_file)
    
    def _generate_html(self, stats: Dict, ragflow_results: List[Dict], feishu_results: List[Dict]) -> str:
        """生成HTML内容"""
        # 创建飞书结果索引（按问题文本）
        feishu_by_question = {}
        for r in feishu_results:
            feishu_by_question[r.get("question", "")] = r
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow vs 飞书Knowledge AI 对比报告</title>
    <style>
        @page {{
            size: A4;
            margin: 1.5cm;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 10px;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 15px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            font-size: 24px;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        h2 {{
            color: #2c3e50;
            font-size: 16px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
            margin-top: 30px;
        }}
        
        /* 总体对比卡片 */
        .summary-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card.ragflow {{
            border-top: 4px solid #3498db;
        }}
        .summary-card.feishu {{
            border-top: 4px solid #00d4aa;
        }}
        .summary-card h3 {{
            margin: 0 0 15px 0;
            font-size: 16px;
        }}
        .summary-card.ragflow h3 {{ color: #3498db; }}
        .summary-card.feishu h3 {{ color: #00d4aa; }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        .stat-row:last-child {{ border-bottom: none; }}
        .stat-label {{ color: #666; }}
        .stat-value {{ font-weight: bold; color: #333; }}
        
        /* 对比项 */
        .comparison-item {{
            background: white;
            margin: 15px 0;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            page-break-inside: avoid;
        }}
        .comparison-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .comparison-header .q-num {{
            font-weight: bold;
            font-size: 12px;
        }}
        .comparison-header .score-badge {{
            background: rgba(255,255,255,0.2);
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 11px;
        }}
        
        .question-text {{
            padding: 12px 15px;
            background: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
            border-bottom: 1px solid #eee;
        }}
        
        .answers-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
        }}
        .answer-box {{
            padding: 15px;
            font-size: 10px;
            line-height: 1.6;
            border-right: 1px solid #eee;
        }}
        .answer-box:last-child {{ border-right: none; }}
        .answer-box.ragflow {{
            background: #f0f7ff;
        }}
        .answer-box.feishu {{
            background: #f0fff7;
        }}
        .answer-box h4 {{
            margin: 0 0 10px 0;
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .answer-box.ragflow h4 {{ color: #3498db; }}
        .answer-box.feishu h4 {{ color: #00d4aa; }}
        
        .answer-content {{
            max-height: 200px;
            overflow-y: auto;
            color: #444;
        }}
        .answer-content p {{ margin: 0 0 8px 0; }}
        
        .score-pill {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
        }}
        .score-pill.excellent {{ background: #d4edda; color: #155724; }}
        .score-pill.good {{ background: #cce5ff; color: #004085; }}
        .score-pill.fair {{ background: #fff3cd; color: #856404; }}
        .score-pill.poor {{ background: #f8d7da; color: #721c24; }}
        
        .no-answer {{
            color: #999;
            font-style: italic;
        }}
        
        .metadata {{
            text-align: center;
            color: #888;
            font-size: 9px;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
        }}
        
        /* 结论区域 */
        .conclusion {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .conclusion h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .conclusion ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .conclusion li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <h1>🔍 RAGFlow vs 飞书Knowledge AI 对比报告</h1>
    
    <h2>第一部分：总体对比</h2>
    
    <div class="summary-section">
        <div class="summary-card ragflow">
            <h3>📊 RAGFlow</h3>
            <div class="stat-row">
                <span class="stat-label">测试问题数</span>
                <span class="stat-value">{stats['ragflow']['total']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">成功回答</span>
                <span class="stat-value">{stats['ragflow']['success']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">成功率</span>
                <span class="stat-value">{stats['ragflow']['success_rate']:.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均评分</span>
                <span class="stat-value">{stats['ragflow']['avg_score']:.2f}/5.0</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均响应时间</span>
                <span class="stat-value">{stats['ragflow']['avg_time']:.1f}s</span>
            </div>
        </div>
        
        <div class="summary-card feishu">
            <h3>📊 飞书 Knowledge AI</h3>
            <div class="stat-row">
                <span class="stat-label">测试问题数</span>
                <span class="stat-value">{stats['feishu']['total']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">成功回答</span>
                <span class="stat-value">{stats['feishu']['success']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">空回答数</span>
                <span class="stat-value">{stats['feishu']['empty']}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">成功率</span>
                <span class="stat-value">{stats['feishu']['success_rate']:.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">平均响应时间</span>
                <span class="stat-value">{stats['feishu']['avg_time']:.1f}s</span>
            </div>
        </div>
    </div>
    
    <div class="conclusion">
        <h3>📋 初步结论</h3>
        <ul>
            <li><strong>响应时间</strong>：RAGFlow平均 {stats['ragflow']['avg_time']:.1f}s，飞书平均 {stats['feishu']['avg_time']:.1f}s</li>
            <li><strong>回答质量</strong>：RAGFlow有LLM评分（平均 {stats['ragflow']['avg_score']:.2f}/5.0），飞书答案需人工评估</li>
            <li><strong>对比问题数</strong>：共 {stats['compared_count']} 个问题可进行对比</li>
        </ul>
    </div>
    
    <h2>第二部分：逐题对比（前{min(93, len(ragflow_results))}题）</h2>
"""
        
        # 逐题对比
        for i, ragflow_result in enumerate(ragflow_results[:93], 1):
            question = ragflow_result.get("question", "")
            ragflow_answer = ragflow_result.get("answer", "")
            ragflow_score = ragflow_result.get("evaluation", {}).get("overall_score", 0)
            ragflow_success = ragflow_result.get("success", False)
            
            # 查找对应的飞书结果
            feishu_result = feishu_by_question.get(question, {})
            feishu_answer_raw = feishu_result.get("answer", "")
            feishu_answer = self.clean_feishu_answer(feishu_answer_raw, question)
            feishu_status = feishu_result.get("status", "not_found")
            feishu_time = feishu_result.get("duration", 0) / 1000
            
            # 评分样式
            if ragflow_score >= 4.5:
                score_class = "excellent"
            elif ragflow_score >= 3.5:
                score_class = "good"
            elif ragflow_score >= 2.5:
                score_class = "fair"
            else:
                score_class = "poor"
            
            # 处理答案显示
            ragflow_display = ragflow_answer[:500] + "..." if len(ragflow_answer) > 500 else ragflow_answer
            if not ragflow_success:
                ragflow_display = '<span class="no-answer">(请求失败)</span>'
            
            feishu_display = feishu_answer[:500] + "..." if len(feishu_answer) > 500 else feishu_answer
            if feishu_status == "empty" or feishu_status == "not_found":
                feishu_display = f'<span class="no-answer">({feishu_status})</span>'
            
            html += f"""
    <div class="comparison-item">
        <div class="comparison-header">
            <span class="q-num">问题 {i}</span>
            <span class="score-badge">RAGFlow: {ragflow_score:.1f}/5.0 | 飞书: {feishu_time:.1f}s</span>
        </div>
        <div class="question-text">Q: {question}</div>
        <div class="answers-grid">
            <div class="answer-box ragflow">
                <h4>
                    RAGFlow
                    <span class="score-pill {score_class}">{ragflow_score:.1f}</span>
                </h4>
                <div class="answer-content">{ragflow_display}</div>
            </div>
            <div class="answer-box feishu">
                <h4>飞书 Knowledge AI</h4>
                <div class="answer-content">{feishu_display}</div>
            </div>
        </div>
    </div>
"""
        
        html += f"""
    <div class="metadata">
        生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        RAGFlow测试: {stats['ragflow']['total']}题 | 
        飞书测试: {stats['feishu']['total']}题
    </div>
</body>
</html>
"""
        return html


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="生成RAGFlow vs 飞书对比报告")
    parser.add_argument("--ragflow", type=str, default="test_output/test_results.json",
                        help="RAGFlow测试结果文件")
    parser.add_argument("--feishu", type=str, default="feishu-test-results.json",
                        help="飞书测试结果文件")
    parser.add_argument("--output", type=str, default="test_output",
                        help="输出目录")
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent
    ragflow_path = Path(args.ragflow)
    if not ragflow_path.is_absolute():
        ragflow_path = base_dir / ragflow_path
    
    feishu_path = Path(args.feishu)
    if not feishu_path.is_absolute():
        feishu_path = base_dir / feishu_path
    
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = base_dir / output_dir
    
    generator = ComparisonReportGenerator(ragflow_path, feishu_path, output_dir)
    generator.generate()


if __name__ == "__main__":
    main()
