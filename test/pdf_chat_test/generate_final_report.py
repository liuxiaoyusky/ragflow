#!/usr/bin/env python3
"""
生成RAGFlow vs 飞书Knowledge AI 完整对比报告（PDF格式）
包含：总结部分 + 详细对比部分
"""
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any
from weasyprint import HTML

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FinalReportGenerator:
    """生成最终对比报告"""
    
    def __init__(self, ragflow_file: str, feishu_file: str, output_dir: str):
        self.ragflow_file = Path(ragflow_file)
        self.feishu_file = Path(feishu_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_data(self):
        """加载数据"""
        with open(self.ragflow_file, 'r', encoding='utf-8') as f:
            self.ragflow_data = json.load(f)
        
        with open(self.feishu_file, 'r', encoding='utf-8') as f:
            self.feishu_data = json.load(f)
        
        self.ragflow_results = {r["index"]: r for r in self.ragflow_data.get("results", [])}
        self.feishu_results = {r["index"]: r for r in self.feishu_data.get("results", [])}
        
        logger.info(f"Loaded {len(self.ragflow_results)} RAGFlow results, {len(self.feishu_results)} Feishu results")
    
    def calculate_stats(self):
        """计算统计信息"""
        # 只统计两个数据集都存在的问题（交集）
        self.common_indices = sorted(set(self.ragflow_results.keys()) & set(self.feishu_results.keys()))
        
        # RAGFlow统计（只统计共同问题）
        rag_scores = []
        rag_times = []
        rag_poor = []  # 评分 < 3
        rag_fair = []  # 评分 3-4
        rag_good = []  # 评分 >= 4
        rag_failed = []  # 失败/无回答
        
        for idx in self.common_indices:
            r = self.ragflow_results[idx]
            score = r.get("evaluation", {}).get("overall_score", 0)
            # 优先使用重测后的响应时间
            resp_time = r.get("retest_response_time") or r.get("response_time", 0)
            
            if r.get("success", False) and score > 0:
                rag_scores.append(score)
                rag_times.append(resp_time)
                
                if score < 3:
                    rag_poor.append((idx, r))
                elif score < 4:
                    rag_fair.append((idx, r))
                else:
                    rag_good.append((idx, r))
            else:
                rag_failed.append((idx, r))
        
        # 飞书统计（只统计共同问题）
        fei_scores = []
        fei_times = []
        fei_poor = []
        fei_fair = []
        fei_good = []
        fei_failed = []
        
        for idx in self.common_indices:
            r = self.feishu_results[idx]
            score = r.get("evaluation", {}).get("overall_score", 0)
            resp_time = r.get("duration", 0) / 1000 if r.get("duration") else 0  # 转换为秒
            
            if score > 0:
                fei_scores.append(score)
                fei_times.append(resp_time)
                
                if score < 3:
                    fei_poor.append((idx, r))
                elif score < 4:
                    fei_fair.append((idx, r))
                else:
                    fei_good.append((idx, r))
            else:
                fei_failed.append((idx, r))
        
        self.stats = {
            "ragflow": {
                "total": len(self.common_indices),
                "avg_score": sum(rag_scores) / len(rag_scores) if rag_scores else 0,
                "avg_time": sum(rag_times) / len(rag_times) if rag_times else 0,
                "min_time": min(rag_times) if rag_times else 0,
                "max_time": max(rag_times) if rag_times else 0,
                "good_count": len(rag_good),
                "fair_count": len(rag_fair),
                "poor_count": len(rag_poor),
                "failed_count": len(rag_failed),
                "poor_cases": rag_poor,
                "fair_cases": rag_fair,
                "scores": rag_scores,
                "times": rag_times
            },
            "feishu": {
                "total": len(self.common_indices),
                "avg_score": sum(fei_scores) / len(fei_scores) if fei_scores else 0,
                "avg_time": sum(fei_times) / len(fei_times) if fei_times else 0,
                "min_time": min(fei_times) if fei_times else 0,
                "max_time": max(fei_times) if fei_times else 0,
                "good_count": len(fei_good),
                "fair_count": len(fei_fair),
                "poor_count": len(fei_poor),
                "failed_count": len(fei_failed),
                "poor_cases": fei_poor,
                "fair_cases": fei_fair,
                "scores": fei_scores,
                "times": fei_times
            }
        }
        
        # 计算对比结果
        all_indices = sorted(set(self.ragflow_results.keys()) & set(self.feishu_results.keys()))
        rag_wins = 0
        fei_wins = 0
        ties = 0
        
        for idx in all_indices:
            rag_score = self.ragflow_results[idx].get("evaluation", {}).get("overall_score", 0)
            fei_score = self.feishu_results[idx].get("evaluation", {}).get("overall_score", 0)
            
            if rag_score > fei_score + 0.5:
                rag_wins += 1
            elif fei_score > rag_score + 0.5:
                fei_wins += 1
            else:
                ties += 1
        
        self.stats["comparison"] = {
            "total_compared": len(all_indices),
            "ragflow_wins": rag_wins,
            "feishu_wins": fei_wins,
            "ties": ties
        }
    
    def generate_html(self) -> str:
        """生成HTML报告"""
        rag = self.stats["ragflow"]
        fei = self.stats["feishu"]
        comp = self.stats["comparison"]
        
        # 确定胜者
        winner = "RAGFlow" if rag["avg_score"] > fei["avg_score"] else "飞书"
        winner_color = "#4CAF50" if winner == "RAGFlow" else "#FF9800"
        score_diff = abs(rag["avg_score"] - fei["avg_score"])
        
        # 稳定性计算
        rag_stability = (rag["good_count"] / rag["total"] * 100) if rag["total"] > 0 else 0
        fei_stability = (fei["good_count"] / fei["total"] * 100) if fei["total"] > 0 else 0
        
        rag_unstable = ((rag["fair_count"] + rag["poor_count"] + rag["failed_count"]) / rag["total"] * 100) if rag["total"] > 0 else 0
        fei_unstable = ((fei["fair_count"] + fei["poor_count"] + fei["failed_count"]) / fei["total"] * 100) if fei["total"] > 0 else 0
        
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
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #1a1a1a;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #2196F3;
            border-left: 4px solid #2196F3;
            padding-left: 15px;
            margin-top: 40px;
        }}
        h3 {{
            color: #555;
            margin-top: 25px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-box {{
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .summary-box.ragflow {{
            border-top: 4px solid #4CAF50;
        }}
        .summary-box.feishu {{
            border-top: 4px solid #FF9800;
        }}
        .summary-box h3 {{
            margin-top: 0;
            text-align: center;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px dashed #ddd;
        }}
        .metric:last-child {{
            border-bottom: none;
        }}
        .metric-label {{
            color: #666;
        }}
        .metric-value {{
            font-weight: bold;
            color: #333;
        }}
        .winner-banner {{
            background: {winner_color};
            color: white;
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            margin: 30px 0;
            font-size: 1.3em;
        }}
        .comparison-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        .comparison-table th, .comparison-table td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        .comparison-table th {{
            background: #f5f5f5;
            font-weight: bold;
        }}
        .comparison-table tr:nth-child(even) {{
            background: #fafafa;
        }}
        .score-good {{ color: #4CAF50; font-weight: bold; }}
        .score-fair {{ color: #FF9800; font-weight: bold; }}
        .score-poor {{ color: #f44336; font-weight: bold; }}
        .problem-list {{
            background: #fff3e0;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }}
        .problem-item {{
            padding: 8px 0;
            border-bottom: 1px solid #ffe0b2;
        }}
        .problem-item:last-child {{
            border-bottom: none;
        }}
        .problem-item a {{
            color: #e65100;
            text-decoration: none;
        }}
        .problem-item a:hover {{
            text-decoration: underline;
        }}
        .detail-section {{
            page-break-before: always;
        }}
        .question-card {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            margin: 20px 0;
            page-break-inside: avoid;
        }}
        .question-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
        }}
        .question-header h4 {{
            margin: 0;
            font-size: 1.1em;
        }}
        .question-content {{
            padding: 20px;
        }}
        .answer-comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .answer-box {{
            background: #f9f9f9;
            border-radius: 8px;
            padding: 15px;
        }}
        .answer-box.ragflow {{
            border-left: 4px solid #4CAF50;
        }}
        .answer-box.feishu {{
            border-left: 4px solid #FF9800;
        }}
        .answer-box h5 {{
            margin: 0 0 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .answer-text {{
            font-size: 11px;
            line-height: 1.4;
            white-space: pre-wrap;
            background: white;
            padding: 10px;
            border-radius: 5px;
            word-break: break-word;
        }}
        .score-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 12px;
            color: white;
        }}
        .score-badge.high {{ background: #4CAF50; }}
        .score-badge.mid {{ background: #FF9800; }}
        .score-badge.low {{ background: #f44336; }}
        .time-info {{
            font-size: 11px;
            color: #888;
            margin-top: 8px;
        }}
    </style>
</head>
<body>
    <h1>🤖 RAGFlow vs 飞书Knowledge AI 对比报告</h1>
    <p style="text-align: center; color: #666;">生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}</p>
    
    <!-- 第一部分：总结 -->
    <h2>📊 第一部分：总体对比总结</h2>
    
    <div class="winner-banner">
        🏆 总体优胜者: {winner} (领先 {score_diff:.2f} 分)
    </div>
    
    <!-- 比分对比 -->
    <h3>1. 评分对比</h3>
    <div class="summary-grid">
        <div class="summary-box ragflow">
            <h3 style="color: #4CAF50;">RAGFlow</h3>
            <div class="metric">
                <span class="metric-label">测试问题数</span>
                <span class="metric-value">{rag["total"]}</span>
            </div>
            <div class="metric">
                <span class="metric-label">综合评分</span>
                <span class="metric-value">{rag["avg_score"]:.2f} / 5</span>
            </div>
            <div class="metric">
                <span class="metric-label">优秀回答 (≥4分)</span>
                <span class="metric-value">{rag["good_count"]} ({rag["good_count"]/rag["total"]*100:.1f}%)</span>
            </div>
            <div class="metric">
                <span class="metric-label">一般回答 (3-4分)</span>
                <span class="metric-value">{rag["fair_count"]} ({rag["fair_count"]/rag["total"]*100:.1f}%)</span>
            </div>
            <div class="metric">
                <span class="metric-label">较差回答 (<3分)</span>
                <span class="metric-value">{rag["poor_count"]} ({rag["poor_count"]/rag["total"]*100:.1f}%)</span>
            </div>
        </div>
        <div class="summary-box feishu">
            <h3 style="color: #FF9800;">飞书 Knowledge AI</h3>
            <div class="metric">
                <span class="metric-label">测试问题数</span>
                <span class="metric-value">{fei["total"]}</span>
            </div>
            <div class="metric">
                <span class="metric-label">综合评分</span>
                <span class="metric-value">{fei["avg_score"]:.2f} / 5</span>
            </div>
            <div class="metric">
                <span class="metric-label">优秀回答 (≥4分)</span>
                <span class="metric-value">{fei["good_count"]} ({fei["good_count"]/fei["total"]*100:.1f}%)</span>
            </div>
            <div class="metric">
                <span class="metric-label">一般回答 (3-4分)</span>
                <span class="metric-value">{fei["fair_count"]} ({fei["fair_count"]/fei["total"]*100:.1f}%)</span>
            </div>
            <div class="metric">
                <span class="metric-label">较差回答 (<3分)</span>
                <span class="metric-value">{fei["poor_count"]} ({fei["poor_count"]/fei["total"]*100:.1f}%)</span>
            </div>
        </div>
    </div>
    
    <table class="comparison-table">
        <tr>
            <th>对比维度</th>
            <th>RAGFlow</th>
            <th>飞书</th>
            <th>胜出</th>
        </tr>
        <tr>
            <td>综合评分</td>
            <td>{rag["avg_score"]:.2f}</td>
            <td>{fei["avg_score"]:.2f}</td>
            <td style="color: {winner_color}; font-weight: bold;">{winner}</td>
        </tr>
        <tr>
            <td>胜出题数</td>
            <td>{comp["ragflow_wins"]}</td>
            <td>{comp["feishu_wins"]}</td>
            <td style="color: {'#4CAF50' if comp['ragflow_wins'] > comp['feishu_wins'] else '#FF9800'}; font-weight: bold;">
                {'RAGFlow' if comp['ragflow_wins'] > comp['feishu_wins'] else '飞书'}
            </td>
        </tr>
        <tr>
            <td>平手</td>
            <td colspan="2" style="text-align: center;">{comp["ties"]}</td>
            <td>-</td>
        </tr>
    </table>
    
    <!-- 响应时间对比 -->
    <h3>2. 响应时间对比</h3>
    <table class="comparison-table">
        <tr>
            <th>指标</th>
            <th>RAGFlow</th>
            <th>飞书</th>
            <th>胜出</th>
        </tr>
        <tr>
            <td>平均响应时间</td>
            <td>{rag["avg_time"]:.1f}s</td>
            <td>{fei["avg_time"]:.1f}s</td>
            <td style="color: {'#4CAF50' if rag['avg_time'] < fei['avg_time'] else '#FF9800'}; font-weight: bold;">
                {'RAGFlow' if rag['avg_time'] < fei['avg_time'] else '飞书'} (更快)
            </td>
        </tr>
        <tr>
            <td>最快响应</td>
            <td>{rag["min_time"]:.1f}s</td>
            <td>{fei["min_time"]:.1f}s</td>
            <td>-</td>
        </tr>
        <tr>
            <td>最慢响应</td>
            <td>{rag["max_time"]:.1f}s</td>
            <td>{fei["max_time"]:.1f}s</td>
            <td>-</td>
        </tr>
    </table>
    
    <!-- 稳定性对比 -->
    <h3>3. 稳定性对比</h3>
    <table class="comparison-table">
        <tr>
            <th>指标</th>
            <th>RAGFlow</th>
            <th>飞书</th>
        </tr>
        <tr>
            <td>优秀回答率 (≥4分)</td>
            <td class="score-good">{rag_stability:.1f}%</td>
            <td class="score-good">{fei_stability:.1f}%</td>
        </tr>
        <tr>
            <td>不稳定回答率 (一般+较差+失败)</td>
            <td class="{'score-fair' if rag_unstable < 30 else 'score-poor'}">{rag_unstable:.1f}%</td>
            <td class="{'score-fair' if fei_unstable < 30 else 'score-poor'}">{fei_unstable:.1f}%</td>
        </tr>
        <tr>
            <td>失败/无回答</td>
            <td>{rag["failed_count"]} ({rag["failed_count"]/rag["total"]*100:.1f}%)</td>
            <td>{fei["failed_count"]} ({fei["failed_count"]/fei["total"]*100:.1f}%)</td>
        </tr>
    </table>
    
    <!-- 糟糕案例 -->
    <h3>4. 需关注案例列表</h3>
"""
        
        # RAGFlow糟糕案例
        html += """
    <h4 style="color: #4CAF50;">RAGFlow 较差案例</h4>
    <div class="problem-list">
"""
        rag_problems = rag["poor_cases"] + rag["fair_cases"]
        if rag_problems:
            for idx, r in rag_problems[:15]:  # 最多显示15个
                score = r.get("evaluation", {}).get("overall_score", 0)
                q = r.get("question", "")[:50]
                html += f'<div class="problem-item"><a href="#q{idx}">Q{idx}</a>: {q}... (评分: {score:.1f})</div>\n'
        else:
            html += '<div class="problem-item">无较差案例</div>\n'
        html += "</div>\n"
        
        # 飞书糟糕案例
        html += """
    <h4 style="color: #FF9800;">飞书 较差案例</h4>
    <div class="problem-list">
"""
        fei_problems = fei["poor_cases"] + fei["fair_cases"]
        if fei_problems:
            for idx, r in fei_problems[:15]:
                score = r.get("evaluation", {}).get("overall_score", 0)
                q = r.get("question", "")[:50]
                html += f'<div class="problem-item"><a href="#q{idx}">Q{idx}</a>: {q}... (评分: {score:.1f})</div>\n'
        else:
            html += '<div class="problem-item">无较差案例</div>\n'
        html += "</div>\n"
        
        # 第二部分：详细对比
        html += f"""
    <div class="detail-section">
    <h2>📝 第二部分：逐题详细对比（共{len(self.common_indices)}题）</h2>
"""
        
        # 只显示共同问题
        for idx in self.common_indices:
            rag_r = self.ragflow_results[idx]
            fei_r = self.feishu_results[idx]
            
            question = rag_r.get("question") or fei_r.get("question", "N/A")
            
            rag_score = rag_r.get("evaluation", {}).get("overall_score", 0)
            fei_score = fei_r.get("evaluation", {}).get("overall_score", 0)
            
            # 优先使用重测后的响应时间和答案
            rag_time = rag_r.get("retest_response_time") or rag_r.get("response_time", 0)
            fei_time = fei_r.get("duration", 0) / 1000 if fei_r.get("duration") else 0
            
            rag_answer = (rag_r.get("retest_answer") or rag_r.get("answer", "N/A"))[:800]
            fei_answer = fei_r.get("answer", "N/A")[:800]
            
            # 评分徽章样式
            rag_badge = "high" if rag_score >= 4 else ("mid" if rag_score >= 3 else "low")
            fei_badge = "high" if fei_score >= 4 else ("mid" if fei_score >= 3 else "low")
            
            html += f"""
    <div class="question-card" id="q{idx}">
        <div class="question-header">
            <h4>问题 {idx}: {question[:80]}{'...' if len(question) > 80 else ''}</h4>
        </div>
        <div class="question-content">
            <div class="answer-comparison">
                <div class="answer-box ragflow">
                    <h5>
                        <span style="color: #4CAF50;">RAGFlow</span>
                        <span class="score-badge {rag_badge}">{rag_score:.1f}</span>
                    </h5>
                    <div class="answer-text">{rag_answer}</div>
                    <div class="time-info">⏱ 响应时间: {rag_time:.1f}s</div>
                </div>
                <div class="answer-box feishu">
                    <h5>
                        <span style="color: #FF9800;">飞书</span>
                        <span class="score-badge {fei_badge}">{fei_score:.1f}</span>
                    </h5>
                    <div class="answer-text">{fei_answer}</div>
                    <div class="time-info">⏱ 响应时间: {fei_time:.1f}s</div>
                </div>
            </div>
        </div>
    </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        return html
    
    def generate_report(self, output_name: str = "final_comparison_report"):
        """生成完整报告"""
        self.load_data()
        self.calculate_stats()
        
        html_content = self.generate_html()
        
        # 保存HTML
        html_path = self.output_dir / f"{output_name}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"✓ HTML report saved to {html_path}")
        
        # 转换为PDF
        pdf_path = self.output_dir / f"{output_name}.pdf"
        try:
            HTML(string=html_content).write_pdf(pdf_path)
            logger.info(f"✓ PDF report saved to {pdf_path}")
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
        
        # 打印总结
        rag = self.stats["ragflow"]
        fei = self.stats["feishu"]
        comp = self.stats["comparison"]
        
        print("\n" + "="*60)
        print("📊 对比报告总结")
        print("="*60)
        print(f"RAGFlow: {rag['avg_score']:.2f}分 | 飞书: {fei['avg_score']:.2f}分")
        print(f"RAGFlow胜出: {comp['ragflow_wins']}题 | 飞书胜出: {comp['feishu_wins']}题 | 平手: {comp['ties']}题")
        print(f"平均响应: RAGFlow {rag['avg_time']:.1f}s | 飞书 {fei['avg_time']:.1f}s")
        print("="*60)
        
        return html_path, pdf_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate final comparison report")
    parser.add_argument("--ragflow", type=str, default="test_output/ragflow_cn_evaluated.json")
    parser.add_argument("--feishu", type=str, default="test_output/feishu_evaluated.json")
    parser.add_argument("--output-dir", type=str, default="test_output")
    parser.add_argument("--name", type=str, default="final_comparison_report")
    args = parser.parse_args()
    
    generator = FinalReportGenerator(args.ragflow, args.feishu, args.output_dir)
    generator.generate_report(args.name)


if __name__ == "__main__":
    main()

