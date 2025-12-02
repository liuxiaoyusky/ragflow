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
from typing import List, Dict, Any

import requests
from openai import OpenAI

from config import TestConfig

# 禁用SSL警告（用于内部测试环境）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuestionGenerator:
    """从PDF chunks生成测试问题"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.headers = config.get_headers()
        self.base_url = config.get_base_url()
        
        # 初始化LLM客户端（用于生成问题）
        if config.eval_llm_api_key:
            self.llm_client = OpenAI(
                api_key=config.eval_llm_api_key,
                base_url=config.eval_llm_base_url
            )
        else:
            # 如果没有配置评估LLM，尝试使用RAGFlow的LLM
            logger.warning("EVAL_LLM_API_KEY not set, will use RAGFlow API for question generation")
            self.llm_client = None
    
    def fetch_all_chunks(self) -> List[Dict[str, Any]]:
        """获取文档的所有chunks"""
        logger.info(f"Fetching chunks for document {self.config.document_id}")
        
        all_chunks = []
        page = 1
        page_size = 100
        
        while True:
            url = f"{self.base_url}/datasets/{self.config.dataset_id}/documents/{self.config.document_id}/chunks"
            params = {"page": page, "page_size": page_size}
            
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30, verify=False)
                response.raise_for_status()
                data = response.json()
                
                if data.get("code") != 0:
                    raise Exception(f"API error: {data.get('message', 'Unknown error')}")
                
                chunks = data.get("data", {}).get("chunks", [])
                if not chunks:
                    break
                
                all_chunks.extend(chunks)
                logger.info(f"Fetched {len(chunks)} chunks (page {page}), total: {len(all_chunks)}")
                
                if len(chunks) < page_size:
                    break
                
                page += 1
                time.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"Error fetching chunks: {e}")
                raise
        
        logger.info(f"Total chunks fetched: {len(all_chunks)}")
        return all_chunks
    
    def generate_questions_from_chunks(self, chunks: List[Dict[str, Any]], target_count: int) -> List[Dict[str, Any]]:
        """从chunks生成问题 - 多轮生成以达到目标数量"""
        if not self.llm_client:
            raise ValueError("LLM client not initialized. Please set EVAL_LLM_API_KEY")
        
        questions = []
        batch_size = self.config.questions_per_batch
        
        # 问题类型列表，每轮使用不同类型以生成多样化问题
        question_types = ["nav_specific", "performance", "dividend", "fees", "holdings", "risk", "general"]
        
        round_num = 0
        max_rounds = 10  # 最多循环10轮
        
        while len(questions) < target_count and round_num < max_rounds:
            question_type = question_types[round_num % len(question_types)]
            logger.info(f"Round {round_num + 1}: Generating {question_type} questions...")
            
            # 将chunks分批处理
            for i in range(0, len(chunks), batch_size):
                if len(questions) >= target_count:
                    break
                    
                batch_chunks = chunks[i:i + batch_size]
                
                # 构建prompt - 使用更长的内容以获得更多细节
                chunk_texts = []
                for chunk in batch_chunks:
                    content = chunk.get("content", "")
                    if content:
                        # 增加内容长度以提供更多细节
                        chunk_texts.append(f"Chunk {chunk.get('id', 'unknown')}:\n{content[:1000]}")
                
                if not chunk_texts:
                    continue
                
                prompt = self._build_question_generation_prompt(
                    chunk_texts, 
                    min(20, target_count - len(questions)),
                    question_type
                )
                
                try:
                    # 调用LLM生成问题
                    response = self.llm_client.chat.completions.create(
                        model=self.config.eval_llm_model,
                        messages=[
                            {"role": "system", "content": "你是一位资深金融分析师。请生成自然语言的测试问题，用于测试RAG系统的检索能力。【重要】问题中不能包含答案或具体数值，让系统去检索和回答。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.8,  # 稍高温度以增加多样性
                        max_tokens=3000
                    )
                    
                    generated_text = response.choices[0].message.content
                    batch_questions = self._parse_questions(generated_text, batch_chunks)
                    
                    # 去重
                    existing_texts = {q["question"].lower().strip() for q in questions}
                    new_questions = [q for q in batch_questions if q["question"].lower().strip() not in existing_texts]
                    
                    questions.extend(new_questions)
                    
                    logger.info(f"Generated {len(new_questions)} new questions (type: {question_type}), total: {len(questions)}")
                    
                    time.sleep(1)  # 避免API限流
                    
                except Exception as e:
                    logger.error(f"Error generating questions: {e}")
                    continue
            
            round_num += 1
        
        logger.info(f"Question generation complete. Total: {len(questions)} questions")
        return questions[:target_count]
    
    def _build_question_generation_prompt(self, chunk_texts: List[str], remaining_count: int, question_type: str = "general") -> str:
        """构建问题生成prompt - 专注于金融报告(Factsheet)内容，使用自然语言提问"""
        chunks_text = "\n\n".join(chunk_texts)
        
        # 不同类型的问题模板 - 不包含具体数值
        question_templates = {
            "nav_specific": """Focus on NAV (Net Asset Value) questions:
