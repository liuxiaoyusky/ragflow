#!/usr/bin/env python3
"""
Metadata Filter Benchmark
Compare retrieval ranking with and without metadata filter auto mode.

Usage:
    python metadata_filter_benchmark.py
"""

import requests
import json
import time
from datetime import datetime
from pathlib import Path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === Configuration ===
RAGFLOW_BASE_URL = "https://10.1.9.133:8443"
RAGFLOW_API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "fbc7fb98d4b311f084b30242ac130006"
CHAT_ID = "f472490cbabe11f0b1a00242ac130006"  # HardyBot with metadata filter auto

# OpenRouter for query enhancement
def load_openrouter_key():
    key_file = Path(__file__).parent.parent / "openai.apikey"
    with open(key_file, 'r') as f:
        return f.readline().strip()

OPENROUTER_API_KEY = None
LATEST_DATA_MONTH = "September 2025"

# 21 test questions
TEST_QUESTIONS = [
    {"id": "Q1", "question": "what is the management fee for High Dividend Stocks fund?"},
    {"id": "Q2", "question": "does High Dividend Stocks fund have performance fees?"},
    {"id": "Q3", "question": "what is the performance fee for High Dividend stocks fund?"},
    {"id": "Q4", "question": "what is the performance fee rate for High Dividend Stocks Fund?"},
    {"id": "Q5", "question": "what is the top fixed income holdings for Asian Income fund as of September 2025?"},
    {"id": "Q6", "question": "what are the top equity holdings of Asian Income as of March 2025"},
    {"id": "Q7", "question": "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025"},
    {"id": "Q8", "question": "what is the geographic exposures for the Asian Income fund?"},
    {"id": "Q9", "question": "show me the geographic locations of High dividend stocks from January 2025 to July 2025"},
    {"id": "Q10", "question": "what are the top holdings of Asian Income Fund from January 2025 to September 2025?"},
    {"id": "Q11", "question": "what is the return for high dividend stocks fund as of September 2025?"},
    {"id": "TC001", "question": "What are top holdings of Asian Income Fund from January to September 2025?"},
    {"id": "TC002", "question": "比较High Dividend Fund和Asian Income Fund 2025年8月的股息率"},
    {"id": "TC003", "question": "Show asset allocation by sector for Asian Income Fund September 2025"},
    {"id": "TC004", "question": "What is the credit rating distribution of Asian Income Fund?"},
    {"id": "TC005", "question": "惠理亚洲收益基金2025年Q1业绩表现"},
    {"id": "TC006", "question": "What are NAV codes for Asian Income Fund Class A?"},
    {"id": "TC007", "question": "Compare fee structures between Asian Income Fund and High Dividend Fund"},
    {"id": "TC008", "question": "Portfolio characteristics of Asian Income Fund from May to August 2025"},
    {"id": "TC009", "question": "哪些月份Asian Income Fund持有台积电？"},
    {"id": "TC010", "question": "What is the investment objective of Asian Income Fund?"},
]

def get_v3_prompt(question: str) -> str:
    """Get the v3.0 query enhancement prompt."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    return f"""你是基金文档检索优化专家。为问题添加精准关键词以提高检索精度。

当前日期: {current_date}
最新数据月份: {LATEST_DATA_MONTH}

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

### 2. 时间范围处理（重要！精准查询版 - 不扩展月份）
**关键：时间范围不扩展，保持原样或只加年份**
- Q1/第一季度 → Q1 2025
- Q2/第二季度 → Q2 2025
- Q3/第三季度 → Q3 2025
- "从1月到7月" → 2025（不展开！）
- "从1月到9月" → 2025（不展开！）
- "January to September 2025" → 2025（不展开！）
- 单个月份保持原样：September 2025

### 3. 默认时间处理（重要！）
当问题**未指定具体时间**时：
- 自动添加最新数据月份: {LATEST_DATA_MONTH}

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

## 示例

