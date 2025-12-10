#!/usr/bin/env python3
"""评估Gemini 2.5 Flash + 新Enhanced Prompt的答案质量"""

import json
import time
import requests

OPENROUTER_API_KEY = open('/home/calvin/github/ragflow/openai.apikey').read().strip()
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
EVAL_MODEL = 'google/gemini-2.5-flash'
BASE_DIR = '/home/calvin/github/ragflow/docs/benchmark/test_cases_20251210'

# 加载问题
with open(f'{BASE_DIR}/questions.json', 'r') as f:
    questions = json.load(f)['questions']

# 加载Gemini 2.5 Enhanced结果
with open(f'{BASE_DIR}/sources/ragflow_gemini25_enhanced.json', 'r') as f:
    data = json.load(f)

def evaluate_answer(question, expected, actual):
    if not actual:
        return {'accuracy': 0, 'completeness': 0, 'relevance': 0, 'total': 0, 'comment': '无答案'}
    
    prompt = f'''评价以下AI答案（1-10分）：

问题: {question}
预期要点: {expected[:500]}
实际答案: {actual[:1000]}

评分维度：
1. accuracy: 事实准确性
2. completeness: 覆盖预期要点
3. relevance: 直接回答问题

返回JSON: {{"accuracy": X, "completeness": X, "relevance": X, "comment": "简评"}}'''

    try:
        resp = requests.post(OPENROUTER_URL, 
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={'model': EVAL_MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1},
            timeout=30)
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            result = json.loads(content.strip())
            result['total'] = (result['accuracy'] + result['completeness'] + result['relevance']) / 3
            return result
    except Exception as e:
        return {'accuracy': -1, 'completeness': -1, 'relevance': -1, 'total': -1, 'comment': str(e)[:50]}

print('='*80)
print('Gemini 2.5 Flash + 新Enhanced Prompt 答案质量评估')
print('='*80)

answers = {r['question']: r.get('answer', '') for r in data['test_results']}
total_score = 0
results = []

for q in questions:
    question = q['question']
    expected = q['expected_answer']
    actual = answers.get(question, '')
    
    print(f"评估 {q['id']}: {question[:40]}...", end=' ')
    result = evaluate_answer(question, expected, actual)
    print(f"得分: {result['total']:.1f}")
    
    results.append({
        'id': q['id'],
        'score': result['total'],
        'accuracy': result['accuracy'],
        'completeness': result['completeness'],
        'relevance': result['relevance'],
        'comment': result['comment']
    })
    total_score += result['total']
    time.sleep(0.3)

print()
print('='*80)
avg = total_score / len(questions)
print(f'平均分: {avg:.2f}/10')
print('='*80)
print()
print('详细评分:')
for r in results:
    comment = r['comment'][:60] if r['comment'] else ''
    print(f"{r['id']}: {r['score']:.1f} (准:{r['accuracy']} 完:{r['completeness']} 关:{r['relevance']}) - {comment}")

