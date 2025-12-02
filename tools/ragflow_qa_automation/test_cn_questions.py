#!/usr/bin/env python3
"""
用RAGFlow测试questions_list.csv中的中文问题，然后和飞书结果对比
"""
import csv
import json
import logging
import time
import sys
import urllib3
from pathlib import Path

import requests

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import TestConfig


class RAGFlowCNTester:
    """用RAGFlow测试中文问题"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.headers = config.get_headers()
        self.base_url = config.get_base_url()
        self.session_id = None
    
    def create_session(self) -> str:
        """创建新的会话"""
        url = f"{self.base_url}/chats/{self.config.chat_id}/sessions"
        payload = {"name": f"CN_Test_{time.strftime('%Y%m%d_%H%M%S')}"}
        
        response = requests.post(url, headers=self.headers, json=payload, verify=False)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"Failed to create session: {result}")
        
        self.session_id = result["data"]["id"]
        logger.info(f"Created session: {self.session_id}")
        return self.session_id
    
    def ask_question(self, question: str) -> dict:
        """向RAGFlow发送问题并获取回答"""
        url = f"{self.base_url}/chats/{self.config.chat_id}/completions"
        payload = {
            "question": question,
            "stream": False,
            "session_id": self.session_id
        }
        
        start_time = time.time()
        try:
            response = requests.post(url, headers=self.headers, json=payload, verify=False, timeout=120)
            response_time = time.time() - start_time
            
            result = response.json()
            
            if result.get("code") != 0:
                return {
                    "success": False,
                    "answer": "",
                    "error": result.get("message", "Unknown error"),
                    "response_time": response_time
                }
            
            data = result.get("data", {})
            answer = data.get("answer", "")
            reference = data.get("reference", {})
            
            return {
                "success": True,
                "answer": answer,
                "reference": reference,
                "response_time": response_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "answer": "",
                "error": str(e),
                "response_time": time.time() - start_time
            }
    
    def load_questions(self, csv_path: str) -> list:
        """从CSV加载问题"""
        questions = []
        # 使用utf-8-sig来自动处理BOM
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 处理可能的字段名变体
                index_key = next((k for k in row.keys() if '序号' in k or k.strip() == '序号'), None)
                question_key = next((k for k in row.keys() if '问题' in k or k.strip() == '问题'), None)
                
                if index_key and question_key:
                    questions.append({
                        "index": int(row[index_key]),
                        "question": row[question_key]
                    })
        return questions
    
    def run_test(self, csv_path: str, output_path: str, start_from: int = 1):
        """运行测试"""
        questions = self.load_questions(csv_path)
        logger.info(f"Loaded {len(questions)} questions from {csv_path}")
        
        # 创建会话
        self.create_session()
        
        results = []
        
        # 如果有已存在的结果，加载它们
        output_file = Path(output_path)
        if output_file.exists() and start_from > 1:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                results = existing_data.get("results", [])
                logger.info(f"Loaded {len(results)} existing results")
        
        for q in questions:
            idx = q["index"]
            
            # 跳过已完成的问题
            if idx < start_from:
                continue
            
            question_text = q["question"]
            logger.info(f"[{idx}/{len(questions)}] Testing: {question_text[:40]}...")
            
            result = self.ask_question(question_text)
            
            results.append({
                "index": idx,
                "question": question_text,
                "answer": result.get("answer", ""),
                "reference": result.get("reference", {}),
                "response_time": result.get("response_time", 0),
                "success": result.get("success", False),
                "error": result.get("error", "")
            })
            
            # 每5个问题保存一次
            if idx % 5 == 0:
                self._save_results(results, output_path)
                logger.info(f"Progress saved at Q{idx}")
            
            # 避免请求过快
            time.sleep(1)
        
        # 最终保存
        self._save_results(results, output_path)
        logger.info(f"✓ Test completed. Results saved to {output_path}")
        
        return results
    
    def _save_results(self, results: list, output_path: str):
        """保存结果"""
        output_data = {
            "metadata": {
                "chat_id": self.config.chat_id,
                "session_id": self.session_id,
                "total_questions": len(results),
                "tested_at": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "results": results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test RAGFlow with Chinese questions")
    parser.add_argument("--csv", type=str, default="test_output/questions_list.csv",
                        help="Path to questions CSV file")
    parser.add_argument("--output", type=str, default="test_output/ragflow_cn_results.json",
                        help="Output JSON file path")
    parser.add_argument("--start", type=int, default=1,
                        help="Start from question number (for resuming)")
    args = parser.parse_args()
    
    config = TestConfig()
    tester = RAGFlowCNTester(config)
    
    tester.run_test(args.csv, args.output, args.start)


if __name__ == "__main__":
    main()