输入: "What are top holdings of Asian Income Fund from January to September 2025?"
输出: "What are top holdings of Asian Income Fund from January to September 2025? (Top holdings equities, Top holdings fixed income, 2025)"

输入: "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025"
输出: "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025? (High Dividend Fund, Top holdings equities, Top holdings fixed income, 2025)"

输入: "惠理亚洲收益基金2025年Q1业绩表现"
输出: "惠理亚洲收益基金2025年Q1业绩表现 (Asian Income Fund, Monthly performance, Q1 2025)"

## 用户问题
{question}

## 输出（原问题 + 括号内关键词，只输出结果，不要解释）"""


def enhance_query_v3(question: str) -> str:
    """Enhance a query using v3.0 prompt."""
    global OPENROUTER_API_KEY
    if OPENROUTER_API_KEY is None:
        OPENROUTER_API_KEY = load_openrouter_key()
    
    prompt = get_v3_prompt(question)
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": "anthropic/claude-haiku-4.5",
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


def retrieval_api_test(query: str, top_k: int = 15) -> list:
    """Test with retrieval API (no metadata filter)."""
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
    
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/retrieval",
        headers=headers,
        json={
            "question": query,
            "dataset_ids": [DATASET_ID],
            "top_k": top_k,
            "similarity_threshold": 0.0
        },
        timeout=60,
        verify=False
    )
    
    data = resp.json()
    if data.get('code') == 0:
        return data.get('data', {}).get('chunks', [])
    return []


def chat_api_test(query: str) -> dict:
    """Test with chat API (metadata filter auto, new session)."""
    headers = {"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
    
    # Create new session
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/sessions",
        headers=headers,
        json={"name": f"benchmark_{int(time.time())}"},
        timeout=30,
        verify=False
    )
    session_id = resp.json().get('data', {}).get('id')
    
    if not session_id:
        return {"error": "Failed to create session", "chunks": []}
    
    # Send query
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/chats/{CHAT_ID}/completions",
        headers=headers,
        json={
            "question": query,
            "session_id": session_id,
            "stream": False
        },
        timeout=180,
        verify=False
    )
    
    data = resp.json()
    if data.get('code') == 0:
        ref = data.get('data', {}).get('reference', {})
        chunks = ref.get('chunks', []) if isinstance(ref, dict) else []
        return {"chunks": chunks, "answer": data.get('data', {}).get('answer', '')}
    else:
        return {"error": data.get('message', 'Unknown error'), "chunks": []}


def extract_chunk_info(chunk: dict) -> dict:
    """Extract key info from a chunk."""
    content = chunk.get('content', '')
    doc_name = chunk.get('document_name', '')
    
    # Extract fund, month, section from content or doc_name
    fund = "Unknown"
    month = "Unknown"
    section = "Unknown"
    
    if "Asian Income Fund" in content or "Asian_Income" in doc_name:
        fund = "Asian Income Fund"
    elif "High Dividend" in content or "High_Dividend" in doc_name:
        fund = "High Dividend Fund"
    elif "Classic Fund" in content or "Classic" in doc_name:
        fund = "Classic Fund"
    
    # Extract month
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    month_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    for i, m in enumerate(months):
        if m in content or month_abbr[i] in doc_name:
            month = f"{m} 2025"
            break
    
    # Extract section
    sections = {
        "Top holdings equities": ["Top holdings - equities", "Top_holdings_equities", "Top holdings equities"],
        "Top holdings fixed income": ["Top holdings - fixed income", "Top_holdings_fixed", "Top holdings fixed income"],
        "Fee structure": ["Fee structure", "Fee_structure"],
        "Credit ratings": ["Credit ratings", "Credit_ratings"],
        "Investment objective": ["Investment objective", "Investment_objective"],
        "Asset type by geography": ["Asset type by geography", "Asset_type_by_geography"],
        "Asset type by sector": ["Asset type by sector", "Asset_type_by_sector"],
        "Monthly performance": ["Monthly performance", "Monthly_performance"],
        "Portfolio characteristics": ["Portfolio characteristics", "Portfolio_characteristics"],
        "NAVs & codes": ["NAVs", "NAVs_codes"],
        "Dividend information": ["Dividend information", "Dividend_information"],
    }
    
    for sec_name, patterns in sections.items():
        for p in patterns:
            if p in content or p in doc_name:
                section = sec_name
                break
    
    return {
        "fund": fund,
        "month": month,
        "section": section,
        "similarity": chunk.get('similarity', 0)
    }


