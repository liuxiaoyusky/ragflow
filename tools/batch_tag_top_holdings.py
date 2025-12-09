#!/usr/bin/env python3
"""
批量为 Top Holdings 表格 chunks 添加关键词标签
自动识别包含 "top holdings" 内容的表格并打标签

用法：
    python batch_tag_top_holdings.py          # 交互式确认
    python batch_tag_top_holdings.py --yes    # 跳过确认直接执行
    python batch_tag_top_holdings.py --dry-run  # 只预览不执行
"""

import argparse
import json
import re
import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置 - 与 batch_set_metadata.py 保持一致
BASE_URL = "https://10.1.9.133:8443"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "92b074cccb6311f0a80a0242ac130006"

# Top Holdings 识别关键词（不区分大小写）
# 基于 VP_High-Dividend-202501-Eng.pdf 等 factsheet 的实际格式
TOP_HOLDINGS_KEYWORDS = [
    "top 10 holdings",
    "top ten holdings",
    "top holdings",
    "these securities constitute",  # "These securities constitute 42% of the Fund"
]

# 表格结构验证：必须是表格且包含持仓相关列名
# 真正的Top Holdings表格特征：<table>...<td>Name</td>...<td>Sector</td>...
HOLDINGS_TABLE_REQUIRED = [
    "<table>",   # 必须是表格
]

# 必须包含以下列名之一（持仓表格的典型列）
HOLDINGS_COLUMN_NAMES = [
    "<td>name</td>",
    "<td>stock name</td>",
    "<td>industry</td>",
    "<td>sector",  # sector 4, sector等
]

# 排除这些内容（误判过滤）
# 注意：只排除明确不是holdings的内容，不要过度排除
EXCLUDE_KEYWORDS = [
    "dividend information - class",  # 分红信息表格
    "dividend amount / unit",        # 分红金额表格
    "ex-dividend date",              # 分红日期表格
    "eligible collective investment",
    "msci ac asia pacific",          # MSCI脚注说明
    "morningstar rating",            # Morningstar评级说明
]

# 要添加的关键词标签
IMPORTANT_KEYWORDS_TO_ADD = [
    "top holdings",
    "top 10 holdings",
    "portfolio holdings", 
    "持仓明细",
    "主要持仓",
    "stock holdings",
]


