#!/usr/bin/env python3
"""
复制 Dataset 到新的测试 Dataset

用法：
    python copy_dataset.py                    # 复制到新dataset
    python copy_dataset.py --name "自定义名称"  # 使用自定义名称
"""

import argparse
import json
import requests
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置 - 与其他脚本保持一致
BASE_URL = "https://10.1.9.133:8443"
API_KEY = "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw"
SOURCE_DATASET_ID = "92b074cccb6311f0a80a0242ac130006"


def get_dataset_info(dataset_id: str) -> dict:
    """获取dataset信息"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    response = requests.get(url, headers=headers, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to get dataset: {data.get('message')}")
    
    return data.get("data", {})


def create_dataset(name: str, description: str = "") -> dict:
    """创建新dataset"""
    url = f"{BASE_URL}/api/v1/datasets"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "description": description,
        "chunk_method": "naive"
    }
    
    response = requests.post(url, headers=headers, json=payload, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to create dataset: {data.get('message')}")
    
    return data.get("data", {})


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


def create_virtual_document(dataset_id: str, name: str) -> dict:
    """在dataset中创建虚拟文档"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name
    }
    
    response = requests.post(url, headers=headers, json=payload, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to create document: {data.get('message')}")
    
    # 返回创建的文档信息
    docs = data.get("data", [])
    if docs:
        return docs[0]
    return {}


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


def add_chunk(dataset_id: str, doc_id: str, content: str, keywords: list, questions: list = None) -> dict:
    """添加chunk到文档"""
    url = f"{BASE_URL}/api/v1/datasets/{dataset_id}/documents/{doc_id}/chunks"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": content,
        "important_keywords": keywords or []
    }
    if questions:
        payload["questions"] = questions
    
    response = requests.post(url, headers=headers, json=payload, verify=False)
    data = response.json()
    
    if data.get("code") != 0:
        raise Exception(f"Failed to add chunk: {data.get('message')}")
    
    return data.get("data", {})


def main():
    parser = argparse.ArgumentParser(description="复制 Dataset 到新的测试 Dataset")
    parser.add_argument("--name", type=str, default=None, help="新dataset的名称")
    args = parser.parse_args()
    
    print("=" * 70)
    print("复制 Dataset 到测试 Dataset")
    print("=" * 70)
    
    # 1. 获取源dataset信息
    print("\n[1/5] 获取源dataset信息...")
    try:
        source_info = get_dataset_info(SOURCE_DATASET_ID)
        source_name = source_info.get("name", "Unknown")
        print(f"    源dataset: {source_name} (ID: {SOURCE_DATASET_ID})")
    except Exception as e:
        print(f"    无法获取源dataset信息: {e}")
        source_name = "Dataset"
    
    # 2. 创建新dataset
    new_name = args.name or f"{source_name}-keywords-test"
    print(f"\n[2/5] 创建新dataset: {new_name}...")
    
    try:
        new_dataset = create_dataset(
            name=new_name,
            description=f"Copy of {source_name} for keyword testing"
        )
        new_dataset_id = new_dataset.get("id")
        print(f"    ✅ 新dataset创建成功: {new_dataset_id}")
    except Exception as e:
        print(f"    ❌ 创建失败: {e}")
        return
    
    # 3. 获取源dataset的所有文档
    print("\n[3/5] 获取源dataset的文档列表...")
    docs = get_documents(SOURCE_DATASET_ID)
    print(f"    共 {len(docs)} 个文档")
    
    # 4. 复制每个文档和其chunks
    print("\n[4/5] 复制文档和chunks...")
    
    total_chunks_copied = 0
    doc_mapping = {}  # 原doc_id -> 新doc_id
    
    for i, doc in enumerate(docs, 1):
        doc_id = doc.get("id", "")
        doc_name = doc.get("name", "")
        
        print(f"\n    [{i}/{len(docs)}] 处理文档: {doc_name}")
        
        # 创建虚拟文档
        try:
            new_doc = create_virtual_document(new_dataset_id, doc_name)
            new_doc_id = new_doc.get("id")
            doc_mapping[doc_id] = new_doc_id
            print(f"        创建虚拟文档: {new_doc_id[:16]}...")
        except Exception as e:
            print(f"        ❌ 创建文档失败: {e}")
            continue
        
        # 获取原文档的所有chunks
        try:
            chunks = get_all_chunks(SOURCE_DATASET_ID, doc_id)
            print(f"        获取到 {len(chunks)} 个chunks")
        except Exception as e:
            print(f"        ❌ 获取chunks失败: {e}")
            continue
        
        # 复制每个chunk
        chunk_success = 0
        for chunk in chunks:
            content = chunk.get("content", "")
            keywords = chunk.get("important_keywords", [])
            questions = chunk.get("questions", [])
            
            try:
                add_chunk(new_dataset_id, new_doc_id, content, keywords, questions)
                chunk_success += 1
            except Exception as e:
                print(f"        ⚠️ 复制chunk失败: {e}")
        
        total_chunks_copied += chunk_success
        print(f"        ✅ 复制了 {chunk_success}/{len(chunks)} 个chunks")
    
    # 5. 汇总
    print("\n" + "=" * 70)
    print("[5/5] 复制完成!")
    print(f"    新Dataset ID: {new_dataset_id}")
    print(f"    新Dataset名称: {new_name}")
    print(f"    复制文档数: {len(doc_mapping)}")
    print(f"    复制Chunks数: {total_chunks_copied}")
    print(f"\n    访问URL: {BASE_URL}/dataset/dataset/{new_dataset_id}")
    print("=" * 70)
    
    # 输出新dataset ID供后续脚本使用
    print(f"\n💡 提示: 在 batch_process_chunk_keywords.py 中使用此ID:")
    print(f'    DATASET_ID = "{new_dataset_id}"')


if __name__ == "__main__":
    main()

