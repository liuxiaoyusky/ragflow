#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class Reporter:
    """生成测试报告"""
    
    def __init__(self, config):
        self.config = config
    
    def generate_report(self, evaluated_results: List[Dict[str, Any]], output_dir: str = None) -> Dict[str, Any]:
        """生成完整报告"""
        if output_dir is None:
            output_dir = self.config.output_dir
        
        # 计算统计信息
        stats = self._calculate_statistics(evaluated_results)
        
        # 生成报告数据
        report_data = {
            "metadata": {
                "chat_id": self.config.chat_id,
                "document_id": self.config.document_id,
                "dataset_id": self.config.dataset_id,
                "total_questions": len(evaluated_results),
                "generated_at": self._get_timestamp()
            },
            "statistics": stats,
            "results": evaluated_results
        }
        
        # 保存JSON报告
        json_path = os.path.join(output_dir, "test_report.json")
        self._save_json_report(report_data, json_path)
        
        # 生成HTML报告
        html_path = os.path.join(output_dir, "test_report.html")
        self._save_html_report(report_data, html_path)
        
        # 生成PDF报告
        pdf_path = os.path.join(output_dir, "test_report.pdf")
        self._save_pdf_report(html_path, pdf_path)
        
        return report_data
    
    def _calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        total = len(results)
        if total == 0:
            return {}
        
        successful = sum(1 for r in results if r.get("success", False))
        failed = total - successful
        
        # 提取评估分数
        accuracy_scores = []
        relevance_scores = []
        completeness_scores = []
        citation_scores = []
        overall_scores = []
        response_times = []
        
        for result in results:
            if result.get("success"):
                eval_data = result.get("evaluation", {})
                if eval_data:
                    accuracy_scores.append(eval_data.get("accuracy", 0))
                    relevance_scores.append(eval_data.get("relevance", 0))
                    completeness_scores.append(eval_data.get("completeness", 0))
                    citation_scores.append(eval_data.get("citation_quality", 0))
                    overall_scores.append(eval_data.get("overall_score", 0))
                
                response_times.append(result.get("response_time", 0))
        
        def avg(lst):
            return sum(lst) / len(lst) if lst else 0
        
        stats = {
            "total_questions": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total * 100 if total > 0 else 0,
            "average_scores": {
                "accuracy": avg(accuracy_scores),
                "relevance": avg(relevance_scores),
                "completeness": avg(completeness_scores),
                "citation_quality": avg(citation_scores),
                "overall": avg(overall_scores)
            },
            "response_time": {
                "average": avg(response_times),
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0
            },
            "score_distribution": {
                "excellent": sum(1 for s in overall_scores if s >= 4.5),
                "good": sum(1 for s in overall_scores if 3.5 <= s < 4.5),
                "fair": sum(1 for s in overall_scores if 2.5 <= s < 3.5),
                "poor": sum(1 for s in overall_scores if s < 2.5)
            }
        }
        
        return stats
    
    def _save_json_report(self, report_data: Dict[str, Any], output_path: str):
        """保存JSON格式报告"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"JSON report saved to: {output_path}")
    
    def _save_html_report(self, report_data: Dict[str, Any], output_path: str):
        """生成HTML格式报告"""
        stats = report_data.get("statistics", {})
        results = report_data.get("results", [])
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAGFlow Chat Test Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #4CAF50;
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            font-weight: normal;
        }}
        .stat-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }}
        .score-bar {{
            background: #e0e0e0;
            height: 24px;
            border-radius: 12px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .score-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #8BC34A);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .score-excellent {{ color: #4CAF50; font-weight: bold; }}
        .score-good {{ color: #8BC34A; font-weight: bold; }}
        .score-fair {{ color: #FFC107; font-weight: bold; }}
        .score-poor {{ color: #F44336; font-weight: bold; }}
        .question-cell {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .answer-cell {{
            max-width: 400px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-success {{ background: #4CAF50; color: white; }}
        .badge-error {{ background: #F44336; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>RAGFlow Chat Test Report</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Questions</h3>
                <div class="value">{stats.get('total_questions', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Success Rate</h3>
                <div class="value">{stats.get('success_rate', 0):.1f}%</div>
            </div>
            <div class="stat-card">
                <h3>Average Overall Score</h3>
                <div class="value">{stats.get('average_scores', {}).get('overall', 0):.2f}</div>
            </div>
            <div class="stat-card">
                <h3>Avg Response Time</h3>
                <div class="value">{stats.get('response_time', {}).get('average', 0):.2f}s</div>
            </div>
        </div>
        
        <h2>Score Distribution</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Excellent (≥4.5)</h3>
                <div class="value">{stats.get('score_distribution', {}).get('excellent', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Good (3.5-4.5)</h3>
                <div class="value">{stats.get('score_distribution', {}).get('good', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Fair (2.5-3.5)</h3>
                <div class="value">{stats.get('score_distribution', {}).get('fair', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Poor (&lt;2.5)</h3>
                <div class="value">{stats.get('score_distribution', {}).get('poor', 0)}</div>
            </div>
        </div>
        
        <h2>Average Scores by Dimension</h2>
        <div style="margin: 20px 0;">
            <div>
                <strong>Accuracy:</strong>
                <div class="score-bar">
                    <div class="score-fill" style="width: {stats.get('average_scores', {}).get('accuracy', 0) / 5 * 100}%">
                        {stats.get('average_scores', {}).get('accuracy', 0):.2f}/5.0
                    </div>
                </div>
            </div>
            <div>
                <strong>Relevance:</strong>
                <div class="score-bar">
                    <div class="score-fill" style="width: {stats.get('average_scores', {}).get('relevance', 0) / 5 * 100}%">
                        {stats.get('average_scores', {}).get('relevance', 0):.2f}/5.0
                    </div>
                </div>
            </div>
            <div>
                <strong>Completeness:</strong>
                <div class="score-bar">
                    <div class="score-fill" style="width: {stats.get('average_scores', {}).get('completeness', 0) / 5 * 100}%">
                        {stats.get('average_scores', {}).get('completeness', 0):.2f}/5.0
                    </div>
                </div>
            </div>
            <div>
                <strong>Citation Quality:</strong>
                <div class="score-bar">
                    <div class="score-fill" style="width: {stats.get('average_scores', {}).get('citation_quality', 0) / 5 * 100}%">
                        {stats.get('average_scores', {}).get('citation_quality', 0):.2f}/5.0
                    </div>
                </div>
            </div>
        </div>
        
        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Question</th>
                    <th>Answer</th>
                    <th>Overall</th>
                    <th>Accuracy</th>
                    <th>Relevance</th>
                    <th>Completeness</th>
                    <th>Citation</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for result in results:
            q_id = result.get("question_id", 0)
            question = result.get("question", "")[:50] + "..." if len(result.get("question", "")) > 50 else result.get("question", "")
            answer = result.get("answer", "")[:50] + "..." if len(result.get("answer", "")) > 50 else result.get("answer", "")
            success = result.get("success", False)
            
            eval_data = result.get("evaluation", {})
            overall = eval_data.get("overall_score", 0)
            accuracy = eval_data.get("accuracy", 0)
            relevance = eval_data.get("relevance", 0)
            completeness = eval_data.get("completeness", 0)
            citation = eval_data.get("citation_quality", 0)
            
            # 确定分数样式
            score_class = "score-poor"
            if overall >= 4.5:
                score_class = "score-excellent"
            elif overall >= 3.5:
                score_class = "score-good"
            elif overall >= 2.5:
                score_class = "score-fair"
            
            status_badge = '<span class="badge badge-success">Success</span>' if success else '<span class="badge badge-error">Failed</span>'
            
            html_content += f"""
                <tr>
                    <td>{q_id}</td>
                    <td class="question-cell" title="{result.get('question', '')}">{question}</td>
                    <td class="answer-cell" title="{result.get('answer', '')}">{answer}</td>
                    <td class="{score_class}">{overall:.2f}</td>
                    <td>{accuracy:.2f}</td>
                    <td>{relevance:.2f}</td>
                    <td>{completeness:.2f}</td>
                    <td>{citation:.2f}</td>
                    <td>{status_badge}</td>
                </tr>
