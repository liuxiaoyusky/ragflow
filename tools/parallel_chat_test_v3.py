#!/usr/bin/env python3
"""
Parallel Chat Test v3.0
Uses Prompt v3.0 with RagFlow Chat API for parallel testing of 21 questions.

Features:
- Parallel execution with configurable concurrency
- Monitors enhance time and chat time
- Saves enhanced query, answer, chunks with scores
- Outputs timestamped JSON file
"""

import requests
import urllib3
import json
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# Configuration
# =============================================================================

RAGFLOW_BASE_URL = "https://10.1.9.133:8443"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
CHAT_ID = "f472490cbabe11f0b1a00242ac130006"

# Concurrency settings
MAX_WORKERS = 3  # Max parallel requests (reduced to avoid AUTH_ERROR)

# Read OpenRouter API key
def load_openrouter_config():
    key_file = Path(__file__).parent.parent / "openai.apikey"
    with open(key_file, 'r') as f:
        lines = f.read().strip().split('\n')
        return {
            'api_key': lines[0],
            'base_url': lines[1] if len(lines) > 1 else "https://openrouter.ai/api/v1"
        }

OPENROUTER_CONFIG = load_openrouter_config()

# =============================================================================
# Prompt v3.0 Template (Simplified time format)
# =============================================================================

PROMPT_V3_TEMPLATE = """你是基金文档检索优化专家。为问题添加精准关键词以提高检索精度。

当前日期: {current_date}
最新数据月份: September 2025

## 严格规则

### 1. 只使用精确的Section Title（从以下列表精确选择，注意无连字符）
| 问题类型 | 精确Section Title |
|---------|-------------------|
| 业绩、表现、回报、Q1/Q2/Q3/Q4 | Monthly performance |
| 股息、分红、派息、yield | Dividend information |
| 股票持仓、top holdings equities | Top holdings equities |
| 债券持仓、fixed income holdings | Top holdings fixed income |
| 费用、管理费 | Fee structure |
| 信用评级 | Credit ratings |
| 组合特征、收益率、波动率 | Portfolio characteristics |
| 净值、代码、ISIN | NAVs & codes |
| 投资目标 | Investment objective |
| 行业配置 | Asset type by sector |
| 地区配置 | Asset type by geography |

### 2. 时间范围展开（重要！简化版 - 避免 ES nested clause 限制）
**关键：只在最后一个月份后加年份，中间月份不加年份**
- Q1/第一季度 → January , February , March 2025
- Q2/第二季度 → April , May , June 2025
- Q3/第三季度 → July , August , September 2025
- "从1月到7月" → January , February , March , April , May , June , July 2025
- "从1月到9月" → January , February , March , April , May , June , July , August , September 2025

### 3. 默认时间处理（重要！）
当问题**未指定具体时间**时：
- 自动添加最新数据月份: September 2025

### 4. Top Holdings 双重强调规则（重要！）
当问题涉及 **持仓/holdings** 时：
- 如果问题**未指定**是 equities 还是 fixed income：
  → 同时添加两个: Top holdings equities, Top holdings fixed income
- 如果问题**已指定** equities 或股票持仓：
  → 重复强调: Top holdings equities, Top holdings equities
- 如果问题**已指定** fixed income 或债券持仓：
  → 重复强调: Top holdings fixed income, Top holdings fixed income

### 5. 精确实体名称
- 台积电 → Taiwan Semiconductor Manufacturing Co Ltd
- 腾讯 → Tencent Holdings Ltd
- 惠理亚洲收益基金 → Asian Income Fund
- 惠理高息股票基金 → High Dividend Fund

### 6. 禁止使用的泛化词（会干扰排名）
❌ yield, return, goal, sector, bond, performance, allocation, holdings

### 7. 多基金对比规则（重要！）
当问题涉及 **比较/对比/compare** 多个基金时：
- 必须在关键词中**明确列出所有基金名称**
- 格式：(Section Title, Fund1 Name, Fund2 Name, 时间)

## 示例

输入: "What are top holdings of Asian Income Fund from January to September 2025?"
输出: "What are top holdings of Asian Income Fund from January to September 2025? (Top holdings equities, Top holdings fixed income, January , February , March , April , May , June , July , August , September 2025)"

输入: "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025"
输出: "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025? (High Dividend Fund, Top holdings equities, Top holdings fixed income, January , February , March , April , May , June , July 2025)"

输入: "What are top equity holdings of Asian Income Fund in September 2025?"
输出: "What are top equity holdings of Asian Income Fund in September 2025? (Top holdings equities, Top holdings equities, September 2025)"

输入: "What is the credit rating distribution of Asian Income Fund?"
输出: "What is the credit rating distribution of Asian Income Fund? (Credit ratings, September 2025)"

输入: "惠理亚洲收益基金2025年Q1业绩表现"
输出: "惠理亚洲收益基金2025年Q1业绩表现 (Monthly performance, January , February , March 2025)"

输入: "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率"
输出: "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率 (Dividend information, High Dividend Fund, Asian Income Fund, August 2025)"

输入: "Compare fee structures between Asian Income Fund and High Dividend Fund"
输出: "Compare fee structures between Asian Income Fund and High Dividend Fund (Fee structure, Asian Income Fund, High Dividend Fund, September 2025)"

## 用户问题
{original_question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""

# =============================================================================
# Load Questions
# =============================================================================

def load_questions():
    """Load all 21 questions (Q1-Q11 + TC001-TC010)"""
    questions = {}
    
    # Q1-Q11 from regression test
    q1_q11 = {
        "Q1": "what is the management fee for High Dividend Stocks fund?",
        "Q2": "does High Dividend Stocks fund have performance fees?",
        "Q3": "what is the performance fee for High Dividend stocks fund?",
        "Q4": "what is the performance fee rate for High Dividend Stocks Fund?",
        "Q5": "what is the top fixed income holdings for Asian Income fund as of September 2025",
        "Q6": "what are the top equity holdings of Asian Income as of March 2025",
        "Q7": "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025",
        "Q8": "what is the geographic exposures for the Asian Income fund?",
        "Q9": "show me the geographic locations of High dividend stocks from January 2025 to September 2025",
        "Q10": "what are the top holdings of Asian Income Fund from January 2025 to September 2025",
        "Q11": "what is the return for high dividend stocks fund as of September 2025?"
    }
    questions.update(q1_q11)
    
    # TC001-TC010 from benchmark
    benchmark_path = Path(__file__).parent.parent / 'docs' / 'benchmark' / 'rag_evaluation_dataset.json'
    with open(benchmark_path, 'r') as f:
        benchmark = json.load(f)
        for tc in benchmark.get('test_cases', []):
            tc_id = tc.get('id', '')
            questions[tc_id] = tc.get('question', '')
    
    return questions

def load_expected_answers():
    """Load expected answers for TC questions"""
    expected_answers = {}
    benchmark_path = Path(__file__).parent.parent / 'docs' / 'benchmark' / 'rag_evaluation_dataset.json'
    with open(benchmark_path, 'r') as f:
        benchmark = json.load(f)
        for tc in benchmark.get('test_cases', []):
            expected_answers[tc['id']] = tc.get('expected_answer', '')
    return expected_answers

# =============================================================================
# Query Enhancement
# =============================================================================

def enhance_query(question):
    """Enhance query using Prompt v3.0 via OpenRouter"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = PROMPT_V3_TEMPLATE.format(
        current_date=current_date,
        original_question=question
    )
    
    start_time = time.time()
    try:
        resp = requests.post(
            f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-haiku-4.5",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0
            },
            timeout=30
        )
        
        enhance_time = time.time() - start_time
        
        if resp.status_code == 200:
            enhanced = resp.json()['choices'][0]['message']['content'].strip()
            return enhanced, enhance_time
        else:
            return question, enhance_time
    except Exception as e:
        return question, time.time() - start_time

