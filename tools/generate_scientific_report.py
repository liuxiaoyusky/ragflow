#!/usr/bin/env python3
"""
Generate Scientific Comparison Report: RagFlow vs Feishu
Neutral language, objective metrics, professional presentation
"""

import json
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Register Chinese font
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

def load_comparison_data():
    """Load comparison results"""
    with open('/home/calvin/github/ragflow/tools/optimized_comparison_results.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_retrieval_metrics():
    """Load retrieval metrics"""
    try:
        with open('/home/calvin/github/ragflow/tools/retrieval_metrics.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def load_benchmark_metrics():
    """Load benchmark TC001-TC010 metrics"""
    try:
        with open('/home/calvin/github/ragflow/tools/benchmark_retrieval_metrics.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def load_benchmark_evaluation():
    """Load benchmark TC001-TC010 LLM evaluation scores"""
    try:
        with open('/home/calvin/github/ragflow/tools/benchmark_evaluation_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def load_benchmark_comparison():
    """Load benchmark TC001-TC010 RagFlow vs Feishu comparison"""
    try:
        with open('/home/calvin/github/ragflow/tools/benchmark_comparison_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def contains_chinese(text):
    """Check if text contains Chinese characters"""
    if not text:
        return False
    for char in str(text):
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def strip_formatting(text):
    """Remove markdown, xml, and other formatting from text"""
    if not text:
        return ""
    # Remove markdown formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic*
    text = re.sub(r'#{1,6}\s*', '', text)           # ## headers
    text = re.sub(r'`([^`]+)`', r'\1', text)        # `code`
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [link](url)
    # Remove table formatting
    text = text.replace('|', ' ')
    text = re.sub(r'-{3,}', '', text)               # ---
    text = re.sub(r':?-+:?', '', text)              # table alignments
    # Remove XML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()

def create_styles():
    """Create document styles"""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='ReportTitle',
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=20,
        alignment=1
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName='Helvetica-Bold',
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor('#1a1a2e')
    ))
    
    styles.add(ParagraphStyle(
        name='SubSection',
        fontName='Helvetica-Bold',
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor('#16213e')
    ))
    
    styles.add(ParagraphStyle(
        name='NormalText',
        fontName='Helvetica',
        fontSize=10,
        spaceAfter=6,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='ChineseText',
        fontName='STSong-Light',
        fontSize=9,
        spaceAfter=4,
        leading=12
    ))
    
    styles.add(ParagraphStyle(
        name='AnswerText',
        fontName='STSong-Light',
        fontSize=8,
        spaceAfter=4,
        leading=11,
        leftIndent=10
    ))
    
    styles.add(ParagraphStyle(
        name='MetricLabel',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#666666')
    ))
    
    # Chinese-compatible styles for mixed content
    styles.add(ParagraphStyle(
        name='SubSectionChinese',
        fontName='STSong-Light',
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor('#16213e')
    ))
    
    styles.add(ParagraphStyle(
        name='NormalTextChinese',
        fontName='STSong-Light',
        fontSize=10,
        spaceAfter=6,
        leading=14
    ))
    
    return styles

def generate_report():
    """Generate the scientific comparison report"""
    
    data = load_comparison_data()
    retrieval_data = load_retrieval_metrics()
    benchmark_data = load_benchmark_metrics()
    benchmark_eval = load_benchmark_evaluation()
    benchmark_comparison = load_benchmark_comparison()  # TC001-TC010 RagFlow vs Feishu
    styles = create_styles()
    
    # Create retrieval lookup by question ID
    retrieval_lookup = {}
    if retrieval_data:
        for q in retrieval_data.get('questions', []):
            retrieval_lookup[q['id']] = q
    
    # Create benchmark lookup
    benchmark_lookup = {}
    if benchmark_data:
        for q in benchmark_data.get('questions', []):
            benchmark_lookup[q['id']] = q
    
    output_path = '/home/calvin/github/ragflow/tools/RagFlow_Feishu_Comparison_Report.pdf'
    doc = SimpleDocTemplate(output_path, pagesize=A4, 
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    story = []
    
    # === Title ===
    story.append(Paragraph("RAG System Accuracy Evaluation Report", styles['ReportTitle']))
    story.append(Paragraph("RagFlow vs Feishu Knowledge AI - Accuracy Focus", styles['NormalText']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['MetricLabel']))
    story.append(Spacer(1, 20))
    
    # === 1. Executive Summary ===
    story.append(Paragraph("1. Executive Summary", styles['SectionHeader']))
    
    summary = data['summary']
    q_count = len(data['results'])  # Q1-Q11
    
    # Get benchmark comparison scores (TC001-TC010 RagFlow vs Feishu)
    bench_comp_summary = benchmark_comparison.get('summary', {}) if benchmark_comparison else {}
    tc_count = bench_comp_summary.get('total_questions', 0)
    tc_ragflow_total = bench_comp_summary.get('ragflow_total', 0)
    tc_feishu_total = bench_comp_summary.get('feishu_total', 0)
    tc_ragflow_avg = bench_comp_summary.get('ragflow_avg', 0)
    tc_feishu_avg = bench_comp_summary.get('feishu_avg', 0)
    tc_ragflow_wins = bench_comp_summary.get('ragflow_wins', 0)
    tc_feishu_wins = bench_comp_summary.get('feishu_wins', 0)
    
    total_questions = q_count + tc_count
    
    # Combined scores (Q1-Q11 + TC001-TC010)
    combined_ragflow_total = summary['ragflow_total'] + tc_ragflow_total
    combined_feishu_total = summary['feishu_total'] + tc_feishu_total
    combined_ragflow_avg = combined_ragflow_total / total_questions if total_questions > 0 else 0
    combined_feishu_avg = combined_feishu_total / total_questions if total_questions > 0 else 0
    
    summary_text = f"""
    This report presents an objective evaluation of RagFlow RAG system across {total_questions} fund-related questions:
    Q1-Q11 ({q_count} questions) comparing RagFlow vs Feishu, and TC001-TC010 ({tc_count} questions) as benchmark evaluation.
    The evaluation was conducted by independent LLM judges using standardized scoring criteria.
    """
    story.append(Paragraph(summary_text, styles['NormalText']))
    story.append(Spacer(1, 10))
    
    # RagFlow vs Feishu comparison (Q1-Q11)
    story.append(Paragraph("<b>RagFlow vs Feishu Comparison (Q1-Q11)</b>", styles['NormalText']))
    summary_data = [
        ['Metric', 'RagFlow', 'Feishu', 'Difference'],
        ['Total Score', str(summary['ragflow_total']), str(summary['feishu_total']), 
         f"+{summary['ragflow_total'] - summary['feishu_total']}"],
        ['Average Score', f"{summary['ragflow_avg']:.1f}/50", f"{summary['feishu_avg']:.1f}/50",
         f"+{summary['ragflow_avg'] - summary['feishu_avg']:.1f}"],
        ['Higher Score Count', str(summary['ragflow_wins']), str(summary['feishu_wins']), '-'],
        ['Avg Response Time', f"{summary['ragflow_avg_time']:.1f}s", f"{summary['feishu_avg_time']:.1f}s",
         f"{summary['ragflow_avg_time'] - summary['feishu_avg_time']:.1f}s"]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3436')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f6fa')])
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 15))
    
    # Benchmark Evaluation (TC001-TC010) - RagFlow vs Feishu
    if tc_count > 0:
        story.append(Paragraph("<b>Benchmark Evaluation (TC001-TC010)</b>", styles['NormalText']))
        tc_diff = tc_ragflow_total - tc_feishu_total
        bench_data = [
            ['Metric', 'RagFlow', 'Feishu', 'Difference'],
            ['Total Score', str(tc_ragflow_total), str(tc_feishu_total), 
             f"+{tc_diff}" if tc_diff > 0 else str(tc_diff)],
            ['Average Score', f"{tc_ragflow_avg:.1f}/50", f"{tc_feishu_avg:.1f}/50",
             f"+{tc_ragflow_avg - tc_feishu_avg:.1f}" if tc_ragflow_avg > tc_feishu_avg else f"{tc_ragflow_avg - tc_feishu_avg:.1f}"],
            ['Higher Score Count', str(tc_ragflow_wins), str(tc_feishu_wins), '-'],
        ]
        
        bench_table = Table(bench_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.2*inch])
        bench_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00b894')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fff4')])
        ]))
        story.append(bench_table)
        story.append(Spacer(1, 15))
    
    # Combined Summary
    story.append(Paragraph("<b>Combined Summary (All 21 Questions)</b>", styles['NormalText']))
    total_diff = combined_ragflow_total - combined_feishu_total
    combined_data = [
        ['Metric', 'RagFlow', 'Feishu', 'Difference'],
        ['Total Questions', str(total_questions), str(total_questions), '-'],
        ['Combined Score', str(combined_ragflow_total), str(combined_feishu_total),
         f"+{total_diff}" if total_diff > 0 else str(total_diff)],
        ['Combined Average', f"{combined_ragflow_avg:.1f}/50", f"{combined_feishu_avg:.1f}/50",
         f"+{combined_ragflow_avg - combined_feishu_avg:.1f}" if combined_ragflow_avg > combined_feishu_avg else f"{combined_ragflow_avg - combined_feishu_avg:.1f}"],
    ]
    
    combined_table = Table(combined_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.2*inch])
    combined_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5ce7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f3ff')])
    ]))
    story.append(combined_table)
    story.append(Spacer(1, 20))
    
    # === 2. Evaluation Methodology ===
    story.append(Paragraph("2. Evaluation Methodology", styles['SectionHeader']))
    
    methodology_text = """
    <b>Evaluation Focus: Accuracy</b><br/>
    This report focuses exclusively on the <b>accuracy</b> of factual information provided by both systems.
    Accuracy is scored on a scale of 0-10 points, measuring the correctness of factual claims, data precision, and alignment with source documents.
    """
    story.append(Paragraph(methodology_text, styles['NormalText']))
    story.append(Spacer(1, 15))
    
    # === 3. RagFlow Retrieval Performance Metrics ===
    story.append(Paragraph("3. RagFlow Retrieval Performance Metrics", styles['SectionHeader']))
    
    retrieval_intro = """
    The following metrics demonstrate RagFlow's document retrieval accuracy. These metrics
    measure how effectively the system identifies and ranks relevant document chunks.
    """
    story.append(Paragraph(retrieval_intro, styles['NormalText']))
    story.append(Spacer(1, 10))
    
    # Combine Q1-Q11 and TC001-TC010 metrics
    ret_summary = retrieval_data.get('summary', {}) if retrieval_data else {}
    q_found = ret_summary.get('found_count', 0)
    q_total = ret_summary.get('total_count', 11)
    q_rank = ret_summary.get('avg_first_rank', 0) if ret_summary.get('avg_first_rank') else 1
    
    tc_found = benchmark_data.get('summary', {}).get('found_count', 0) if benchmark_data else 0
    tc_total = benchmark_data.get('summary', {}).get('total', 10) if benchmark_data else 10
    tc_rank = benchmark_data.get('summary', {}).get('avg_first_rank', 0) if benchmark_data else 0
    tc_coverage = benchmark_data.get('summary', {}).get('avg_coverage', 0) if benchmark_data else 0
    
    total_found = q_found + tc_found
    total_questions = q_total + tc_total
    avg_rank_all = (q_rank * q_found + tc_rank * tc_found) / total_found if total_found > 0 else 0
    
    retrieval_metrics = [
        ['Metric', 'Value', 'Description'],
        ['Target Chunk Found Rate (Q1-Q11)', f"{q_found}/{q_total}", 'Regression test questions'],
        ['Target Chunk Found Rate (TC001-TC010)', f"{tc_found}/{tc_total}", 'Benchmark evaluation questions'],
        ['Overall Found Rate', f"{total_found}/{total_questions}", 'All questions combined'],
        ['Avg First Relevant Chunk Rank', f"#{avg_rank_all:.1f}", 'Average rank position of first relevant chunk'],
        ['Benchmark Chunk Coverage', f"{tc_coverage:.0f}%", 'Percentage of expected chunks retrieved (TC001-TC010)'],
        ['Query Enhancement', 'Enabled', 'LLM-based keyword expansion (Claude Haiku 4.5)'],
        ['Dataset', 'factsheets_tables', '275 documents with structured fund data'],
    ]
    
    retrieval_table = Table(retrieval_metrics, colWidths=[2*inch, 0.8*inch, 3*inch])
    retrieval_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00b894')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fff4')])
    ]))
    story.append(retrieval_table)
    story.append(Spacer(1, 20))
    
    # === 4. Accuracy Analysis ===
    story.append(Paragraph("4. Accuracy Analysis", styles['SectionHeader']))
    
    # Only calculate accuracy averages
    accuracy_scores = {'a': 0, 'b': 0}
    for r in data['results']:
        d = r['details']
        accuracy_scores['a'] += d.get('a_accuracy', 0)
        accuracy_scores['b'] += d.get('b_accuracy', 0)
    
    n = len(data['results'])
    a_avg = accuracy_scores['a'] / n
    b_avg = accuracy_scores['b'] / n
    diff = a_avg - b_avg
    
    criteria_data = [['Criterion', 'RagFlow Avg', 'Feishu Avg', 'Difference']]
    criteria_data.append([
        'Accuracy',
        f"{a_avg:.1f}/10",
        f"{b_avg:.1f}/10",
        f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
    ])
    
    criteria_table = Table(criteria_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1*inch])
    criteria_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c5ce7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f3ff')])
    ]))
    story.append(criteria_table)
    story.append(Spacer(1, 20))
    
    # === 5. Detailed Question Analysis ===
    story.append(PageBreak())
    story.append(Paragraph("5. Detailed Question Analysis", styles['SectionHeader']))
    
    for i, r in enumerate(data['results']):
        # Use Chinese-compatible style if question contains Chinese
        question_text = f"Question {r['id']}: {r['question']}"
        question_style = 'SubSectionChinese' if contains_chinese(r['question']) else 'SubSection'
        story.append(Paragraph(question_text, styles[question_style]))
        
        # Scores
        diff = r['ragflow_score'] - r['feishu_score']
        score_info = f"<b>Scores:</b> RagFlow {r['ragflow_score']}/50 | Feishu {r['feishu_score']}/50 | Difference: {'+' if diff > 0 else ''}{diff} points"
        story.append(Paragraph(score_info, styles['NormalText']))
        
        # Accuracy Score Only
        details = r.get('details', {})
        if details:
            ragflow_accuracy = details.get('a_accuracy', 'N/A')
            feishu_accuracy = details.get('b_accuracy', 'N/A')
            accuracy_info = f"<b>Accuracy:</b> RagFlow {ragflow_accuracy}/10 | Feishu {feishu_accuracy}/10"
            story.append(Paragraph(accuracy_info, styles['NormalText']))
        
        # Response Times
        ragflow_time = r.get('ragflow_time', 0)
        feishu_time = r.get('feishu_time', 0)
        if ragflow_time > 0 and feishu_time > 0:
            time_info = f"<b>Response Time:</b> RagFlow {ragflow_time:.2f}s | Feishu {feishu_time:.2f}s | Speedup: {feishu_time/ragflow_time:.1f}x faster"
        else:
            time_info = f"<b>Response Time:</b> RagFlow {ragflow_time:.2f}s | Feishu {feishu_time:.2f}s"
        story.append(Paragraph(time_info, styles['NormalText']))
        
        # First Relevant Chunk Rank
        ret_q = retrieval_lookup.get(r['id'], {})
        if ret_q:
            rank = ret_q.get('first_relevant_rank')
            if rank:
                rank_info = f"<b>First Relevant Chunk Rank:</b> #{rank}"
            else:
                rank_info = f"<b>First Relevant Chunk Rank:</b> Not found in top 30"
            story.append(Paragraph(rank_info, styles['NormalText']))
        
        # RagFlow answer (full, plain text)
        story.append(Paragraph("<b>RagFlow:</b>", styles['NormalText']))
        rag_text = strip_formatting(r['ragflow_answer'])
        story.append(Paragraph(rag_text, styles['AnswerText']))
        
        # Feishu answer (full, plain text)
        story.append(Paragraph("<b>Feishu:</b>", styles['NormalText']))
        fei_text = strip_formatting(r['feishu_answer'])
        story.append(Paragraph(fei_text, styles['AnswerText']))
        
        story.append(Spacer(1, 15))
        
        # Page break after each question for readability
        if i < len(data['results']) - 1:
            story.append(PageBreak())
    
    # === 6. Benchmark Questions (TC001-TC010) - RagFlow vs Feishu ===
    if benchmark_comparison:
        story.append(PageBreak())
        story.append(Paragraph("6. Benchmark Evaluation (TC001-TC010)", styles['SectionHeader']))
        
        # Create lookup for benchmark comparison
        comp_lookup = {}
        for r in benchmark_comparison.get('results', []):
            comp_lookup[r['id']] = r
        
        bench_comp_sum = benchmark_comparison.get('summary', {})
        bench_intro = f"""
        The following 10 questions are from the RAG evaluation benchmark dataset. Both RagFlow and Feishu 
        were evaluated by an LLM judge ({benchmark_comparison.get('judge_model', 'Claude Sonnet 4')}).
        RagFlow average: <b>{bench_comp_sum.get('ragflow_avg', 0):.1f}/50</b>, Feishu average: <b>{bench_comp_sum.get('feishu_avg', 0):.1f}/50</b>.
        """
        story.append(Paragraph(bench_intro, styles['NormalText']))
        story.append(Spacer(1, 10))
        
        questions_list = benchmark_comparison.get('results', [])
        
        for i, tc in enumerate(questions_list):
            tc_id = tc.get('id')
            question = tc.get('question', '')
            
            # Use Chinese-compatible style if question contains Chinese
            question_style = 'SubSectionChinese' if contains_chinese(question) else 'SubSection'
            story.append(Paragraph(f"{tc_id}: {question}", styles[question_style]))
            
            # Scores comparison
            ragflow_score = tc.get('ragflow_score', 0)
            feishu_score = tc.get('feishu_score', 0)
            diff = ragflow_score - feishu_score
            score_info = f"<b>Scores:</b> RagFlow {ragflow_score}/50 | Feishu {feishu_score}/50 | Difference: {'+' if diff > 0 else ''}{diff} points"
            story.append(Paragraph(score_info, styles['NormalText']))
            
            # Accuracy Score Only
            details = tc.get('details', {})
            if details:
                ragflow_accuracy = details.get('a_accuracy', 'N/A')
                feishu_accuracy = details.get('b_accuracy', 'N/A')
                accuracy_info = f"<b>Accuracy:</b> RagFlow {ragflow_accuracy}/10 | Feishu {feishu_accuracy}/10"
                story.append(Paragraph(accuracy_info, styles['NormalText']))
            
            # Response Times (if available)
            ragflow_time = tc.get('ragflow_time', 0)
            feishu_time = tc.get('feishu_time', 0)
            if ragflow_time > 0 or feishu_time > 0:
                if ragflow_time > 0 and feishu_time > 0:
                    time_info = f"<b>Response Time:</b> RagFlow {ragflow_time:.2f}s | Feishu {feishu_time:.2f}s | Speedup: {feishu_time/ragflow_time:.1f}x faster"
                else:
                    time_info = f"<b>Response Time:</b> RagFlow {ragflow_time:.2f}s | Feishu {feishu_time:.2f}s"
                story.append(Paragraph(time_info, styles['NormalText']))
            
            # Retrieval Metrics from benchmark_data
            bench_q = benchmark_lookup.get(tc_id, {})
            if bench_q:
                rank = bench_q.get('first_relevant_rank')
                coverage = bench_q.get('coverage', 0)
                matched = bench_q.get('matched_count', 0)
                expected = bench_q.get('expected_chunks_count', 0)
                
                metrics_info = f"<b>First Relevant Chunk Rank:</b> #{rank if rank else 'N/A'} | "
                metrics_info += f"<b>Coverage:</b> {coverage:.0f}% ({matched}/{expected} chunks)"
                story.append(Paragraph(metrics_info, styles['NormalText']))
            
            # Category
            category = tc.get('category', '')
            if category:
                story.append(Paragraph(f"<b>Category:</b> {category}", styles['MetricLabel']))
            
            # RagFlow answer
            rag_answer = tc.get('ragflow_answer', '')
            if rag_answer:
                story.append(Paragraph("<b>RagFlow:</b>", styles['NormalText']))
                rag_text = strip_formatting(rag_answer)
                if len(rag_text) > 1500:
                    rag_text = rag_text[:1500] + "... (truncated)"
                story.append(Paragraph(rag_text, styles['AnswerText']))
            
            # Feishu answer
            fei_answer = tc.get('feishu_answer', '')
            if fei_answer:
                story.append(Paragraph("<b>Feishu:</b>", styles['NormalText']))
                fei_text = strip_formatting(fei_answer)
                if len(fei_text) > 1500:
                    fei_text = fei_text[:1500] + "... (truncated)"
                story.append(Paragraph(fei_text, styles['AnswerText']))
            
            story.append(Spacer(1, 10))
            
            # Page break after each question for readability
            if i < len(questions_list) - 1:
                story.append(PageBreak())
    
    # === 7. Summary of Findings ===
    story.append(PageBreak())
    story.append(Paragraph("7. Summary of Findings", styles['SectionHeader']))
    
    # Q1-Q11 comparison stats
    q1_ragflow_higher = sum(1 for r in data['results'] if r['ragflow_score'] > r['feishu_score'])
    q1_feishu_higher = sum(1 for r in data['results'] if r['feishu_score'] > r['ragflow_score'])
    q1_ties = sum(1 for r in data['results'] if r['ragflow_score'] == r['feishu_score'])
    
    # TC001-TC010 comparison stats
    bench_comp_sum = benchmark_comparison.get('summary', {}) if benchmark_comparison else {}
    tc_count = bench_comp_sum.get('total_questions', 0)
    tc_ragflow_total = bench_comp_sum.get('ragflow_total', 0)
    tc_feishu_total = bench_comp_sum.get('feishu_total', 0)
    tc_ragflow_avg = bench_comp_sum.get('ragflow_avg', 0)
    tc_feishu_avg = bench_comp_sum.get('feishu_avg', 0)
    tc_ragflow_wins = bench_comp_sum.get('ragflow_wins', 0)
    tc_feishu_wins = bench_comp_sum.get('feishu_wins', 0)
    tc_ties = bench_comp_sum.get('ties', 0)
    
    # Combined stats
    all_questions = q_count + tc_count
    all_ragflow_total = summary['ragflow_total'] + tc_ragflow_total
    all_feishu_total = summary['feishu_total'] + tc_feishu_total
    all_ragflow_avg = all_ragflow_total / all_questions if all_questions > 0 else 0
    all_feishu_avg = all_feishu_total / all_questions if all_questions > 0 else 0
    all_ragflow_wins = q1_ragflow_higher + tc_ragflow_wins
    all_feishu_wins = q1_feishu_higher + tc_feishu_wins
    all_ties = q1_ties + tc_ties
    
    conclusion_text = f"""
    <b>RagFlow vs Feishu Comparison (Q1-Q11):</b><br/>
    - Out of {q_count} questions, RagFlow achieved higher scores on {q1_ragflow_higher} questions.<br/>
    - Feishu achieved higher scores on {q1_feishu_higher} questions, with {q1_ties} ties.<br/>
    - RagFlow average: {summary['ragflow_avg']:.1f}/50 vs Feishu: {summary['feishu_avg']:.1f}/50.<br/>
    - RagFlow response time: {summary['ragflow_avg_time']:.1f}s vs Feishu: {summary['feishu_avg_time']:.1f}s.<br/><br/>
    
    <b>Benchmark Evaluation (TC001-TC010):</b><br/>
    - Out of {tc_count} questions, RagFlow achieved higher scores on {tc_ragflow_wins} questions.<br/>
    - Feishu achieved higher scores on {tc_feishu_wins} questions, with {tc_ties} ties.<br/>
    - RagFlow average: {tc_ragflow_avg:.1f}/50 vs Feishu: {tc_feishu_avg:.1f}/50.<br/><br/>
    
    <b>Combined Results (All {all_questions} Questions):</b><br/>
    - RagFlow total: {all_ragflow_total}/{all_questions * 50} (average: {all_ragflow_avg:.1f}/50)<br/>
    - Feishu total: {all_feishu_total}/{all_questions * 50} (average: {all_feishu_avg:.1f}/50)<br/>
    - RagFlow higher on {all_ragflow_wins} questions, Feishu higher on {all_feishu_wins} questions, {all_ties} ties.<br/><br/>
    
    <b>Qualitative Observations:</b><br/>
    - RagFlow showed stronger performance in structure and citation criteria.<br/>
    - Both systems performed comparably on accuracy for single-period queries.<br/>
    - Multi-month time-range queries showed the largest score differentials.<br/><br/>
    
    <b>Technical Notes:</b><br/>
    - RagFlow used query enhancement with keyword expansion and time range normalization.<br/>
    - All evaluations conducted by Claude Sonnet 4 with temperature 0.1 for consistency.<br/>
    - All scores use standardized 50-point scale (5 criteria x 10 points each).
    """
    story.append(Paragraph(conclusion_text, styles['NormalText']))
    
    # Build PDF
    doc.build(story)
    print(f"Report generated: {output_path}")
    return output_path

if __name__ == "__main__":
    generate_report()
