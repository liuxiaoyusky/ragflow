#!/usr/bin/env python3
"""
答案评价脚本 - 使用Gemini 2.5 Flash评价所有答案组
评价维度: 准确性、完整性、相关性
"""

import json
import os
import time
import csv
from datetime import datetime
import requests

# OpenRouter配置
OPENROUTER_API_KEY = open('/home/calvin/github/ragflow/openai.apikey').read().strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
EVAL_MODEL = "google/gemini-2.5-flash"

# 数据源配置
SOURCES = {
    'A': {'file': 'ragflow_grok_enhanced.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Grok 4.1 Fast', 'mode': 'OldEnhanced'},
    'B': {'file': 'ragflow_gemini_enhanced.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Gemini 2.0 Flash', 'mode': 'OldEnhanced'},
    'C': {'file': 'ragflow_grok_baseline.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Grok 4.1 Fast', 'mode': 'Baseline'},
    'D': {'file': 'ragflow_gemini_baseline.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Gemini 2.0 Flash', 'mode': 'Baseline'},
    'E': {'file': 'feishu_pdf_v1.json', 'system': 'Feishu', 'format': 'PDF', 'model': 'Knowledge AI', 'mode': '-'},
    'F': {'file': 'feishu_markdown_v2.json', 'system': 'Feishu', 'format': 'MD', 'model': 'Knowledge AI', 'mode': '-'},
    'G': {'file': 'ragflow_gemini25_baseline.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Gemini 2.5 Flash', 'mode': 'Baseline'},
    'H': {'file': 'ragflow_gemini25_enhanced.json', 'system': 'RagFlow', 'format': 'MD', 'model': 'Gemini 2.5 Flash', 'mode': 'NewEnhanced'},
}

BASE_DIR = '/home/calvin/github/ragflow/docs/benchmark/test_cases_20251210'

def load_questions():
    """加载测试问题"""
    with open(f'{BASE_DIR}/questions.json', 'r', encoding='utf-8') as f:
        return json.load(f)['questions']

def load_source_answers(source_id):
    """加载某个数据源的答案"""
    source = SOURCES[source_id]
    filepath = f'{BASE_DIR}/sources/{source["file"]}'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Feishu格式: results是列表
    if 'results' in data and isinstance(data['results'], list):
        return {item['question']: {
            'answer': item.get('answer', ''),
            'duration': item.get('duration', 0) / 1000  # 转为秒
        } for item in data['results']}
    
    # RagFlow格式: test_results是列表，每个元素有answer和timings
    if 'test_results' in data and isinstance(data['test_results'], list):
        return {item['question']: {
            'answer': item.get('answer', ''),
            'duration': item.get('timings', {}).get('total', 0)
        } for item in data['test_results']}
    
    return {}

def evaluate_answer(question, expected_answer, actual_answer, timeout=60):
    """使用Gemini 2.5 Flash评价单个答案"""
    
    if not actual_answer or actual_answer == "找不到相关信息 (From Feishu Knowledge AI | https://ask.feishu.cn)":
        return {
            'accuracy': 0,
            'completeness': 0, 
            'relevance': 0,
            'total': 0,
            'comment': '无答案或找不到信息'
        }
    
    prompt = f"""你是一个专业的RAG系统评测专家。请评价以下AI生成的答案。

## 问题
{question}

## 预期答案要点
{expected_answer}

## 实际生成的答案
{actual_answer}

## 评分标准（每项1-10分）
1. **准确性** (accuracy): 答案中的事实信息是否正确？数字、日期、名称是否准确？
2. **完整性** (completeness): 答案是否涵盖了预期答案中提到的主要要点？
3. **相关性** (relevance): 答案是否直接回答了问题？是否有无关信息？

请用以下JSON格式返回评分结果（只返回JSON，不要其他文字）：
```json
{{
    "accuracy": <1-10>,
    "completeness": <1-10>,
    "relevance": <1-10>,
    "comment": "<简短评语，说明优缺点>"
}}
```"""

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": EVAL_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            # 提取JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            result = json.loads(content.strip())
            result['total'] = (result['accuracy'] + result['completeness'] + result['relevance']) / 3
            return result
        else:
            print(f"API错误: {response.status_code} - {response.text[:200]}")
            return {'accuracy': -1, 'completeness': -1, 'relevance': -1, 'total': -1, 'comment': f'API Error: {response.status_code}'}
            
    except Exception as e:
        print(f"评价异常: {str(e)[:100]}")
        return {'accuracy': -1, 'completeness': -1, 'relevance': -1, 'total': -1, 'comment': str(e)[:100]}