def run_benchmark():
    """Run the full benchmark."""
    print("=" * 80)
    print("Metadata Filter Benchmark - v3.0 Prompt")
    print("=" * 80)
    print()
    
    results = []
    
    for i, q in enumerate(TEST_QUESTIONS):
        qid = q['id']
        question = q['question']
        
        print(f"\n[{i+1}/{len(TEST_QUESTIONS)}] {qid}: {question[:50]}...")
        
        # Step 1: Enhance query with v3.0 prompt
        print("  Enhancing query...")
        enhanced = enhance_query_v3(question)
        print(f"  Enhanced: {enhanced[:80]}...")
        
        # Step 2: Retrieval API test
        print("  Testing Retrieval API (no metadata filter)...")
        retrieval_chunks = retrieval_api_test(enhanced)
        retrieval_info = [extract_chunk_info(c) for c in retrieval_chunks[:15]]
        
        # Step 3: Chat API test
        print("  Testing Chat API (metadata filter auto)...")
        chat_result = chat_api_test(enhanced)
        
        if "error" in chat_result:
            print(f"  ⚠️  Chat API error: {chat_result['error'][:100]}")
            chat_info = []
            chat_error = chat_result['error']
        else:
            chat_info = [extract_chunk_info(c) for c in chat_result['chunks'][:15]]
            chat_error = None
        
        # Record result
        result = {
            "id": qid,
            "question": question,
            "enhanced_query": enhanced,
            "retrieval": {
                "chunk_count": len(retrieval_chunks),
                "top_chunks": retrieval_info[:5]
            },
            "chat": {
                "chunk_count": len(chat_result.get('chunks', [])),
                "top_chunks": chat_info[:5],
                "error": chat_error
            }
        }
        results.append(result)
        
        # Print summary
        print(f"  Retrieval: {len(retrieval_chunks)} chunks")
        if retrieval_info:
            print(f"    #1: {retrieval_info[0]['section']} ({retrieval_info[0]['month']})")
        
        print(f"  Chat: {len(chat_info)} chunks")
        if chat_info:
            print(f"    #1: {chat_info[0]['section']} ({chat_info[0]['month']})")
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    # Save results
    output = {
        "version": "3.0",
        "timestamp": datetime.now().isoformat(),
        "prompt_version": "v3.0",
        "total_questions": len(TEST_QUESTIONS),
        "results": results
    }
    
    output_path = Path(__file__).parent / "metadata_filter_benchmark_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n\nResults saved to: {output_path}")
    
    # Print summary table
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'ID':<8} {'Retrieval #1':<30} {'Chat #1':<30}")
    print("-" * 80)
    
    for r in results:
        ret_top = r['retrieval']['top_chunks'][0] if r['retrieval']['top_chunks'] else {}
        chat_top = r['chat']['top_chunks'][0] if r['chat']['top_chunks'] else {}
        
        ret_str = f"{ret_top.get('section', 'N/A')[:20]} ({ret_top.get('month', 'N/A')[:8]})" if ret_top else "N/A"
        chat_str = f"{chat_top.get('section', 'N/A')[:20]} ({chat_top.get('month', 'N/A')[:8]})" if chat_top else (r['chat'].get('error', 'N/A') or 'N/A')[:25]
        
        print(f"{r['id']:<8} {ret_str:<30} {chat_str:<30}")
    
    return output


if __name__ == "__main__":
    run_benchmark()