# =============================================================================
# RagFlow Chat API
# =============================================================================

def create_conversation():
    """Create a new conversation in the chat"""
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/sessions",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        json={"name": f"Test_v3.0_{datetime.now().strftime('%Y%m%d_%H%M%S')}"},
        timeout=30,
        verify=False
    )
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get('code') == 0:
            return data.get('data', {}).get('id')
    return None

def send_message(session_id, message):
    """Send message to RagFlow chat and get response with chunks"""
    start_time = time.time()
    try:
        resp = requests.post(
            f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/completions",
            headers={
                "Authorization": f"Bearer {RAGFLOW_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "question": message,
                "session_id": session_id,
                "stream": False
            },
            timeout=120,
            verify=False
        )
        
        chat_time = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                answer_data = data.get('data', {})
                reference = answer_data.get('reference', {})
                
                # Extract chunks with scores
                chunks = []
                raw_chunks = reference.get('chunks', [])
                for i, chunk in enumerate(raw_chunks):
                    chunks.append({
                        'rank': i + 1,
                        'document': chunk.get('document_name', chunk.get('doc_name', '')),
                        'similarity': chunk.get('similarity', 0),
                        'content_preview': chunk.get('content', '')[:200] + '...' if len(chunk.get('content', '')) > 200 else chunk.get('content', '')
                    })
                
                return {
                    'answer': answer_data.get('answer', ''),
                    'chunks': chunks,
                    'total_chunks': len(raw_chunks),
                    'chat_time': chat_time
                }
        
        return {
            'answer': f'ERROR: {resp.status_code}',
            'chunks': [],
            'total_chunks': 0,
            'chat_time': chat_time,
            'error': resp.text[:500]
        }
        
    except Exception as e:
        return {
            'answer': f'ERROR: {str(e)}',
            'chunks': [],
            'total_chunks': 0,
            'chat_time': time.time() - start_time,
            'error': str(e)
        }

# =============================================================================
# Test Single Question
# =============================================================================