- "Class A1 USD的当前资产净值是多少？"
- "Class A1 HKD2和Class A HKD Hedged Acc的NAV相差多少？"
- "哪个份额类别的NAV最高？"
- "该基金各个份额类别的NAV分别是多少？" """,
            
            "performance": """Focus on PERFORMANCE questions:
- "Class A1 USD在2017年的年度表现如何？"
- "该基金2018年的收益率是正还是负？"
- "请比较Class A1 USD在2017年和2018年的业绩差异"
- "该基金哪个月份表现最好？"
- "Year-to-Date的累计收益是多少？" """,
            
            "dividend": """Focus on DIVIDEND questions:
- "Class A2 USD MDis的每单位派息是多少？"
- "该基金的年化收益率是多少？"
- "最近一次除息日是什么时候？"
- "哪个份额类别的派息最高？" """,
            
            "fees": """Focus on FEE STRUCTURE questions:
- "该基金的管理费是多少？"
- "认购费和赎回费分别是多少？"
- "最低认购金额是多少？"
- "不同份额类别的费用结构有什么区别？" """,
            
            "holdings": """Focus on HOLDINGS and ALLOCATION questions:
- "该基金的前十大持仓是什么？"
- "金融板块的配置比例是多少？"
- "该基金主要投资于哪些行业？"
- "地理分布情况如何？" """,
            
            "risk": """Focus on RISK questions:
- "该基金的主要风险因素有哪些？"
- "该基金面临哪些市场风险？"
- "该基金是否使用衍生品？"
- "信用评级分布是怎样的？" """,
            
            "general": """Focus on GENERAL FUND INFORMATION:
- "该基金的成立日期是什么时候？"
- "基金的基础货币是什么？"
- "托管人是哪家机构？"
- "该基金有哪些份额类别可选？"
- "Class A1 USD的ISIN代码是什么？" """
        }
        
        type_hint = question_templates.get(question_type, question_templates["general"])
        
        return f"""你是一位资深金融分析师，正在对一只基金进行尽职调查。请根据以下文档内容，生成 {min(remaining_count, 20)} 个测试问题。

{type_hint}

【核心要求 - 必须遵守】

1. **禁止在问题中包含答案**：
   ❌ 错误示例："Class A1 USD在2017年的收益率（+32.9%）和2018年（-14.2%）相比如何？"
   ✅ 正确示例："Class A1 USD在2017年和2018年的年度收益率分别是多少？"
   
   ❌ 错误示例："NAV为104.55的Class A1 USD是否..."
   ✅ 正确示例："Class A1 USD的当前NAV是多少？"

2. **使用自然语言提问**：
   - 问题应该像真实用户提问一样自然
   - 可以使用中文或英文提问
   - 问题应该测试系统的检索能力，而不是确认已知信息

3. **问题类型多样化**：
   - 直接查询："XX的NAV是多少？"
   - 比较查询："哪个份额类别的费用最低？"
   - 计算查询："前五大持仓的总权重是多少？"
   - 趋势查询："该基金近期业绩有何变化？"

4. **禁止询问的内容**：
   - QR码、二维码、格式、布局
   - 图表的视觉效果
   - 任何不在金融数据中的内容

格式要求：每行一个问题，编号（1.、2.、3.、...）。只输出问题列表。

文档内容：
{chunks_text}

