#!/usr/bin/env python3
"""
批量为 RAGFlow 知识库文档设置 metadata
从文件名中解析 fund_type 和 report_time
"""

import json
import re
import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
BASE_URL = "https://10.1.9.133:8443"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
DATASET_ID = "92b074cccb6311f0a80a0242ac130006"


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


def parse_filename(filename: str) -> dict | None:
    """
    解析文件名，提取 fund_type 和 report_time
    格式: VP_{Fund Type}-{YYYYMM}-Eng.pdf
    """
    # 月份名称映射
    MONTH_NAMES = {
        "01": "January", "02": "February", "03": "March",
        "04": "April", "05": "May", "06": "June",
        "07": "July", "08": "August", "09": "September",
        "10": "October", "11": "November", "12": "December"
    }
    
    match = re.match(r'VP_(.+)-(\d{6})-Eng\.pdf', filename)
    if not match:
        return None
    
    fund_type = match.group(1)
    yyyymm = match.group(2)
    year = yyyymm[:4]
    month = yyyymm[4:]
    
    # 转换为 YYYY-MM-DD 格式 (每月第一天，用于auto metadata filter日期比较)
    report_time = f"{year}-{month}-01"
    # 转换为自然语言格式: "January 2025"
    report_month = f"{MONTH_NAMES.get(month, month)} {year}"
    
    return {
        "fund_type": fund_type,
        "report_time": report_time,
        "report_month": report_month
    }


def set_document_meta(dataset_id: str, doc_id: str, meta: dict) -> tuple[bool, str]:
    """设置文档的 metadata (通过 SDK API)"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{doc_id}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "meta_fields": meta
    }
    
    response = requests.put(url, headers=headers, json=payload, verify=False)
    data = response.json()
    
    if data.get("code") == 0:
        return True, ""
    else:
        return False, data.get("message", "Unknown error")


def main():
    print("=" * 60)
    print("批量设置文档 Metadata")
    print("=" * 60)
    
    # 1. 获取文档列表
    print("\n[1/3] 获取文档列表...")
    docs = get_documents(DATASET_ID)
    print(f"    共 {len(docs)} 个文档")
    
    # 2. 解析并设置 metadata
    print("\n[2/3] 解析文件名并设置 metadata...")
    success_count = 0
    fail_count = 0
    
    for doc in docs:
        name = doc.get("name", "")
        doc_id = doc.get("id", "")
        current_meta = doc.get("meta_fields", {})
        
        # 解析文件名
        parsed = parse_filename(name)
        if not parsed:
            print(f"    ⚠️  跳过 (无法解析): {name}")
            fail_count += 1
            continue
        
        # 不跳过已有 metadata 的文档，直接更新
        
        # 设置 metadata
        success, error = set_document_meta(DATASET_ID, doc_id, parsed)
        if success:
            print(f"    ✅ {name}")
            print(f"       → fund_type: {parsed['fund_type']}, report_time: {parsed['report_time']}")
            success_count += 1
        else:
            print(f"    ❌ 失败: {name} - {error}")
            fail_count += 1
    
    # 3. 汇总
    print("\n[3/3] 完成!")
    print("=" * 60)
    print(f"成功: {success_count}")
    print(f"失败/跳过: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()

