#!/usr/bin/env python3
"""
Retest AUTH_ERROR questions and run full evaluation for v3.1
1. Retest only specified questions (TC001, TC005, TC006, TC008, TC009, TC010)
2. Merge with previous successful results
3. Run LLM evaluation comparing RagFlow vs Feishu (parallel)
4. Output complete evaluation results
"""

import requests
import urllib3
import json
import time
import sys
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
MAX_WORKERS = 5

# Questions to retest
RETEST_IDS = ["TC001", "TC005", "TC006", "TC008", "TC009", "TC010"]

# Previous results file
PREVIOUS_RESULTS_FILE = "chat_test_v3.1_20251211_085008.json"

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
# Prompt v3.1 Template
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

### 2. 时间范围展开（重要！简化版）
**关键：只在最后一个月份后加年份**
- Q1/第一季度 → January , February , March 2025
- Q2/第二季度 → April , May , June 2025
- Q3/第三季度 → July , August , September 2025

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

### 6. 禁止使用的泛化词
❌ yield, return, goal, sector, bond, performance, allocation, holdings

### 7. 多基金对比规则（重要！）
当问题涉及 **比较/对比/compare** 多个基金时：
- 必须在关键词中**明确列出所有基金名称**

## 用户问题
{original_question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""

# =============================================================================
# Load Questions
# =============================================================================

def load_questions():
    """Load TC questions from benchmark"""
    questions = {}
    benchmark_path = Path(__file__).parent.parent / 'docs' / 'benchmark' / 'rag_evaluation_dataset.json'
    with open(benchmark_path, 'r') as f:
        benchmark = json.load(f)
        for tc in benchmark.get('test_cases', []):
            tc_id = tc.get('id', '')
            questions[tc_id] = tc.get('question', '')
    return questions

def load_feishu_answers():
    """Load Feishu answers for all 21 questions"""
    feishu = {}
    
    # Q1-Q11 from test-results.json
    q_path = Path(__file__).parent.parent / 'test-results.json'
    with open(q_path, 'r') as f:
        data = json.load(f)
        for r in data.get('results', []):
            q_id = f"Q{r['index']}"
            feishu[q_id] = r.get('answer', '')
    
    # TC001-TC010 from benchmark_comparison_results.json
    tc_path = Path(__file__).parent / 'benchmark_comparison_results.json'
    with open(tc_path, 'r') as f:
        data = json.load(f)
        for r in data.get('results', []):
            tc_id = r.get('id', '')
            feishu[tc_id] = r.get('feishu_answer', '')
    
    return feishu

# =============================================================================
# RagFlow API Functions
# =============================================================================

def enhance_query(question):
    """Enhance query using Prompt v3.1"""
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

def create_conversation():
    """Create a new conversation"""
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/sessions",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        json={"name": f"Retest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"},
        timeout=30,
        verify=False
    )
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get('code') == 0:
            return data.get('data', {}).get('id')
    return None

def send_message(session_id, message):
    """Send message to RagFlow chat"""
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

def test_question(q_id, question):
    """Test a single question"""
    result = {
        'id': q_id,
        'question': question,
        'timestamp': datetime.now().isoformat()
    }
    
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
    
    enhanced, enhance_time = enhance_query(question)
    result['enhanced_query'] = enhanced
    result['enhance_time'] = enhance_time
    
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
# LLM Evaluation
# =============================================================================

EVALUATION_PROMPT = """You are an impartial judge evaluating two RAG system answers about fund factsheets.

## Question
{question}

## System A (RagFlow) Answer
{ragflow_answer}

## System B (Feishu) Answer
{feishu_answer}

## Evaluation Criteria
Rate EACH answer on a scale of 1-10 for each criterion:

1. **Accuracy** (1-10): Is the information factually correct?
2. **Completeness** (1-10): Does it fully answer the question?
3. **Structure** (1-10): Is the answer well-organized?
4. **Citation** (1-10): Does it properly cite sources?
5. **Professionalism** (1-10): Is the language precise?

## Output Format (JSON only)
{{
  "a_accuracy": <score>,
  "a_completeness": <score>,
  "a_structure": <score>,
  "a_citation": <score>,
  "a_professionalism": <score>,
  "a_total": <sum of A scores>,
  "b_accuracy": <score>,
  "b_completeness": <score>,
  "b_structure": <score>,
  "b_citation": <score>,
  "b_professionalism": <score>,
  "b_total": <sum of B scores>,
  "reason": "<one paragraph explaining the key differences>"
}}"""

