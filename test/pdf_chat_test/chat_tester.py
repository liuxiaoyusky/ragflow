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
import json
import logging
import os
import time
import urllib3
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

from config import TestConfig

# 禁用SSL警告（用于内部测试环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatTester:
    """执行Chat API测试"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.headers = config.get_headers()
        self.base_url = config.get_base_url()
        self.session_id: Optional[str] = None
    
    def create_session(self) -> str:
        """创建测试session"""
        logger.info(f"Creating session for chat {self.config.chat_id}")
        
        url = f"{self.base_url}/chats/{self.config.chat_id}/sessions"
        payload = {"name": f"Test Session {int(time.time())}"}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30, verify=False)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                raise Exception(f"API error: {data.get('message', 'Unknown error')}")
            
            self.session_id = data.get("data", {}).get("id")
            if not self.session_id:
                raise Exception("Session ID not found in response")
            
            logger.info(f"Session created: {self.session_id}")
            return self.session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def ask_question(self, question: str, stream: bool = False) -> Dict[str, Any]:
        """向Chat API提问"""
        if not self.session_id:
            self.create_session()
        
        url = f"{self.base_url}/chats/{self.config.chat_id}/completions"
        payload = {
            "question": question,
            "session_id": self.session_id,
            "stream": stream
        }
        
        start_time = time.time()
        
        try:
            if stream:
                # 流式响应处理
                response = requests.post(
                    url, 
                    headers=self.headers, 
                    json=payload, 
                    stream=True,
                    timeout=120,
                    verify=False
                )
                response.raise_for_status()
                
                answer = ""
                reference = {}
                last_data = None
                
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    
                    line = line.strip()
                    if line.startswith("data:"):
                        content = line[5:].strip()
                        if content == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(content)
                            if data.get("code") == 0:
                                data_content = data.get("data", {})
                                if isinstance(data_content, bool):
                                    # 最后一个标记
                                    break
                                
                                answer = data_content.get("answer", answer)
                                if "reference" in data_content:
                                    reference = data_content.get("reference", {})
                                last_data = data_content
                        except json.JSONDecodeError:
                            continue
                
                elapsed_time = time.time() - start_time
                
                return {
                    "answer": answer,
                    "reference": reference,
                    "response_time": elapsed_time,
                    "success": True
                }
            else:
                # 非流式响应
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                    verify=False
                )
                response.raise_for_status()
                data = response.json()
                
                elapsed_time = time.time() - start_time
                
                if data.get("code") != 0:
                    return {
                        "answer": "",
                        "reference": {},
                        "response_time": elapsed_time,
                        "success": False,
                        "error": data.get("message", "Unknown error")
                    }
                
                data_content = data.get("data", {})
                return {
                    "answer": data_content.get("answer", ""),
                    "reference": data_content.get("reference", {}),
                    "response_time": elapsed_time,
                    "success": True
                }
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Error asking question: {e}")
            return {
                "answer": "",
                "reference": {},
                "response_time": elapsed_time,
                "success": False,
                "error": str(e)
            }
    
    def test_questions(self, questions: List[Dict[str, Any]], output_path: str = None) -> List[Dict[str, Any]]:
        """批量测试问题"""
        if output_path is None:
            output_path = os.path.join(self.config.output_dir, "test_results.json")
        
        # 检查是否有已存在的结果（支持断点续测）
        results = []
        start_index = 0
        
        if os.path.exists(output_path):
            logger.info(f"Found existing results file: {output_path}")
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    results = existing_data.get("results", [])
                    start_index = len(results)
                    logger.info(f"Resuming from question {start_index + 1}")
            except Exception as e:
                logger.warning(f"Could not load existing results: {e}")
        
        # 创建session
        if not self.session_id:
            self.create_session()
        
        # 测试每个问题
        total = len(questions)
        for i, q_data in enumerate(questions[start_index:], start=start_index + 1):
            question = q_data.get("question", "")
            logger.info(f"[{i}/{total}] Testing question: {question[:50]}...")
            
            result = self.ask_question(question, stream=False)
            
            test_result = {
                "question_id": i,
                "question": question,
                "answer": result.get("answer", ""),
                "reference": result.get("reference", {}),
                "response_time": result.get("response_time", 0),
                "success": result.get("success", False),
                "error": result.get("error"),
                "source_chunk_ids": q_data.get("source_chunk_ids", []),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            results.append(test_result)
            
            # 每10个问题保存一次（防止数据丢失）
            if i % 10 == 0:
                self._save_results(results, output_path, questions)
                logger.info(f"Progress saved: {i}/{total}")
            
            # 避免请求过快
            time.sleep(0.5)
        
        # 最终保存
        self._save_results(results, output_path, questions)
        logger.info(f"All {total} questions tested. Results saved to {output_path}")
        
        return results
    
    def _save_results(self, results: List[Dict[str, Any]], output_path: str, questions: List[Dict[str, Any]]):
        """保存测试结果"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "metadata": {
                "chat_id": self.config.chat_id,
                "session_id": self.session_id,
                "document_id": self.config.document_id,
                "total_questions": len(questions),
                "completed_tests": len(results),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "results": results
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

