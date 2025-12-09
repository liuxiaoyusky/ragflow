#!/usr/bin/env python3
"""
批量处理 Chunk Keywords

基于预定义的标题列表，匹配chunk内容中的标题并设置为keywords。

标题列表来自 Value Partners Fund factsheet 的章节标题。

用法：
    python batch_process_chunk_keywords.py          # 交互式确认
    python batch_process_chunk_keywords.py --yes    # 跳过确认直接执行
    python batch_process_chunk_keywords.py --dry-run  # 只预览不执行
"""

import argparse
import json
import re
import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
BASE_URL = "https://10.1.9.133:8443"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "92b074cccb6311f0a80a0242ac130006"  # 原始dataset

# ============ 标题关键词列表 ============
# 这些是 factsheet 中的章节标题，用于匹配和设置keywords

# 简单标题 -> 直接匹配添加
SIMPLE_TITLE_KEYWORDS = [
    "Investment objective",
    "Performance since launch",
    "Performance update",
    "NAVs & codes",
    "Dividend information",
    "Monthly performance",
    "Portfolio characteristics",
    "Asset type by geography",
    "Asset type by sector",
    "Credit ratings of fixed income",
    "Credit ratings",
    "Fund facts",
    "Fee structure & Subscription information",
    "Fee structure",
    "Subscription information",
    "Senior investment staff",
    "Key fund and corporate awards",
]

# 基金类型关键词
FUND_TYPE_KEYWORDS = [
    "Asian Income Fund",
    "High Dividend Fund",
    "Classic Fund",
]


# ============ 关键词提取 ============

def detect_top_holdings_type(content: str) -> str:
    """
    检测Top holdings是equities还是fixed income
    
    equities特征：
    - 包含 "Top holdings - equities" 或 "Top holdings – equities"
    - 包含行业如 "Semiconductors", "Banks", "Technology"
    - 包含公司如 "Taiwan Semiconductor", "SK Hynix"
    
    fixed income特征：
    - 包含 "Top holdings - fixed income" 或 "Top holdings – fixed income"
    - 包含债券信息如 "5% 05/18/2026", "PERP", "Industrials", "Financials"
    - 包含公司如 "Fortune Star", "Sumitomo Mitsui"
    """
    content_lower = content.lower()
    
    # 明确的标题标识
    if re.search(r'top holdings\s*[-–]\s*equities', content_lower):
        return "equities"
    if re.search(r'top holdings\s*[-–]\s*fixed income', content_lower):
        return "fixed_income"
    
    # 通过特征判断
    equities_indicators = [
        r'taiwan semiconductor',
        r'sk hynix',
        r'tencent holdings',
        r'china mobile',
        r'alchip technologies',
        r'wiwynn corp',
        r'icici bank',
        r'semiconductors\s*&\s*semiconductor equipment',
        r'<td>industry\s*\d*</td>',  # equities表格的列名
    ]
    
    fixed_income_indicators = [
        r'fortune star',
        r'sumitomo mitsui',
        r'ehi car services',
        r'elect global',
        r'westwood group',
        r'\d+%\s*\d{2}/\d{2}/\d{4}',  # 债券格式如 "5% 05/18/2026"
        r'perp',  # perpetual bond
        r'<td>sector\s*\d*</td>',  # fixed income表格的列名
    ]
    
    equities_score = sum(1 for p in equities_indicators if re.search(p, content_lower))
    fixed_income_score = sum(1 for p in fixed_income_indicators if re.search(p, content_lower))
    
    if equities_score > fixed_income_score and equities_score >= 2:
        return "equities"
    if fixed_income_score > equities_score and fixed_income_score >= 2:
        return "fixed_income"
    
    return "unknown"


