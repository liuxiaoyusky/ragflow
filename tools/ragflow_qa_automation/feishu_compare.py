#!/usr/bin/env python3
"""
飞书Knowledge AI对比测试脚本
使用Playwright连接本机Chrome浏览器进行自动化测试
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 飞书Knowledge AI URL
FEISHU_ASK_URL = "https://ask.feishu.cn/"


class FeishuKnowledgeAITester:
    """飞书Knowledge AI自动化测试器"""
    
    def __init__(self, questions_file: str, output_dir: str = "test_output"):
        self.questions_file = questions_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
        
    def load_questions(self) -> List[str]:
        """加载问题列表"""
        with open(self.questions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        questions = [q["question"] for q in data.get("questions", [])]
        logger.info(f"Loaded {len(questions)} questions")
        return questions
    
    async def run_test(self, max_questions: int = 20):
        """运行测试
        
        Args:
            max_questions: 最大测试问题数（建议先用少量问题测试）
        """
        from playwright.async_api import async_playwright
        
        questions = self.load_questions()[:max_questions]
        
        print("\n" + "="*60)
        print("飞书Knowledge AI 对比测试")
        print("="*60)
        print(f"测试问题数: {len(questions)}")
        print(f"目标URL: {FEISHU_ASK_URL}")
        print("="*60)
        
        async with async_playwright() as p:
            # 连接到已运行的Chrome浏览器
            # 需要先用以下命令启动Chrome:
            # google-chrome --remote-debugging-port=9222
            print("\n⚠️  请确保Chrome浏览器已启动并开启远程调试:")
            print("    运行命令: google-chrome --remote-debugging-port=9222")
            print("    然后在浏览器中登录 https://ask.feishu.cn/")
            print("\n按 Enter 继续...")
            input()
            
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                logger.info("Successfully connected to Chrome browser")
            except Exception as e:
                print(f"\n❌ 无法连接到Chrome浏览器: {e}")
                print("\n请按以下步骤操作:")
                print("1. 关闭所有Chrome窗口")
                print("2. 运行: google-chrome --remote-debugging-port=9222")
                print("3. 在浏览器中打开 https://ask.feishu.cn/ 并登录")
                print("4. 重新运行此脚本")
                return
            
            # 获取已有页面或创建新页面
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
                pages = context.pages
                page = None
                for p in pages:
                    if "ask.feishu.cn" in p.url:
                        page = p
                        break
                if not page:
                    page = await context.new_page()
                    await page.goto(FEISHU_ASK_URL)
            else:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(FEISHU_ASK_URL)
            
            print(f"\n当前页面: {page.url}")
            print("\n开始测试...")
            
            for i, question in enumerate(questions, 1):
                print(f"\n[{i}/{len(questions)}] 测试问题: {question[:50]}...")
                
                try:
                    result = await self._ask_question(page, question)
                    self.results.append(result)
                    
                    if result["success"]:
                        print(f"  ✓ 获取回答成功 (耗时: {result['response_time']:.2f}s)")
                        print(f"  回答预览: {result['answer'][:100]}...")
                    else:
                        print(f"  ✗ 获取回答失败: {result.get('error', 'Unknown error')}")
                    
                    # 每5个问题保存一次中间结果
                    if i % 5 == 0:
                        self._save_results()
                        
                    # 间隔一下避免请求过快
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error testing question {i}: {e}")
                    self.results.append({
                        "question": question,
                        "answer": "",
                        "success": False,
                        "error": str(e),
                        "response_time": 0
                    })
            
            # 保存最终结果
            self._save_results()
            self._generate_comparison_report()
            
            print("\n" + "="*60)
            print("测试完成!")
            print(f"结果保存到: {self.output_dir}/feishu_results.json")
            print(f"对比报告: {self.output_dir}/comparison_report.html")
            print("="*60)
    
    async def _ask_question(self, page, question: str) -> Dict[str, Any]:
        """向飞书Knowledge AI提问并获取回答"""
        start_time = time.time()
        
        try:
            # 等待输入框出现
            # 注意：选择器可能需要根据实际页面调整
            input_selectors = [
                'textarea[placeholder*="问"]',
                'textarea[placeholder*="输入"]',
                'input[placeholder*="问"]',
                'input[placeholder*="输入"]',
                '[data-testid="chat-input"]',
                '.chat-input textarea',
                'textarea',
            ]
            
            input_element = None
            for selector in input_selectors:
                try:
                    input_element = await page.wait_for_selector(selector, timeout=5000)
                    if input_element:
                        break
                except:
                    continue
            
            if not input_element:
                return {
                    "question": question,
                    "answer": "",
                    "success": False,
                    "error": "找不到输入框",
                    "response_time": 0
                }
            
            # 清空输入框并输入问题
            await input_element.click()
            await input_element.fill("")
            await input_element.fill(question)
            
            # 发送问题 - 尝试多种方式
            # 方式1: 按Enter键
            await page.keyboard.press("Enter")
            
            # 等待回答生成（观察页面变化）
            await asyncio.sleep(3)  # 等待开始生成
            
            # 等待回答完成（检测加载状态消失或内容稳定）
            max_wait = 60  # 最多等待60秒
            last_content = ""
            stable_count = 0
            
            for _ in range(max_wait):
                await asyncio.sleep(1)
                
                # 尝试获取最新的回答内容
                answer_selectors = [
                    '.message-content:last-child',
                    '.chat-message:last-child .content',
                    '.answer-content:last-child',
                    '[data-testid="message"]:last-child',
                    '.markdown-body:last-child',
                ]
                
                current_content = ""
                for selector in answer_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            current_content = await elements[-1].inner_text()
                            if current_content:
                                break
                    except:
                        continue
                
                # 检查内容是否稳定（连续3秒没有变化）
                if current_content and current_content == last_content:
                    stable_count += 1
                    if stable_count >= 3:
                        break
                else:
                    stable_count = 0
                    last_content = current_content
            
            response_time = time.time() - start_time
            
            if last_content:
                return {
                    "question": question,
                    "answer": last_content,
                    "success": True,
                    "response_time": response_time
                }
            else:
                return {
                    "question": question,
                    "answer": "",
                    "success": False,
                    "error": "未能获取到回答内容",
                    "response_time": response_time
                }
                
        except Exception as e:
            return {
                "question": question,
                "answer": "",
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }
    
    def _save_results(self):
        """保存测试结果"""
        output_file = self.output_dir / "feishu_results.json"
        data = {
            "metadata": {
                "source": "feishu_knowledge_ai",
                "url": FEISHU_ASK_URL,
                "tested_at": datetime.now().isoformat(),
                "total_questions": len(self.results)
            },
            "results": self.results
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Results saved to {output_file}")
    
    def _generate_comparison_report(self):
        """生成对比报告"""
        # 加载RAGFlow测试结果
        ragflow_file = self.output_dir / "test_results.json"
        ragflow_results = {}
        if ragflow_file.exists():
            with open(ragflow_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data.get("results", []):
                    ragflow_results[r["question"]] = r
        
        # 生成HTML对比报告
        html = self._build_comparison_html(ragflow_results)
        
        output_file = self.output_dir / "comparison_report.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Comparison report saved to {output_file}")
    
    def _build_comparison_html(self, ragflow_results: Dict) -> str:
        """构建对比报告HTML"""
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>RAGFlow vs 飞书Knowledge AI 对比报告</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        .summary {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary-card h3 { margin-top: 0; color: #2c3e50; }
        .summary-card.ragflow { border-left: 4px solid #3498db; }
        .summary-card.feishu { border-left: 4px solid #00d4aa; }
        .comparison-item {
            background: white;
            margin: 15px 0;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .question {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
            padding: 10px;
            background: #ecf0f1;
            border-radius: 4px;
        }
        .answers {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .answer-box {
            padding: 15px;
            border-radius: 6px;
            font-size: 14px;
            line-height: 1.6;
        }
        .answer-box.ragflow {
            background: #e8f4fc;
            border: 1px solid #3498db;
        }
        .answer-box.feishu {
            background: #e8fcf4;
            border: 1px solid #00d4aa;
        }
        .answer-box h4 {
            margin: 0 0 10px 0;
            color: #555;
        }
        .score { font-weight: bold; }
        .score.good { color: #27ae60; }
        .score.fair { color: #f39c12; }
        .score.poor { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>🔍 RAGFlow vs 飞书Knowledge AI 对比报告</h1>
    
    <div class="summary">
        <div class="summary-card ragflow">
            <h3>RAGFlow</h3>
            <p>测试问题数: """ + str(len(ragflow_results)) + """</p>
        </div>
        <div class="summary-card feishu">
            <h3>飞书 Knowledge AI</h3>
            <p>测试问题数: """ + str(len(self.results)) + """</p>
        </div>
    </div>
    
    <h2>详细对比</h2>
"""
        
        for i, feishu_result in enumerate(self.results, 1):
            question = feishu_result["question"]
            feishu_answer = feishu_result.get("answer", "无回答")
            
            ragflow_result = ragflow_results.get(question, {})
            ragflow_answer = ragflow_result.get("answer", "无回答")
            ragflow_score = ragflow_result.get("evaluation", {}).get("overall_score", 0)
            
            score_class = "good" if ragflow_score >= 4 else ("fair" if ragflow_score >= 3 else "poor")
            
            html += f"""
    <div class="comparison-item">
        <div class="question">问题 {i}: {question}</div>
        <div class="answers">
            <div class="answer-box ragflow">
                <h4>RAGFlow <span class="score {score_class}">({ragflow_score:.1f}/5.0)</span></h4>
                <div>{ragflow_answer[:500]}{'...' if len(ragflow_answer) > 500 else ''}</div>
            </div>
            <div class="answer-box feishu">
                <h4>飞书 Knowledge AI</h4>
                <div>{feishu_answer[:500]}{'...' if len(feishu_answer) > 500 else ''}</div>
            </div>
        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="飞书Knowledge AI对比测试")
    parser.add_argument("--questions", type=str, default="test_output/questions.json",
                        help="问题文件路径")
    parser.add_argument("--max", type=int, default=10,
                        help="最大测试问题数（建议先少量测试）")
    parser.add_argument("--output", type=str, default="test_output",
                        help="输出目录")
    
    args = parser.parse_args()
    
    tester = FeishuKnowledgeAITester(args.questions, args.output)
    await tester.run_test(max_questions=args.max)


if __name__ == "__main__":
    asyncio.run(main())

