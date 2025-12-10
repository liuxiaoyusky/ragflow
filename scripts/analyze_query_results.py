#!/usr/bin/env python3
"""
分析RagFlow查询结果，记录详细的chunk信息和分数分布
"""

import json
import sys
import re
from datetime import datetime
from typing import List, Dict

API_URL = "https://10.1.9.133:8443/api/v1/retrieval"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"

def query_ragflow(question: str, top_n: int = 30) -> List[Dict]:
    """查询RagFlow API"""
    import requests
    
    payload = {
        "question": question,
        "dataset_ids": [DATASET_ID],
        "top_n": top_n,
        "metadata_condition": {
            "logic": "and",
            "conditions": [
                {"name": "fund_name", "comparison_operator": "=", "value": "Asian Income Fund"}
            ]
        }
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(API_URL, json=payload, headers=headers, verify=False)
    response.raise_for_status()
    data = response.json()
    return data.get('data', {}).get('chunks', [])

def analyze_chunks(chunks: List[Dict], query_name: str) -> Dict:
    """分析chunks并分类"""
    holdings_equities = []
    holdings_fixed_income = []
    other_chunks = []
    
    for i, chunk in enumerate(chunks):
        doc = chunk.get('document_keyword', '')
        kw = str(chunk.get('important_keywords', [])).lower()
        content = chunk.get('content', '')
        score = chunk.get('similarity', 0)
        chunk_id = chunk.get('chunk_id', '')
        
        month_match = re.search(r'(January|February|March|April|May|June|July|August|September)\s+2025', content)
        month = month_match.group(0) if month_match else None
        
        chunk_info = {
            'rank': i + 1,
            'chunk_id': chunk_id,
            'document': doc,
            'score': score,
            'month': month,
            'keywords': chunk.get('important_keywords', []),
            'content_preview': content[:200] + '...' if len(content) > 200 else content
        }
        
        if 'holdings' in kw:
            if 'equities' in kw:
                holdings_equities.append(chunk_info)
            elif 'fixed income' in kw:
                holdings_fixed_income.append(chunk_info)
        else:
            other_chunks.append(chunk_info)
    
    return {
        'query_name': query_name,
        'total_chunks': len(chunks),
        'holdings_equities': holdings_equities,
        'holdings_fixed_income': holdings_fixed_income,
        'other_chunks': other_chunks,
        'holdings_equities_count': len(holdings_equities),
        'holdings_fixed_income_count': len(holdings_fixed_income),
        'other_chunks_count': len(other_chunks)
    }

def calculate_score_gap(analysis: Dict) -> Dict:
    """计算分数差距"""
    holdings_scores = []
    other_scores = []
    
    for chunk in analysis['holdings_equities'] + analysis['holdings_fixed_income']:
        holdings_scores.append(chunk['score'])
    
    for chunk in analysis['other_chunks']:
        other_scores.append(chunk['score'])
    
    if not holdings_scores or not other_scores:
        return {}
    
    holdings_avg = sum(holdings_scores) / len(holdings_scores)
    other_avg = sum(other_scores) / len(other_scores)
    gap = holdings_avg - other_avg
    
    return {
        'holdings_avg': holdings_avg,
        'holdings_min': min(holdings_scores),
        'holdings_max': max(holdings_scores),
        'other_avg': other_avg,
        'other_min': min(other_scores),
        'other_max': max(other_scores),
        'gap': gap,
        'gap_percentage': (gap / other_avg * 100) if other_avg > 0 else 0
    }

def generate_report(analyses: List[Dict], output_file: str):
    """生成详细报告"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# RagFlow Query Analysis Report\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        for analysis in analyses:
            f.write(f"## {analysis['query_name']}\n\n")
            f.write(f"### 统计信息\n\n")
            f.write(f"- 总chunks: {analysis['total_chunks']}\n")
            f.write(f"- Top holdings - equities: {analysis['holdings_equities_count']}\n")
            f.write(f"- Top holdings - fixed income: {analysis['holdings_fixed_income_count']}\n")
            f.write(f"- 其他类型: {analysis['other_chunks_count']}\n\n")
            
            # 分数差距分析
            score_gap = calculate_score_gap(analysis)
            if score_gap:
                f.write(f"### 分数差距分析\n\n")
                f.write(f"- Top holdings平均分: {score_gap['holdings_avg']:.4f}\n")
                f.write(f"- Top holdings范围: {score_gap['holdings_min']:.4f} - {score_gap['holdings_max']:.4f}\n")
                f.write(f"- 其他类型平均分: {score_gap['other_avg']:.4f}\n")
                f.write(f"- 其他类型范围: {score_gap['other_min']:.4f} - {score_gap['other_max']:.4f}\n")
                f.write(f"- **平均差距: {score_gap['gap']:.4f} ({score_gap['gap_percentage']:.2f}%)**\n\n")
            
            # Top holdings - equities
            f.write(f"### Top holdings - equities (详细)\n\n")
            for chunk in analysis['holdings_equities']:
                f.write(f"**Rank {chunk['rank']}** | Score: {chunk['score']:.4f} | {chunk['month']}\n")
                f.write(f"- Document: `{chunk['document']}`\n")
                f.write(f"- Keywords: {chunk['keywords']}\n")
                f.write(f"- Content preview: {chunk['content_preview']}\n\n")
            
            # Top holdings - fixed income
            f.write(f"### Top holdings - fixed income (详细)\n\n")
            for chunk in analysis['holdings_fixed_income']:
                f.write(f"**Rank {chunk['rank']}** | Score: {chunk['score']:.4f} | {chunk['month']}\n")
                f.write(f"- Document: `{chunk['document']}`\n")
                f.write(f"- Keywords: {chunk['keywords']}\n")
                f.write(f"- Content preview: {chunk['content_preview']}\n\n")
            
            # 其他类型chunks
            f.write(f"### 其他类型chunks (详细)\n\n")
            for chunk in analysis['other_chunks'][:10]:  # 只显示前10个
                f.write(f"**Rank {chunk['rank']}** | Score: {chunk['score']:.4f}\n")
                f.write(f"- Document: `{chunk['document']}`\n")
                f.write(f"- Keywords: {chunk['keywords']}\n")
                f.write(f"- Content preview: {chunk['content_preview']}\n\n")
            
            f.write("---\n\n")
        
        # 对比总结
        if len(analyses) == 2:
            f.write("## 对比总结\n\n")
            gap1 = calculate_score_gap(analyses[0])
            gap2 = calculate_score_gap(analyses[1])
            
            if gap1 and gap2:
                f.write(f"| 指标 | {analyses[0]['query_name']} | {analyses[1]['query_name']} |\n")
                f.write(f"|------|----------------|----------------|\n")
                f.write(f"| Top holdings平均分 | {gap1['holdings_avg']:.4f} | {gap2['holdings_avg']:.4f} |\n")
                f.write(f"| 其他类型平均分 | {gap1['other_avg']:.4f} | {gap2['other_avg']:.4f} |\n")
                f.write(f"| **分数差距** | **{gap1['gap']:.4f}** | **{gap2['gap']:.4f}** |\n")
                f.write(f"| **差距百分比** | **{gap1['gap_percentage']:.2f}%** | **{gap2['gap_percentage']:.2f}%** |\n\n")
                
                if gap2['gap'] > gap1['gap']:
                    f.write(f"**结论**: {analyses[1]['query_name']} 的分数差距更大，更有利于区分想要的chunk。\n")
                else:
                    f.write(f"**结论**: {analyses[0]['query_name']} 的分数差距更大，更有利于区分想要的chunk。\n")

def main():
    queries = [
        {
            'name': '查询1: 带括号展开版本',
            'question': 'What are top holdings of Asian Income Fund from January to September 2025 (months: January 2025, February 2025, March 2025, April 2025, May 2025, June 2025, July 2025, August 2025, September 2025)'
        },
        {
            'name': '查询2: 原始版本（不带括号）',
            'question': 'What are top holdings of Asian Income Fund from January to September 2025'
        }
    ]
    
    analyses = []
    for query in queries:
        print(f"正在查询: {query['name']}...")
        chunks = query_ragflow(query['question'])
        analysis = analyze_chunks(chunks, query['name'])
        analyses.append(analysis)
        print(f"  完成: {analysis['total_chunks']} chunks")
    
    # 生成报告
    output_file = 'query_analysis_detailed.md'
    generate_report(analyses, output_file)
    print(f"\n详细报告已保存到: {output_file}")
    
    # 打印分数差距对比
    print("\n=== 分数差距对比 ===")
    for analysis in analyses:
        gap = calculate_score_gap(analysis)
        if gap:
            print(f"\n{analysis['query_name']}:")
            print(f"  Top holdings平均分: {gap['holdings_avg']:.4f}")
            print(f"  其他类型平均分: {gap['other_avg']:.4f}")
            print(f"  分数差距: {gap['gap']:.4f} ({gap['gap_percentage']:.2f}%)")

if __name__ == '__main__':
    main()

