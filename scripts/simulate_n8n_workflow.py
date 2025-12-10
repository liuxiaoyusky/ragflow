#!/usr/bin/env python3
"""
模拟n8n workflow流程 - 带细粒度计时
支持两种模式：
1. baseline: 直接用原问题检索（无enhancement）
2. enhanced: LLM增强后检索

时间分解：
- T1: Query Enhancement (LLM调用)
- T2: Retrieval (RagFlow检索API)
- T3: Generation (RagFlow Chat API生成答案)
"""

import json
import requests
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')

# API配置
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = "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"
RAGFLOW_API_URL = "https://10.1.9.133:8443/api/v1"
RAGFLOW_CHAT_API_URL = "https://10.1.9.133:8443/api/v1/chats"
CHAT_ID = "f472490cbabe11f0b1a00242ac130006"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
BENCHMARK_FILE = "/home/calvin/github/ragflow/docs/benchmark/rag_evaluation_dataset.json"
RESULTS_DIR = Path("/home/calvin/github/ragflow/docs/benchmark/evaluation_results")

def load_benchmark():
    """加载评测数据集"""
    with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def prepare_llm_prompt(original_question):
    """准备LLM prompt - 优化版：使用精确section title，禁止泛化词，支持最近6个月"""
    from datetime import datetime
    
    # 计算最近6个月（使用标准库）
    now = datetime.now()
    recent_months = []
    for i in range(6):
        # 计算i个月前的日期
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_date = datetime(year, month, 1)
        recent_months.append(month_date.strftime("%B %Y"))
    recent_months_str = ", ".join(recent_months)
    current_date = now.strftime("%Y年%m月%d日")
    
    prompt = f"""你是基金文档检索优化专家。为问题添加精准关键词以提高检索精度。

当前日期: {current_date}

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

### 3. 跨基金对比问题的时间处理（重要！）
当问题涉及**多个基金的对比**（如 A Fund vs B Fund、比较X和Y）且**未指定具体时间**时：
- 自动添加最近6个月作为时间范围关键词
- 最近6个月是: {recent_months_str}
- 示例: "Compare fee structures between Asian Income Fund and High Dividend Fund"
  → 添加关键词: (Fee structure, {recent_months_str})

### 4. 精确实体名称
- 台积电 → Taiwan Semiconductor Manufacturing Co Ltd
- 腾讯 → Tencent Holdings Ltd
- 惠理亚洲收益基金 → Asian Income Fund
- 惠理高息股票基金 → High Dividend Fund

### 5. 禁止使用的泛化词（会干扰排名）
❌ yield, return, goal, sector, bond, performance, allocation, holdings
❌ 这些词太通用，会匹配到不相关的chunks

## 示例

输入: "惠理亚洲收益基金2025年Q1业绩表现"
输出: "惠理亚洲收益基金2025年Q1业绩表现 (Monthly performance, January 2025, February 2025, March 2025)"

输入: "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率"
输出: "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率 (Dividend information, August 2025)"

输入: "Compare fee structures between Asian Income Fund and High Dividend Fund"
输出: "Compare fee structures between Asian Income Fund and High Dividend Fund (Fee structure, {recent_months_str})"

输入: "哪些月份Asian Income Fund持有台积电？"
输出: "哪些月份Asian Income Fund持有台积电？ (Top holdings - equities, Taiwan Semiconductor Manufacturing Co Ltd)"

输入: "What are top holdings of Asian Income Fund from January to September 2025?"
输出: "What are top holdings of Asian Income Fund from January to September 2025? (Top holdings - equities, Top holdings - fixed income)"

## 用户问题
{original_question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""
    return prompt

def call_openrouter(prompt):
    """T1: 调用OpenRouter API进行Query Enhancement"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://n8n.vp.com.hk",
        "X-Title": "HardyBot Query Enhancement"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    start_time = time.time()
    response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        enhanced_question = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        return enhanced_question, elapsed
    else:
        raise Exception(f"OpenRouter API error: {response.status_code}")

def call_retrieval_api(question, top_n=30):
    """T2: 调用RagFlow Retrieval API"""
    headers = {
        "Authorization": f"Bearer {RAGFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "question": question,
        "dataset_ids": [DATASET_ID],  # 正确的参数名
        "top_n": top_n,
        "similarity_threshold": 0.1,
        "vector_similarity_weight": 0.3,
        "keywords_similarity_weight": 0.7
    }
    
    start_time = time.time()
    response = requests.post(f"{RAGFLOW_API_URL}/retrieval", json=payload, headers=headers, verify=False, timeout=60)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json().get('data', {})
        chunks = data.get('chunks', [])
        return chunks, elapsed
    else:
        raise Exception(f"Retrieval API error: {response.status_code}")

