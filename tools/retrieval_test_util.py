#!/usr/bin/env python3
"""
Retrieval Test Utility
Reusable functions for testing RagFlow retrieval with query enhancement.

Usage:
    # Single question test
    python retrieval_test_util.py --question "What is the credit rating distribution of Asian Income Fund?"
    
    # Batch test all 21 questions
    python retrieval_test_util.py --batch
    
    # Test specific question ID
    python retrieval_test_util.py --id TC004
"""

import requests
import json
import argparse
from datetime import datetime
from pathlib import Path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === Configuration ===
RAGFLOW_BASE_URL = "https://10.1.9.133:8443"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"  # factsheets_tables (275 docs)

# OpenRouter API key loaded from file
def load_openrouter_key():
    key_file = Path(__file__).parent.parent / "openai.apikey"
    with open(key_file, 'r') as f:
        return f.readline().strip()

OPENROUTER_API_KEY = None  # Loaded on demand

# === Prompt Configuration ===
LATEST_DATA_MONTH = "September 2025"

def get_enhancement_prompt(question: str, latest_month: str = LATEST_DATA_MONTH) -> str:
    """Get the query enhancement prompt with default time handling."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return f"""你是基金文档检索优化专家。为问题添加精准关键词以提高检索精度。

当前日期: {current_date}
最新数据月份: {latest_month}

## 严格规则

### 1. 只使用精确的Section Title（从以下列表精确选择）
| 问题类型 | 精确Section Title |
|---------|-------------------|
| 业绩、表现、回报、Q1/Q2/Q3/Q4 | Monthly performance |
| 股息、分红、派息、yield | Dividend information |
| 股票持仓、top holdings | Top holdings - equities |
| 债券持仓、fixed income | Top holdings - fixed income |
| 费用、管理费 | Fee structure |
| 信用评级 | Credit ratings |
| 组合特征、收益率、波动率 | Portfolio characteristics |
| 净值、代码、ISIN | NAVs & codes |
| 投资目标 | Investment objective |
| 行业配置 | Asset type by sector |
| 地区配置 | Asset type by geography |

### 2. 时间范围展开（重要！）
- Q1/第一季度 → January 2025, February 2025, March 2025
- Q2/第二季度 → April 2025, May 2025, June 2025
- Q3/第三季度 → July 2025, August 2025, September 2025
- "从1月到9月" → January, February, March, April, May, June, July, August, September

### 3. 默认时间处理（重要！）
当问题**未指定具体时间**时：
- 自动添加最新数据月份: {latest_month}

### 4. 精确实体名称
- 台积电 → Taiwan Semiconductor Manufacturing Co Ltd
- 腾讯 → Tencent Holdings Ltd
- 惠理亚洲收益基金 → Asian Income Fund
- 惠理高息股票基金 → High Dividend Fund

### 5. 禁止使用的泛化词（会干扰排名）
❌ yield, return, goal, sector, bond, performance, allocation, holdings

## 用户问题
{question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""


def enhance_query(question: str, model: str = "anthropic/claude-haiku-4.5") -> str:
    """Enhance a query using LLM with the optimization prompt."""
    global OPENROUTER_API_KEY
    if OPENROUTER_API_KEY is None:
        OPENROUTER_API_KEY = load_openrouter_key()
    
    prompt = get_enhancement_prompt(question)
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500
        },
        timeout=60
    )
    
    result = response.json()
    if 'choices' in result:
        return result['choices'][0]['message']['content'].strip()
    return question


def retrieve_chunks(query: str, top_k: int = 30, keyword_weight: float = 0.7) -> list:
    """Retrieve chunks from RagFlow."""
    response = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/retrieval",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        json={
            "question": query,
            "dataset_ids": [DATASET_ID],
            "similarity_threshold": 0.0,
            "top_k": top_k,
            "keyword_similarity_weight": keyword_weight
        },
        timeout=60,
        verify=False
    )
    
    data = response.json()
    if data.get('code') == 0:
        return data.get('data', {}).get('chunks', [])
    else:
        print(f"API Error: {data.get('message')}")
        return []


def analyze_results(chunks: list, expected_chunks: list = None) -> dict:
    """Analyze retrieval results against expected chunks."""
    result = {
        'total_chunks': len(chunks),
        'top_chunks': []
    }
    
    for i, c in enumerate(chunks[:10]):
        doc = c.get('document_keyword', c.get('document_name', ''))
        result['top_chunks'].append({
            'rank': i + 1,
            'document': doc,
            'similarity': c.get('similarity', 0)
        })
    
    if expected_chunks:
        first_rank = None
        matched = set()
        
        for i, c in enumerate(chunks):
            doc = c.get('document_keyword', c.get('document_name', ''))
            for exp in expected_chunks:
                if exp.replace('.md', '') in doc:
                    if first_rank is None:
                        first_rank = i + 1
                    matched.add(exp)
        
        result['first_relevant_rank'] = first_rank
        result['matched_count'] = len(matched)
        result['expected_count'] = len(expected_chunks)
        result['coverage'] = len(matched) / len(expected_chunks) * 100 if expected_chunks else 0
    
    return result


