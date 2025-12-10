#!/usr/bin/env python3
"""
模型判断力对比测试
对 Gemini 2.0 Flash 表现最差的3道题，用不同模型测试生成回答质量
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
OPENROUTER_API_KEY = open('/home/calvin/github/ragflow/openai.apikey').read().strip()
RAGFLOW_API_URL = "https://10.1.9.133:8443/api/v1"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"

# 待测试的模型
MODELS = [
    "google/gemini-2.0-flash-001",
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct"
]

# Gemini 2.0 Flash 评分最差的3道题
TEST_CASES = [
    {
        "id": "TC002",
        "question": "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率",
        "enhanced_question": "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率 (Dividend information, August 2025)",
        "gemini_score": 1.0,
        "issue": "时间维度错误，可能幻觉"
    },
    {
        "id": "TC009",
        "question": "哪些月份Asian Income Fund持有台积电？",
        "enhanced_question": "哪些月份Asian Income Fund持有台积电？ (Top holdings - equities, Taiwan Semiconductor Manufacturing Co Ltd)",
        "gemini_score": 5.0,
        "issue": "遗漏3月份，无持仓比例"
    },
    {
        "id": "TC008",
        "question": "Portfolio characteristics of Asian Income Fund from May to August 2025",
        "enhanced_question": "Portfolio characteristics of Asian Income Fund from May to August 2025 (Portfolio characteristics, May 2025, June 2025, July 2025, August 2025)",
        "gemini_score": 6.0,
        "issue": "缺少久期、持仓数量等关键指标"
    }
]

def call_retrieval(question, top_n=10):
    """调用RagFlow检索API获取chunks"""
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "question": question,
        "dataset_ids": [DATASET_ID],
        "top_n": top_n,
        "similarity_threshold": 0.0,
        "keyword_similarity_weight": 0.5
    }
    response = requests.post(f"{RAGFLOW_API_URL}/retrieval", json=payload, headers=headers, verify=False, timeout=60)
    return response.json().get('data', {}).get('chunks', [])

def format_chunks_for_prompt(chunks):
    """将chunks格式化为prompt中的上下文"""
    context_parts = []
    for i, chunk in enumerate(chunks):
        content = chunk.get('content', '')
        doc_name = chunk.get('document_keyword', 'Unknown')
        context_parts.append(f"[来源{i+1}: {doc_name}]\n{content}\n")
    return "\n".join(context_parts)

def call_model(model, question, context):
    """调用OpenRouter API生成回答"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://n8n.vp.com.hk",
        "X-Title": "Model Comparison Test"
    }
    
    system_prompt = """你是一个专业的基金分析助手。根据提供的知识库内容回答用户问题。
要求：
1. 只使用提供的知识库内容回答，不要编造信息
2. 如果信息不完整，明确指出
3. 引用来源时使用[来源X]格式
4. 回答要准确、完整、结构清晰"""
    
    user_prompt = f"""知识库内容：
{context}

用户问题：{question}

请根据上述知识库内容回答问题。"""
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    start_time = time.time()
    try:
        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            return answer, elapsed, None
        else:
            return None, elapsed, f"API error: {response.status_code} - {response.text[:200]}"
    except Exception as e:
        return None, time.time() - start_time, str(e)

def run_comparison():
    """运行对比测试"""
    print("=" * 80)
    print("模型判断力对比测试")
    print("=" * 80)
    
    results = []
    
    for tc in TEST_CASES:
        print(f"\n{'='*80}")
        print(f"测试 {tc['id']}: {tc['question'][:50]}...")
        print(f"Gemini原分: {tc['gemini_score']}, 问题: {tc['issue']}")
        print("=" * 80)
        
        # 检索chunks
        print("\n检索中...")
        chunks = call_retrieval(tc['enhanced_question'])
        context = format_chunks_for_prompt(chunks)
        print(f"检索到 {len(chunks)} 个chunks")
        
        tc_results = {
            "test_id": tc['id'],
            "question": tc['question'],
            "enhanced_question": tc['enhanced_question'],
            "gemini_original_score": tc['gemini_score'],
            "chunks_count": len(chunks),
            "model_answers": {}
        }
        
        # 对每个模型生成回答
        for model in MODELS:
            model_name = model.split('/')[-1]
            print(f"\n>>> 测试模型: {model_name}")
            
            answer, elapsed, error = call_model(model, tc['question'], context)
            
            if error:
                print(f"    ❌ 错误: {error}")
                tc_results['model_answers'][model] = {
                    "error": error,
                    "time": elapsed
                }
            else:
                preview = answer[:150].replace('\n', ' ') if answer else "无回答"
                print(f"    ✓ 耗时: {elapsed:.2f}s")
                print(f"    回答预览: {preview}...")
                tc_results['model_answers'][model] = {
                    "answer": answer,
                    "time": elapsed,
                    "answer_length": len(answer) if answer else 0
                }
        
        results.append(tc_results)
    
    return results

def print_comparison_table(results):
    """打印对比表格"""
    print("\n" + "=" * 80)
    print("对比结果汇总")
    print("=" * 80)
    
    for tc_result in results:
        print(f"\n### {tc_result['test_id']}: {tc_result['question'][:60]}...")
        print(f"Gemini原分: {tc_result['gemini_original_score']}")
        print("-" * 80)
        print(f"{'模型':<35} {'耗时':>8} {'长度':>8} {'状态':>10}")
        print("-" * 80)
        
        for model, data in tc_result['model_answers'].items():
            model_name = model.split('/')[-1][:30]
            if 'error' in data:
                print(f"{model_name:<35} {data['time']:>7.2f}s {'N/A':>8} {'❌ 失败':>10}")
            else:
                print(f"{model_name:<35} {data['time']:>7.2f}s {data['answer_length']:>8} {'✓ 成功':>10}")

def save_results(results):
    """保存详细结果"""
    output_dir = Path("/home/calvin/github/ragflow/docs/benchmark/model_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"comparison_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果已保存到: {output_file}")
    
    # 同时生成Markdown报告
    md_file = output_dir / f"comparison_{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# 模型判断力对比测试报告\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for tc_result in results:
            f.write(f"## {tc_result['test_id']}: {tc_result['question']}\n\n")
            f.write(f"- **增强后问题**: {tc_result['enhanced_question']}\n")
            f.write(f"- **Gemini原始得分**: {tc_result['gemini_original_score']}\n")
            f.write(f"- **检索chunks数**: {tc_result['chunks_count']}\n\n")
            
            for model, data in tc_result['model_answers'].items():
                model_name = model.split('/')[-1]
                f.write(f"### {model_name}\n\n")
                
                if 'error' in data:
                    f.write(f"**错误**: {data['error']}\n\n")
                else:
                    f.write(f"- **耗时**: {data['time']:.2f}s\n")
                    f.write(f"- **回答长度**: {data['answer_length']} 字符\n\n")
                    f.write("**回答内容**:\n\n")
                    f.write(f"```\n{data['answer']}\n```\n\n")
            
            f.write("---\n\n")
    
    print(f"Markdown报告已保存到: {md_file}")

def main():
    results = run_comparison()
    print_comparison_table(results)
    save_results(results)

if __name__ == '__main__':
    main()

