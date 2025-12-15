#!/usr/bin/env python3
"""
Test pre-filtering documents by metadata before calling Retrieval API.
This bypasses the too_many_nested_clauses issue by:
1. First filtering documents by metadata (fund_name, section_type, report_month)
2. Then calling Retrieval API with the filtered doc_ids
"""
import requests
import urllib3
import yaml
import json
import re
from datetime import datetime

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
        "location": "test_prefilter_retrieval.py",
        "message": message,
        "data": data or {}
    }
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def get_all_documents():
    """Fetch all documents with their metadata"""
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
    
    return all_docs


def parse_question_for_filters(question: str) -> dict:
    """
    Parse question to extract filter conditions.
    Returns dict with: fund_name, section_types, month_range
    """
    filters = {
        "fund_name": None,
        "section_types": [],
        "month_start": None,
        "month_end": None
    }
    
    # Fund name detection
    if "asian income" in question.lower():
        filters["fund_name"] = "Asian Income Fund"
    elif "high dividend" in question.lower():
        filters["fund_name"] = "High Dividend Fund"
    elif "classic" in question.lower():
        filters["fund_name"] = "Classic Fund"
    
    # Section type detection
    if "top holdings" in question.lower() or "holdings" in question.lower():
        filters["section_types"] = ["Top_holdings_-_equities", "Top_holdings_-_fixed_income"]
    elif "performance" in question.lower():
        filters["section_types"] = ["Monthly_performance"]
    elif "dividend" in question.lower():
        filters["section_types"] = ["Dividend_information"]
    elif "fee" in question.lower():
        filters["section_types"] = ["Fee_structure"]
    elif "credit" in question.lower():
        filters["section_types"] = ["Credit_ratings"]
    elif "geography" in question.lower() or "geographic" in question.lower():
        filters["section_types"] = ["Asset_type_by_geography"]
    elif "sector" in question.lower():
        filters["section_types"] = ["Asset_type_by_sector"]
    
    # Month range detection
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }
    
    # Pattern: "from January to September 2025"
    range_match = re.search(r"from\s+(\w+)\s+to\s+(\w+)\s+(\d{4})", question.lower())
    if range_match:
        start_month = month_map.get(range_match.group(1))
        end_month = month_map.get(range_match.group(2))
        year = range_match.group(3)
        if start_month and end_month:
            filters["month_start"] = f"{year}-{start_month:02d}-01"
            filters["month_end"] = f"{year}-{end_month:02d}-01"
    
    return filters


def filter_documents(docs: list, filters: dict) -> list:
    """Filter documents based on parsed conditions"""
    filtered = []
    
    for doc in docs:
        meta = doc.get('meta_fields', {})
        
        # Check fund_name
        if filters["fund_name"]:
            if meta.get('fund_name') != filters["fund_name"]:
                continue
        
        # Check section_type
        if filters["section_types"]:
            if meta.get('section_type') not in filters["section_types"]:
                continue
        
        # Check month range
        if filters["month_start"] and filters["month_end"]:
            report_month = meta.get('report_month', '')
            if report_month:
                if report_month < filters["month_start"] or report_month > filters["month_end"]:
                    continue
        
        filtered.append(doc)
    
    return filtered


def retrieval_with_doc_ids(question: str, doc_ids: list, top_k: int = 10):
    """Call Retrieval API with pre-filtered doc_ids"""
    payload = {
        "question": question,
        "dataset_ids": [DATASET_ID],
        "doc_ids": doc_ids,  # Pre-filtered!
        "similarity_threshold": 0.0,
        "top_k": top_k,
        "keyword_similarity_weight": 0.7
    }
    
    log("C1", "Retrieval API payload", {
        "doc_ids_count": len(doc_ids),
        "doc_ids_sample": doc_ids[:3],
        "top_k": top_k
    })
    
    resp = requests.post(
        f"{RAGFLOW_BASE_URL}/api/v1/retrieval",
        headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
        json=payload,
        timeout=60,
        verify=False
    )
    
    if resp.status_code != 200:
        return None, f"Error: {resp.status_code} - {resp.text[:200]}"
    
    result = resp.json()
    chunks = result.get('data', {}).get('chunks', [])
    
    # Log each chunk's doc_id to verify filtering
    chunk_doc_ids = [c.get('doc_id', 'unknown') for c in chunks[:10]]
    log("C2", "Returned chunk doc_ids", {
        "chunk_count": len(chunks),
        "chunk_doc_ids": chunk_doc_ids
    })
    
    # Check if any returned chunk's doc_id is NOT in our filter list
    unexpected_docs = [c for c in chunks if c.get('doc_id') not in doc_ids]
    if unexpected_docs:
        log("C3", "UNEXPECTED: Chunks from non-filtered docs", {
            "count": len(unexpected_docs),
            "sample": [c.get('document_keyword', '')[:50] for c in unexpected_docs[:5]]
        })
    
    return chunks, None


