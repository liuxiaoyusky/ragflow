#!/usr/bin/env python3
"""
横评脚本：RagFlow + Haiku vs 飞书
评委：OpenRouter Gemini 2.5 Pro
"""

import json
import requests
import time
from datetime import datetime
from pathlib import Path

# API配置
with open('/home/calvin/github/ragflow/openai.apikey', 'r') as f:
    OPENROUTER_API_KEY = f.read().strip().split('\n')[0]

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
JUDGE_MODEL = "google/gemini-2.5-pro-preview"  # Gemini 2.5 Pro 作为评委

# 加载RagFlow答案
RAGFLOW_RESULTS_FILE = "/home/calvin/github/ragflow/tools/regression_final_20251210_104324.json"

# 11个测试问题和期望答案
QUESTIONS = [
    {"id": "Q1", "question": "what is the management fee for High Dividend Stocks fund?", 
     "expected": "Class A1/A2 MDis: 1.25% p.a.; Class A Acc/B: 1.50% p.a."},
    {"id": "Q2", "question": "does High Dividend Stocks fund have performance fees?", 
     "expected": "Yes. Class A1/A Acc/B: 15% of profit (high-on-high); Class A2 MDis: Nil"},
    {"id": "Q3", "question": "what is the performance fee for High Dividend stocks fund?", 
     "expected": "15% of profit (high-on-high principle); Nil for Class A Acc"},
    {"id": "Q4", "question": "what is the performance fee rate for High Dividend Stocks Fund?", 
     "expected": "15% for Class A1/A2 MDis; Nil (0%) for Class A Acc"},
    {"id": "Q5", "question": "what is the top fixed income holdings for Asian Income fund as of September 2025", 
     "expected": "Top 5 fixed income holdings with percentages"},
    {"id": "Q6", "question": "what are the top equity holdings of Asian Income as of March 2025", 
     "expected": "Taiwan Semiconductor 7.2%, China Telecom 3.0%, etc."},
    {"id": "Q7", "question": "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025", 
     "expected": "Multiple months top holdings comparison"},
    {"id": "Q8", "question": "what is the geographic exposures for the High dividend stocks fund?", 
     "expected": "Hong Kong ~25-28%, South Korea ~15-17%, Taiwan ~13-16%"},
    {"id": "Q9", "question": "show me the geographic locations of High dividend stocks from January 2025 to September 2025", 
     "expected": "Monthly geographic allocation changes"},
    {"id": "Q10", "question": "what are the top holdings of Asian Income Fund from January 2025 to September 2025", 
     "expected": "Both equity and fixed income holdings across months"},
    {"id": "Q11", "question": "what is the return for high dividend stocks fund as of September 2025?", 
     "expected": "YTD +23.2%, Since Launch +1197.9%, Annualized +11.7%"},
]

# 飞书答案文件
FEISHU_ANSWERS_FILE = "/home/calvin/github/ragflow/tools/feishu_answers.json"