"""
        
        html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"HTML report saved to: {output_path}")
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        import time
        return time.strftime("%Y-%m-%d %H:%M:%S")
    
    def _save_pdf_report(self, html_path: str, pdf_path: str):
        """将HTML报告转换为PDF"""
        try:
            from weasyprint import HTML, CSS
            
            # 添加打印友好的CSS样式
            print_css = CSS(string="""
                @page {
                    size: A4 landscape;
                    margin: 1cm;
                }
                body {
                    font-size: 10px;
                }
                .container {
                    box-shadow: none;
                }
                table {
                    font-size: 9px;
                }
                th, td {
                    padding: 6px;
                }
                .question-cell, .answer-cell {
                    max-width: 200px;
                }
            """)
            
            HTML(filename=html_path).write_pdf(pdf_path, stylesheets=[print_css])
            print(f"PDF report saved to: {pdf_path}")
            
        except ImportError:
            logger.warning("weasyprint not installed. Skipping PDF generation.")
            logger.warning("To enable PDF export, install weasyprint: pip install weasyprint")
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            logger.warning("PDF generation failed. HTML report is still available.")
    
    @staticmethod
    def html_to_pdf(html_path: str, pdf_path: str = None):
        """独立的HTML转PDF方法（可直接调用）"""
        if pdf_path is None:
            pdf_path = html_path.replace(".html", ".pdf")
        
        try:
            from weasyprint import HTML, CSS
            
            print_css = CSS(string="""
                @page {
                    size: A4 landscape;
                    margin: 1cm;
                }
                body {
                    font-size: 10px;
                }
                .container {
                    box-shadow: none;
                }
                table {
                    font-size: 9px;
                }
            """)
            
            HTML(filename=html_path).write_pdf(pdf_path, stylesheets=[print_css])
            print(f"PDF saved to: {pdf_path}")
            return pdf_path
            
        except ImportError:
            print("Error: weasyprint not installed.")
            print("Install it with: pip install weasyprint")
            return None
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return None