def evaluate_single(q_id, question, ragflow_answer, feishu_answer):
    """Evaluate a single question using LLM"""
    prompt = EVALUATION_PROMPT.format(
        question=question,
        ragflow_answer=ragflow_answer[:3000],
        feishu_answer=feishu_answer[:3000]
    )
    
    try:
        resp = requests.post(
            f"{OPENROUTER_CONFIG['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": "anthropic/claude-sonnet-4",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.1
            },
            timeout=60
        )
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            # Extract JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                scores = json.loads(content[start:end])
                return {
                    'id': q_id,
                    'question': question,
                    'ragflow_score': scores.get('a_total', 0),
                    'feishu_score': scores.get('b_total', 0),
                    'details': scores,
                    'ragflow_answer': ragflow_answer,
                    'feishu_answer': feishu_answer
                }
        
        return {
            'id': q_id,
            'question': question,
            'ragflow_score': 0,
            'feishu_score': 0,
            'error': 'Evaluation failed',
            'ragflow_answer': ragflow_answer,
            'feishu_answer': feishu_answer
        }
        
    except Exception as e:
        return {
            'id': q_id,
            'question': question,
            'ragflow_score': 0,
            'feishu_score': 0,
            'error': str(e),
            'ragflow_answer': ragflow_answer,
            'feishu_answer': feishu_answer
        }

# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 80)
    print("Retest and Evaluate v3.1")
    print("=" * 80)
    print(f"Start time: {datetime.now().isoformat()}")
    
    # Step 1: Load previous results and identify errors
    print("\n[Step 1] Loading previous results...")
    prev_path = Path(__file__).parent / PREVIOUS_RESULTS_FILE
    with open(prev_path, 'r') as f:
        prev_data = json.load(f)
    
    prev_results = {r['id']: r for r in prev_data['results']}
    print(f"  Loaded {len(prev_results)} previous results")
    
    # Step 2: Load questions to retest
    print(f"\n[Step 2] Retesting {len(RETEST_IDS)} questions...")
    questions = load_questions()
    
    retested = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_id = {
            executor.submit(test_question, q_id, questions[q_id]): q_id 
            for q_id in RETEST_IDS if q_id in questions
        }
        
        for future in as_completed(future_to_id):
            q_id = future_to_id[future]
            result = future.result()
            retested.append(result)
            
            status = "✓" if 'error' not in result or 'AUTH_ERROR' not in result.get('answer', '') else "✗"
            answer_preview = result['answer'][:50] if result['answer'] else 'N/A'
            print(f"  {status} {q_id}: {result['total_time']:.1f}s - {answer_preview}...")
    
    # Step 3: Merge results
    print("\n[Step 3] Merging results...")
    merged_results = {}
    
    # Add previous successful results (non-AUTH_ERROR)
    for q_id, r in prev_results.items():
        if 'AUTH_ERROR' not in r.get('answer', ''):
            merged_results[q_id] = r
    
    # Add retested results
    for r in retested:
        if 'AUTH_ERROR' not in r.get('answer', ''):
            merged_results[r['id']] = r
        else:
            print(f"  WARNING: {r['id']} still has AUTH_ERROR!")
    
    print(f"  Total merged: {len(merged_results)} questions")
    
    # Step 4: Load Feishu answers
    print("\n[Step 4] Loading Feishu answers...")
    feishu_answers = load_feishu_answers()
    print(f"  Loaded {len(feishu_answers)} Feishu answers")
    
    # Step 5: Run parallel evaluation
    print(f"\n[Step 5] Running LLM evaluation (parallel, {MAX_WORKERS} workers)...")
    
    eval_tasks = []
    for q_id, result in merged_results.items():
        feishu = feishu_answers.get(q_id, 'No answer available')
        eval_tasks.append((q_id, result['question'], result['answer'], feishu))
    
    evaluations = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_id = {
            executor.submit(evaluate_single, t[0], t[1], t[2], t[3]): t[0]
            for t in eval_tasks
        }
        
        completed = 0
        for future in as_completed(future_to_id):
            completed += 1
            result = future.result()
            evaluations.append(result)
            
            r_score = result.get('ragflow_score', 0)
            f_score = result.get('feishu_score', 0)
            winner = "RagFlow" if r_score > f_score else ("Feishu" if f_score > r_score else "Tie")
            print(f"  [{completed}/{len(eval_tasks)}] {result['id']}: RagFlow={r_score}/50 vs Feishu={f_score}/50 ({winner})")
    
    # Sort evaluations
    evaluations.sort(key=lambda x: (0 if x['id'].startswith('Q') else 1, int(x['id'][1:]) if x['id'][1:].isdigit() else int(x['id'][2:])))
    
    # Step 6: Calculate summary
    print("\n[Step 6] Calculating summary...")
    
    ragflow_total = sum(e.get('ragflow_score', 0) for e in evaluations)
    feishu_total = sum(e.get('feishu_score', 0) for e in evaluations)
    ragflow_wins = sum(1 for e in evaluations if e.get('ragflow_score', 0) > e.get('feishu_score', 0))
    feishu_wins = sum(1 for e in evaluations if e.get('feishu_score', 0) > e.get('ragflow_score', 0))
    ties = sum(1 for e in evaluations if e.get('ragflow_score', 0) == e.get('feishu_score', 0))
    
    summary = {
        'version': 'v3.1',
        'timestamp': datetime.now().isoformat(),
        'total_questions': len(evaluations),
        'ragflow_total': ragflow_total,
        'feishu_total': feishu_total,
        'ragflow_avg': round(ragflow_total / len(evaluations), 1) if evaluations else 0,
        'feishu_avg': round(feishu_total / len(evaluations), 1) if evaluations else 0,
        'ragflow_wins': ragflow_wins,
        'feishu_wins': feishu_wins,
        'ties': ties
    }
    
    # Step 7: Save results
    print("\n[Step 7] Saving results...")
    
    # Save merged RagFlow answers
    merged_output = {
        'summary': {
            'version': 'v3.1',
            'timestamp': datetime.now().isoformat(),
            'total_questions': len(merged_results)
        },
        'results': list(merged_results.values())
    }
    
    merged_file = Path(__file__).parent / 'chat_test_v3.1_merged.json'
    with open(merged_file, 'w', encoding='utf-8') as f:
        json.dump(merged_output, f, indent=2, ensure_ascii=False)
    print(f"  Saved merged results: {merged_file}")
    
    # Save evaluation results
    eval_output = {
        'summary': summary,
        'judge_model': 'anthropic/claude-sonnet-4',
        'results': evaluations
    }
    
    eval_file = Path(__file__).parent / 'evaluation_v3.1_results.json'
    with open(eval_file, 'w', encoding='utf-8') as f:
        json.dump(eval_output, f, indent=2, ensure_ascii=False)
    print(f"  Saved evaluation results: {eval_file}")
    
    # Print final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Total Questions: {len(evaluations)}")
    print(f"RagFlow Total: {ragflow_total}/{len(evaluations)*50} (avg: {summary['ragflow_avg']}/50)")
    print(f"Feishu Total: {feishu_total}/{len(evaluations)*50} (avg: {summary['feishu_avg']}/50)")
    print(f"RagFlow Wins: {ragflow_wins} | Feishu Wins: {feishu_wins} | Ties: {ties}")
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    
    return eval_output

if __name__ == "__main__":
    main()



