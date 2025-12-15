#!/usr/bin/env python3
"""Debug: Find what triggers ES nested clause error"""
import requests
import urllib3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
urllib3.disable_warnings()

BASE = 'https://10.1.9.133:8443'
KEY = 'ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw'
CHAT = 'f472490cbabe11f0b1a00242ac130006'
H = {'Authorization': f'Bearer {KEY}'}
LOG_FILE = '/home/calvin/github/ragflow/.cursor/debug.log'

def log(hypothesis_id, message, data=None):
    import time
    entry = {"timestamp": int(time.time()*1000), "hypothesisId": hypothesis_id, 
             "message": message, "data": data or {}, "sessionId": "debug-es"}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

# Base question that we know works with original
BASE_Q = "show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025"

# Test variations
TEST_CASES = [
    ("A1", "原问题", BASE_Q),
    ("A2", "原问题 + 基金名", f"{BASE_Q} (High Dividend Fund)"),
    ("A3", "原问题 + section", f"{BASE_Q} (Top holdings equities)"),
    ("A4", "原问题 + 2个section", f"{BASE_Q} (Top holdings equities, Top holdings fixed income)"),
    ("A5", "原问题 + 基金+section", f"{BASE_Q} (High Dividend Fund, Top holdings equities)"),
    ("A6", "原问题 + 基金+2section", f"{BASE_Q} (High Dividend Fund, Top holdings equities, Top holdings fixed income)"),
    ("A7", "原问题 + 基金+2section+年份", f"{BASE_Q} (High Dividend Fund, Top holdings equities, Top holdings fixed income, 2025)"),
    ("B1", "原问题 + 7个月份", f"{BASE_Q} (January, February, March, April, May, June, July)"),
    ("B2", "原问题 + 7个月份+年份", f"{BASE_Q} (January, February, March, April, May, June, July 2025)"),
    ("B3", "原问题 + 基金+7月份", f"{BASE_Q} (High Dividend Fund, January, February, March, April, May, June, July)"),
]

def test_query(test_id, desc, query):
    """Test a single query"""
    log(test_id, f"Testing: {desc}", {"query": query[:80]})
    
    try:
        # Create new session
        r = requests.post(f'{BASE}/api/v1/chats/{CHAT}/sessions', headers=H,
                          json={'name': f'debug_{test_id}'}, timeout=30, verify=False)
        sid = r.json().get('data', {}).get('id')
        
        # Send query
        r = requests.post(f'{BASE}/api/v1/chats/{CHAT}/completions', headers=H,
                          json={'question': query, 'session_id': sid, 'stream': False},
                          timeout=180, verify=False)
        
        data = r.json()
        if data.get('code') == 0:
            chunks = data.get('data', {}).get('reference', {}).get('chunks', [])
            result = f"SUCCESS ({len(chunks)} chunks)"
            log(test_id, "Result", {"status": "SUCCESS", "chunks": len(chunks)})
        else:
            msg = data.get('message', '')[:100]
            result = f"ERROR: {msg[:50]}"
            log(test_id, "Result", {"status": "ERROR", "message": msg})
        
        return (test_id, desc, result)
    except Exception as e:
        log(test_id, "Exception", {"error": str(e)[:100]})
        return (test_id, desc, f"EXCEPTION: {str(e)[:50]}")

if __name__ == '__main__':
    print("=" * 80)
    print("DEBUG: What triggers ES nested clause error?")
    print("=" * 80)
    
    log("START", "Starting debug tests", {"total_tests": len(TEST_CASES)})
    
    # Run tests in parallel
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_query, tid, desc, q): tid for tid, desc, q in TEST_CASES}
        for future in as_completed(futures):
            results.append(future.result())
    
    # Sort by test ID and print
    results.sort(key=lambda x: x[0])
    print()
    print(f"{'ID':<5} {'Description':<30} {'Result':<40}")
    print("-" * 80)
    for tid, desc, result in results:
        print(f"{tid:<5} {desc:<30} {result:<40}")
    
    log("END", "Tests completed", {"results": [r[2][:20] for r in results]})
    print(f"\nLogs saved to: {LOG_FILE}")