def extract_title_keywords(content: str) -> list:
    """
    从content中匹配预定义的标题关键词
    多个关键词可以提高搜索排名
    """
    keywords = []
    
    # 清理content用于匹配
    clean_content = re.sub(r'<[^>]+>', ' ', content)
    clean_content = re.sub(r'\s+', ' ', clean_content)
    
    # 匹配简单标题关键词
    for title in SIMPLE_TITLE_KEYWORDS:
        pattern = re.escape(title)
        if re.search(pattern, clean_content, re.IGNORECASE):
            keywords.append(title)
    
    # 特殊处理 Top holdings - 区分 equities 和 fixed income
    if re.search(r'top holdings', clean_content, re.IGNORECASE):
        holdings_type = detect_top_holdings_type(content)
        
        if holdings_type == "equities":
            # 添加多个相关关键词，提高匹配度
            keywords.append("Top holdings - equities")
            keywords.append("Top holdings")
            keywords.append("equities")
        elif holdings_type == "fixed_income":
            keywords.append("Top holdings - fixed income")
            keywords.append("Top holdings")
            keywords.append("fixed income")
        else:
            # 无法确定类型，只添加通用关键词
            keywords.append("Top holdings")
    
    # 匹配基金类型关键词
    for fund_type in FUND_TYPE_KEYWORDS:
        pattern = re.escape(fund_type)
        if re.search(pattern, clean_content, re.IGNORECASE):
            if fund_type not in keywords:
                keywords.append(fund_type)
    
    return keywords


def detect_chunk_type(content: str) -> str:
    """
    检测chunk的内容类型
    返回: 'text', 'table', 'image'
    """
    content_lower = content.lower().strip()
    
    # 检测图片描述 (VLM生成的内容)
    if content_lower.startswith("- **visual type:**") or \
       content_lower.startswith("**visual type:**") or \
       content_lower.startswith("based on the visual analysis"):
        return "image"
    
    # 检测表格
    if "<table>" in content_lower:
        return "table"
    
    # 默认为文字
    return "text"


def filter_image_keywords(content: str, existing_keywords: list) -> list:
    """
    对于图片类型，保留图表类型关键词
    """
    keywords = []
    
    # 检测图表类型
    chart_types = [
        ("Line Chart", r"line\s*chart"),
        ("Bar Chart", r"bar\s*chart"),
        ("Pie Chart", r"pie\s*chart"),
        ("QR Code", r"qr\s*code"),
        ("Trophy", r"trophy"),
        ("Icon", r"icon|illustration"),
    ]
    
    for name, pattern in chart_types:
        if re.search(pattern, content, re.IGNORECASE):
            keywords.append(name)
    
    # 如果没有检测到，从现有keywords中选择
    if not keywords and existing_keywords:
        # 选择最短的1-2个
        sorted_kw = sorted(existing_keywords, key=len)
        keywords = [kw.strip() for kw in sorted_kw[:2] if kw.strip()]
    
    return keywords[:2]  # 图片最多2个keywords


# ============ API 操作 ============

