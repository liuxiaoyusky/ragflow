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
import os
from typing import Optional


class TestConfig:
    """测试配置类，支持环境变量覆盖"""
    
    def __init__(self):
        # RAGFlow API配置
        self.host_address: str = os.getenv("RAGFLOW_HOST", "https://10.1.9.133:8443")
        self.api_key: str = os.getenv("RAGFLOW_API_KEY", "ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw")
        self.api_version: str = os.getenv("RAGFLOW_API_VERSION", "v1")
        
        # Chat和Document配置
        self.chat_id: str = os.getenv("RAGFLOW_CHAT_ID", "f472490cbabe11f0b1a00242ac130006")
        self.dataset_id: str = os.getenv("RAGFLOW_DATASET_ID", "92b074cccb6311f0a80a0242ac130006")
        self.document_id: str = os.getenv("RAGFLOW_DOCUMENT_ID", "fef92d40cb6311f09cf40242ac130006")
        
        # 测试配置
        self.num_questions: int = int(os.getenv("NUM_QUESTIONS", "100"))
        self.questions_per_batch: int = int(os.getenv("QUESTIONS_PER_BATCH", "15"))
        self.output_dir: str = os.getenv("TEST_OUTPUT_DIR", "./test_output")
        
        # LLM评估配置（用于问题生成和评估）
        self.eval_llm_provider: str = os.getenv("EVAL_LLM_PROVIDER", "siliconflow")
        self.eval_llm_model: str = os.getenv("EVAL_LLM_MODEL", "Pro/deepseek-ai/DeepSeek-V3")
        self.eval_llm_api_key: Optional[str] = os.getenv("EVAL_LLM_API_KEY", "sk-wsjkejkoczyjjiqdcintnmbtrqdqjqalcoiugpsudycywgny")
        self.eval_llm_base_url: Optional[str] = os.getenv("EVAL_LLM_BASE_URL", "https://api.siliconflow.cn/v1")
        
        # 验证必需配置
        self._validate()
    
    def _validate(self):
        """验证必需配置项"""
        if not self.api_key:
            raise ValueError("RAGFLOW_API_KEY environment variable is required")
        if not self.chat_id:
            raise ValueError("RAGFLOW_CHAT_ID environment variable is required")
        if not self.dataset_id:
            raise ValueError("RAGFLOW_DATASET_ID environment variable is required")
    
    def get_headers(self):
        """返回HTTP请求头，包含Bearer token认证"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_base_url(self):
        """返回API基础URL"""
        return f"{self.host_address}/api/{self.api_version}"
    
    @classmethod
    def from_url(cls, url: str):
        """从chunks URL中提取信息（辅助方法）"""
        # URL格式: https://10.1.9.133:8443/chunk/parsed/chunks?id=xxx&doc_id=yyy
        import re
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        config = cls()
        config.host_address = f"{parsed.scheme}://{parsed.netloc}"
        config.document_id = params.get("doc_id", [config.document_id])[0]
        
        return config