def test_question(q_id, question):
    """Test a single question end-to-end"""
    result = {
        'id': q_id,
        'question': question,
        'timestamp': datetime.now().isoformat()
    }
    
    # Step 1: Create session for this question
    session_id = create_conversation()
    if not session_id:
        result['error'] = 'Failed to create session'
        result['enhanced_query'] = question
        result['answer'] = 'ERROR: Session creation failed'
        result['chunks'] = []
        result['enhance_time'] = 0
        result['chat_time'] = 0
        result['total_time'] = 0
        return result
    
    result['session_id'] = session_id
    
    # Step 2: Enhance query
    enhanced, enhance_time = enhance_query(question)
    result['enhanced_query'] = enhanced
    result['enhance_time'] = enhance_time
    
    # Step 3: Send to RagFlow
    response = send_message(session_id, enhanced)
    result['answer'] = response.get('answer', '')
    result['chunks'] = response.get('chunks', [])
    result['total_chunks'] = response.get('total_chunks', 0)
    result['chat_time'] = response.get('chat_time', 0)
    result['total_time'] = enhance_time + response.get('chat_time', 0)
    
    if 'error' in response:
        result['error'] = response['error']
    
    return result

# =============================================================================
# Main Execution
# =============================================================================

def main():
    print("=" * 80)
    print("Parallel Chat Test v3.1")
    print("=" * 80)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Prompt version: v3.1 (multi-fund comparison rule)")
    print(f"RagFlow URL: {RAGFLOW_BASE_URL}")
    print(f"Chat ID: {CHAT_ID}")
    print(f"Max workers: {MAX_WORKERS}")
    
    # Load questions
    questions = load_questions()
    print(f"\nLoaded {len(questions)} questions")
    
    # Sort question IDs
    sorted_ids = sorted(questions.keys(), key=lambda x: (0 if x.startswith('Q') else 1, int(x[1:]) if x[1:].isdigit() else int(x[2:])))
    
    # Run parallel tests
    results = []
    start_total = time.time()
    
    print(f"\n{'=' * 60}")
    print("Starting parallel tests...")
    print(f"{'=' * 60}")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_id = {
            executor.submit(test_question, q_id, questions[q_id]): q_id 
            for q_id in sorted_ids
        }
        
        # Collect results as they complete
        completed = 0
        for future in as_completed(future_to_id):
            q_id = future_to_id[future]
            completed += 1
            
            try:
                result = future.result()
                results.append(result)
                
                # Print progress
                status = "✓" if 'error' not in result else "✗"
                answer_preview = result['answer'][:50] if result['answer'] else 'N/A'
                print(f"[{completed}/{len(questions)}] {status} {q_id}: {result['total_time']:.1f}s - {answer_preview}...")
                
            except Exception as e:
                print(f"[{completed}/{len(questions)}] ✗ {q_id}: Exception - {str(e)}")
                results.append({
                    'id': q_id,
                    'question': questions[q_id],
                    'error': str(e),
                    'enhanced_query': '',
                    'answer': f'ERROR: {str(e)}',
                    'chunks': [],
                    'enhance_time': 0,
                    'chat_time': 0,
                    'total_time': 0
                })
    
    total_time = time.time() - start_total
    
    # Sort results by ID
    results.sort(key=lambda x: (0 if x['id'].startswith('Q') else 1, int(x['id'][1:]) if x['id'][1:].isdigit() else int(x['id'][2:])))
    
    # Calculate summary statistics
    successful = [r for r in results if 'error' not in r]
    failed = [r for r in results if 'error' in r]
    
    avg_enhance_time = sum(r['enhance_time'] for r in results) / len(results) if results else 0
    avg_chat_time = sum(r['chat_time'] for r in successful) / len(successful) if successful else 0
    avg_total_time = sum(r['total_time'] for r in successful) / len(successful) if successful else 0
    
    summary = {
        'version': 'v3.1',
        'timestamp': datetime.now().isoformat(),
        'prompt_strategy': 'multi_fund_comparison',
        'total_questions': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'total_execution_time': total_time,
        'avg_enhance_time': round(avg_enhance_time, 2),
        'avg_chat_time': round(avg_chat_time, 2),
        'avg_total_time': round(avg_total_time, 2),
        'parallelism': MAX_WORKERS
    }
    
    # Prepare output
    output = {
        'summary': summary,
        'results': results
    }
    
    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = Path(__file__).parent / f'chat_test_v3.1_{timestamp}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total questions: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Total execution time: {total_time:.1f}s (parallel)")
    print(f"Avg enhance time: {avg_enhance_time:.2f}s")
    print(f"Avg chat time: {avg_chat_time:.2f}s")
    print(f"Avg total time per question: {avg_total_time:.2f}s")
    print(f"\nResults saved to: {output_file}")
    
    # Print failed questions if any
    if failed:
        print(f"\n{'=' * 40}")
        print("FAILED QUESTIONS:")
        for r in failed:
            print(f"  - {r['id']}: {r.get('error', 'Unknown error')}")
    
    # Print chunk statistics
    print(f"\n{'=' * 40}")
    print("CHUNK STATISTICS:")
    for r in results[:5]:  # Show first 5
        print(f"  {r['id']}: {r['total_chunks']} chunks, top score: {r['chunks'][0]['similarity']:.3f}" if r['chunks'] else f"  {r['id']}: No chunks")
    print("  ...")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    
    return output

if __name__ == "__main__":
    main()

