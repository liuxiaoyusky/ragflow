#!/usr/bin/env python3
"""
测试多种Query Enhancement策略
"""

import json
import requests
import warnings
warnings.filterwarnings('ignore')

API_URL = "https://10.1.9.133:8443/api/v1/retrieval"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"

# 定义测试策略
STRATEGIES = {
    "baseline": "What are top holdings of Asian Income Fund from January to September 2025",
    
    "strategy_A": "What are top holdings top holdings top holdings of Asian Income Fund from January to September 2025 equities fixed income",
    
    "strategy_B": "What are top holdings of Asian Income Fund January 2025, February 2025, March 2025, April 2025, May 2025, June 2025, July 2025, August 2025, September 2025",
    
    "strategy_C": "top holdings equities fixed income Asian Income Fund January February March April May June July August September 2025",
    
    "strategy_D": "Asian Income Fund top holdings top holdings equities fixed income January February March April May June July August September 2025 NOT performance NOT investment NOT credit NOT asset NOT portfolio",
    
    "strategy_E": "top holdings equities Asian Income Fund 2025",
    
    "strategy_F": "What are the top 5 stock holdings and top 5 bond holdings of Asian Income Fund from January to September 2025",
}

def query_ragflow(question: str, top_n: int = 30) -> list:
    """查询RagFlow API"""
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

def analyze_strategy(name: str, question: str) -> dict:
    """分析单个策略的结果"""
    chunks = query_ragflow(question)
    
    wanted_scores = []
    unwanted_scores = []
    wanted_chunks = []
    unwanted_chunks = []
    
    for i, c in enumerate(chunks):
        kw_str = str(c.get('important_keywords', [])).lower()
        score = c.get('similarity', 0)
        doc = c.get('document_keyword', '')
        
        chunk_info = {
            'rank': i + 1,
            'doc': doc,
            'score': score,
            'keywords': c.get('important_keywords', [])
        }
        
        if 'holdings' in kw_str:
            wanted_scores.append(score)
            wanted_chunks.append(chunk_info)
        else:
            unwanted_scores.append(score)
            unwanted_chunks.append(chunk_info)
    
    if not wanted_scores:
        wanted_scores = [0]
    if not unwanted_scores:
        unwanted_scores = [0]
    
    wanted_avg = sum(wanted_scores) / len(wanted_scores)
    unwanted_avg = sum(unwanted_scores) / len(unwanted_scores) if unwanted_scores else 0
    gap = wanted_avg - unwanted_avg
    gap_pct = (gap / unwanted_avg * 100) if unwanted_avg > 0 else float('inf')
    
    # 计算UNWANTED最高分排名
    if unwanted_chunks:
        unwanted_top_rank = min(c['rank'] for c in unwanted_chunks)
    else:
        unwanted_top_rank = 31  # 不在前30
    
    return {
        'name': name,
        'question': question,
        'wanted_count': len(wanted_chunks),
        'unwanted_count': len(unwanted_chunks),
        'wanted_avg': wanted_avg,
        'wanted_max': max(wanted_scores),
        'wanted_min': min(wanted_scores),
        'unwanted_avg': unwanted_avg,
        'unwanted_max': max(unwanted_scores) if unwanted_scores else 0,
        'unwanted_min': min(unwanted_scores) if unwanted_scores else 0,
        'gap': gap,
        'gap_pct': gap_pct,
        'unwanted_top_rank': unwanted_top_rank,
        'wanted_chunks': wanted_chunks,
        'unwanted_chunks': unwanted_chunks
    }

def main():
    results = []
    
    print("=" * 100)
    print("测试多种Query Enhancement策略")
    print("=" * 100)
    print()
    
    for name, question in STRATEGIES.items():
        print(f"测试 {name}...")
        result = analyze_strategy(name, question)
        results.append(result)
        
        print(f"  WANTED: {result['wanted_count']}, UNWANTED: {result['unwanted_count']}")
        print(f"  Gap: {result['gap']:.4f} ({result['gap_pct']:.2f}%)")
        print(f"  UNWANTED最高排名: Rank {result['unwanted_top_rank']}")
        print()
    
    # 打印对比表格
    print("=" * 100)
    print("策略对比表")
    print("=" * 100)
    print(f"{'策略':<15} {'WANTED数':<10} {'UNWANTED数':<12} {'WANTED均分':<12} {'UNWANTED均分':<14} {'差距':<10} {'差距%':<10} {'UNWANTED首位':<12}")
    print("-" * 100)
    
    for r in results:
        print(f"{r['name']:<15} {r['wanted_count']:<10} {r['unwanted_count']:<12} {r['wanted_avg']:.4f}      {r['unwanted_avg']:.4f}        {r['gap']:.4f}    {r['gap_pct']:.2f}%    Rank {r['unwanted_top_rank']}")
    
    # 找出最优策略
    print()
    print("=" * 100)
    print("最优策略分析")
    print("=" * 100)
    
    # 按差距百分比排序
    sorted_by_gap = sorted(results, key=lambda x: x['gap_pct'], reverse=True)
    print(f"\n按差距百分比排序 (越大越好):")
    for i, r in enumerate(sorted_by_gap[:3]):
        print(f"  {i+1}. {r['name']}: {r['gap_pct']:.2f}%")
    
    # 按UNWANTED首位排名排序
    sorted_by_rank = sorted(results, key=lambda x: x['unwanted_top_rank'], reverse=True)
    print(f"\n按UNWANTED首位排名排序 (越靠后越好):")
    for i, r in enumerate(sorted_by_rank[:3]):
        print(f"  {i+1}. {r['name']}: Rank {r['unwanted_top_rank']}")
    
    # 保存详细结果到文件
    with open('/home/calvin/github/ragflow/query_strategy_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: query_strategy_results.json")
    
    return results

if __name__ == '__main__':
    main()
