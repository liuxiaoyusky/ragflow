#!/usr/bin/env python3
"""
Check actual meta_fields of factsheet documents in RagFlow
Usage: python tools/check_metadata.py
"""
import requests
import urllib3
import json
import os
import yaml
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load RagFlow config from YAML file
def load_ragflow_config():
    config_file = os.path.join(os.path.dirname(__file__), '..', 'ragflow_config.yaml')
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

_config = load_ragflow_config()
RAGFLOW_API_KEY = _config['api_key']
RAGFLOW_BASE_URL = _config['base_url']
DATASET_ID = _config['dataset_id']

# Get dataset info
print("="*80)
print("Checking Dataset Info")
print("="*80)

resp = requests.get(
    f"{RAGFLOW_BASE_URL}/api/v1/datasets/{DATASET_ID}",
    headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
    timeout=30,
    verify=False
)

if resp.status_code == 200:
    result = resp.json()
    data = result.get('data') if result else None
    if data:
        print(f"Dataset Name: {data.get('name')}")
        print(f"Document Count: {data.get('document_count')}")
        print(f"Chunk Count: {data.get('chunk_count')}")
    else:
        print(f"Response: {result}")
else:
    print(f"Error: {resp.status_code} - {resp.text[:200]}")

# List documents to get their IDs
print("\n" + "="*80)
print("Listing Documents")
print("="*80)

resp = requests.get(
    f"{RAGFLOW_BASE_URL}/api/v1/datasets/{DATASET_ID}/documents",
    headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
    params={"page": 1, "page_size": 10},
    timeout=30,
    verify=False
)

docs = []
if resp.status_code == 200:
    result = resp.json()
    data = result.get('data') if result else {}
    docs = data.get('docs', []) if data else []
    print(f"Found {len(docs)} documents (showing first 5)")
    
    for i, doc in enumerate(docs[:5]):
        print(f"\n--- Document {i+1} ---")
        print(f"ID: {doc.get('id')}")
        print(f"Name: {doc.get('name')}")
        print(f"Type: {doc.get('type')}")
        print(f"Size: {doc.get('size')}")
        print(f"Chunk Count: {doc.get('chunk_count')}")
        
        # Check meta_fields
        meta = doc.get('meta_fields', {})
        print(f"Meta Fields: {json.dumps(meta, indent=2, ensure_ascii=False) if meta else 'EMPTY'}")
        
        # Check other potentially useful fields
        for key in ['parser_config', 'run', 'progress_msg']:
            if key in doc and doc[key]:
                print(f"{key}: {doc[key]}")
else:
    print(f"Error: {resp.status_code} - {resp.text[:200]}")

# Skip document details API (not working)
print("\n" + "="*80)
print("Skipping Document Details (API returns empty)")
print("="*80)

# Check chunks for metadata
print("\n" + "="*80)
print("Checking Chunk Metadata (via retrieval)")
print("="*80)

resp = requests.post(
    f"{RAGFLOW_BASE_URL}/api/v1/retrieval",
    headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
    json={
        "question": "Asian Income Fund Fee structure",
        "dataset_ids": [DATASET_ID],
        "top_k": 3
    },
    timeout=30,
    verify=False
)

if resp.status_code == 200:
    chunks = resp.json().get('data', {}).get('chunks', [])
    print(f"Retrieved {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"All chunk fields: {list(chunk.keys())}")
        for k, v in chunk.items():
            if k != 'content' and v:
                print(f"  {k}: {v if len(str(v)) < 80 else str(v)[:80]+'...'}")
else:
    print(f"Error: {resp.status_code}")