问题列表："""
    
    def _parse_questions(self, text: str, source_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解析LLM生成的问题文本，并过滤无效问题"""
        import re
        
        questions = []
        lines = text.strip().split("\n")
        
        # 需要过滤的关键词（不区分大小写）
        filter_keywords = [
            "qr code", "qr-code", "barcode", "scan",
            "chart format", "bar length", "visual", "layout",
            "page number", "document structure", "formatting",
            "here are", "following questions", "based on the",
            "test questions", "diverse questions"
        ]
        
        # 检测问题中是否包含答案数值的模式
        # 匹配：(+32.9%)、(-14.2%)、(104.55)、（32.9%）等
        answer_in_question_patterns = [
            r'\([+-]?\d+\.?\d*%?\)',        # (+32.9%) or (104.55)
            r'（[+-]?\d+\.?\d*%?）',          # 中文括号
            r'\s[+-]\d+\.?\d*%\s',           # +32.9% 或 -14.2%
            r'NAV\s*(of|is|为|是)\s*\d+',    # NAV is 104.55
            r'收益率[是为]?\s*[+-]?\d+',      # 收益率是32.9
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 移除编号（如 "1. ", "2. ", "1、" etc.）
            line = re.sub(r"^\d+[\.\)、]\s*", "", line)
            
            # 跳过太短的行
            if len(line) < 10:
                continue
            
            # 跳过不是问句的行
            question_indicators = ["what", "which", "how", "why", "when", "where", "who", 
                                   "compare", "是多少", "有哪些", "是什么", "如何", "怎样", 
                                   "哪个", "哪些", "请问", "能否"]
            is_question = line.endswith("?") or line.endswith("？") or \
                          any(w in line.lower() for w in question_indicators)
            if not is_question:
                continue
            
            # 过滤无效问题
            line_lower = line.lower()
            if any(kw in line_lower for kw in filter_keywords):
                logger.debug(f"Filtered (keyword): {line[:50]}...")
                continue
            
            # 过滤包含答案数值的问题
            has_answer = False
            for pattern in answer_in_question_patterns:
                if re.search(pattern, line):
                    logger.debug(f"Filtered (contains answer): {line[:50]}...")
                    has_answer = True
                    break
            if has_answer:
                continue
            
            questions.append({
                "question": line,
                "source_chunk_ids": [chunk.get("id") for chunk in source_chunks],
                "source_chunk_count": len(source_chunks)
            })
        
        return questions
    
    def filter_existing_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已有问题列表中的无效问题"""
        import re
        
        filter_keywords = [
            "qr code", "qr-code", "barcode", "scan",
            "chart format", "bar length", "visual", "layout",
            "page number", "document structure", "formatting",
            "here are", "following questions", "based on the",
            "test questions", "diverse questions"
        ]
        
        # 检测问题中是否包含答案数值的模式
        answer_in_question_patterns = [
            r'\([+-]?\d+\.?\d*%?\)',        # (+32.9%) or (104.55)
            r'（[+-]?\d+\.?\d*%?）',          # 中文括号
            r'\s[+-]\d+\.?\d*%\s',           # +32.9% 或 -14.2%
            r'NAV\s*(of|is|为|是)\s*\d+',    # NAV is 104.55
            r'收益率[是为]?\s*[+-]?\d+',      # 收益率是32.9
        ]
        
        valid_questions = []
        for q in questions:
            question_text = q.get("question", "")
            question_lower = question_text.lower()
            
            # 跳过太短的问题
            if len(question_text) < 10:
                continue
            
            # 过滤无效问题
            if any(kw in question_lower for kw in filter_keywords):
                continue
            
            # 过滤包含答案数值的问题
            has_answer = False
            for pattern in answer_in_question_patterns:
                if re.search(pattern, question_text):
                    logger.debug(f"Filtered existing (contains answer): {question_text[:50]}...")
                    has_answer = True
                    break
            if has_answer:
                continue
            
            valid_questions.append(q)
        
        logger.info(f"Filtered {len(questions) - len(valid_questions)} invalid questions, kept {len(valid_questions)}")
        return valid_questions
    
    def save_questions(self, questions: List[Dict[str, Any]], output_path: str):
        """保存问题到JSON文件"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "metadata": {
                "document_id": self.config.document_id,
                "dataset_id": self.config.dataset_id,
                "total_questions": len(questions),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "questions": questions
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(questions)} questions to {output_file}")
    
    def load_questions(self, input_path: str) -> List[Dict[str, Any]]:
        """从JSON文件加载问题"""
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("questions", [])
    
    def generate(self, output_path: str = None, append_to_existing: bool = False) -> List[Dict[str, Any]]:
        """主方法：生成问题
        
        Args:
            output_path: 输出文件路径
            append_to_existing: 是否在已有问题基础上补充
        """
        if output_path is None:
            output_path = os.path.join(self.config.output_dir, "questions.json")
        
        existing_questions = []
        
        # 检查是否已存在
        if os.path.exists(output_path):
            logger.info(f"Questions file already exists: {output_path}")
            existing_questions = self.load_questions(output_path)
            
            if append_to_existing:
                # 过滤已有问题中的无效问题
                existing_questions = self.filter_existing_questions(existing_questions)
                logger.info(f"Keeping {len(existing_questions)} valid existing questions")
                
                if len(existing_questions) >= self.config.num_questions:
                    logger.info(f"Already have {len(existing_questions)} questions, no need to generate more")
                    return existing_questions[:self.config.num_questions]
            else:
                # 非追加模式，询问是否加载
                try:
                    response = input("Load existing questions? (y/n): ")
                    if response.lower() == "y":
                        return existing_questions
                except EOFError:
                    # 非交互模式，直接返回已有问题
                    return existing_questions
        
        # 获取chunks
        chunks = self.fetch_all_chunks()
        if not chunks:
            raise ValueError("No chunks found for the document")
        
        # 计算需要生成的问题数量
        target_count = self.config.num_questions - len(existing_questions)
        logger.info(f"Need to generate {target_count} more questions")
        
        # 生成问题
        new_questions = self.generate_questions_from_chunks(chunks, target_count)
        
        # 合并问题
        all_questions = existing_questions + new_questions
        
        # 去重（基于问题文本）
        seen = set()
        unique_questions = []
        for q in all_questions:
            q_text = q.get("question", "").lower().strip()
            if q_text not in seen:
                seen.add(q_text)
                unique_questions.append(q)
        
        logger.info(f"Total unique questions: {len(unique_questions)}")
        
        # 保存
        self.save_questions(unique_questions[:self.config.num_questions], output_path)
        
        return unique_questions[:self.config.num_questions]