def load_feishu_answers():
    """从JSON文件加载飞书答案"""
    try:
        with open(FEISHU_ANSWERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载飞书答案失败: {e}")
        return {}

def load_ragflow_answers():
    """加载RagFlow答案"""
    with open(RAGFLOW_RESULTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {r['id']: r.get('answer', '') for r in data['results']}

def judge_answers(question_id, question, expected, answer_a, answer_b):
    """使用Gemini 2.5 Pro评判两个答案"""
    
    prompt = f"""你是一位专业的基金文档问答评委。请公正地评估两个AI系统对同一问题的回答质量。

## 评估问题
**问题**: {question}
**参考答案/期望内容**: {expected}

## 系统A的回答
{answer_a}

## 系统B的回答
{answer_b}

## 评分标准（每项10分）
1. **准确性** (Accuracy): 答案是否包含正确的数据和信息
2. **完整性** (Completeness): 是否完整回答了问题的所有方面
3. **结构性** (Structure): 答案的组织是否清晰、易读
4. **引用性** (Citation): 是否提供了来源引用
5. **专业性** (Professionalism): 语言表达是否专业、准确

## 输出格式（严格JSON）
```json
{{
  "question_id": "{question_id}",
  "system_a_scores": {{
    "accuracy": X,
    "completeness": X,
    "structure": X,
    "citation": X,
    "professionalism": X,
    "total": XX
  }},
  "system_b_scores": {{
    "accuracy": X,
    "completeness": X,
    "structure": X,
    "citation": X,
    "professionalism": X,
    "total": XX
  }},
  "winner": "A" 或 "B" 或 "TIE",
  "analysis": "简要分析两者差异（50字内）"
}}
```

请直接输出JSON，不要其他内容:"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://n8n.vp.com.hk"
    }
    
    payload = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            # 尝试解析JSON
            content = content.strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            return json.loads(content)
    except Exception as e:
        print(f"评判错误: {e}")
    
    return None

def run_comparison():
    """运行横评"""
    print("=" * 100)
    print("🏆 RagFlow + Haiku vs 飞书 横评")
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 评委: {JUDGE_MODEL}")
    print("=" * 100)
    
    # 加载RagFlow答案
    ragflow_answers = load_ragflow_answers()
    
    results = []
    total_a = 0
    total_b = 0
    wins_a = 0
    wins_b = 0
    ties = 0
    
    for q in QUESTIONS:
        qid = q['id']
        print(f"\n{'─'*80}")
        print(f"📌 [{qid}] {q['question'][:60]}...")
        print("─" * 80)
        
        answer_a = ragflow_answers.get(qid, "")
        answer_b = FEISHU_ANSWERS.get(qid, "")
        
        if not answer_a:
            print(f"   ⚠️ RagFlow答案缺失")
            continue
        if not answer_b or answer_b.startswith("请在此处"):
            print(f"   ⚠️ 飞书答案未填入，跳过")
            continue
        
        print(f"   🔄 正在评判...")
        judgment = judge_answers(qid, q['question'], q['expected'], answer_a, answer_b)
        
        if judgment:
            score_a = judgment['system_a_scores']['total']
            score_b = judgment['system_b_scores']['total']
            winner = judgment['winner']
            
            total_a += score_a
            total_b += score_b
            
            if winner == 'A':
                wins_a += 1
                winner_str = "🅰️ RagFlow"
            elif winner == 'B':
                wins_b += 1
                winner_str = "🅱️ 飞书"
            else:
                ties += 1
                winner_str = "🤝 平局"
            
            print(f"   RagFlow: {score_a}/50 | 飞书: {score_b}/50 | 胜者: {winner_str}")
            print(f"   📝 {judgment.get('analysis', '')}")
            
            results.append({
                "question_id": qid,
                "question": q['question'],
                "ragflow_score": score_a,
                "feishu_score": score_b,
                "winner": winner,
                "analysis": judgment.get('analysis', ''),
                "details": judgment
            })
        else:
            print(f"   ❌ 评判失败")
    
    # 汇总
    n = len(results)
    if n > 0:
        print("\n" + "=" * 100)
        print("📊 横评汇总")
        print("=" * 100)
        
        print(f"\n| 问题 | RagFlow | 飞书 | 胜者 |")
        print(f"|------|---------|------|------|")
        for r in results:
            winner_emoji = "🅰️" if r['winner'] == 'A' else ("🅱️" if r['winner'] == 'B' else "🤝")
            print(f"| {r['question_id']} | {r['ragflow_score']}/50 | {r['feishu_score']}/50 | {winner_emoji} |")
        
        print(f"\n{'─'*50}")
        print(f"📈 总分: RagFlow {total_a}/{n*50} ({total_a/n:.1f}平均) vs 飞书 {total_b}/{n*50} ({total_b/n:.1f}平均)")
        print(f"🏆 胜场: RagFlow {wins_a} | 飞书 {wins_b} | 平局 {ties}")
        
        if total_a > total_b:
            print(f"\n🎉 最终胜者: RagFlow + Haiku (领先 {total_a - total_b} 分)")
        elif total_b > total_a:
            print(f"\n🎉 最终胜者: 飞书 (领先 {total_b - total_a} 分)")
        else:
            print(f"\n🤝 最终结果: 平局")
        
        # 保存结果
        output = {
            "timestamp": datetime.now().isoformat(),
            "judge_model": JUDGE_MODEL,
            "summary": {
                "ragflow_total": total_a,
                "feishu_total": total_b,
                "ragflow_wins": wins_a,
                "feishu_wins": wins_b,
                "ties": ties
            },
            "results": results
        }
        
        output_file = f"/home/calvin/github/ragflow/tools/comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存: {output_file}")

if __name__ == "__main__":
    run_comparison()