def run_evaluation():
    """运行完整评价"""
    questions = load_questions()
    results = []
    
    print("=" * 70)
    print("开始答案评价 - 使用 Gemini 2.5 Flash")
    print(f"评价时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"问题数量: {len(questions)}")
    print(f"数据源数量: {len(SOURCES)} (A-F)")
    print(f"总评价数: {len(questions) * len(SOURCES)}")
    print("=" * 70)
    
    for source_id in sorted(SOURCES.keys()):
        source = SOURCES[source_id]
        print(f"\n处理数据源 {source_id}: {source['system']} / {source['format']} / {source['model']} / {source['mode']}")
        
        try:
            answers = load_source_answers(source_id)
        except Exception as e:
            print(f"  加载失败: {e}")
            continue
        
        for q in questions:
            question = q['question']
            expected = q['expected_answer']
            
            # 查找答案（可能因为问题文本略有差异）
            actual_data = answers.get(question, None)
            if not actual_data:
                # 尝试模糊匹配
                for key in answers.keys():
                    if question[:30] in key or key[:30] in question:
                        actual_data = answers[key]
                        break
            
            actual_answer = actual_data['answer'] if actual_data else ''
            duration = actual_data['duration'] if actual_data else 0
            
            # 评价
            print(f"  评价 {q['id']}: {question[:40]}...", end=" ")
            eval_result = evaluate_answer(question, expected, actual_answer)
            print(f"得分: {eval_result['total']:.1f}")
            
            # 记录结果
            results.append({
                'question_id': q['id'],
                'question': question,
                'category': q['category'],
                'difficulty': q['difficulty'],
                'source_id': source_id,
                'system': source['system'],
                'format': source['format'],
                'model': source['model'],
                'mode': source['mode'],
                'answer_preview': actual_answer[:200] if actual_answer else '',
                'accuracy': eval_result['accuracy'],
                'completeness': eval_result['completeness'],
                'relevance': eval_result['relevance'],
                'total_score': eval_result['total'],
                'comment': eval_result['comment'],
                'response_time': duration
            })
            
            # 避免API限速
            time.sleep(0.5)
    
    return results

def save_results(results):
    """保存评价结果"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存CSV
    csv_path = f'{BASE_DIR}/evaluation_results.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nCSV结果已保存: {csv_path}")
    
    # 保存JSON
    json_path = f'{BASE_DIR}/evaluation_results.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"JSON结果已保存: {json_path}")
    
    return csv_path

def generate_analysis_report(results):
    """生成分析报告"""
    report_path = f'{BASE_DIR}/analysis_report.md'
    
    # 按数据源分组统计
    source_stats = {}
    for r in results:
        sid = r['source_id']
        if sid not in source_stats:
            source_stats[sid] = {'scores': [], 'times': [], 'info': SOURCES[sid]}
        source_stats[sid]['scores'].append(r['total_score'])
        if r['response_time'] > 0:
            source_stats[sid]['times'].append(r['response_time'])
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 答案交叉对比分析报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 概览表格
        f.write("## 1. 总体评分概览\n\n")
        f.write("| 来源ID | 系统 | 格式 | 模型 | 模式 | 平均分 | 响应时间(s) |\n")
        f.write("|--------|------|------|------|------|--------|------------|\n")
        
        for sid in sorted(source_stats.keys()):
            stats = source_stats[sid]
            info = stats['info']
            avg_score = sum(stats['scores']) / len(stats['scores']) if stats['scores'] else 0
            avg_time = sum(stats['times']) / len(stats['times']) if stats['times'] else 0
            f.write(f"| {sid} | {info['system']} | {info['format']} | {info['model']} | {info['mode']} | {avg_score:.2f} | {avg_time:.1f} |\n")
        
        # 对比分析
        f.write("\n## 2. 关键对比分析\n\n")
        
        # 格式对比: E vs F
        if 'E' in source_stats and 'F' in source_stats:
            e_avg = sum(source_stats['E']['scores']) / len(source_stats['E']['scores'])
            f_avg = sum(source_stats['F']['scores']) / len(source_stats['F']['scores'])
            diff = f_avg - e_avg
            f.write(f"### 2.1 Markdown vs PDF (飞书)\n")
            f.write(f"- **PDF格式 (E)**: 平均分 {e_avg:.2f}\n")
            f.write(f"- **Markdown格式 (F)**: 平均分 {f_avg:.2f}\n")
            f.write(f"- **提升**: {diff:+.2f} ({diff/e_avg*100 if e_avg else 0:+.1f}%)\n\n")
        
        # 模型对比: A vs B
        if 'A' in source_stats and 'B' in source_stats:
            a_avg = sum(source_stats['A']['scores']) / len(source_stats['A']['scores'])
            b_avg = sum(source_stats['B']['scores']) / len(source_stats['B']['scores'])
            diff = b_avg - a_avg
            f.write(f"### 2.2 Gemini vs Grok (Enhanced模式)\n")
            f.write(f"- **Grok 4.1 Fast (A)**: 平均分 {a_avg:.2f}\n")
            f.write(f"- **Gemini 2.0 Flash (B)**: 平均分 {b_avg:.2f}\n")
            f.write(f"- **差异**: {diff:+.2f}\n\n")
        
        # 增强对比: A vs C, B vs D
        f.write(f"### 2.3 Enhanced vs Baseline\n")
        if 'A' in source_stats and 'C' in source_stats:
            a_avg = sum(source_stats['A']['scores']) / len(source_stats['A']['scores'])
            c_avg = sum(source_stats['C']['scores']) / len(source_stats['C']['scores'])
            diff = a_avg - c_avg
            f.write(f"- **Grok Enhanced (A)**: {a_avg:.2f} vs **Baseline (C)**: {c_avg:.2f} → 提升 {diff:+.2f}\n")
        
        if 'B' in source_stats and 'D' in source_stats:
            b_avg = sum(source_stats['B']['scores']) / len(source_stats['B']['scores'])
            d_avg = sum(source_stats['D']['scores']) / len(source_stats['D']['scores'])
            diff = b_avg - d_avg
            f.write(f"- **Gemini Enhanced (B)**: {b_avg:.2f} vs **Baseline (D)**: {d_avg:.2f} → 提升 {diff:+.2f}\n")
        
        # 问题维度分析
        f.write("\n## 3. 按问题分析\n\n")
        f.write("| 问题ID | 类别 | 难度 | 最高分 | 最低分 | 最佳来源 |\n")
        f.write("|--------|------|------|--------|--------|----------|\n")
        
        # 按问题分组
        q_results = {}
        for r in results:
            qid = r['question_id']
            if qid not in q_results:
                q_results[qid] = {'category': r['category'], 'difficulty': r['difficulty'], 'scores': []}
            q_results[qid]['scores'].append((r['source_id'], r['total_score']))
        
        for qid in sorted(q_results.keys()):
            qr = q_results[qid]
            valid_scores = [(s, score) for s, score in qr['scores'] if score >= 0]
            if valid_scores:
                max_score = max(s[1] for s in valid_scores)
                min_score = min(s[1] for s in valid_scores)
                best = [s[0] for s in valid_scores if s[1] == max_score]
                f.write(f"| {qid} | {qr['category']} | {qr['difficulty']} | {max_score:.1f} | {min_score:.1f} | {','.join(best)} |\n")
        
        f.write("\n## 4. 结论\n\n")
        f.write("基于上述分析，可以得出以下结论：\n\n")
        f.write("1. **格式影响**: Markdown格式相比PDF格式的准确性差异\n")
        f.write("2. **模型影响**: Grok与Gemini模型的表现对比\n")
        f.write("3. **增强影响**: Query Enhancement对答案质量的提升效果\n")
        f.write("4. **综合推荐**: 根据评分结果推荐最佳配置组合\n")
    
    print(f"分析报告已保存: {report_path}")
    return report_path

if __name__ == '__main__':
    results = run_evaluation()
    save_results(results)
    generate_analysis_report(results)
    print("\n评价完成!")

