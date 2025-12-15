#!/usr/bin/env python3
"""
RAG Evaluation Script v2.0
Uses Prompt v2.0 (double emphasis strategy) with real RagFlow Chat session.

Pipeline:
1. Load 21 questions (Q1-Q11 + TC001-TC010)
2. Enhance each question using Prompt v2.0 via OpenRouter
3. Send enhanced query to RagFlow Chat API
4. Collect answers and metadata
5. Run LLM evaluation
6. Save results to JSON files
"""

import requests
import urllib3
import json
import time
import os
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# Configuration
# =============================================================================

RAGFLOW_BASE_URL = "https://10.1.9.133:8443"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
CHAT_ID = "f472490cbabe11f0b1a00242ac130006"

# Read OpenRouter API key
def load_openrouter_config():
    with open('openai.apikey', 'r') as f:
        lines = f.read().strip().split('\n')
        return {
            'api_key': lines[0],
            'base_url': lines[1] if len(lines) > 1 else "https://openrouter.ai/api/v1"
        }

OPENROUTER_CONFIG = load_openrouter_config()

# =============================================================================
# Prompt v2.0 Template
# =============================================================================

PROMPT_V2_TEMPLATE = """你是基金文档检索优化专家。为问题添加精准关键词以提高检索精度。

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

### 2. 时间范围处理（重要！简化版）
- Q1/第一季度 → Q1 2025
- Q2/第二季度 → Q2 2025
- Q3/第三季度 → Q3 2025
- "从1月到9月" 或 "January to September" → 2025（不要展开每个月份！）
- 只有单个月份时才具体写出，如: September 2025

### 3. 默认时间处理（重要！）
当问题**未指定具体时间**时：
- 自动添加最新数据月份: September 2025

### 4. Top Holdings 双重强调规则（新增！重要！）
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

## 示例

输入: "What are top holdings of Asian Income Fund from January to September 2025?"
输出: "What are top holdings of Asian Income Fund from January to September 2025? (Asian Income Fund, Top holdings equities, Top holdings fixed income, 2025)"

输入: "What are top equity holdings of Asian Income Fund in September 2025?"
输出: "What are top equity holdings of Asian Income Fund in September 2025? (Top holdings equities, Top holdings equities, September 2025)"

输入: "show me the geographic locations from January 2025 to September 2025"
输出: "show me the geographic locations from January 2025 to September 2025? (Asset type by geography, 2025)"

## 用户问题
{original_question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""

# =============================================================================
# Load Questions
# =============================================================================

def load_questions():
    """Load all 21 questions from various sources"""
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
        "Q8": "what is the geographic exposures for the Asian Income fund?",  # Changed from HDF
        "Q9": "show me the geographic locations of High dividend stocks from January 2025 to September 2025",  # Expected: no answer
        "Q10": "what are the top holdings of Asian Income Fund from January 2025 to September 2025",
        "Q11": "what is the return for high dividend stocks fund as of September 2025?"
    }
    questions.update(q1_q11)
    
    # TC001-TC010 from benchmark
    with open('docs/benchmark/rag_evaluation_dataset.json', 'r') as f:
        benchmark = json.load(f)
        for tc in benchmark.get('test_cases', []):
            tc_id = tc.get('id', '')
            questions[tc_id] = tc.get('question', '')
    
    return questions

# =============================================================================
# Query Enhancement
# =============================================================================

def enhance_query(question):
    """Enhance query using Prompt v2.0 via OpenRouter"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = PROMPT_V2_TEMPLATE.format(
        current_date=current_date,
        original_question=question
    )
    
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
        
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip()
        else:
            print(f"  Enhancement error: {resp.status_code}")
            return question
    except Exception as e:
        print(f"  Enhancement exception: {e}")
        return question

# =============================================================================
# RagFlow Chat API
# =============================================================================

def create_conversation():
    """Create a new conversation in the chat"""
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/sessions",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        json={"name": f"Evaluation_v2.0_{datetime.now().strftime('%Y%m%d_%H%M%S')}"},
        timeout=30,
        verify=False
    )
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get('code') == 0:
            return data.get('data', {}).get('id')
    print(f"  Failed to create conversation: {resp.text[:200]}")
    return None

def send_message(session_id, message):
    """Send message to RagFlow chat and get response"""
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
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                answer_data = data.get('data', {})
                return {
                    'answer': answer_data.get('answer', ''),
                    'reference': answer_data.get('reference', {}),
                    'prompt': answer_data.get('prompt', '')
                }
        
        print(f"  Chat error: {resp.status_code} - {resp.text[:200]}")
        return None
        
    except Exception as e:
        print(f"  Chat exception: {e}")
        return None

# =============================================================================
# LLM Evaluation
# =============================================================================

EVALUATION_PROMPT = """You are an impartial judge evaluating RAG system answers about fund factsheets.

## Question
{question}

## RAG System Answer
{answer}

## Expected Answer (if available)
{expected}

## Evaluation Criteria
Rate the answer on a scale of 1-10 for each criterion:

1. **Accuracy** (1-10): Is the information factually correct?
2. **Completeness** (1-10): Does it fully answer the question?
3. **Relevance** (1-10): Is the answer focused on what was asked?
4. **Clarity** (1-10): Is the answer well-structured and clear?
5. **Citation** (1-10): Does it properly cite sources/documents?

## Output Format (JSON only)
{{
  "accuracy": <score>,
  "completeness": <score>,
  "relevance": <score>,
  "clarity": <score>,
  "citation": <score>,
  "total": <sum of all scores>,
  "brief_comment": "<one sentence evaluation>"
}}"""

