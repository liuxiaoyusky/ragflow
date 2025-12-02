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
import time
from typing import Dict, Any, List

from openai import OpenAI

from config import TestConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Evaluator:
    """使用LLM评估Chat回复质量"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        
        # 初始化LLM客户端
        if config.eval_llm_api_key:
            self.llm_client = OpenAI(
                api_key=config.eval_llm_api_key,
                base_url=config.eval_llm_base_url
            )
        else:
            raise ValueError("EVAL_LLM_API_KEY is required for evaluation")
    
    def evaluate_response(self, question: str, answer: str, reference: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个回复"""
        prompt = self._build_evaluation_prompt(question, answer, reference)
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.eval_llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert evaluator for RAG (Retrieval-Augmented Generation) systems. Evaluate the quality of answers based on accuracy, relevance, completeness, and citation quality."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # 低温度确保评估一致性
                max_tokens=500
            )
            
            evaluation_text = response.choices[0].message.content
            scores = self._parse_evaluation(evaluation_text)
            
            return {
                "accuracy": scores.get("accuracy", 0),
                "relevance": scores.get("relevance", 0),
                "completeness": scores.get("completeness", 0),
                "citation_quality": scores.get("citation_quality", 0),
                "overall_score": scores.get("overall", 0),
                "evaluation_text": evaluation_text,
                "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"Error evaluating response: {e}")
            return {
                "accuracy": 0,
                "relevance": 0,
                "completeness": 0,
                "citation_quality": 0,
                "overall_score": 0,
                "evaluation_text": f"Evaluation error: {str(e)}",
                "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
    
    def _build_evaluation_prompt(self, question: str, answer: str, reference: Dict[str, Any]) -> str:
        """构建评估prompt"""
        chunks_info = ""
        if reference and "chunks" in reference:
            chunks = reference.get("chunks", [])
            chunks_info = f"\n\nReferenced Chunks ({len(chunks)}):\n"
            for i, chunk in enumerate(chunks[:5], 1):  # 只显示前5个chunks
                chunk_content = chunk.get("content_with_weight", chunk.get("content", ""))[:200]
                chunks_info += f"{i}. {chunk_content}...\n"
        
        return f"""Evaluate the following RAG system response on a scale of 1-5 for each dimension:

Question: {question}

Answer: {answer}
{chunks_info}

Evaluation Criteria:
1. **Accuracy (1-5)**: Is the answer factually correct based on the referenced chunks? Does it match the source material?
2. **Relevance (1-5)**: Does the answer directly address the question? Is it on-topic?
3. **Completeness (1-5)**: Does the answer cover all aspects of the question? Is information missing?
4. **Citation Quality (1-5)**: Are the referenced chunks relevant to the question? Do they support the answer?

Provide your evaluation in the following JSON format:
{{
    "accuracy": <score>,
    "relevance": <score>,
    "completeness": <score>,
    "citation_quality": <score>,
    "overall": <average_score>,
    "comments": "<brief explanation>"
}}"""
    
    def _parse_evaluation(self, text: str) -> Dict[str, int]:
        """解析评估结果"""
        scores = {
            "accuracy": 0,
            "relevance": 0,
            "completeness": 0,
            "citation_quality": 0,
            "overall": 0
        }
        
        # 尝试提取JSON
        import re
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                scores.update({
                    "accuracy": int(parsed.get("accuracy", 0)),
                    "relevance": int(parsed.get("relevance", 0)),
                    "completeness": int(parsed.get("completeness", 0)),
                    "citation_quality": int(parsed.get("citation_quality", 0)),
                    "overall": float(parsed.get("overall", 0))
                })
            except json.JSONDecodeError:
                # 如果JSON解析失败，尝试正则提取数字
                scores = self._extract_scores_regex(text)
        else:
            scores = self._extract_scores_regex(text)
        
        # 计算平均分
        if scores["overall"] == 0:
            values = [scores["accuracy"], scores["relevance"], scores["completeness"], scores["citation_quality"]]
            scores["overall"] = sum(values) / len(values) if values else 0
        
        return scores
    
    def _extract_scores_regex(self, text: str) -> Dict[str, float]:
        """使用正则表达式提取分数"""
        import re
        scores = {
            "accuracy": 0,
            "relevance": 0,
            "completeness": 0,
            "citation_quality": 0,
            "overall": 0
        }
        
        patterns = {
            "accuracy": r'accuracy["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',
            "relevance": r'relevance["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',
            "completeness": r'completeness["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',
            "citation_quality": r'citation["\s_]*quality["\']?\s*[:=]\s*(\d+(?:\.\d+)?)',
            "overall": r'overall["\']?\s*[:=]\s*(\d+(?:\.\d+)?)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    scores[key] = float(match.group(1))
                except ValueError:
                    pass
        
        return scores
    
    def evaluate_all(self, test_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """评估所有测试结果"""
        evaluated_results = []
        total = len(test_results)
        
        for i, result in enumerate(test_results, 1):
            if not result.get("success"):
                # 失败的请求直接标记为0分
                evaluation = {
                    "accuracy": 0,
                    "relevance": 0,
                    "completeness": 0,
                    "citation_quality": 0,
                    "overall_score": 0,
                    "evaluation_text": "Request failed",
                    "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                logger.info(f"[{i}/{total}] Evaluating response...")
                evaluation = self.evaluate_response(
                    result.get("question", ""),
                    result.get("answer", ""),
                    result.get("reference", {})
                )
                time.sleep(0.5)  # 避免API限流
            
            result["evaluation"] = evaluation
            evaluated_results.append(result)
        
        return evaluated_results

