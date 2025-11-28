#!/usr/bin/env python3
"""
展示测试问答结果
"""
import json
import sys
from pathlib import Path


def load_results(file_path: str = "test_output/test_results.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def show_qa_list(results_file: str = "test_output/test_results.json", output_file: str = None):
    """显示问答列表"""
    data = load_results(results_file)
    results = data.get("results", [])
    
    output_lines = []
    separator = "=" * 80
    
    output_lines.append(separator)
    output_lines.append(f"RAGFlow Chat 测试问答结果")
    output_lines.append(f"总问题数: {len(results)}")
    output_lines.append(separator)
    output_lines.append("")
    
    for i, result in enumerate(results, 1):
        question = result.get("question", "")
        answer = result.get("answer", "")
        success = result.get("success", False)
        response_time = result.get("response_time", 0)
        
        # 获取引用的文档
        reference = result.get("reference", {})
        doc_aggs = reference.get("doc_aggs", [])
        chunks = reference.get("chunks", [])
        
        output_lines.append(f"{'─' * 80}")
        output_lines.append(f"问题 {i}:")
        output_lines.append(f"  {question}")
        output_lines.append("")
        output_lines.append(f"答案:")
        # 格式化答案，保留换行
        for line in answer.split('\n'):
            output_lines.append(f"  {line}")
        output_lines.append("")
        
        if doc_aggs:
            output_lines.append(f"引用文档:")
            for doc in doc_aggs:
                output_lines.append(f"  - {doc.get('doc_name', 'Unknown')} ({doc.get('count', 0)} chunks)")
        
        output_lines.append(f"")
        output_lines.append(f"状态: {'✓ 成功' if success else '✗ 失败'} | 响应时间: {response_time:.2f}s")
        output_lines.append("")
    
    output_text = "\n".join(output_lines)
    
    # 打印到控制台
    print(output_text)
    
    # 保存到文件
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"\n结果已保存到: {output_file}")
    
    return output_lines


def export_to_markdown(results_file: str = "test_output/test_results.json", output_file: str = "test_output/qa_list.md"):
    """导出为Markdown格式"""
    data = load_results(results_file)
    results = data.get("results", [])
    
    lines = []
    lines.append("# RAGFlow Chat 测试问答结果\n")
    lines.append(f"**总问题数**: {len(results)}\n")
    lines.append(f"**测试时间**: {data.get('metadata', {}).get('updated_at', 'N/A')}\n")
    lines.append("---\n")
    
    for i, result in enumerate(results, 1):
        question = result.get("question", "")
        answer = result.get("answer", "")
        success = result.get("success", False)
        response_time = result.get("response_time", 0)
        
        reference = result.get("reference", {})
        doc_aggs = reference.get("doc_aggs", [])
        
        lines.append(f"## 问题 {i}\n")
        lines.append(f"**Q**: {question}\n")
        lines.append(f"**A**: {answer}\n")
        
        if doc_aggs:
            lines.append(f"**引用文档**:")
            for doc in doc_aggs:
                lines.append(f"- {doc.get('doc_name', 'Unknown')} ({doc.get('count', 0)} chunks)")
            lines.append("")
        
        status = "✅ 成功" if success else "❌ 失败"
        lines.append(f"*{status} | 响应时间: {response_time:.2f}s*\n")
        lines.append("---\n")
    
    output_text = "\n".join(lines)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_text)
    
    print(f"Markdown结果已保存到: {output_file}")
    return output_file


def export_to_pdf(results_file: str = "test_output/test_results.json", output_file: str = "test_output/qa_list.pdf"):
    """导出为PDF格式"""
    data = load_results(results_file)
    results = data.get("results", [])
    metadata = data.get("metadata", {})
    
    # 先生成HTML
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow Chat 测试问答结果</title>
    <style>
        @page {
            size: A4;
            margin: 1.5cm;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            font-size: 11px;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            font-size: 20px;
        }
        .metadata {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .qa-item {
            margin-bottom: 25px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            page-break-inside: avoid;
        }
        .question-header {
            background: #3498db;
            color: white;
            padding: 8px 12px;
            margin: -15px -15px 15px -15px;
            border-radius: 8px 8px 0 0;
            font-weight: bold;
        }
        .question {
            color: #2c3e50;
            font-weight: bold;
            margin-bottom: 10px;
            font-size: 12px;
        }
        .answer {
            background: #f9f9f9;
            padding: 12px;
            border-left: 4px solid #27ae60;
            margin: 10px 0;
            white-space: pre-wrap;
        }
        .references {
            font-size: 10px;
            color: #666;
            margin-top: 10px;
        }
        .references ul {
            margin: 5px 0;
            padding-left: 20px;
        }
        .status {
            font-size: 10px;
            color: #888;
            text-align: right;
            margin-top: 10px;
        }
        .status.success { color: #27ae60; }
        .status.failed { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>RAGFlow Chat 测试问答结果</h1>
    <div class="metadata">
        <strong>总问题数:</strong> """ + str(len(results)) + """<br>
        <strong>测试时间:</strong> """ + metadata.get('updated_at', 'N/A') + """<br>
        <strong>Chat ID:</strong> """ + metadata.get('chat_id', 'N/A') + """
    </div>
"""
    
    for i, result in enumerate(results, 1):
        question = result.get("question", "").replace("<", "&lt;").replace(">", "&gt;")
        answer = result.get("answer", "").replace("<", "&lt;").replace(">", "&gt;")
        success = result.get("success", False)
        response_time = result.get("response_time", 0)
        
        reference = result.get("reference", {})
        doc_aggs = reference.get("doc_aggs", [])
        
        status_class = "success" if success else "failed"
        status_text = "✓ 成功" if success else "✗ 失败"
        
        html_content += f"""
    <div class="qa-item">
        <div class="question-header">问题 {i}</div>
        <div class="question">Q: {question}</div>
        <div class="answer">{answer}</div>
"""
        
        if doc_aggs:
            html_content += """        <div class="references">
            <strong>引用文档:</strong>
            <ul>
"""
            for doc in doc_aggs:
                html_content += f"                <li>{doc.get('doc_name', 'Unknown')} ({doc.get('count', 0)} chunks)</li>\n"
            html_content += """            </ul>
        </div>
"""
        
        html_content += f"""        <div class="status {status_class}">{status_text} | 响应时间: {response_time:.2f}s</div>
    </div>
"""
    
    html_content += """
</body>
</html>
"""
    
    # 保存临时HTML文件
    html_file = output_file.replace(".pdf", ".html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # 转换为PDF
    try:
        from weasyprint import HTML
        HTML(filename=html_file).write_pdf(output_file)
        print(f"✓ PDF问答列表已保存到: {output_file}")
        return output_file
    except ImportError:
        print("Error: weasyprint未安装，请运行: pip install weasyprint")
        print(f"HTML版本已保存到: {html_file}")
        return html_file
    except Exception as e:
        print(f"PDF生成失败: {e}")
        print(f"HTML版本已保存到: {html_file}")
        return html_file


if __name__ == "__main__":
    results_file = sys.argv[1] if len(sys.argv) > 1 else "test_output/test_results.json"
    
    # 显示问答列表
    show_qa_list(results_file, "test_output/qa_list.txt")
    
    # 导出Markdown格式
    export_to_markdown(results_file, "test_output/qa_list.md")
    
    # 导出PDF格式
    export_to_pdf(results_file, "test_output/qa_list.pdf")