def evaluate_answer(question, answer, expected="Not provided"):
    """Evaluate answer using LLM"""
    prompt = EVALUATION_PROMPT.format(
        question=question,
        answer=answer[:2000],  # Truncate long answers
        expected=expected[:1000] if expected else "Not provided"
    )
    
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
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            # Extract JSON from response
            try:
                # Find JSON in response
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            except:
                pass
        
        return {"total": 0, "brief_comment": "Evaluation failed"}
        
    except Exception as e:
        return {"total": 0, "brief_comment": f"Error: {str(e)}"}

# =============================================================================
# Main Execution
# =============================================================================

def main():
    print("="*80)
    print("RAG Evaluation v2.0 - Full Pipeline")
    print("="*80)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Prompt version: 2.0 (double emphasis strategy)")
    print(f"RagFlow URL: {RAGFLOW_BASE_URL}")
    print(f"Chat ID: {CHAT_ID}")
    
    # Load questions
    questions = load_questions()
    print(f"\nLoaded {len(questions)} questions")
    
    # Create new conversation
    print("\nCreating new conversation...")
    session_id = create_conversation()
    if not session_id:
        print("ERROR: Failed to create conversation. Exiting.")
        return
    print(f"Session ID: {session_id}")
    
    # Load expected answers for TC questions
    expected_answers = {}
    with open('docs/benchmark/rag_evaluation_dataset.json', 'r') as f:
        benchmark = json.load(f)
        for tc in benchmark.get('test_cases', []):
            expected_answers[tc['id']] = tc.get('expected_answer', '')
    
    # Process each question
    results = []
    
    for q_id in sorted(questions.keys(), key=lambda x: (0 if x.startswith('Q') else 1, int(x[1:]) if x[1:].isdigit() else int(x[2:]))):
        question = questions[q_id]
        print(f"\n{'='*60}")
        print(f"[{q_id}] {question[:60]}...")
        
        # Step 1: Enhance query
        print("  1. Enhancing query...")
        start_time = time.time()
        enhanced = enhance_query(question)
        enhance_time = time.time() - start_time
        print(f"     Enhanced ({enhance_time:.1f}s): ...{enhanced[-60:]}")
        
        # Step 2: Send to RagFlow
        print("  2. Sending to RagFlow...")
        start_time = time.time()
        response = send_message(session_id, enhanced)
        chat_time = time.time() - start_time
        
        if response:
            answer = response.get('answer', '')
            print(f"     Answer ({chat_time:.1f}s): {answer[:100]}...")
            
            # Step 3: Evaluate
            print("  3. Evaluating...")
            expected = expected_answers.get(q_id, '')
            evaluation = evaluate_answer(question, answer, expected)
            print(f"     Score: {evaluation.get('total', 0)}/50 - {evaluation.get('brief_comment', '')}")
            
            result = {
                'id': q_id,
                'question': question,
                'enhanced_query': enhanced,
                'answer': answer,
                'reference': response.get('reference', {}),
                'enhance_time': enhance_time,
                'chat_time': chat_time,
                'evaluation': evaluation,
                'expected_answer': expected
            }
        else:
            print(f"     ERROR: No response from RagFlow")
            result = {
                'id': q_id,
                'question': question,
                'enhanced_query': enhanced,
                'answer': '',
                'error': 'No response from RagFlow',
                'enhance_time': enhance_time,
                'chat_time': 0,
                'evaluation': {'total': 0, 'brief_comment': 'No response'}
            }
        
        results.append(result)
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    # Save results
    print("\n" + "="*80)
    print("Saving results...")
    
    # Save answers
    answers_file = 'tools/rag_answers_v2.0.json'
    with open(answers_file, 'w', encoding='utf-8') as f:
        json.dump({
            'version': '2.0',
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'prompt_strategy': 'double_emphasis',
            'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"  Answers saved to: {answers_file}")
    
    # Save evaluation results
    eval_file = 'tools/evaluation_results_v2.0.json'
    eval_summary = {
        'version': '2.0',
        'timestamp': datetime.now().isoformat(),
        'total_questions': len(results),
        'avg_score': sum(r['evaluation'].get('total', 0) for r in results) / len(results),
        'avg_enhance_time': sum(r.get('enhance_time', 0) for r in results) / len(results),
        'avg_chat_time': sum(r.get('chat_time', 0) for r in results if r.get('chat_time', 0) > 0) / max(1, len([r for r in results if r.get('chat_time', 0) > 0])),
        'evaluations': [
            {
                'id': r['id'],
                'question': r['question'][:50],
                'score': r['evaluation'].get('total', 0),
                'comment': r['evaluation'].get('brief_comment', '')
            }
            for r in results
        ]
    }
    with open(eval_file, 'w', encoding='utf-8') as f:
        json.dump(eval_summary, f, indent=2, ensure_ascii=False)
    print(f"  Evaluation saved to: {eval_file}")
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total questions: {len(results)}")
    print(f"Average score: {eval_summary['avg_score']:.1f}/50")
    print(f"Average enhance time: {eval_summary['avg_enhance_time']:.1f}s")
    print(f"Average chat time: {eval_summary['avg_chat_time']:.1f}s")
    
    # Score distribution
    scores = [r['evaluation'].get('total', 0) for r in results]
    print(f"\nScore distribution:")
    print(f"  40-50: {sum(1 for s in scores if s >= 40)} questions")
    print(f"  30-39: {sum(1 for s in scores if 30 <= s < 40)} questions")
    print(f"  20-29: {sum(1 for s in scores if 20 <= s < 30)} questions")
    print(f"  <20:   {sum(1 for s in scores if s < 20)} questions")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()



