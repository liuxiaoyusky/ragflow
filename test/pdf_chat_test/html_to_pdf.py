#!/usr/bin/env python3
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
将HTML测试报告转换为PDF

用法:
    python html_to_pdf.py [html_file] [--output pdf_file]

示例:
    python html_to_pdf.py test_output/test_report.html
    python html_to_pdf.py test_output/test_report.html --output my_report.pdf
"""
import argparse
import sys


def convert_html_to_pdf(html_path: str, pdf_path: str = None) -> bool:
    """将HTML文件转换为PDF"""
    if pdf_path is None:
        pdf_path = html_path.replace(".html", ".pdf")
    
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        print("=" * 60)
        print("ERROR: weasyprint 未安装")
        print("=" * 60)
        print("\n请先安装 weasyprint:")
        print("\n    pip install weasyprint")
        print("\n注意: weasyprint 可能需要一些系统依赖:")
        print("  - Ubuntu/Debian: sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0")
        print("  - macOS: brew install pango")
        print("  - 更多信息: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html")
        return False
    
    try:
        print(f"Converting {html_path} to PDF...")
        
        # 添加打印友好的CSS样式
        print_css = CSS(string="""
            @page {
                size: A4 landscape;
                margin: 1cm;
            }
            body {
                font-size: 10px;
            }
            .container {
                box-shadow: none;
                padding: 15px;
            }
            h1 {
                font-size: 18px;
            }
            h2 {
                font-size: 14px;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
            }
            .stat-card {
                padding: 10px;
            }
            .stat-card .value {
                font-size: 20px;
            }
            table {
                font-size: 8px;
                width: 100%;
            }
            th, td {
                padding: 4px;
            }
            .question-cell, .answer-cell {
                max-width: 180px;
                word-wrap: break-word;
            }
            .score-bar {
                height: 16px;
            }
        """)
        
        HTML(filename=html_path).write_pdf(pdf_path, stylesheets=[print_css])
        
        print(f"✓ PDF report saved to: {pdf_path}")
        return True
        
    except Exception as e:
        print(f"✗ Error generating PDF: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="将HTML测试报告转换为PDF")
    parser.add_argument("html_file", nargs="?", default="test_output/test_report.html",
                        help="HTML文件路径 (默认: test_output/test_report.html)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="输出PDF文件路径 (默认: 与HTML文件同名)")
    
    args = parser.parse_args()
    
    success = convert_html_to_pdf(args.html_file, args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