def call_chat_api(question):
    """T3: 调用RagFlow Chat Completion API生成答案"""
    headers = {
        "Authorization": f"Bearer {RAGFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 创建session
    session_url = f"{RAGFLOW_CHAT_API_URL}/{CHAT_ID}/sessions"
    session_resp = requests.post(session_url, json={"name": "benchmark_test"}, headers=headers, verify=False)
    session_data = session_resp.json().get('data', {})
    session_id = session_data.get('id', '') if session_data else ''
    
    if not session_id:
        raise Exception("Failed to create chat session")
    
    # 发送问题
    completion_url = f"{RAGFLOW_CHAT_API_URL}/{CHAT_ID}/completions"
    payload = {
        "question": question,
        "stream": False,
        "session_id": session_id,
        "reference": True
    }
    
    start_time = time.time()
    response = requests.post(completion_url, json=payload, headers=headers, verify=False, timeout=120)
    elapsed = time.time() - start_time
    
    result = response.json()
    data = result.get('data', {})
    answer = data.get('answer', '') if data else ''
    reference_data = data.get('reference', {}) if data else {}
    references = reference_data.get('chunks', []) if isinstance(reference_data, dict) else []
    
    # 删除session
    delete_url = f"{RAGFLOW_CHAT_API_URL}/{CHAT_ID}/sessions"
    requests.delete(delete_url, json={"ids": [session_id]}, headers=headers, verify=False)
    
    return answer, references, elapsed

def run_baseline_test(question, use_chat=False):
    """Baseline模式：直接用原问题检索，不做enhancement"""
    timings = {'t1_enhancement': 0.0}
    
    # T2: Retrieval
    chunks, t2 = call_retrieval_api(question)
    timings['t2_retrieval'] = t2
    
    # T3: Chat API
    answer = ''
    chat_refs = []
    if use_chat:
        answer, chat_refs, t3 = call_chat_api(question)
        timings['t3_generation'] = t3
    else:
        timings['t3_generation'] = 0.0
    
    total = sum(timings.values())
    timings['total'] = total
    
    # 计算百分比
    distribution = {}
    for k, v in timings.items():
        if k != 'total' and total > 0:
            distribution[k] = f"{v/total*100:.1f}%"
    
    return {
        'question': question,
        'enhanced_question': question,
        'was_enhanced': False,
        'chunks': chunks,
        'answer': answer,
        'chat_refs': chat_refs,
        'timings': timings,
        'time_distribution': distribution
    }

def run_enhanced_test(question, use_chat=False):
    """Enhanced模式：LLM增强后检索"""
    timings = {}
    
    # T1: Query Enhancement
    prompt = prepare_llm_prompt(question)
    enhanced_question, t1 = call_openrouter(prompt)
    timings['t1_enhancement'] = t1
    
    # T2: Retrieval
    chunks, t2 = call_retrieval_api(enhanced_question)
    timings['t2_retrieval'] = t2
    
    # T3: Chat API
    answer = ''
    chat_refs = []
    if use_chat:
        answer, chat_refs, t3 = call_chat_api(enhanced_question)
        timings['t3_generation'] = t3
    else:
        timings['t3_generation'] = 0.0
    
    total = sum(timings.values())
    timings['total'] = total
    
    # 计算百分比
    distribution = {}
    for k, v in timings.items():
        if k != 'total' and total > 0:
            distribution[k] = f"{v/total*100:.1f}%"
    
    return {
        'question': question,
        'enhanced_question': enhanced_question,
        'was_enhanced': question != enhanced_question,
        'chunks': chunks,
        'answer': answer,
        'chat_refs': chat_refs,
        'timings': timings,
        'time_distribution': distribution
    }

def calculate_coverage(retrieved_chunks, expected_chunks):
    """计算chunk覆盖率"""
    # 使用document_keyword字段（RagFlow API返回的实际字段名）
    retrieved_docs = set(c.get('document_keyword', '') for c in retrieved_chunks)
    expected_set = set(expected_chunks)
    
    matched = retrieved_docs & expected_set
    coverage = len(matched) / len(expected_set) if expected_set else 0
    
    return {
        'matched_count': len(matched),
        'expected_count': len(expected_set),
        'coverage': coverage,
        'matched_chunks': list(matched),
        'missing_chunks': list(expected_set - retrieved_docs)
    }

def analyze_scores(chunks, expected_chunks):
    """分析分数分布：wanted vs unwanted"""
    expected_set = set(expected_chunks)
    
    wanted_scores = []
    unwanted_scores = []
    
    for c in chunks:
        doc = c.get('document_keyword', '')  # 使用正确的字段名
        score = c.get('similarity', 0)
        
        if doc in expected_set:
            wanted_scores.append(score)
        else:
            unwanted_scores.append(score)
    
    wanted_avg = sum(wanted_scores) / len(wanted_scores) if wanted_scores else 0
    unwanted_avg = sum(unwanted_scores) / len(unwanted_scores) if unwanted_scores else 0
    
    return {
        'wanted_count': len(wanted_scores),
        'unwanted_count': len(unwanted_scores),
        'wanted_avg': wanted_avg,
        'wanted_max': max(wanted_scores) if wanted_scores else 0,
        'wanted_min': min(wanted_scores) if wanted_scores else 0,
        'unwanted_avg': unwanted_avg,
        'unwanted_max': max(unwanted_scores) if unwanted_scores else 0,
        'unwanted_min': min(unwanted_scores) if unwanted_scores else 0,
        'gap': wanted_avg - unwanted_avg,
        'gap_percent': f"{(wanted_avg - unwanted_avg) / unwanted_avg * 100:.1f}%" if unwanted_avg > 0 else "N/A"
    }

def run_single_test(test_case, mode='enhanced', use_chat=False):
    """运行单个测试用例"""
    question = test_case['question']
    expected_chunks = test_case.get('expected_chunks', [])
    
    print(f"\n测试 {test_case['id']}: {question[:60]}...")
    
    try:
        # 根据模式运行测试
        if mode == 'baseline':
            result = run_baseline_test(question, use_chat)
        else:
            result = run_enhanced_test(question, use_chat)
        
        # 计算覆盖率和分数
        coverage = calculate_coverage(result['chunks'], expected_chunks)
        scores = analyze_scores(result['chunks'], expected_chunks)
        
        # 输出结果
        print(f"  模式: {mode}" + (" + Chat" if use_chat else ""))
        t1 = result['timings']['t1_enhancement']
        t2 = result['timings']['t2_retrieval']
        t3 = result['timings']['t3_generation']
        total = result['timings']['total']
        print(f"  时间: T1={t1:.2f}s, T2={t2:.2f}s, T3={t3:.2f}s, 总计={total:.2f}s")
        print(f"  时间分布: {result['time_distribution']}")
        print(f"  覆盖率: {coverage['matched_count']}/{coverage['expected_count']} ({coverage['coverage']*100:.1f}%)")
        print(f"  分数差距: {scores['gap']:.4f} ({scores['gap_percent']})")
        if result['was_enhanced']:
            print(f"  增强后: {result['enhanced_question'][:80]}...")
        if use_chat and result.get('answer'):
            answer_preview = result['answer'][:100].replace('\n', ' ')
            print(f"  答案: {answer_preview}...")
        
        return {
            'test_id': test_case['id'],
            'mode': mode,
            'use_chat': use_chat,
            'question': question,
            'enhanced_question': result['enhanced_question'],
            'was_enhanced': result['was_enhanced'],
            'answer': result.get('answer', ''),
            'chat_refs_count': len(result.get('chat_refs', [])),
            'coverage': coverage,
            'scores': scores,
            'timings': result['timings'],
            'time_distribution': result['time_distribution'],
            'chunks_count': len(result['chunks']),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"  ❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'test_id': test_case['id'],
            'mode': mode,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def run_all_tests(mode='enhanced', use_chat=False):
    """运行所有测试用例"""
    benchmark = load_benchmark()
    
    mode_desc = f"{mode}" + (" + Chat" if use_chat else "")
    print("=" * 70)
    print(f"运行Benchmark测试 - 模式: {mode_desc}")
    print("=" * 70)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'mode': mode,
        'use_chat': use_chat,
        'test_results': []
    }
    
    # 累计时间统计
    total_t1 = 0
    total_t2 = 0
    total_t3 = 0
    
    for tc in benchmark['test_cases']:
        result = run_single_test(tc, mode, use_chat)
        results['test_results'].append(result)
        
        if 'timings' in result:
            total_t1 += result['timings'].get('t1_enhancement', 0)
            total_t2 += result['timings'].get('t2_retrieval', 0)
            total_t3 += result['timings'].get('t3_generation', 0)
    
    # 计算汇总统计
    successful = [r for r in results['test_results'] if 'error' not in r]
    if successful:
        coverages = [r['coverage']['coverage'] for r in successful]
        times = [r['timings']['total'] for r in successful]
        gaps = [r['scores']['gap'] for r in successful]
        
        total_time = total_t1 + total_t2 + total_t3
        
        results['summary'] = {
            'total_tests': len(results['test_results']),
            'successful_tests': len(successful),
            'failed_tests': len(results['test_results']) - len(successful),
            'avg_coverage': sum(coverages) / len(coverages),
            'avg_time': sum(times) / len(times),
            'avg_gap': sum(gaps) / len(gaps),
            'perfect_coverage': sum(1 for c in coverages if c == 1.0),
            'time_breakdown': {
                't1_enhancement_total': total_t1,
                't2_retrieval_total': total_t2,
                't3_generation_total': total_t3,
                'total': total_time,
                't1_percent': f"{total_t1/total_time*100:.1f}%" if total_time > 0 else "0%",
                't2_percent': f"{total_t2/total_time*100:.1f}%" if total_time > 0 else "0%",
                't3_percent': f"{total_t3/total_time*100:.1f}%" if total_time > 0 else "0%"
            }
        }
        
        print("\n" + "=" * 70)
        print("汇总统计:")
        print(f"  总测试数: {results['summary']['total_tests']}")
        print(f"  成功/失败: {results['summary']['successful_tests']}/{results['summary']['failed_tests']}")
        print(f"  平均覆盖率: {results['summary']['avg_coverage']*100:.1f}%")
        print(f"  完美覆盖: {results['summary']['perfect_coverage']}/{results['summary']['total_tests']}")
        print(f"  平均分数差距: {results['summary']['avg_gap']:.4f}")
        print(f"\n时间分布（总计 {total_time:.2f}秒）:")
        print(f"  T1 Enhancement: {total_t1:.2f}s ({results['summary']['time_breakdown']['t1_percent']})")
        print(f"  T2 Retrieval: {total_t2:.2f}s ({results['summary']['time_breakdown']['t2_percent']})")
        print(f"  T3 Generation: {total_t3:.2f}s ({results['summary']['time_breakdown']['t3_percent']})")
        print("=" * 70)
    
    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chat_suffix = "_chat" if use_chat else ""
    output_file = RESULTS_DIR / f"{timestamp}_{mode}{chat_suffix}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")
    
    return results

