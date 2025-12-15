#!/usr/bin/env python3
"""
Generate Answer Comparison Cards as Images (Fixed Version)
- Fixed Chinese font rendering
- More complete answer display
- Corrected score comparison bar
"""

import json
import os
import textwrap
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# =============================================================================
# Configuration
# =============================================================================

OUTPUT_DIR = Path(__file__).parent / 'report_images'
CARD_WIDTH = 1400
MIN_CARD_HEIGHT = 800
PADDING = 50
LINE_HEIGHT = 22

# Colors
COLOR_BG = (250, 251, 252)
COLOR_HEADER = (45, 52, 54)
COLOR_RAGFLOW = (0, 184, 148)
COLOR_FEISHU = (108, 92, 231)
COLOR_TEXT = (33, 37, 41)
COLOR_LIGHT_TEXT = (108, 117, 125)
COLOR_WHITE = (255, 255, 255)
COLOR_CARD_BG = (255, 255, 255)
COLOR_BORDER = (222, 226, 230)
COLOR_LIGHT_GREEN = (200, 247, 237)
COLOR_LIGHT_PURPLE = (230, 225, 255)

def load_evaluation_results():
    """Load evaluation results"""
    eval_path = Path(__file__).parent / 'evaluation_v3.1_results.json'
    with open(eval_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_merged_results():
    """Load merged results with timing info"""
    merged_path = Path(__file__).parent / 'chat_test_v3.1_merged.json'
    with open(merged_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Create lookup by ID
        return {r['id']: r for r in data.get('results', [])}

def strip_markdown(text):
    """Remove markdown formatting from text"""
    if not text:
        return ""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = text.replace('|', ' ')
    text = re.sub(r'-{3,}', '', text)
    text = re.sub(r'\[ID:\d+\]', '', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()

def get_cjk_font(size):
    """Get CJK-compatible font"""
    font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception as e:
                continue
    
    # Try to find any Noto font
    import subprocess
    try:
        result = subprocess.run(['fc-match', '-f', '%{file}', 'Noto Sans CJK SC'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            return ImageFont.truetype(result.stdout.strip(), size)
    except:
        pass
    
    return ImageFont.load_default()

def get_bold_font(size):
    """Get bold CJK-compatible font"""
    font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    
    return get_cjk_font(size)

def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width"""
    if not text:
        return []
    
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph.strip():
            lines.append('')
            continue
        
        words = list(paragraph)  # Split by character for CJK
        current_line = ''
        
        for char in words:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
    
    return lines

def draw_rounded_rect(draw, coords, radius, fill, outline=None):
    """Draw a rounded rectangle"""
    x1, y1, x2, y2 = coords
    
    # Main rectangles
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    
    # Corners
    draw.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
    draw.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)
    
    if outline:
        # Draw outline
        draw.arc([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=outline)
        draw.arc([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=outline)
        draw.arc([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=outline)
        draw.arc([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=outline)
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=outline)
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=outline)
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=outline)
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=outline)

def generate_card(result, index, summary, timing_data=None):
    """Generate a single comparison card with dynamic height (no truncation)"""
    
    # First, calculate required height
    font_text = get_cjk_font(16)
    
    # Create temp image to measure text
    temp_img = Image.new('RGB', (CARD_WIDTH, 100), COLOR_BG)
    temp_draw = ImageDraw.Draw(temp_img)
    
    answer_width = CARD_WIDTH - 2 * PADDING - 20
    
    ragflow_text = strip_markdown(result.get('ragflow_answer', 'N/A'))
    feishu_text = strip_markdown(result.get('feishu_answer', 'N/A'))
    
    ragflow_lines = wrap_text(ragflow_text, font_text, answer_width, temp_draw)
    feishu_lines = wrap_text(feishu_text, font_text, answer_width, temp_draw)
    
    # Calculate total height needed
    header_height = 90
    scores_section = 120
    comparison_bar = 85
    divider = 20
    ragflow_header = 35
    feishu_header = 35
    footer_height = 50
    spacing = 30
    
    ragflow_content_height = len(ragflow_lines) * LINE_HEIGHT
    feishu_content_height = len(feishu_lines) * LINE_HEIGHT
    
    total_height = (header_height + 20 + scores_section + comparison_bar + divider + 
                   ragflow_header + ragflow_content_height + spacing +
                   feishu_header + feishu_content_height + spacing + footer_height)
    
    card_height = max(MIN_CARD_HEIGHT, total_height)
    
    # Now create the actual image
    img = Image.new('RGB', (CARD_WIDTH, card_height), COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    # Fonts
    font_title = get_bold_font(28)
    font_label = get_bold_font(20)
    font_score = get_bold_font(48)
    font_small = get_cjk_font(14)
    
    y = 0
    
    # === Header ===
    draw.rectangle([0, 0, CARD_WIDTH, 90], fill=COLOR_HEADER)
    
    q_id = result['id']
    question = result['question']
    if len(question) > 80:
        question = question[:77] + '...'
    
    draw.text((PADDING, 30), f"{q_id}", fill=COLOR_WHITE, font=font_title)
    draw.text((PADDING + 120, 35), question, fill=COLOR_WHITE, font=font_label)
    
    # Response time badge (if timing data available)
    if timing_data:
        enhance_time = timing_data.get('enhance_time', 0)
        chat_time = timing_data.get('chat_time', 0)
        total_time = enhance_time + chat_time
        time_text = f"{total_time:.1f}s"
        draw.text((CARD_WIDTH - PADDING - 80, 35), time_text, fill=COLOR_LIGHT_TEXT, font=font_label)
    
    y = 110
    
    # === Scores Section ===
    ragflow_score = result.get('ragflow_score', 0)
    feishu_score = result.get('feishu_score', 0)
    
    score_card_width = (CARD_WIDTH - 3 * PADDING) // 2
    
    # RagFlow score card
    draw_rounded_rect(draw, [PADDING, y, PADDING + score_card_width, y + 100], 10, COLOR_WHITE)
    draw.rectangle([PADDING, y, PADDING + 8, y + 100], fill=COLOR_RAGFLOW)
    draw.text((PADDING + 25, y + 12), "RagFlow v3.1", fill=COLOR_RAGFLOW, font=font_label)
    draw.text((PADDING + 25, y + 45), f"{ragflow_score}", fill=COLOR_TEXT, font=font_score)
    draw.text((PADDING + 110, y + 60), "/50", fill=COLOR_LIGHT_TEXT, font=font_label)
    
    # Feishu score card
    fx = PADDING * 2 + score_card_width
    draw_rounded_rect(draw, [fx, y, fx + score_card_width, y + 100], 10, COLOR_WHITE)
    draw.rectangle([fx, y, fx + 8, y + 100], fill=COLOR_FEISHU)
    draw.text((fx + 25, y + 12), "Feishu AI", fill=COLOR_FEISHU, font=font_label)
    draw.text((fx + 25, y + 45), f"{feishu_score}", fill=COLOR_TEXT, font=font_score)
    draw.text((fx + 110, y + 60), "/50", fill=COLOR_LIGHT_TEXT, font=font_label)
    
    # Winner badge
    diff = ragflow_score - feishu_score
    if diff > 0:
        badge_text = f"RagFlow +{diff}"
        badge_color = COLOR_RAGFLOW
    elif diff < 0:
        badge_text = f"Feishu +{-diff}"
        badge_color = COLOR_FEISHU
    else:
        badge_text = "Tie"
        badge_color = COLOR_LIGHT_TEXT
    
    badge_x = CARD_WIDTH - PADDING - 140
    draw_rounded_rect(draw, [badge_x, y + 35, badge_x + 120, y + 70], 15, badge_color)
    draw.text((badge_x + 15, y + 42), badge_text, fill=COLOR_WHITE, font=font_small)
    
    y += 120
    
    # === Score Comparison Bar ===
    draw.text((PADDING, y), "Score Comparison", fill=COLOR_TEXT, font=font_label)
    y += 30
    
    bar_width = CARD_WIDTH - 2 * PADDING
    bar_height = 35
    
    draw_rounded_rect(draw, [PADDING, y, PADDING + bar_width, y + bar_height], 5, COLOR_BORDER)
    
    total_score = ragflow_score + feishu_score
    if total_score > 0:
        ragflow_bar_width = int(bar_width * ragflow_score / total_score)
    else:
        ragflow_bar_width = bar_width // 2
    
    if ragflow_bar_width > 0:
        draw.rectangle([PADDING, y, PADDING + ragflow_bar_width, y + bar_height], fill=COLOR_RAGFLOW)
    if bar_width - ragflow_bar_width > 0:
        draw.rectangle([PADDING + ragflow_bar_width, y, PADDING + bar_width, y + bar_height], fill=COLOR_FEISHU)
    
    draw.text((PADDING + 10, y + 8), f"RagFlow: {ragflow_score}", fill=COLOR_WHITE, font=font_small)
    draw.text((PADDING + bar_width - 100, y + 8), f"Feishu: {feishu_score}", fill=COLOR_WHITE, font=font_small)
    
    y += 55
    
    # === Divider ===
    draw.line([(PADDING, y), (CARD_WIDTH - PADDING, y)], fill=COLOR_BORDER, width=2)
    y += 20
    
    # === RagFlow Answer (FULL - NO TRUNCATION) ===
    draw.rectangle([PADDING - 5, y, PADDING + 5, y + 25], fill=COLOR_RAGFLOW)
    draw.text((PADDING + 15, y), "RagFlow Answer", fill=COLOR_RAGFLOW, font=font_label)
    y += 35
    
    for line in ragflow_lines:
        draw.text((PADDING, y), line, fill=COLOR_TEXT, font=font_text)
        y += LINE_HEIGHT
    
    y += 15
    
    # === Feishu Answer (FULL - NO TRUNCATION) ===
    draw.rectangle([PADDING - 5, y, PADDING + 5, y + 25], fill=COLOR_FEISHU)
    draw.text((PADDING + 15, y), "Feishu Answer", fill=COLOR_FEISHU, font=font_label)
    y += 35
    
    for line in feishu_lines:
        draw.text((PADDING, y), line, fill=COLOR_TEXT, font=font_text)
        y += LINE_HEIGHT
    
    # === Footer ===
    draw.rectangle([0, card_height - 40, CARD_WIDTH, card_height], fill=COLOR_HEADER)
    footer = f"RagFlow v3.1 Evaluation | Q {index + 1}/{summary['total_questions']} | Avg: RagFlow {summary['ragflow_avg']}/50 vs Feishu {summary['feishu_avg']}/50"
    draw.text((PADDING, card_height - 30), footer, fill=COLOR_LIGHT_TEXT, font=font_small)
    
    return img

def generate_summary_card(summary):
    """Generate summary card"""
    img = Image.new('RGB', (CARD_WIDTH, 700), COLOR_BG)
    draw = ImageDraw.Draw(img)
    
    font_title = get_bold_font(32)
    font_label = get_bold_font(24)
    font_score = get_bold_font(64)
    font_text = get_cjk_font(20)
    
    # Header
    draw.rectangle([0, 0, CARD_WIDTH, 100], fill=COLOR_HEADER)
    draw.text((PADDING, 35), "RAG System Evaluation Summary", fill=COLOR_WHITE, font=font_title)
    draw.text((CARD_WIDTH - 350, 45), "RagFlow v3.1 vs Feishu AI", fill=COLOR_LIGHT_TEXT, font=font_text)
    
    y = 130
    
    # Score cards
    card_width = (CARD_WIDTH - 3 * PADDING) // 2
    
    # RagFlow total
    draw_rounded_rect(draw, [PADDING, y, PADDING + card_width, y + 180], 15, COLOR_WHITE)
    draw.rectangle([PADDING, y, PADDING + 12, y + 180], fill=COLOR_RAGFLOW)
    draw.text((PADDING + 35, y + 20), "RagFlow v3.1", fill=COLOR_RAGFLOW, font=font_label)
    draw.text((PADDING + 35, y + 60), f"{summary['ragflow_avg']}", fill=COLOR_TEXT, font=font_score)
    draw.text((PADDING + 170, y + 90), "/50 avg", fill=COLOR_LIGHT_TEXT, font=font_label)
    draw.text((PADDING + 35, y + 140), f"Total: {summary['ragflow_total']}/1050", fill=COLOR_LIGHT_TEXT, font=font_text)
    
    # Feishu total
    fx = PADDING * 2 + card_width
    draw_rounded_rect(draw, [fx, y, fx + card_width, y + 180], 15, COLOR_WHITE)
    draw.rectangle([fx, y, fx + 12, y + 180], fill=COLOR_FEISHU)
    draw.text((fx + 35, y + 20), "Feishu AI", fill=COLOR_FEISHU, font=font_label)
    draw.text((fx + 35, y + 60), f"{summary['feishu_avg']}", fill=COLOR_TEXT, font=font_score)
    draw.text((fx + 170, y + 90), "/50 avg", fill=COLOR_LIGHT_TEXT, font=font_label)
    draw.text((fx + 35, y + 140), f"Total: {summary['feishu_total']}/1050", fill=COLOR_LIGHT_TEXT, font=font_text)
    
    y += 210
    
    # Win statistics
    draw.text((PADDING, y), "Win Statistics", fill=COLOR_TEXT, font=font_label)
    y += 40
    
    bar_width = CARD_WIDTH - 2 * PADDING
    total_q = summary['total_questions']
    
    # Calculate proportional widths
    r_width = int(bar_width * summary['ragflow_wins'] / total_q)
    t_width = int(bar_width * summary['ties'] / total_q)
    f_width = bar_width - r_width - t_width
    
    # Draw bar
    if r_width > 0:
        draw.rectangle([PADDING, y, PADDING + r_width, y + 60], fill=COLOR_RAGFLOW)
    if t_width > 0:
        draw.rectangle([PADDING + r_width, y, PADDING + r_width + t_width, y + 60], fill=COLOR_BORDER)
    if f_width > 0:
        draw.rectangle([PADDING + r_width + t_width, y, PADDING + bar_width, y + 60], fill=COLOR_FEISHU)
    
    # Labels
    draw.text((PADDING + 15, y + 18), f"RagFlow Wins: {summary['ragflow_wins']}", fill=COLOR_WHITE, font=font_text)
    if summary['ties'] > 0 and t_width > 100:
        draw.text((PADDING + r_width + 10, y + 18), f"Ties: {summary['ties']}", fill=COLOR_TEXT, font=font_text)
    draw.text((PADDING + bar_width - 180, y + 18), f"Feishu Wins: {summary['feishu_wins']}", fill=COLOR_WHITE, font=font_text)
    
    y += 80
    
    # Percentage summary
    ragflow_pct = summary['ragflow_avg'] / 50 * 100
    feishu_pct = summary['feishu_avg'] / 50 * 100
    summary_text = f"RagFlow achieves {ragflow_pct:.0f}% average score vs Feishu's {feishu_pct:.0f}% | Difference: +{summary['ragflow_avg'] - summary['feishu_avg']:.1f} points"
    draw.text((PADDING, y), summary_text, fill=COLOR_TEXT, font=font_text)
    
    # Footer
    draw.rectangle([0, 660, CARD_WIDTH, 700], fill=COLOR_HEADER)
    draw.text((PADDING, 672), f"21 Questions | Judge: Claude Sonnet 4 | {summary['timestamp'][:10]}", fill=COLOR_LIGHT_TEXT, font=font_text)
    
    return img

def main():
    print("=" * 60)
    print("Generating Answer Comparison Cards (Fixed)")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Output: {OUTPUT_DIR}")
    
    data = load_evaluation_results()
    results = data['results']
    summary = data['summary']
    
    # Load timing data
    timing_lookup = load_merged_results()
    print(f"Loaded {len(results)} results, {len(timing_lookup)} timing entries")
    
    # Generate individual cards
    for i, result in enumerate(results):
        q_id = result['id']
        timing = timing_lookup.get(q_id)
        print(f"  [{i+1}/{len(results)}] {q_id}...")
        
        img = generate_card(result, i, summary, timing)
        img.save(OUTPUT_DIR / f"card_{q_id}.png", 'PNG')
    
    # Generate summary card
    print("  Generating summary card...")
    summary_img = generate_summary_card(summary)
    summary_img.save(OUTPUT_DIR / "card_summary.png", 'PNG')
    
    print(f"\nGenerated {len(results) + 1} cards")
    print("=" * 60)

if __name__ == "__main__":
    main()
