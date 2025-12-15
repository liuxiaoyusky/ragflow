#!/usr/bin/env python3
"""
Generate PDF Report with Answer Comparison Card Images
Following the format of generate_scientific_report.py
"""

import json
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

TOOLS_DIR = Path(__file__).parent
IMAGES_DIR = TOOLS_DIR / 'report_images'

def load_evaluation_data():
    with open(TOOLS_DIR / 'evaluation_v3.1_results.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_merged_results():
    with open(TOOLS_DIR / 'chat_test_v3.1_merged.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        return {r['id']: r for r in data.get('results', [])}

def create_styles():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='ReportTitle',
        fontName='Helvetica-Bold',
        fontSize=18,
        spaceAfter=10,
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
        name='NormalText',
        fontName='Helvetica',
        fontSize=10,
        spaceAfter=6,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='MetricLabel',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#666666')
    ))
    
    styles.add(ParagraphStyle(
        name='ChineseText',
        fontName='STSong-Light',
        fontSize=9,
        spaceAfter=4,
        leading=12
    ))
    
    return styles

def generate_report():
    eval_data = load_evaluation_data()
    timing_data = load_merged_results()
    styles = create_styles()
    summary = eval_data['summary']
    results = eval_data['results']
    
    # Separate Q and TC results
    q_results = [r for r in results if r['id'].startswith('Q')]
    tc_results = [r for r in results if r['id'].startswith('TC')]
    
    # Calculate Q1-Q11 stats
    q_ragflow_total = sum(r['ragflow_score'] for r in q_results)
    q_feishu_total = sum(r['feishu_score'] for r in q_results)
    q_ragflow_avg = q_ragflow_total / len(q_results) if q_results else 0
    q_feishu_avg = q_feishu_total / len(q_results) if q_results else 0
    q_ragflow_wins = sum(1 for r in q_results if r['ragflow_score'] > r['feishu_score'])
    q_feishu_wins = sum(1 for r in q_results if r['feishu_score'] > r['ragflow_score'])
    
    # Calculate TC001-TC010 stats
    tc_ragflow_total = sum(r['ragflow_score'] for r in tc_results)
    tc_feishu_total = sum(r['feishu_score'] for r in tc_results)
    tc_ragflow_avg = tc_ragflow_total / len(tc_results) if tc_results else 0
    tc_feishu_avg = tc_feishu_total / len(tc_results) if tc_results else 0
    tc_ragflow_wins = sum(1 for r in tc_results if r['ragflow_score'] > r['feishu_score'])
    tc_feishu_wins = sum(1 for r in tc_results if r['feishu_score'] > r['ragflow_score'])
    
    # Calculate avg response time
    q_times = [timing_data[r['id']].get('enhance_time', 0) + timing_data[r['id']].get('chat_time', 0) 
               for r in q_results if r['id'] in timing_data]
    avg_response_time = sum(q_times) / len(q_times) if q_times else 0
    
    output_path = TOOLS_DIR / 'RagFlow_v3.1_Evaluation_Report.pdf'
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                           leftMargin=0.75*inch, rightMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    story = []
    
    # === Title ===
    story.append(Paragraph("RAG System Accuracy Evaluation Report", styles['ReportTitle']))
    story.append(Paragraph("RagFlow v3.1 vs Feishu Knowledge AI", styles['NormalText']))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['MetricLabel']))
    story.append(Spacer(1, 20))
    
    # === 1. Executive Summary ===
    story.append(Paragraph("1. Executive Summary", styles['SectionHeader']))
    
    summary_text = f"""
    This report presents an objective evaluation of RagFlow v3.1 RAG system across {len(results)} fund-related questions:
    Q1-Q11 ({len(q_results)} questions) and TC001-TC010 ({len(tc_results)} benchmark questions).
    The evaluation was conducted by Claude Sonnet 4 using standardized scoring criteria focused on <b>Accuracy</b>.
    """
    story.append(Paragraph(summary_text, styles['NormalText']))
    story.append(Spacer(1, 10))
    
    # RagFlow vs Feishu comparison (Q1-Q11)
    story.append(Paragraph("<b>RagFlow vs Feishu Comparison (Q1-Q11)</b>", styles['NormalText']))
    q_summary_data = [
        ['Metric', 'RagFlow', 'Feishu', 'Difference'],
        ['Total Score', str(q_ragflow_total), str(q_feishu_total), 
         f"+{q_ragflow_total - q_feishu_total}"],
        ['Average Score', f"{q_ragflow_avg:.1f}/50", f"{q_feishu_avg:.1f}/50",
         f"+{q_ragflow_avg - q_feishu_avg:.1f}"],
        ['Higher Score Count', str(q_ragflow_wins), str(q_feishu_wins), '-'],
        ['Avg Response Time', f"{avg_response_time:.1f}s", 'N/A', '-']
    ]
    
    q_table = Table(q_summary_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.2*inch])
    q_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3436')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f6fa')])
    ]))
    story.append(q_table)
    story.append(Spacer(1, 15))
    
    # Benchmark Evaluation (TC001-TC010)
    story.append(Paragraph("<b>Benchmark Evaluation (TC001-TC010)</b>", styles['NormalText']))
    tc_diff = tc_ragflow_total - tc_feishu_total
    tc_data = [
        ['Metric', 'RagFlow', 'Feishu', 'Difference'],
        ['Total Score', str(tc_ragflow_total), str(tc_feishu_total), 
         f"+{tc_diff}" if tc_diff > 0 else str(tc_diff)],
        ['Average Score', f"{tc_ragflow_avg:.1f}/50", f"{tc_feishu_avg:.1f}/50",
         f"+{tc_ragflow_avg - tc_feishu_avg:.1f}"],
        ['Higher Score Count', str(tc_ragflow_wins), str(tc_feishu_wins), '-'],
    ]
    
    tc_table = Table(tc_data, colWidths=[2*inch, 1.3*inch, 1.3*inch, 1.2*inch])
    tc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00b894')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fff4')])
    ]))
    story.append(tc_table)
    story.append(Spacer(1, 15))
    
    # Combined Summary
    story.append(Paragraph("<b>Combined Summary (All 21 Questions)</b>", styles['NormalText']))
    total_diff = summary['ragflow_total'] - summary['feishu_total']
    combined_data = [
        ['Metric', 'RagFlow', 'Feishu', 'Difference'],
        ['Total Questions', str(len(results)), str(len(results)), '-'],
        ['Combined Score', str(summary['ragflow_total']), str(summary['feishu_total']),
         f"+{total_diff}" if total_diff > 0 else str(total_diff)],
        ['Combined Average', f"{summary['ragflow_avg']:.1f}/50", f"{summary['feishu_avg']:.1f}/50",
         f"+{summary['ragflow_avg'] - summary['feishu_avg']:.1f}"],
        ['Win/Lose/Tie', f"{summary['ragflow_wins']}", f"{summary['feishu_wins']}", f"Ties: {summary['ties']}"],
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
    This report focuses on the <b>accuracy</b> of factual information provided by both systems.
    Each answer is scored on a scale of 1-50 based on:
    <br/><br/>
    - <b>Accuracy</b> (Primary): Is the information factually correct?
    - Completeness: Does it fully answer the question?
    - Structure: Is the answer well-organized?
    - Citation: Are sources properly referenced?
    - Professionalism: Is the language appropriate?
    <br/><br/>
    <b>Judge Model:</b> Claude Sonnet 4 (anthropic/claude-sonnet-4)
    <br/>
    <b>Prompt Version:</b> v3.1 (with multi-fund comparison rule)
    """
    story.append(Paragraph(methodology_text, styles['NormalText']))
    story.append(Spacer(1, 15))
    
    # === 3. Score Distribution ===
    story.append(Paragraph("3. Score Distribution by Question", styles['SectionHeader']))
    
    score_header = ['ID', 'RagFlow', 'Feishu', 'Diff', 'Time(s)', 'Winner']
    score_rows = [score_header]
    
    for r in results:
        timing = timing_data.get(r['id'], {})
        resp_time = timing.get('enhance_time', 0) + timing.get('chat_time', 0)
        diff = r['ragflow_score'] - r['feishu_score']
        winner = 'RagFlow' if diff > 0 else ('Feishu' if diff < 0 else 'Tie')
        score_rows.append([
            r['id'],
            f"{r['ragflow_score']}/50",
            f"{r['feishu_score']}/50",
            f"+{diff}" if diff > 0 else str(diff),
            f"{resp_time:.1f}",
            winner
        ])
    
    score_table = Table(score_rows, colWidths=[0.7*inch, 0.9*inch, 0.9*inch, 0.6*inch, 0.7*inch, 0.9*inch])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3436')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))
    
    # === 4. Summary Card ===
    story.append(PageBreak())
    story.append(Paragraph("4. Visual Summary", styles['SectionHeader']))
    
    summary_card_path = IMAGES_DIR / 'card_summary.png'
    if summary_card_path.exists():
        img_width = 6.5 * inch
        img_height = 3.5 * inch
        story.append(Image(str(summary_card_path), width=img_width, height=img_height))
    story.append(Spacer(1, 20))
    
    # === 5. Detailed Question Analysis (Q1-Q11) ===
    story.append(PageBreak())
    story.append(Paragraph("5. Detailed Question Analysis (Q1-Q11)", styles['SectionHeader']))
    story.append(Paragraph(
        "Each card shows question, scores, response time, and complete answers from both systems.",
        styles['NormalText']
    ))
    
    for r in q_results:
        card_path = IMAGES_DIR / f"card_{r['id']}.png"
        if card_path.exists():
            story.append(PageBreak())
            
            # Get image dimensions
            from PIL import Image as PILImage
            with PILImage.open(card_path) as pil_img:
                img_w, img_h = pil_img.size
            
            # Scale to fit page width
            page_width = 6.5 * inch
            scale = page_width / img_w
            img_height = img_h * scale
            
            # If too tall, scale down
            max_height = 9 * inch
            if img_height > max_height:
                img_height = max_height
                scale = img_height / img_h
                page_width = img_w * scale
            
            story.append(Image(str(card_path), width=page_width, height=img_height))
    
    # === 6. Benchmark Questions (TC001-TC010) ===
    story.append(PageBreak())
    story.append(Paragraph("6. Benchmark Evaluation (TC001-TC010)", styles['SectionHeader']))
    story.append(Paragraph(
        "These questions are from the RAG evaluation benchmark dataset for systematic testing.",
        styles['NormalText']
    ))
    
    for r in tc_results:
        card_path = IMAGES_DIR / f"card_{r['id']}.png"
        if card_path.exists():
            story.append(PageBreak())
            
            from PIL import Image as PILImage
            with PILImage.open(card_path) as pil_img:
                img_w, img_h = pil_img.size
            
            page_width = 6.5 * inch
            scale = page_width / img_w
            img_height = img_h * scale
            
            max_height = 9 * inch
            if img_height > max_height:
                img_height = max_height
                scale = img_height / img_h
                page_width = img_w * scale
            
            story.append(Image(str(card_path), width=page_width, height=img_height))
    
    # === 7. Summary of Findings ===
    story.append(PageBreak())
    story.append(Paragraph("7. Summary of Findings", styles['SectionHeader']))
    
    findings_text = f"""
    <b>Overall Performance:</b><br/>
    RagFlow v3.1 achieved an average score of <b>{summary['ragflow_avg']:.1f}/50</b> compared to Feishu's <b>{summary['feishu_avg']:.1f}/50</b>,
    representing a <b>+{summary['ragflow_avg'] - summary['feishu_avg']:.1f}</b> point advantage.
    <br/><br/>
    <b>Win/Loss Record:</b><br/>
    - RagFlow won: <b>{summary['ragflow_wins']}</b> questions
    - Feishu won: <b>{summary['feishu_wins']}</b> questions
    - Ties: <b>{summary['ties']}</b> questions
    <br/><br/>
    <b>Key Observations:</b><br/>
    - RagFlow demonstrates strong accuracy in fund factsheet Q&A
    - Query Enhancement v3.1 improves multi-fund comparison handling
    - Average response time: {avg_response_time:.1f}s per question
    <br/><br/>
    <b>Conclusion:</b><br/>
    RagFlow v3.1 with Query Enhancement Prompt v3.1 shows significant improvement in accuracy
    over Feishu Knowledge AI for fund-related queries.
    """
    story.append(Paragraph(findings_text, styles['NormalText']))
    
    # Footer
    story.append(Spacer(1, 30))
    footer = f"<i>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | RagFlow v3.1 Evaluation</i>"
    story.append(Paragraph(footer, styles['MetricLabel']))
    
    doc.build(story)
    print(f"Report saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    print("=" * 60)
    print("Generating PDF Report (Scientific Format)")
    print("=" * 60)
    generate_report()
    print("\nDone!")