def get_documents(dataset_id: str) -> list:
    """获取知识库中的所有文档"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params = {"page": 1, "page_size": 200}
    
    response = requests.get(url, headers=headers, params=params, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get documents: {data.get('message')}")
    
    return data.get("data", {}).get("docs", [])


def get_chunks(dataset_id: str, doc_id: str, page: int = 1, page_size: int = 100) -> dict:
    """获取文档的chunks"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params = {"page": page, "page_size": page_size}
    
    response = requests.get(url, headers=headers, params=params, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get chunks: {data.get('message')}")
    
    return data.get("data", {})


def get_all_chunks(dataset_id: str, doc_id: str) -> list:
    """获取文档的所有chunks（处理分页）"""
    all_chunks = []
    page = 1
    page_size = 100
    
    while True:
        data = get_chunks(dataset_id, doc_id, page, page_size)
        chunks = data.get("chunks", [])
        all_chunks.extend(chunks)
        
        total = data.get("total", 0)
        if len(all_chunks) >= total or not chunks:
            break
        page += 1
    
    return all_chunks


def is_top_holdings_chunk(chunk: dict) -> bool:
    """
    判断chunk是否是Top Holdings表格
    基于 Value Partners factsheet 格式优化
    
    识别策略：
    1. 必须是表格 (<table>)
    2. 必须包含持仓表格的列名 (Name, Sector等)
    3. 排除分红信息、脚注等误判内容
    """
    content = chunk.get("content", "").lower()
    
    # 排除明确不是holdings的内容
    for exclude in EXCLUDE_KEYWORDS:
        if exclude.lower() in content:
            return False
    
    # 方法1：包含 "top holdings" 或 "these securities constitute" 关键词
    has_title_keyword = any(kw.lower() in content for kw in TOP_HOLDINGS_KEYWORDS)
    
    # 方法2：是表格且包含持仓相关列名
    is_table = "<table>" in content
    has_holdings_column = any(col.lower() in content for col in HOLDINGS_COLUMN_NAMES)
    
    # 必须满足：(有标题关键词) 或 (是表格且有持仓列名)
    if has_title_keyword:
        return True
    
    if is_table and has_holdings_column:
        return True
    
    return False


def update_chunk_keywords(dataset_id: str, doc_id: str, chunk_id: str, keywords: list) -> tuple[bool, str]:
    """更新chunk的important_keywords"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks/{chunk_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "important_keywords": keywords
    }
    
    response = requests.put(url, headers=headers, json=payload, verify=False)
    data = response.json()
    
    if data.get("code") == 0:
        return True, ""
    else:
        return False, data.get("message", "Unknown error")


def preview_chunk_content(content: str, max_length: int = 100) -> str:
    """预览chunk内容"""
    content = content.replace("\n", " ").strip()
    if len(content) > max_length:
        return content[:max_length] + "..."
    return content


def main():
    parser = argparse.ArgumentParser(description="批量为 Top Holdings 表格 chunks 添加关键词标签")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认直接执行")
    parser.add_argument("--dry-run", action="store_true", help="只预览不执行")
    args = parser.parse_args()
    
    print("=" * 70)
    print("批量为 Top Holdings 表格 Chunks 添加关键词标签")
    print("=" * 70)
    
    # 1. 获取文档列表
    print("\n[1/4] 获取文档列表...")
    docs = get_documents(DATASET_ID)
    print(f"    共 {len(docs)} 个文档")
    
    # 2. 扫描所有chunks，找出Top Holdings表格
    print("\n[2/4] 扫描所有chunks，识别Top Holdings表格...")
    
    top_holdings_chunks = []  # [(doc_id, doc_name, chunk)]
    total_chunks = 0
    
    for doc in docs:
        doc_id = doc.get("id", "")
        doc_name = doc.get("name", "")
        
        chunks = get_all_chunks(DATASET_ID, doc_id)
        total_chunks += len(chunks)
        
        for chunk in chunks:
            if is_top_holdings_chunk(chunk):
                top_holdings_chunks.append((doc_id, doc_name, chunk))
    
    print(f"    扫描了 {total_chunks} 个chunks")
    print(f"    找到 {len(top_holdings_chunks)} 个Top Holdings相关chunks")
    
    if not top_holdings_chunks:
        print("\n⚠️  未找到任何Top Holdings表格，请检查关键词配置")
        return
    
    # 3. 预览找到的chunks
    print("\n[3/4] 预览找到的Top Holdings chunks:")
    print("-" * 70)
    for i, (doc_id, doc_name, chunk) in enumerate(top_holdings_chunks, 1):
        chunk_id = chunk.get("id", "")
        content = chunk.get("content", "")
        existing_keywords = chunk.get("important_keywords", [])
        
        print(f"\n  [{i}] 文档: {doc_name}")
        print(f"      Chunk ID: {chunk_id[:16]}...")
        print(f"      现有关键词: {existing_keywords}")
        print(f"      内容预览: {preview_chunk_content(content, 150)}")
    print("-" * 70)
    
    # Dry-run 模式
    if args.dry_run:
        print("\n[Dry-run 模式] 预览完成，未执行任何更新")
        return
    
    # 4. 确认并更新
    print(f"\n[4/4] 准备添加关键词: {IMPORTANT_KEYWORDS_TO_ADD}")
    
    if not args.yes:
        confirm = input("\n确认要为这些chunks添加关键词吗？(y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消操作")
            return
    else:
        print("\n[--yes 模式] 跳过确认，直接执行...")
    
    print("\n开始更新...")
    success_count = 0
    fail_count = 0
    
    for doc_id, doc_name, chunk in top_holdings_chunks:
        chunk_id = chunk.get("id", "")
        existing_keywords = chunk.get("important_keywords", [])
        
        # 合并现有关键词和新关键词（去重）
        merged_keywords = list(set(existing_keywords + IMPORTANT_KEYWORDS_TO_ADD))
        
        success, error = update_chunk_keywords(DATASET_ID, doc_id, chunk_id, merged_keywords)
        
        if success:
            print(f"    ✅ {doc_name} - {chunk_id[:16]}...")
            success_count += 1
        else:
            print(f"    ❌ {doc_name} - {chunk_id[:16]}... - 错误: {error}")
            fail_count += 1
    
    # 汇总
    print("\n" + "=" * 70)
    print("完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print("=" * 70)


if __name__ == "__main__":
    main()