def main():
    print("="*80)
    print("PRE-FILTER RETRIEVAL TEST")
    print("="*80)
    
    question = "What are top holdings of Asian Income Fund from January to September 2025"
    print(f"\nQuestion: {question}")
    
    # Step 1: Parse question for filter conditions
    print("\n" + "-"*40)
    print("Step 1: Parse question for filters")
    print("-"*40)
    
    filters = parse_question_for_filters(question)
    print(f"Parsed filters: {json.dumps(filters, indent=2)}")
    log("A", "Parsed filters", filters)
    
    # Step 2: Get all documents
    print("\n" + "-"*40)
    print("Step 2: Fetch all documents")
    print("-"*40)
    
    all_docs = get_all_documents()
    print(f"Total documents: {len(all_docs)}")
    log("A", "Total documents", {"count": len(all_docs)})
    
    # Step 3: Filter documents by metadata
    print("\n" + "-"*40)
    print("Step 3: Filter documents by metadata")
    print("-"*40)
    
    filtered_docs = filter_documents(all_docs, filters)
    doc_ids = [doc['id'] for doc in filtered_docs]
    
    print(f"Filtered documents: {len(filtered_docs)}")
    for doc in filtered_docs:
        meta = doc.get('meta_fields', {})
        print(f"  - {meta.get('fund_name')} | {meta.get('section_type')} | {meta.get('report_month')}")
    
    log("B", "Filtered documents", {
        "count": len(filtered_docs),
        "doc_ids": doc_ids[:5]  # Sample
    })
    
    # Step 4: Call Retrieval API with filtered doc_ids
    print("\n" + "-"*40)
    print("Step 4: Call Retrieval API with filtered doc_ids")
    print("-"*40)
    
    chunks, error = retrieval_with_doc_ids(question, doc_ids, top_k=15)
    
    if error:
        print(f"Error: {error}")
        log("C", "Retrieval error", {"error": error})
    else:
        print(f"Retrieved {len(chunks)} chunks")
        log("C", "Retrieved chunks", {"count": len(chunks)})
        
        # Analyze results
        holdings_eq = 0
        holdings_fi = 0
        
        for i, chunk in enumerate(chunks[:15]):
            doc_kw = chunk.get('document_keyword', '')
            sim = chunk.get('similarity', 0)
            
            if 'Top_holdings' in doc_kw and 'equities' in doc_kw:
                holdings_eq += 1
                mark = "✅ EQ"
            elif 'Top_holdings' in doc_kw and 'fixed_income' in doc_kw:
                holdings_fi += 1
                mark = "✅ FI"
            else:
                mark = "❓"
            
            print(f"#{i+1:2d} [{sim:.3f}] {doc_kw[:60]} {mark}")
        
        print("\n" + "-"*40)
        print("SUMMARY")
        print("-"*40)
        print(f"Holdings Equities: {holdings_eq}")
        print(f"Holdings Fixed Income: {holdings_fi}")
        print(f"Total relevant: {holdings_eq + holdings_fi}/15")
        
        log("D", "Analysis", {
            "holdings_eq": holdings_eq,
            "holdings_fi": holdings_fi,
            "total_relevant": holdings_eq + holdings_fi
        })


if __name__ == "__main__":
    main()