def test_single_question(question: str, expected_chunks: list = None, verbose: bool = True) -> dict:
    """Test a single question end-to-end."""
    if verbose:
        print(f"\nQuestion: {question[:60]}...")
    
    # Enhance
    enhanced = enhance_query(question)
    if verbose:
        print(f"Enhanced: {enhanced[:70]}...")
    
    # Retrieve
    chunks = retrieve_chunks(enhanced)
    if verbose:
        print(f"Retrieved: {len(chunks)} chunks")
    
    # Analyze
    analysis = analyze_results(chunks, expected_chunks)
    
    if verbose and expected_chunks:
        rank = analysis.get('first_relevant_rank')
        cov = analysis.get('coverage', 0)
        print(f"First Rank: #{rank if rank else 'N/A'} | Coverage: {cov:.0f}%")
        
        print("Top 5 chunks:")
        for c in analysis['top_chunks'][:5]:
            mark = "✓" if any(exp.replace('.md', '') in c['document'] for exp in expected_chunks) else ""
            print(f"  #{c['rank']} [{c['similarity']:.3f}] {c['document'][:45]} {mark}")
    
    return {
        'question': question,
        'enhanced': enhanced,
        'chunks_count': len(chunks),
        'analysis': analysis
    }


def load_all_questions() -> list:
    """Load all 21 test questions (Q1-Q11 + TC001-TC010)."""
    base_path = Path(__file__).parent.parent
    
    # Q1-Q11 from regression test
    questions = []
    csv_path = base_path / "tools" / "regression_test_20251205.csv"
    if csv_path.exists():
        with open(csv_path, 'r') as f:
            lines = f.readlines()[1:]
            for i, line in enumerate(lines):
                parts = line.strip().split(',', 1)
                if len(parts) >= 2:
                    questions.append({
                        'id': f'Q{i+1}',
                        'question': parts[1].strip('"'),
                        'expected_chunks': []
                    })
    
    # TC001-TC010 from benchmark
    benchmark_path = base_path / "docs" / "benchmark" / "rag_evaluation_dataset.json"
    if benchmark_path.exists():
        with open(benchmark_path, 'r') as f:
            benchmark = json.load(f)
            for tc in benchmark['test_cases']:
                questions.append({
                    'id': tc['id'],
                    'question': tc['question'],
                    'expected_chunks': tc.get('expected_chunks', [])
                })
    
    return questions


def run_batch_test(output_file: str = None) -> dict:
    """Run batch test on all 21 questions."""
    questions = load_all_questions()
    print(f"Loaded {len(questions)} questions")
    
    results = []
    for q in questions:
        print(f"\n{'='*60}")
        print(f"{q['id']}: {q['question'][:50]}...")
        
        result = test_single_question(q['question'], q.get('expected_chunks', []), verbose=True)
        result['id'] = q['id']
        results.append(result)
    
    # Summary
    tc_results = [r for r in results if r['id'].startswith('TC')]
    found = sum(1 for r in tc_results if r['analysis'].get('first_relevant_rank'))
    avg_rank = sum(r['analysis']['first_relevant_rank'] for r in tc_results if r['analysis'].get('first_relevant_rank')) / found if found else 0
    avg_cov = sum(r['analysis'].get('coverage', 0) for r in tc_results) / len(tc_results) if tc_results else 0
    
    summary = {
        'timestamp': str(datetime.now()),
        'total_questions': len(results),
        'tc_found': found,
        'tc_total': len(tc_results),
        'avg_first_rank': round(avg_rank, 1),
        'avg_coverage': round(avg_cov, 1)
    }
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"TC001-TC010: Found={found}/{len(tc_results)}, Avg Rank=#{avg_rank:.1f}, Avg Coverage={avg_cov:.0f}%")
    
    output = {
        'summary': summary,
        'results': results
    }
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nSaved: {output_file}")
    
    return output


def main():
    parser = argparse.ArgumentParser(description='RagFlow Retrieval Test Utility')
    parser.add_argument('--question', '-q', help='Test a single question')
    parser.add_argument('--id', help='Test a specific question by ID (e.g., TC004)')
    parser.add_argument('--batch', '-b', action='store_true', help='Run batch test on all 21 questions')
    parser.add_argument('--output', '-o', help='Output file for results')
    
    args = parser.parse_args()
    
    if args.question:
        test_single_question(args.question, verbose=True)
    elif args.id:
        questions = load_all_questions()
        q = next((q for q in questions if q['id'] == args.id), None)
        if q:
            test_single_question(q['question'], q.get('expected_chunks', []), verbose=True)
        else:
            print(f"Question {args.id} not found")
    elif args.batch:
        output_file = args.output or str(Path(__file__).parent / "retrieval_test_results.json")
        run_batch_test(output_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()



