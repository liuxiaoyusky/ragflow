#!/usr/bin/env python3
"""
RAG评测基准测试脚本
运行baseline和enhanced查询，保存结果用于对比

测试模式：
- retrieval: 只测试检索（快速）
- full: 完整测试包括LLM生成答案（需要更长时间）
"""

import json
import requests
import warnings
import time
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')

RETRIEVAL_API_URL = "https://10.1.9.133:8443/api/v1/retrieval"
CHAT_API_URL = "https://10.1.9.133:8443/api/v1/chats"
N8N_WEBHOOK_URL = "https://n8n.vp.com.hk/webhook-test/hardybot-test"  # n8n Webhook URL
CHAT_ID = "f472490cbabe11f0b1a00242ac130006"  # HardyBot chat ID
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
BENCHMARK_FILE = "/home/calvin/github/ragflow/docs/benchmark/rag_evaluation_dataset.json"
RESULTS_DIR = Path("/home/calvin/github/ragflow/docs/benchmark/evaluation_results")

def load_benchmark():
    """加载评测数据集"""
    with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def query_ragflow(question: str, dataset_id: str, top_n: int = 30) -> tuple:
    """查询RagFlow Retrieval API，返回结果和响应时间"""
    payload = {
        "question": question,
        "dataset_ids": [dataset_id],
        "top_n": top_n
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    start_time = time.time()
    response = requests.post(RETRIEVAL_API_URL, json=payload, headers=headers, verify=False)
    response_time = time.time() - start_time
    
    response.raise_for_status()
    return response.json(), response_time

def query_chat_completion(question: str) -> dict:
    """查询RagFlow Chat Completion API（完整LLM流程），返回答案和响应时间"""
    # 先创建session
    session_url = f"{CHAT_API_URL}/{CHAT_ID}/sessions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    session_resp = requests.post(session_url, json={"name": "benchmark_test"}, headers=headers, verify=False)
    session_id = session_resp.json().get('data', {}).get('id', '')
    
    # 发送问题
    completion_url = f"{CHAT_API_URL}/{CHAT_ID}/completions"
    payload = {
        "question": question,
        "stream": False,
        "session_id": session_id,
        "reference": True
    }
    
    start_time = time.time()
    response = requests.post(completion_url, json=payload, headers=headers, verify=False, timeout=120)
    response_time = time.time() - start_time
    
    result = response.json()
    answer = result.get('data', {}).get('answer', '')
    references = result.get('data', {}).get('reference', {}).get('chunks', [])
    
    # 删除session
    delete_url = f"{CHAT_API_URL}/{CHAT_ID}/sessions"
    requests.delete(delete_url, json={"ids": [session_id]}, headers=headers, verify=False)
    
    return {
        'answer': answer,
        'references': references,
        'response_time': response_time
    }

def query_n8n_webhook(question: str) -> dict:
    """
    通过n8n Webhook调用完整流程（飞书→n8n→OpenRouter→RagFlow→返回）
    这是最完整的端到端测试
    """
    # 模拟飞书消息格式
    payload = {
        "message": {
            "content": json.dumps({"text": question})
        },
        "sender": {
            "sender_id": {
                "open_id": "benchmark_test_user"
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    start_time = time.time()
    try:
        response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=120, verify=False)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'original_question': result.get('original_question', question),
                'enhanced_question': result.get('enhanced_question', ''),
                'was_enhanced': result.get('was_enhanced', False),
                'answer': result.get('answer', ''),
                'references': result.get('references', {}).get('chunks', []),
                'response_time': response_time
            }
        else:
            return {
                'success': False,
                'error': f"HTTP {response.status_code}: {response.text}",
                'response_time': response_time
            }
    except Exception as e:
        response_time = time.time() - start_time
        return {
            'success': False,
            'error': str(e),
            'response_time': response_time
        }

def enhance_query_keywords(question: str) -> tuple:
    """使用keywords标签增强查询，返回(增强后的问题, 提取的关键词列表)"""
    question_lower = question.lower()
    keywords = []
    matched_category = None
    
    # 关键词映射（基于16个Factsheet Section Titles）
    keyword_map = {
        'holdings': {
            'triggers': ['holdings', 'holding', '持仓', '持股'],
            'keywords': ['top holdings', 'equities', 'fixed income', 'stock holdings', 'bond holdings']
        },
        'dividend': {
            'triggers': ['dividend', '股息', '分红', 'payout', 'yield'],
            'keywords': ['dividend information', 'dividend', 'payout', 'yield', 'distribution']
        },
        'performance': {
            'triggers': ['performance', '业绩', '表现', 'return', '回报'],
            'keywords': ['performance update', 'monthly performance', 'return', 'YTD']
        },
        'asset_allocation': {
            'triggers': ['asset', 'allocation', '配置', 'sector', 'geography', '行业', '地区'],
            'keywords': ['asset type by geography', 'asset type by sector', 'asset allocation', 'geography', 'sector']
        },
        'credit': {
            'triggers': ['credit', 'rating', '评级', '信用'],
            'keywords': ['credit ratings', 'rating distribution', 'AAA', 'AA', 'BBB']
        },
        'nav': {
            'triggers': ['nav', 'code', '代码', 'isin', '净值'],
            'keywords': ['NAVs codes', 'NAV', 'ISIN', 'fund code']
        },
        'fee': {
            'triggers': ['fee', '费用', '费率', 'expense', 'management fee'],
            'keywords': ['fee structure', 'management fee', 'subscription fee', 'expense ratio']
        },
        'portfolio': {
            'triggers': ['portfolio', 'characteristics', '组合', '特征', 'duration'],
            'keywords': ['portfolio characteristics', 'yield', 'duration']
        },
        'investment_objective': {
            'triggers': ['objective', 'investment objective', '目标', '投资目标'],
            'keywords': ['investment objective', 'investment goal', 'fund objective']
        },
        'fund_facts': {
            'triggers': ['fund facts', '基金概况', 'aum', 'inception'],
            'keywords': ['fund facts', 'AUM', 'inception date', 'fund information']
        }
    }
    
    # 匹配关键词类别
    for category, config in keyword_map.items():
        for trigger in config['triggers']:
            if trigger in question_lower:
                keywords = config['keywords'][:5]  # 最多5个关键词
                matched_category = category
                break
        if keywords:
            break
    
    # 特殊匹配：台积电/TSMC
    if not keywords and ('台积电' in question or 'tsmc' in question_lower or 'semiconductor' in question_lower):
        keywords = ['top holdings', 'equities', 'Taiwan Semiconductor', 'stock holdings']
        matched_category = 'holdings_tsmc'
    
    # 特殊匹配：惠理基金
    if not keywords and ('惠理' in question or 'value partners' in question_lower):
        keywords = ['Asian Income Fund', 'High Dividend Fund', 'Classic Fund']
        matched_category = 'fund_names'
    
    enhanced_question = question
    if keywords:
        enhanced_question = f"{question} keywords: [{', '.join(keywords)}]"
    
    return enhanced_question, {
        'original_question': question,
        'matched_category': matched_category,
        'extracted_keywords': keywords,
        'enhanced_question': enhanced_question
    }

def calculate_coverage(retrieved_chunks: list, expected_chunks: list) -> dict:
    """计算chunk覆盖率"""
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

def analyze_scores(chunks: list, expected_chunks: list) -> dict:
    """分析分数分布"""
    expected_set = set(expected_chunks)
    
    wanted_scores = []
    unwanted_scores = []
    
    for c in chunks:
        doc = c.get('document_keyword', '')
        score = c.get('similarity', 0)
        
        if doc in expected_set:
            wanted_scores.append(score)
        else:
            unwanted_scores.append(score)
    
    return {
        'wanted_count': len(wanted_scores),
        'unwanted_count': len(unwanted_scores),
        'wanted_avg': sum(wanted_scores) / len(wanted_scores) if wanted_scores else 0,
        'wanted_max': max(wanted_scores) if wanted_scores else 0,
        'wanted_min': min(wanted_scores) if wanted_scores else 0,
        'unwanted_avg': sum(unwanted_scores) / len(unwanted_scores) if unwanted_scores else 0,
        'unwanted_max': max(unwanted_scores) if unwanted_scores else 0,
        'unwanted_min': min(unwanted_scores) if unwanted_scores else 0,
        'gap': (sum(wanted_scores) / len(wanted_scores) if wanted_scores else 0) - 
               (sum(unwanted_scores) / len(unwanted_scores) if unwanted_scores else 0)
    }

def run_test(test_case: dict, dataset_id: str, mode: str = 'baseline', test_type: str = 'retrieval') -> dict:
    """运行单个测试用例
    
    Args:
        test_case: 测试用例
        dataset_id: 数据集ID
        mode: 'baseline' 或 'enhanced'
        test_type: 
            - 'retrieval': 只检索（快速，直接调RagFlow API）
            - 'full': 完整LLM（调RagFlow Chat API）
            - 'n8n': 端到端（调n8n Webhook，包含Query Enhancement）
    """
    question = test_case['question']
    keyword_info = None
    
    # n8n模式不需要在这里增强，增强在n8n流程中完成
    if mode == 'enhanced' and test_type != 'n8n':
        question, keyword_info = enhance_query_keywords(test_case['question'])
    
    result = {
        'test_id': test_case['id'],
        'original_question': test_case['question'],
        'actual_question': question,
        'mode': mode,
        'test_type': test_type,
        'keyword_enhancement': keyword_info,
        'timestamp': datetime.now().isoformat()
    }
    
    chunks = []
    
    if test_type == 'n8n':
        # 端到端测试：通过n8n Webhook
        n8n_result = query_n8n_webhook(test_case['question'])
        result['response_time_seconds'] = n8n_result['response_time']
        result['n8n_success'] = n8n_result.get('success', False)
        
        if n8n_result.get('success'):
            result['llm_answer'] = n8n_result.get('answer', '')
            result['enhanced_by_llm'] = n8n_result.get('enhanced_question', '')
            result['was_enhanced'] = n8n_result.get('was_enhanced', False)
            chunks = n8n_result.get('references', [])
        else:
            result['error'] = n8n_result.get('error', 'Unknown error')
            
    elif test_type == 'full':
        # 完整测试：调用Chat Completion API
        chat_result = query_chat_completion(question)
        result['llm_answer'] = chat_result['answer']
        result['response_time_seconds'] = chat_result['response_time']
        chunks = chat_result['references']
    else:
        # 只检索测试
        response, response_time = query_ragflow(question, dataset_id)
        result['response_time_seconds'] = response_time
        chunks = response.get('data', {}).get('chunks', [])
    
    # 计算覆盖率和分数
    coverage = calculate_coverage(chunks, test_case['expected_chunks'])
    scores = analyze_scores(chunks, test_case['expected_chunks'])
    
    result['coverage'] = coverage
    result['scores'] = scores
    result['chunks'] = [
        {
            'rank': i + 1,
            'document': c.get('document_keyword', ''),
            'score': c.get('similarity', 0),
            'is_expected': c.get('document_keyword', '') in set(test_case['expected_chunks'])
        }
        for i, c in enumerate(chunks)
    ]
    
    return result

def run_all_tests(mode: str = 'baseline', test_type: str = 'retrieval'):
    """运行所有测试用例
    
    Args:
        mode: 'baseline' 或 'enhanced'
        test_type: 'retrieval' (只检索，快速) 或 'full' (包含LLM，较慢)
    """
    benchmark = load_benchmark()
    dataset_id = benchmark['dataset_id']
    
    total_start_time = time.time()
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'mode': mode,
        'test_type': test_type,
        'dataset_id': dataset_id,
        'test_results': [],
        'summary': {}
    }
    
    print(f"\n{'='*70}")
    print(f"运行 {mode.upper()} 测试 (类型: {test_type})")
    print(f"{'='*70}\n")
    
    for tc in benchmark['test_cases']:
        print(f"测试 {tc['id']}: {tc['question'][:50]}...")
        result = run_test(tc, dataset_id, mode, test_type)
        results['test_results'].append(result)
        
        cov = result['coverage']
        print(f"  覆盖率: {cov['matched_count']}/{cov['expected_count']} ({cov['coverage']*100:.1f}%)")
        print(f"  响应时间: {result['response_time_seconds']:.3f}秒")
        print(f"  分数差距: {result['scores']['gap']:.4f}")
        
        # 显示关键词增强信息（本地增强）
        if result.get('keyword_enhancement'):
            kw = result['keyword_enhancement']
            print(f"  关键词类别: {kw.get('matched_category', 'N/A')}")
            print(f"  提取关键词: {kw.get('extracted_keywords', [])}")
        
        # 显示n8n LLM增强信息
        if result.get('enhanced_by_llm'):
            print(f"  LLM增强后: {result['enhanced_by_llm'][:80]}...")
            print(f"  是否增强: {result.get('was_enhanced', False)}")
        
        # 显示错误信息
        if result.get('error'):
            print(f"  ❌ 错误: {result['error']}")
        print()
    
    total_time = time.time() - total_start_time
    
    # 计算汇总统计
    all_coverages = [r['coverage']['coverage'] for r in results['test_results']]
    all_gaps = [r['scores']['gap'] for r in results['test_results']]
    all_times = [r['response_time_seconds'] for r in results['test_results']]
    
    results['summary'] = {
        'total_tests': len(results['test_results']),
        'total_time_seconds': total_time,
        'avg_response_time_seconds': sum(all_times) / len(all_times),
        'avg_coverage': sum(all_coverages) / len(all_coverages),
        'avg_score_gap': sum(all_gaps) / len(all_gaps),
        'perfect_coverage_count': sum(1 for c in all_coverages if c == 1.0)
    }
    
    print(f"{'='*70}")
    print(f"汇总统计:")
    print(f"  总测试数: {results['summary']['total_tests']}")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  平均响应时间: {results['summary']['avg_response_time_seconds']:.3f}秒")
    print(f"  平均覆盖率: {results['summary']['avg_coverage']*100:.1f}%")
    print(f"  平均分数差距: {results['summary']['avg_score_gap']:.4f}")
    print(f"  完美覆盖数: {results['summary']['perfect_coverage_count']}/{results['summary']['total_tests']}")
    print(f"{'='*70}\n")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = RESULTS_DIR / f"{timestamp}_{mode}_{test_type}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"结果已保存到: {output_file}")
    
    return results

def main():
    """主函数
    
    用法: python run_benchmark_tests.py [baseline|enhanced|both] [retrieval|full|n8n]
    
    示例:
        python run_benchmark_tests.py baseline retrieval  # 快速检索测试（直接调RagFlow）
        python run_benchmark_tests.py enhanced retrieval  # 本地关键词增强测试
        python run_benchmark_tests.py both retrieval      # 对比baseline和enhanced
        python run_benchmark_tests.py enhanced full       # 完整LLM测试（调RagFlow Chat API）
        python run_benchmark_tests.py baseline n8n        # 端到端测试（通过n8n Webhook）
    
    测试类型说明:
        retrieval: 直接调用RagFlow Retrieval API（最快，~0.5秒）
        full: 调用RagFlow Chat Completion API（中等，~10-30秒）
        n8n: 通过n8n Webhook端到端测试（最慢但最真实，~30-60秒）
    """
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
    test_type = sys.argv[2] if len(sys.argv) > 2 else 'retrieval'
    
    if mode not in ['baseline', 'enhanced', 'both']:
        print("用法: python run_benchmark_tests.py [baseline|enhanced|both] [retrieval|full|n8n]")
        print()
        print("  mode:")
        print("    baseline  - 原始查询（不做增强）")
        print("    enhanced  - 关键词增强（本地或n8n LLM增强）")
        print("    both      - 对比两种模式")
        print()
        print("  test_type:")
        print("    retrieval - 只检索（快速，~0.5秒/问题）")
        print("    full      - 含LLM生成（中等，~10-30秒/问题）")
        print("    n8n       - 端到端测试（完整流程，~30-60秒/问题）")
        sys.exit(1)
    
    if test_type not in ['retrieval', 'full', 'n8n']:
        print(f"错误: 未知的test_type '{test_type}'")
        print("支持: retrieval, full, n8n")
        sys.exit(1)
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if mode == 'both':
        baseline_results = run_all_tests('baseline', test_type)
        enhanced_results = run_all_tests('enhanced', test_type)
        return baseline_results, enhanced_results
    else:
        return run_all_tests(mode, test_type)

if __name__ == '__main__':
    main()

