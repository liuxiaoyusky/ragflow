#!/usr/bin/env python3
"""
Debug script to understand why Auto Metadata Filter causes too_many_nested_clauses error.
"""
import requests
import urllib3
import yaml
import os
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load config
with open('ragflow_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

RAGFLOW_API_KEY = config['api_key']
RAGFLOW_BASE_URL = config['base_url']
DATASET_ID = config['dataset_id']

LOG_FILE = '/home/calvin/github/ragflow/.cursor/debug.log'

def log(hypothesis_id, message, data=None):
    """Write debug log"""
    import time
    entry = {
        "timestamp": int(time.time() * 1000),
        "hypothesisId": hypothesis_id,
        "message": message,
        "data": data or {}
    }
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

# Simulate what gen_meta_filter receives
print("="*80)
print("Debugging Auto Metadata Filter")
print("="*80)

# Get all documents to build meta_data structure
print("\n1. Fetching all documents...")
all_docs = []
page = 1

while True:
    resp = requests.get(
        f"{RAGFLOW_BASE_URL}/api/v1/datasets/{DATASET_ID}/documents",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        params={"page": page, "page_size": 100},
        timeout=30,
        verify=False
    )
    
    if resp.status_code != 200:
        break
    
    result = resp.json()
    data = result.get('data') if result else {}
    docs = data.get('docs', []) if data else []
    
    if not docs:
        break
    
    all_docs.extend(docs)
    total = data.get('total', 0)
    if len(all_docs) >= total:
        break
    page += 1

print(f"   Found {len(all_docs)} documents")
log("A", "Total documents", {"count": len(all_docs)})

# Build meta_data structure (simulating DocumentService.get_meta_by_kbs)
print("\n2. Building metadata structure...")
meta_data = {}
for doc in all_docs:
    doc_id = doc.get('id')
    meta_fields = doc.get('meta_fields', {})
    
    for k, v in meta_fields.items():
        if k not in meta_data:
            meta_data[k] = {}
        v_str = str(v)
        if v_str not in meta_data[k]:
            meta_data[k][v_str] = []
        meta_data[k][v_str].append(doc_id)

# Log meta_data structure
print("\n3. Metadata structure summary:")
for key, values in meta_data.items():
    print(f"   {key}: {len(values)} unique values")
    log("A", f"Metadata key: {key}", {"unique_values": len(values), "sample": list(values.keys())[:5]})

# Build meta_data_structure (what gets sent to LLM)
meta_data_structure = {}
for key, values in meta_data.items():
    meta_data_structure[key] = list(values.keys())

print("\n4. meta_data_structure sent to LLM:")
print(json.dumps(meta_data_structure, indent=2, ensure_ascii=False))
log("B", "meta_data_structure", meta_data_structure)

# Calculate total possible combinations
total_values = 1
for key, values in meta_data_structure.items():
    total_values *= len(values)
print(f"\n5. Cartesian product of all values: {total_values}")
log("B", "Cartesian product", {"total": total_values})

# Simulate what LLM might generate for TC001
print("\n6. Simulating LLM filter for TC001...")
question = "What are top holdings of Asian Income Fund from January to September 2025"

# LLM might generate something like this:
simulated_filter = {
    "logic": "and",
    "conditions": [
        {"key": "fund_name", "value": "Asian Income Fund", "op": "="},
        {"key": "section_type", "value": "Top_holdings", "op": "contains"},
        # For January to September, LLM might generate:
        {"key": "report_month", "value": "2025-01-01, 2025-02-01, 2025-03-01, 2025-04-01, 2025-05-01, 2025-06-01, 2025-07-01, 2025-08-01, 2025-09-01", "op": "in"}
    ]
}
print(f"   Simulated filter: {json.dumps(simulated_filter, indent=2)}")
log("C", "Simulated LLM filter", simulated_filter)

# Calculate how many doc_ids would match
print("\n7. Calculating matching doc_ids...")
matching_docs = set()
for doc in all_docs:
    meta = doc.get('meta_fields', {})
    fund_name = meta.get('fund_name', '')
    section_type = meta.get('section_type', '')
    report_month = meta.get('report_month', '')
    
    # Check fund_name
    if fund_name != 'Asian Income Fund':
        continue
    
    # Check section_type contains "Top_holdings"
    if 'Top_holdings' not in section_type:
        continue
    
    # Check report_month in range
    months_2025 = [f"2025-0{i}-01" for i in range(1, 10)]
    if report_month not in months_2025:
        continue
    
    matching_docs.add(doc.get('id'))

print(f"   Matching documents: {len(matching_docs)}")
log("D", "Matching doc_ids", {"count": len(matching_docs), "sample": list(matching_docs)[:5]})

# The real problem
print("\n" + "="*80)
print("ANALYSIS")
print("="*80)
print(f"""
Hypothesis A: Auto Metadata Filter generates too many conditions
  - Found {len(all_docs)} documents with metadata
  - Each document has ~3 metadata fields
  
Hypothesis B: LLM receives all possible metadata values
  - meta_data_structure contains: {list(meta_data_structure.keys())}
  - Total unique values: {sum(len(v) for v in meta_data_structure.values())}
  
Hypothesis C: Time range generates multiple conditions
  - "January to September 2025" = 9 months
  - If LLM generates 9 separate conditions, this adds complexity
  
Hypothesis D: doc_ids list is too large
  - Matching documents for this query: {len(matching_docs)}
  - This becomes a terms query with {len(matching_docs)} values
  
Hypothesis E: BM25 + metadata filter + vector search = nested explosion
  - The full query combines:
    - terms filter for doc_ids (up to {len(matching_docs)} values)
    - bool query for text matching
    - knn query for vector search
  - Each combination adds nested clauses
""")

log("E", "Analysis complete", {
    "total_docs": len(all_docs),
    "matching_docs": len(matching_docs),
    "unique_metadata_values": sum(len(v) for v in meta_data_structure.values())
})

print("\nDebug logs written to:", LOG_FILE)