def main():
    """主函数"""
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'enhanced'
    use_chat = '--chat' in sys.argv
    
    if mode not in ['baseline', 'enhanced', 'both']:
        print("用法: python simulate_n8n_workflow.py [baseline|enhanced|both] [--chat]")
        print("  --chat: 启用Chat API测试（包含T3 Generation）")
        sys.exit(1)
    
    if mode == 'both':
        print("\n>>> 运行Baseline测试...")
        baseline_results = run_all_tests('baseline', use_chat)
        print("\n>>> 运行Enhanced测试...")
        enhanced_results = run_all_tests('enhanced', use_chat)
        
        # 对比输出
        print("\n" + "=" * 70)
        print("对比总结:")
        print("=" * 70)
        b_sum = baseline_results.get('summary', {})
        e_sum = enhanced_results.get('summary', {})
        
        print(f"{'指标':<20} {'Baseline':>15} {'Enhanced':>15} {'差异':>15}")
        print("-" * 70)
        print(f"{'平均覆盖率':<20} {b_sum.get('avg_coverage', 0)*100:>14.1f}% {e_sum.get('avg_coverage', 0)*100:>14.1f}% {(e_sum.get('avg_coverage', 0) - b_sum.get('avg_coverage', 0))*100:>+14.1f}%")
        print(f"{'完美覆盖数':<20} {b_sum.get('perfect_coverage', 0):>15} {e_sum.get('perfect_coverage', 0):>15} {e_sum.get('perfect_coverage', 0) - b_sum.get('perfect_coverage', 0):>+15}")
        print(f"{'平均分数差距':<20} {b_sum.get('avg_gap', 0):>15.4f} {e_sum.get('avg_gap', 0):>15.4f} {e_sum.get('avg_gap', 0) - b_sum.get('avg_gap', 0):>+15.4f}")
        print(f"{'平均耗时(秒)':<20} {b_sum.get('avg_time', 0):>15.2f} {e_sum.get('avg_time', 0):>15.2f} {e_sum.get('avg_time', 0) - b_sum.get('avg_time', 0):>+15.2f}")
    else:
        run_all_tests(mode, use_chat)

if __name__ == '__main__':
    main()
