#!/usr/bin/env python3
"""
Update document meta_fields for factsheet documents in RagFlow.
Extracts fund_name, section_type, report_month from document names.

Usage: 
  python tools/update_metadata.py          # Interactive mode
  python tools/update_metadata.py --yes    # Auto-confirm
  python tools/update_metadata.py --dry    # Dry run (no changes)
"""
import requests
import urllib3
import json
import re
import os
import sys
import yaml
from datetime import datetime

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

# Month name to number mapping
MONTH_MAP = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12'
}

# Fund name mapping (from filename pattern to readable name)
FUND_NAME_MAP = {
    'Asian_Income_Fund': 'Asian Income Fund',
    'High_Dividend_Fund': 'High Dividend Fund',
    'Classic_Fund': 'Classic Fund'
}

def parse_document_name(doc_name):
    """
    Parse document name to extract metadata.
    Example: VP_Asian_Income_Fund_2025Sep_Fee_structure.md
    Returns: {fund_name, section_type, report_month}
    """
    # Remove .md extension
    name = doc_name.replace('.md', '')
    
    # Pattern: VP_<FundName>_<YearMonth>_<SectionType>
    # Example: VP_Asian_Income_Fund_2025Sep_Fee_structure
    
    # Extract year and month
    year_month_pattern = r'(\d{4})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    match = re.search(year_month_pattern, name)
    
    if not match:
        return None
    
    year = match.group(1)
    month_abbr = match.group(2)
    month_num = MONTH_MAP.get(month_abbr, '01')
    report_month = f"{year}-{month_num}-01"
    
    # Extract fund name (between VP_ and year)
    fund_pattern = r'VP_(.+?)_\d{4}'
    fund_match = re.search(fund_pattern, name)
    fund_key = fund_match.group(1) if fund_match else 'Unknown'
    fund_name = FUND_NAME_MAP.get(fund_key, fund_key.replace('_', ' '))
    
    # Extract section type (after YearMonth_)
    section_pattern = r'\d{4}[A-Za-z]+_(.+)$'
    section_match = re.search(section_pattern, name)
    section_type = section_match.group(1) if section_match else 'Unknown'
    
    return {
        'fund_name': fund_name,
        'section_type': section_type,
        'report_month': report_month
    }

def get_all_documents():
    """Get all documents from the dataset"""
    all_docs = []
    page = 1
    page_size = 100
    
    while True:
        resp = requests.get(
            f"{RAGFLOW_BASE_URL}/api/v1/datasets/{DATASET_ID}/documents",
            headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
            params={"page": page, "page_size": page_size},
            timeout=30,
            verify=False
        )
        
        if resp.status_code != 200:
            print(f"Error fetching documents: {resp.status_code}")
            break
        
        result = resp.json()
        data = result.get('data') if result else {}
        docs = data.get('docs', []) if data else []
        
        if not docs:
            break
        
        all_docs.extend(docs)
        
        # Check if there are more pages
        total = data.get('total', 0)
        if len(all_docs) >= total:
            break
        
        page += 1
    
    return all_docs

def update_document_metadata(doc_id, meta_fields):
    """Update metadata for a single document"""
    resp = requests.put(
        f"{RAGFLOW_BASE_URL}/api/v1/datasets/{DATASET_ID}/documents/{doc_id}",
        headers={
            "Authorization": f"Bearer {RAGFLOW_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"meta_fields": meta_fields},
        timeout=30,
        verify=False
    )
    
    return resp.status_code == 200, resp.text

def main():
    # Parse command line arguments
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    dry_run = '--dry' in sys.argv
    
    print("="*80)
    print("Update Document Metadata")
    if dry_run:
        print("(DRY RUN - no changes will be made)")
    print("="*80)
    
    # Get all documents
    print("\nFetching all documents...")
    docs = get_all_documents()
    print(f"Found {len(docs)} documents")
    
    # Parse and prepare metadata
    updates = []
    for doc in docs:
        doc_id = doc.get('id')
        doc_name = doc.get('name')
        
        meta = parse_document_name(doc_name)
        if meta:
            updates.append({
                'id': doc_id,
                'name': doc_name,
                'meta_fields': meta
            })
    
    print(f"\nParsed {len(updates)} documents for update")
    
    # Show sample
    print("\n" + "-"*80)
    print("Sample metadata (first 5):")
    print("-"*80)
    for u in updates[:5]:
        print(f"\n{u['name']}")
        print(f"  → fund_name: {u['meta_fields']['fund_name']}")
        print(f"  → section_type: {u['meta_fields']['section_type']}")
        print(f"  → report_month: {u['meta_fields']['report_month']}")
    
    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN completed. No changes made.")
        print("="*80)
        return
    
    # Confirm before updating
    if not auto_confirm:
        print("\n" + "="*80)
        response = input(f"Update metadata for {len(updates)} documents? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print(f"\nAuto-confirm enabled. Updating {len(updates)} documents...")
    
    # Update documents
    print("\nUpdating documents...")
    success_count = 0
    fail_count = 0
    
    for i, u in enumerate(updates):
        success, msg = update_document_metadata(u['id'], u['meta_fields'])
        
        if success:
            success_count += 1
            if (i + 1) % 20 == 0 or i == len(updates) - 1:
                print(f"  Progress: {i+1}/{len(updates)} ({success_count} success)")
        else:
            fail_count += 1
            print(f"  [{i+1}/{len(updates)}] ✗ {u['name'][:50]} - {msg[:100]}")
    
    print("\n" + "="*80)
    print(f"SUMMARY: {success_count} success, {fail_count} failed")
    print("="*80)

if __name__ == "__main__":
    main()

