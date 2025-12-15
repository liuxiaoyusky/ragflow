#!/usr/bin/env python3
"""Test original questions (no enhancement) with metadata filter auto - parallel execution"""
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
urllib3.disable_warnings()

BASE = 'https://10.1.9.133:8443'
KEY = 'ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw'
CHAT = 'f472490cbabe11f0b1a00242ac130006'
H = {'Authorization': f'Bearer {KEY}'}

FAILED_QUESTIONS = [
    ('Q7', 'show me the top holdings of High Dividend Stocks Fund from January 2025 to July 2025'),
    ('Q10', 'what are the top holdings of Asian Income Fund from January 2025 to September 2025?'),
    ('TC001', 'What are top holdings of Asian Income Fund from January to September 2025?'),
    ('TC002', '比较High Dividend Fund和Asian Income Fund 2025年8月的股息率'),
    ('TC007', 'Compare fee structures between Asian Income Fund and High Dividend Fund'),
]

def test_question(qid, question):
    """Test a single question"""
    try:
        # Create new session
        r = requests.post(f'{BASE}/api/v1/chats/{CHAT}/sessions', headers=H,
                          json={'name': f'test_{qid}'}, timeout=30, verify=False)
        sid = r.json().get('data', {}).get('id')
        
        # Send original question
        r = requests.post(f'{BASE}/api/v1/chats/{CHAT}/completions', headers=H,
                          json={'question': question, 'session_id': sid, 'stream': False},
                          timeout=180, verify=False)
        
        data = r.json()
        if data.get('code') == 0:
            ref = data.get('data', {}).get('reference', {})
            chunks = ref.get('chunks', []) if isinstance(ref, dict) else []
            top_chunk = chunks[0].get('content', '')[:80].replace('\n', ' ') if chunks else 'N/A'
            return (qid, 'SUCCESS', len(chunks), top_chunk)
        else:
            return (qid, 'ERROR', 0, data.get('message', '')[:100])
    except Exception as e:
        return (qid, 'EXCEPTION', 0, str(e)[:100])

if __name__ == '__main__':
    print('Testing ORIGINAL questions with metadata filter auto (parallel)')
    print('=' * 80)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_question, qid, q): qid for qid, q in FAILED_QUESTIONS}
        
        for future in as_completed(futures):
            qid, status, chunks, info = future.result()
            print(f'{qid}: {status} ({chunks} chunks)')
            print(f'  {info[:70]}...')
            print()


