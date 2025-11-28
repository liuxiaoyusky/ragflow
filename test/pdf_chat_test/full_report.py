#!/usr/bin/env python3
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
"""
生成完整PDF测试报告（评分汇总 + 详细问答）
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

import re
import markdown

logger = logging.getLogger(__name__)


class FullReportGenerator:
    """生成完整的PDF测试报告"""
    
    def __init__(self, config=None):
        self.config = config
    
    def generate(self, results_file: str, output_file: str = None) -> str:
        """生成完整PDF报告"""
        # 加载测试结果
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        results = data.get("results", [])
        metadata = data.get("metadata", {})
        
        if output_file is None:
            output_file = results_file.replace(".json", "_full_report.pdf")
        
        # 计算统计信息
        stats = self._calculate_stats(results)
        
        # 生成HTML
        html_content = self._generate_html(metadata, stats, results)
        
        # 保存HTML
        html_file = output_file.replace(".pdf", ".html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 转换为PDF
        try:
            from weasyprint import HTML
            HTML(filename=html_file).write_pdf(output_file)
            logger.info(f"Full PDF report saved to: {output_file}")
            print(f"✓ 完整PDF报告已保存到: {output_file}")
            return output_file
        except ImportError:
            logger.warning("weasyprint not installed, HTML report saved instead")
            print(f"✓ HTML报告已保存到: {html_file}")
            return html_file
    
    def _calculate_stats(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        total = len(results)
        if total == 0:
            return {}
        
        successful = sum(1 for r in results if r.get("success", False))
        
        # 提取评估分数
        scores = {"accuracy": [], "relevance": [], "completeness": [], "citation_quality": [], "overall": []}
        response_times = []
        
        for result in results:
            if result.get("success"):
                eval_data = result.get("evaluation", {})
                if eval_data:
                    for key in scores:
                        score_key = "overall_score" if key == "overall" else key
                        val = eval_data.get(score_key, 0)
                        # 对于overall分数，包含0分（表示评估失败或无法评估）
                        # 对于其他维度，只有>0才计入平均值
                        if key == "overall":
                            scores[key].append(val)
                        elif val > 0:
                            scores[key].append(val)
                
                response_times.append(result.get("response_time", 0))
        
        def avg(lst):
            return sum(lst) / len(lst) if lst else 0
        
        return {
            "total_questions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total * 100 if total > 0 else 0,
            "avg_accuracy": avg(scores["accuracy"]),
            "avg_relevance": avg(scores["relevance"]),
            "avg_completeness": avg(scores["completeness"]),
            "avg_citation": avg(scores["citation_quality"]),
            "avg_overall": avg(scores["overall"]),
            "avg_response_time": avg(response_times),
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "excellent": sum(1 for s in scores["overall"] if s >= 4.5),
            "good": sum(1 for s in scores["overall"] if 3.5 <= s < 4.5),
            "fair": sum(1 for s in scores["overall"] if 2.5 <= s < 3.5),
            "poor": sum(1 for s in scores["overall"] if s < 2.5)
        }
    
    def _render_markdown(self, text: str) -> str:
        """将Markdown文本渲染为HTML，处理LaTeX公式和代码块中的HTML表格"""
        if not text:
            return ""
        
        # 检测是否已经包含HTML表格标签（且不在代码块中）
        has_html_table = '<table>' in text or '<tr>' in text
        has_code_block = '```' in text
        
        if has_html_table and not has_code_block:
            # 纯HTML内容，直接返回
            return text
        
        # 将代码块中的HTML表格提取出来，直接渲染成表格
        # 匹配 ```\n<table>...</table>\n``` 或 ```<table>...```
        def replace_table_code_block(match):
            table_html = match.group(1).strip()
            # 添加样式类
            table_html = table_html.replace('<table>', '<table class="quoted-table">')
            return f'\n{table_html}\n'
        
        # 匹配代码块中的HTML表格
        text = re.sub(r'```\n?(<table>.*?</table>)\n?```', replace_table_code_block, text, flags=re.DOTALL | re.IGNORECASE)
        
        # 处理不完整的表格（没有</table>结束标签）
        def replace_incomplete_table(match):
            table_html = match.group(1).strip()
            # 尝试修复不完整的表格
            if not table_html.endswith('</table>'):
                table_html += '</table>'
            table_html = table_html.replace('<table>', '<table class="quoted-table">')
            return f'\n{table_html}\n'
        
        text = re.sub(r'```\n?(<table>.*?</tr>)\n?```', replace_incomplete_table, text, flags=re.DOTALL | re.IGNORECASE)
        
        # 处理LaTeX公式：将 \[...\] 格式转为代码样式
        text = re.sub(r'\\\[(.*?)\\\]', r'<div class="formula">\1</div>', text, flags=re.DOTALL)
        
        # 处理 [\text{...}...] 格式的LaTeX公式
        text = re.sub(r'\[(\\text\{.*?\}.*?)\]', r'<div class="formula">\1</div>', text, flags=re.DOTALL)
        
        # 处理行内LaTeX公式 \(...\)
        text = re.sub(r'\\\((.*?)\\\)', r'<code class="formula-inline">\1</code>', text, flags=re.DOTALL)
        
        # 使用markdown库渲染，支持表格扩展
        return markdown.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])
    
    def _get_score_class(self, score: float) -> str:
        """根据分数返回评分等级类名"""
        if score >= 4.5:
            return "excellent"
        elif score >= 3.5:
            return "good"
        elif score >= 2.5:
            return "fair"
        return "poor"
    
    def _categorize_results(self, results: List[Dict]) -> Dict[str, List[tuple]]:
        """将结果按评分分类，返回{类别: [(索引, 结果)]}
        只处理成功的请求，与评分分布统计保持一致
        """
        categories = {"fair": [], "poor": []}
        for i, result in enumerate(results):
            # 只处理成功的请求
            if not result.get("success", False):
                continue
            eval_data = result.get("evaluation", {})
            if not eval_data:
                continue
            score = eval_data.get("overall_score", 0)
            if 2.5 <= score < 3.5:
                categories["fair"].append((i + 1, result))
            elif score < 2.5:
                categories["poor"].append((i + 1, result))
        return categories

    def _generate_html(self, metadata: Dict, stats: Dict, results: List[Dict]) -> str:
        """生成HTML内容"""
        # 预先分类结果
        categories = self._categorize_results(results)
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow Chat 完整测试报告</title>
    <style>
        @page {{
            size: A4;
            margin: 1.5cm;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 10px;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 15px;
        }}
        h1 {{
            color: #2c3e50;
            font-size: 22px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        h2 {{
            color: #2c3e50;
            font-size: 16px;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 8px;
            margin-top: 25px;
            page-break-after: avoid;
        }}
        h3 {{
            font-size: 13px;
            color: #555;
            margin: 15px 0 10px 0;
        }}
        
        /* 内部链接样式 */
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .clickable {{
            cursor: pointer;
        }}
        
        /* 元数据区域 */
        .metadata {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 10px;
        }}
        .metadata-row {{
            display: flex;
            margin-bottom: 5px;
        }}
        .metadata-label {{
            font-weight: bold;
            width: 120px;
        }}
        
        /* 统计卡片 */
        .stats-section {{
            margin-bottom: 25px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card.success {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .stat-card.warning {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .stat-card .label {{
            font-size: 9px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .stat-card .value {{
            font-size: 24px;
            font-weight: bold;
        }}
        
        /* 评分条 */
        .score-section {{
            margin: 20px 0;
        }}
        .score-row {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}
        .score-label {{
            width: 120px;
            font-weight: 500;
        }}
        .score-bar-container {{
            flex: 1;
            background: #e0e0e0;
            height: 20px;
            border-radius: 10px;
            overflow: hidden;
            margin: 0 10px;
        }}
        .score-bar {{
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2ecc71);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 10px;
            font-weight: bold;
        }}
        .score-value {{
            width: 50px;
            text-align: right;
            font-weight: bold;
        }}
        
        /* 分布统计 */
        .distribution {{
            display: flex;
            gap: 15px;
            margin: 15px 0;
        }}
        .dist-item {{
            flex: 1;
            text-align: center;
            padding: 10px;
            border-radius: 6px;
        }}
        .dist-item.excellent {{ background: #d4edda; color: #155724; }}
        .dist-item.good {{ background: #cce5ff; color: #004085; }}
        .dist-item.fair {{ background: #fff3cd; color: #856404; }}
        .dist-item.poor {{ background: #f8d7da; color: #721c24; }}
        .dist-item .count {{
            font-size: 20px;
            font-weight: bold;
        }}
        .dist-item .count a {{
            color: inherit;
            text-decoration: underline;
        }}
        .dist-item .label {{
            font-size: 9px;
        }}
        
        /* 需关注问题列表 */
        .attention-section {{
            margin: 25px 0;
            padding: 15px;
            background: #fff8e1;
            border-radius: 8px;
            border-left: 4px solid #ff9800;
        }}
        .attention-section h3 {{
            color: #e65100;
            margin-top: 0;
        }}
        .attention-list {{
            margin: 10px 0;
        }}
        .attention-item {{
            display: flex;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px dotted #ffe0b2;
            text-decoration: none;
            color: inherit;
            border-radius: 4px;
            transition: background-color 0.2s;
        }}
        .attention-item:hover {{
            background-color: #fff3cd;
        }}
        .attention-item:last-child {{
            border-bottom: none;
        }}
        .attention-item .q-num {{
            font-weight: bold;
            min-width: 60px;
            color: #e65100;
        }}
        .attention-item .q-text {{
            flex: 1;
            font-size: 10px;
            color: #555;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .attention-item .q-score {{
            min-width: 50px;
            text-align: right;
            font-weight: bold;
        }}
        .attention-item .q-score.fair {{ color: #f39c12; }}
        .attention-item .q-score.poor {{ color: #e74c3c; }}
        
        /* 详细问答 */
        .qa-section {{
            margin-top: 30px;
        }}
        .qa-item {{
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 15px;
            page-break-inside: avoid;
            overflow: hidden;
        }}
        .qa-header {{
            background: #3498db;
            color: white;
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .qa-header .id {{
            font-weight: bold;
            font-size: 12px;
        }}
        .qa-header .scores {{
            font-size: 10px;
        }}
        .qa-header .score-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 5px;
            font-weight: bold;
        }}
        .qa-header .score-badge.excellent {{ background: #27ae60; }}
        .qa-header .score-badge.good {{ background: #3498db; }}
        .qa-header .score-badge.fair {{ background: #f39c12; }}
        .qa-header .score-badge.poor {{ background: #e74c3c; }}
        
        .qa-body {{
            padding: 15px;
        }}
        .question {{
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 11px;
        }}
        .answer {{
            background: #f9f9f9;
            padding: 12px;
            border-left: 4px solid #27ae60;
            margin: 10px 0;
            font-size: 10px;
        }}
        
        /* Markdown渲染样式 */
        .answer p {{
            margin: 0 0 10px 0;
        }}
        .answer p:last-child {{
            margin-bottom: 0;
        }}
        .answer strong, .answer b {{
            font-weight: bold;
            color: #2c3e50;
        }}
        .answer em, .answer i {{
            font-style: italic;
        }}
        .answer ul, .answer ol {{
            margin: 8px 0;
            padding-left: 25px;
        }}
        .answer li {{
            margin-bottom: 4px;
        }}
        .answer table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 9px;
        }}
        .answer th, .answer td {{
            border: 1px solid #ddd;
            padding: 6px 8px;
            text-align: left;
        }}
        /* 引用文档中的表格样式 */
        .quoted-table {{
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            margin: 10px 0;
        }}
        .quoted-table td {{
            border: 1px solid #dee2e6;
            padding: 8px 10px;
        }}
        .quoted-table tr:first-child td {{
            background: #e9ecef;
            font-weight: bold;
        }}
        .answer th {{
            background: #f0f0f0;
            font-weight: bold;
        }}
        .answer tr:nth-child(even) {{
            background: #fafafa;
        }}
        .answer code {{
            background: #e8e8e8;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 9px;
        }}
        
        /* LaTeX公式样式 */
        .formula {{
            background: #f5f5f5;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 8px 12px;
            margin: 8px 0;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 9px;
            white-space: pre-wrap;
            word-break: break-all;
            color: #333;
        }}
        .formula-inline {{
            background: #f5f5f5;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 9px;
        }}
        
        .answer pre {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 9px;
        }}
        .answer pre code {{
            background: transparent;
            padding: 0;
            color: inherit;
        }}
        .answer blockquote {{
            border-left: 3px solid #3498db;
            margin: 10px 0;
            padding-left: 15px;
            color: #666;
            font-style: italic;
        }}
        
        .references {{
            font-size: 9px;
            color: #666;
            margin-top: 10px;
        }}
        .references ul {{
            margin: 5px 0;
            padding-left: 20px;
        }}
        .score-details {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin-top: 10px;
            font-size: 9px;
        }}
        .score-detail {{
            background: #f0f0f0;
            padding: 5px 8px;
            border-radius: 4px;
            text-align: center;
        }}
        .score-detail .label {{
            color: #666;
        }}
        .score-detail .value {{
            font-weight: bold;
            color: #333;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 9px;
            font-weight: bold;
        }}
        .status-badge.success {{ background: #27ae60; color: white; }}
        .status-badge.failed {{ background: #e74c3c; color: white; }}
        
        .response-time {{
            font-size: 9px;
            color: #888;
            margin-top: 8px;
        }}
    </style>
</head>
<body>
    <h1>RAGFlow Chat 完整测试报告</h1>
    
    <div class="metadata">
        <div class="metadata-row"><span class="metadata-label">测试时间:</span> {metadata.get('updated_at', 'N/A')}</div>
        <div class="metadata-row"><span class="metadata-label">Chat ID:</span> {metadata.get('chat_id', 'N/A')}</div>
        <div class="metadata-row"><span class="metadata-label">Document ID:</span> {metadata.get('document_id', 'N/A')}</div>
    </div>
    
    <h2>第一部分：测试概览</h2>
    
    <div class="stats-section">
        <h3>总体统计</h3>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">总问题数</div>
                <div class="value">{stats.get('total_questions', 0)}</div>
            </div>
            <div class="stat-card success">
                <div class="label">成功率</div>
                <div class="value">{stats.get('success_rate', 0):.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="label">平均总分</div>
                <div class="value">{stats.get('avg_overall', 0):.2f}</div>
            </div>
            <div class="stat-card warning">
                <div class="label">平均响应时间</div>
                <div class="value">{stats.get('avg_response_time', 0):.1f}s</div>
            </div>
        </div>
        
        <h3>各维度评分</h3>
        <div class="score-section">
            <div class="score-row">
                <span class="score-label">准确性</span>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: {stats.get('avg_accuracy', 0) / 5 * 100}%">{stats.get('avg_accuracy', 0):.2f}</div>
                </div>
                <span class="score-value">{stats.get('avg_accuracy', 0):.2f}/5.0</span>
            </div>
            <div class="score-row">
                <span class="score-label">相关性</span>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: {stats.get('avg_relevance', 0) / 5 * 100}%">{stats.get('avg_relevance', 0):.2f}</div>
                </div>
                <span class="score-value">{stats.get('avg_relevance', 0):.2f}/5.0</span>
            </div>
            <div class="score-row">
                <span class="score-label">完整性</span>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: {stats.get('avg_completeness', 0) / 5 * 100}%">{stats.get('avg_completeness', 0):.2f}</div>
                </div>
                <span class="score-value">{stats.get('avg_completeness', 0):.2f}/5.0</span>
            </div>
            <div class="score-row">
                <span class="score-label">引用质量</span>
                <div class="score-bar-container">
                    <div class="score-bar" style="width: {stats.get('avg_citation', 0) / 5 * 100}%">{stats.get('avg_citation', 0):.2f}</div>
                </div>
                <span class="score-value">{stats.get('avg_citation', 0):.2f}/5.0</span>
            </div>
        </div>
        
        <h3>评分分布</h3>
        <div class="distribution">
            <div class="dist-item excellent">
                <div class="count">{stats.get('excellent', 0)}</div>
                <div class="label">优秀 (≥4.5)</div>
            </div>
            <div class="dist-item good">
                <div class="count">{stats.get('good', 0)}</div>
                <div class="label">良好 (3.5-4.5)</div>
            </div>
            <div class="dist-item fair">
                <div class="count"><a href="#attention-fair">{stats.get('fair', 0)}</a></div>
                <div class="label">一般 (2.5-3.5)</div>
            </div>
            <div class="dist-item poor">
                <div class="count"><a href="#attention-poor">{stats.get('poor', 0)}</a></div>
                <div class="label">较差 (&lt;2.5)</div>
            </div>
        </div>
    </div>
"""
        
        # 添加需关注问题列表
        if categories["fair"] or categories["poor"]:
            html += """
    <div class="attention-section">
        <h3>⚠️ 需关注问题列表</h3>
"""
            if categories["poor"]:
                html += f"""
        <h4 id="attention-poor" style="color: #e74c3c; margin: 15px 0 8px 0;">较差评分（共 {len(categories["poor"])} 个）</h4>
        <div class="attention-list">
"""
                for idx, result in categories["poor"]:
                    q_text = result.get("question", "")[:80]
                    score = result.get("evaluation", {}).get("overall_score", 0)
                    html += f"""            <a href="#q-{idx}" class="attention-item">
                <span class="q-num">问题 {idx}</span>
                <span class="q-text">{q_text}...</span>
                <span class="q-score poor">{score:.2f}</span>
            </a>
"""
                html += "        </div>\n"
            
            if categories["fair"]:
                html += f"""
        <h4 id="attention-fair" style="color: #f39c12; margin: 15px 0 8px 0;">一般评分（共 {len(categories["fair"])} 个）</h4>
        <div class="attention-list">
"""
                for idx, result in categories["fair"]:
                    q_text = result.get("question", "")[:80]
                    score = result.get("evaluation", {}).get("overall_score", 0)
                    html += f"""            <a href="#q-{idx}" class="attention-item">
                <span class="q-num">问题 {idx}</span>
                <span class="q-text">{q_text}...</span>
                <span class="q-score fair">{score:.2f}</span>
            </a>
"""
                html += "        </div>\n"
            
            html += "    </div>\n"
        
        html += """
    <h2>第二部分：详细问答</h2>
    <div class="qa-section">
"""
        
        # 添加每个问答
        for i, result in enumerate(results, 1):
            question = result.get("question", "").replace("<", "&lt;").replace(">", "&gt;")
            raw_answer = result.get("answer", "")
            # 使用Markdown渲染答案
            answer_html = self._render_markdown(raw_answer)
            success = result.get("success", False)
            response_time = result.get("response_time", 0)
            
            eval_data = result.get("evaluation", {})
            overall = eval_data.get("overall_score", 0)
            accuracy = eval_data.get("accuracy", 0)
            relevance = eval_data.get("relevance", 0)
            completeness = eval_data.get("completeness", 0)
            citation = eval_data.get("citation_quality", 0)
            
            # 确定评分等级
            score_class = self._get_score_class(overall)
            
            reference = result.get("reference", {})
            doc_aggs = reference.get("doc_aggs", [])
            
            # 添加锚点ID用于跳转
            html += f"""
        <div class="qa-item" id="q-{i}">
            <div class="qa-header">
                <span class="id">问题 {i}</span>
                <span class="scores">
                    总分: <span class="score-badge {score_class}">{overall:.2f}</span>
                </span>
            </div>
            <div class="qa-body">
                <div class="question">Q: {question}</div>
                <div class="answer">{answer_html}</div>
"""
            
            if doc_aggs:
                html += """                <div class="references">
                    <strong>引用文档:</strong>
                    <ul>
"""
                for doc in doc_aggs[:5]:  # 最多显示5个
                    html += f"                        <li>{doc.get('doc_name', 'Unknown')} ({doc.get('count', 0)} chunks)</li>\n"
                html += """                    </ul>
                </div>
"""
            
            html += f"""
                <div class="score-details">
                    <div class="score-detail"><span class="label">准确性</span><br><span class="value">{accuracy:.1f}</span></div>
                    <div class="score-detail"><span class="label">相关性</span><br><span class="value">{relevance:.1f}</span></div>
                    <div class="score-detail"><span class="label">完整性</span><br><span class="value">{completeness:.1f}</span></div>
                    <div class="score-detail"><span class="label">引用质量</span><br><span class="value">{citation:.1f}</span></div>
                </div>
                <div class="response-time">
                    <span class="status-badge {'success' if success else 'failed'}">{'成功' if success else '失败'}</span>
                    响应时间: {response_time:.2f}s
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


def main():
    """命令行入口"""
    import sys
    
    results_file = sys.argv[1] if len(sys.argv) > 1 else "test_output/test_results.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    generator = FullReportGenerator()
    generator.generate(results_file, output_file)


if __name__ == "__main__":
    main()