def get_documents(dataset_id: str) -> list:
    """获取dataset中的所有文档"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params = {"page": 1, "page_size": 200}
    
    response = requests.get(url, headers=headers, params=params, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get documents: {data.get('message')}")
    
    return data.get("data", {}).get("docs", [])


def get_all_chunks(dataset_id: str, doc_id: str) -> list:
    """获取文档的所有chunks（处理分页）"""
    all_chunks = []
    page = 1
    page_size = 100
    
    while True:
        url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        params = {"page": page, "page_size": page_size}
        
        response = requests.get(url, headers=headers, params=params, verify=False)
        data = response.json()
        
        if data.get("code") != 0:
            raise Exception(f"Failed to get chunks: {data.get('message')}")
        
        chunks = data.get("data", {}).get("chunks", [])
        all_chunks.extend(chunks)
        
        total = data.get("data", {}).get("total", 0)
        if len(all_chunks) >= total or not chunks:
            break
        page += 1
    
    return all_chunks


def update_chunk_keywords(dataset_id: str, doc_id: str, chunk_id: str, keywords: list) -> tuple:
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


def preview_content(content: str, max_length: int = 80) -> str:
    """预览chunk内容"""
    content = content.replace("\n", " ").strip()
    # 移除HTML标签用于显示
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'\s+', ' ', content)
    if len(content) > max_length:
        return content[:max_length] + "..."
    return content


# ============ 主程序 ============

def process_chunk(chunk: dict) -> dict:
    """
    处理单个chunk，返回处理结果
    
    逻辑：
    1. 检测chunk类型（text/table/image）
    2. 从content中匹配预定义的标题关键词
    3. 对于图片类型，使用特殊处理
    """
    content = chunk.get("content", "")
    existing_keywords = chunk.get("important_keywords", [])
    
    # 检测类型
    chunk_type = detect_chunk_type(content)
    
    # 根据类型生成新关键词
    if chunk_type == "image":
        # 图片类型：检测图表类型
        new_keywords = filter_image_keywords(content, existing_keywords)
    else:
        # 文字和表格类型：匹配标题关键词
        new_keywords = extract_title_keywords(content)
    
    return {
        "chunk_id": chunk.get("id", ""),
        "chunk_type": chunk_type,
        "old_keywords": existing_keywords,
        "new_keywords": new_keywords,
        "content_preview": preview_content(content),
        "changed": set(existing_keywords) != set(new_keywords)
    }


def main():
    parser = argparse.ArgumentParser(description="批量处理 Chunk Keywords")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认直接执行")
    parser.add_argument("--dry-run", action="store_true", help="只预览不执行")
    parser.add_argument("--dataset-id", type=str, default=DATASET_ID, help="指定dataset ID")
    args = parser.parse_args()
    
    dataset_id = args.dataset_id
    
    print("=" * 80)
    print("批量处理 Chunk Keywords")
    print("=" * 80)
    print(f"Dataset ID: {dataset_id}")
    print()
    
    # 1. 获取文档列表
    print("[1/4] 获取文档列表...")
    docs = get_documents(dataset_id)
    print(f"    共 {len(docs)} 个文档")
    
    # 2. 扫描所有chunks并分析
    print("\n[2/4] 扫描所有chunks并分析类型...")
    
    all_results = []  # [(doc_id, doc_name, result)]
    type_stats = {"text": 0, "table": 0, "image": 0}
    change_count = 0
    
    for doc in docs:
        doc_id = doc.get("id", "")
        doc_name = doc.get("name", "")
        
        chunks = get_all_chunks(dataset_id, doc_id)
        
        for chunk in chunks:
            result = process_chunk(chunk)
            result["doc_id"] = doc_id
            result["doc_name"] = doc_name
            all_results.append(result)
            
            type_stats[result["chunk_type"]] += 1
            if result["changed"]:
                change_count += 1
    
    print(f"    扫描了 {len(all_results)} 个chunks")
    print(f"    类型分布: 文字={type_stats['text']}, 表格={type_stats['table']}, 图片={type_stats['image']}")
    print(f"    需要更新: {change_count} 个chunks")
    
    # 3. 预览变更
    print("\n[3/4] 预览需要更新的chunks:")
    print("-" * 80)
    
    # 只显示需要变更的
    changed_results = [r for r in all_results if r["changed"]]
    
    # 分类显示
    for chunk_type in ["text", "table", "image"]:
        type_results = [r for r in changed_results if r["chunk_type"] == chunk_type]
        if not type_results:
            continue
        
        type_name = {"text": "📝 文字类型", "table": "📊 表格类型", "image": "🖼️ 图片类型"}[chunk_type]
        print(f"\n{type_name} ({len(type_results)} 个):")
        
        for i, result in enumerate(type_results[:10], 1):  # 每类最多显示10个
            print(f"\n  [{i}] {result['doc_name'][:30]}...")
            print(f"      内容: {result['content_preview']}")
            print(f"      旧关键词: {result['old_keywords']}")
            print(f"      新关键词: {result['new_keywords']}")
        
        if len(type_results) > 10:
            print(f"\n  ... 还有 {len(type_results) - 10} 个 {chunk_type} 类型的变更未显示")
    
    print("\n" + "-" * 80)
    
    # Dry-run 模式
    if args.dry_run:
        print("\n[Dry-run 模式] 预览完成，未执行任何更新")
        return
    
    # 4. 确认并更新
    print(f"\n[4/4] 准备更新 {change_count} 个chunks的关键词")
    
    if not changed_results:
        print("    没有需要更新的chunks")
        return
    
    if not args.yes:
        confirm = input("\n确认要更新这些chunks的关键词吗？(y/n): ").strip().lower()
        if confirm != 'y':
            print("已取消操作")
            return
    else:
        print("\n[--yes 模式] 跳过确认，直接执行...")
    
    print("\n开始更新...")
    success_count = 0
    fail_count = 0
    
    for result in changed_results:
        doc_id = result["doc_id"]
        chunk_id = result["chunk_id"]
        new_keywords = result["new_keywords"]
        
        success, error = update_chunk_keywords(dataset_id, doc_id, chunk_id, new_keywords)
        
        if success:
            print(f"    ✅ {result['doc_name'][:25]}... - {chunk_id[:12]}...")
            success_count += 1
        else:
            print(f"    ❌ {result['doc_name'][:25]}... - {chunk_id[:12]}... - 错误: {error}")
            fail_count += 1
    
    # 汇总
    print("\n" + "=" * 80)
    print("完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()

