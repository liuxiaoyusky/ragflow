<!-- 39a72871-d807-4feb-b3a2-96feaea9ce60 7079d50c-b744-4049-a0d2-84d0124e3d68 -->
# 修复 SILICONFLOW-Overseas 服务配置

## 问题分析

### 已确认的问题

1. **Pro/BAAI/bge-m3 模型多余**

   - 错误现象：添加 `Pro/BAAI/bge-m3` 时报错 "Model does not exist (code 20012)"
   - **根本原因**：海外版不支持这个特定的 BAAI embedding 模型
   - **解决方案**：删除 `Pro/BAAI/bge-m3` 配置
   - **重要**：Qwen 的 embedding 模型（Qwen3-Embedding-8B/4B/0.6B）是正常可用的，保持不变

2. **Rerank 缺失代码实现**

   - 配置文件中有 `Pro/BAAI/bge-reranker-v2-m3` 模型
   - 但缺少 `SILICONFLOWOverseasRerank` Python 类

3. **Image2Text 缺失代码实现**

   - 配置文件中有 Qwen2.5-VL、QVQ 模型
   - 但缺少 `SILICONFLOWOverseasCV` Python 类

4. **TTS 未配置**

   - 需要添加完整的 TTS 支持（代码类 + 配置）

5. **模型列表过于庞大**

   - 需要精简，只保留指定厂商的模型

### 保留的模型厂商范围

- **MiniMaxAI**: MiniMax-M2 系列
- **DeepSeek**: DeepSeek-V3.1, DeepSeek-R1, DeepSeek-R1-Distill 系列
- **Qwen**: Qwen3 系列（Chat + Embedding），Qwen2.5-VL, QVQ
- **OpenAI**: GPT 系列（如果海外版支持）
- **Kimi**: Kimi 系列（如果海外版支持）
- **BAAI**: bge-reranker 系列（仅 rerank）

## 实施步骤

### 步骤 1：添加缺失的 Python 类实现

#### 1.1 Rerank 支持

**文件**: `rag/llm/rerank_model.py`

**位置**: 在 `SILICONFLOWRerank` 类后添加（约 line 303）

```python
class SILICONFLOWOverseasRerank(SILICONFLOWRerank):
    _FACTORY_NAME = "SILICONFLOW-Overseas"

    def __init__(self, key, model_name, base_url="https://api.siliconflow.com/v1/rerank"):
        if not base_url:
            base_url = "https://api.siliconflow.com/v1/rerank"
        super().__init__(key, model_name, base_url)
```

#### 1.2 Image2Text 支持

**文件**: `rag/llm/cv_model.py`

**位置**: 在 `SILICONFLOWCV` 类后添加（约 line 392）

```python
class SILICONFLOWOverseasCV(SILICONFLOWCV):
    _FACTORY_NAME = "SILICONFLOW-Overseas"

    def __init__(self, key, model_name, lang="Chinese", base_url="https://api.siliconflow.com/v1", **kwargs):
        if not base_url:
            base_url = "https://api.siliconflow.com/v1"
        super().__init__(key, model_name, lang, base_url, **kwargs)
```

#### 1.3 TTS 支持

**文件**: `rag/llm/tts_model.py`

**位置**: 在 `SILICONFLOWTTS` 类后添加（约 line 389）

```python
class SILICONFLOWOverseasTTS(SILICONFLOWTTS):
    _FACTORY_NAME = "SILICONFLOW-Overseas"

    def __init__(self, key, model_name="FunAudioLLM/CosyVoice2-0.5B", base_url="https://api.siliconflow.com/v1"):
        if not base_url:
            base_url = "https://api.siliconflow.com/v1"
        super().__init__(key, model_name, base_url)
```

### 步骤 2：修正配置文件

**文件**: `conf/llm_factories.json`

**目标配置块**: SILICONFLOW-Overseas (约 line 5167-5278)

#### 2.1 删除 Pro/BAAI/bge-m3（仅此一个）

找到并删除以下配置项：

```json
{
    "llm_name": "Pro/BAAI/bge-m3",
    "tags": "LLM,EMBEDDING,8k",
    "max_tokens": 8192,
    "model_type": "embedding",
    "is_tools": false
}
```

#### 2.2 保留 Qwen Embedding 模型（这些是正常的）

**不要删除**以下配置，它们是可用的：

- `Qwen/Qwen3-Embedding-8B`
- `Qwen/Qwen3-Embedding-4B`
- `Qwen/Qwen3-Embedding-0.6B`

#### 2.3 保留和精简模型列表

只保留以下厂商的模型：

**Chat 模型**:

- DeepSeek: DeepSeek-V3.1, DeepSeek-R1, DeepSeek-R1-Distill-Qwen-32B/14B/7B
- Qwen: Qwen3-32B, Qwen3-14B, Qwen3-8B
- MiniMax: MiniMax-M2 系列（需从官方文档确认可用性）
- OpenAI: GPT 系列（需从官方文档确认可用性）
- Kimi: Kimi 系列（需从官方文档确认可用性）

**Embedding 模型**:

- Qwen/Qwen3-Embedding-8B ✅ 保留
- Qwen/Qwen3-Embedding-4B ✅ 保留
- Qwen/Qwen3-Embedding-0.6B ✅ 保留
- ~~Pro/BAAI/bge-m3~~ ❌ 删除

**Rerank 模型**:

- `Pro/BAAI/bge-reranker-v2-m3` ✅ 保留

**Image2Text 模型**:

- Qwen/Qwen2.5-VL-72B-Instruct ✅ 保留
- Qwen/QVQ-72B-Preview ✅ 保留

**TTS 模型** (需添加):

- FunAudioLLM/CosyVoice2-0.5B（如果海外版支持）

删除不在上述列表中的其他厂商模型。

### 步骤 3：部署前测试验证

#### 3.1 验证 Qwen Embedding（应该可用）

```bash
curl -X POST https://api.siliconflow.com/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-8B",
    "input": ["test text"]
  }'
```

预期：返回 embedding 向量

#### 3.2 验证 Rerank API

```bash
curl -X POST https://api.siliconflow.com/v1/rerank \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Pro/BAAI/bge-reranker-v2-m3",
    "query": "test query",
    "documents": ["doc1", "doc2"]
  }'
```

#### 3.3 验证 JSON 格式

```bash
python3 -m json.tool conf/llm_factories.json > /dev/null && echo "✓ JSON 格式正确"
```

### 步骤 4：增量更新 Docker 容器

```bash
cd /home/calvin/github/ragflow

# 1. 复制修改后的 Python 文件
docker cp rag/llm/rerank_model.py ragflow-gpu:/ragflow/rag/llm/
docker cp rag/llm/cv_model.py ragflow-gpu:/ragflow/rag/llm/
docker cp rag/llm/tts_model.py ragflow-gpu:/ragflow/rag/llm/

# 2. 复制修改后的配置文件
docker cp conf/llm_factories.json ragflow-gpu:/ragflow/conf/

# 3. 重启服务生效
docker compose -f docker/docker-compose.yml restart ragflow-gpu

# 4. 查看日志确认无错误
docker compose -f docker/docker-compose.yml logs -f ragflow-gpu
```

### 步骤 5：部署后功能测试

#### 5.1 测试 Qwen Embedding（应该正常）

1. 在 Web UI 添加 `Qwen/Qwen3-Embedding-8B` 或 `Qwen/Qwen3-Embedding-4B`
2. 创建知识库，上传文档
3. 验证文档能正常解析和向量化（不再出现 error 20012）
4. 确认 `Pro/BAAI/bge-m3` 不再出现在可选列表中

#### 5.2 测试 Rerank 功能

1. 在 Web UI 添加 `Pro/BAAI/bge-reranker-v2-m3` rerank 模型
2. 创建知识库，配置使用该 rerank 模型
3. 执行搜索查询，验证结果能正常排序

#### 5.3 测试 Image2Text 功能

1. 添加 Qwen2.5-VL 或 QVQ 模型
2. 上传包含图片的 PDF 文档
3. 验证图片能正常识别和提取内容

#### 5.4 测试 TTS 功能

1. 添加 TTS 模型（如果海外版支持）
2. 测试问答结果的语音合成功能

### 步骤 6：测试报告

```
【SILICONFLOW-Overseas 配置修复测试报告】
测试时间: YYYY-MM-DD HH:MM
测试环境: Docker ragflow-gpu

✅ Qwen Embedding (Qwen3-Embedding-8B/4B/0.6B)
  模型添加: [成功/失败]
  文档向量化: [成功/失败]
  错误: error 20012 不再出现 ✓

❌ BAAI Embedding (Pro/BAAI/bge-m3)
  状态: 已删除
  验证: Web UI 中不再显示此选项 ✓

✅ Rerank (Pro/BAAI/bge-reranker-v2-m3)
  模型添加: [成功/失败]
  检索排序: [成功/失败]

✅ Image2Text (Qwen2.5-VL / QVQ)
  模型添加: [成功/失败]
  图片识别: [成功/失败]

✅ TTS (FunAudioLLM)
  模型添加: [成功/失败 / 海外版不支持]
  语音生成: [成功/失败 / N/A]

📋 模型精简统计
  保留厂商: MiniMax, DeepSeek, Qwen, OpenAI, Kimi, BAAI
  删除的多余配置: Pro/BAAI/bge-m3
  保留的 Embedding: Qwen3-Embedding 系列
```

## 关键修正说明

**重要澄清**：

- ❌ **错误理解**：海外版不支持所有 embedding
- ✅ **正确理解**：海外版支持 Qwen 的 embedding，但不支持 `Pro/BAAI/bge-m3`
- 🎯 **解决方案**：只删除 `Pro/BAAI/bge-m3` 这一个配置项，其他 Qwen embedding 保持不变

## Linus 视角的设计原则

1. **精确定位问题**：问题不是"所有 embedding 不支持"，而是"特定的 BAAI 模型不支持"。精确定位，精确删除。
2. **最小修改原则**：只删除有问题的 1 个配置项，不动其他正常工作的 3 个 Qwen embedding 配置。
3. **消除特殊情况**：所有 Overseas 类通过继承实现，零重复代码。
4. **测试驱动**：部署前测试 Qwen embedding API，确认可用性。部署后验证 error 20012 不再出现。

### To-dos

- [ ] 在 rag/llm/rerank_model.py 添加 SILICONFLOWOverseasRerank 类
- [ ] 在 rag/llm/cv_model.py 添加 SILICONFLOWOverseasCV 类
- [ ] 在 rag/llm/tts_model.py 添加 SILICONFLOWOverseasTTS 类
- [ ] 精简模型列表，只保留 MiniMax、DeepSeek、Qwen、OpenAI、Kimi、BAAI 厂商
- [ ] 使用 docker cp 增量更新容器文件并重启服务