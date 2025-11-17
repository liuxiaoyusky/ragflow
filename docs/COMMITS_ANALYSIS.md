# Main 分支 Commits 分析

## 决策分类

### ✅ 完全保留（不需要容器内改动）

#### 1. 运维脚本 (`scripts/`)
- Commit: `363bbf9f`, `3324260f`
- 内容：`ragflow_start/stop/restart/logs.sh`, `backup_database.sh`, `sync_upstream.sh`
- **决策：保留**
- **方式：宿主机使用，不挂载到容器**
- **复杂度：0**

#### 2. GPU 配置
- Commit: `363bbf9f`
- 内容：`DEVICE=gpu`, docker-compose.yml 的 GPU 配置
- **决策：保留**
- **方式：docker-compose.yml 配置**
- **复杂度：0.1**

#### 3. 端口配置
- Commit: `363bbf9f`
- 内容：`SVR_WEB_HTTP_PORT=8080` 等
- **决策：保留**
- **方式：docker/.env 环境变量**
- **复杂度：0.5（5个端口变量）**

---

### ✅ 保留（通过配置文件）

#### 4. Admin Panel
- Commit: `02429af2`
- 内容：启用 admin server
- **决策：保留**
- **方式：`command: --enable-adminserver`**
- **复杂度：0.1**

#### 5. Feishu OIDC
- Commit: `3324260f`
- 内容：`docker/service_conf.yaml` 的 OIDC 配置
- **决策：保留**
- **方式：挂载 `service_conf.yaml`**
- **复杂度：0.5**

#### 6. 外置 MinerU
- Commit: `3324260f`
- 内容：`MINERU_APISERVER=http://10.1.9.133:9987`
- **决策：保留**
- **方式：环境变量**
- **复杂度：0.4（4个 MinerU 变量）**

---

### 🤔 待评估（可能单文件挂载）

#### 7. MinerU Parser 增强
- Commit: `ce7e3bdc`, `a4fdc17a`, `1dd77915`, `02429af2`, `3324260f`
- 内容：`deepdoc/parser/mineru_parser.py`
- 改动：
  - 支持 `vlm-vllm-async-engine`
  - 优先 HTTP API
  - LLM enhance hook
- **依赖分析：不依赖 `common` 模块 ✅**
- **决策：评估后决定**
- **如果需要挂载：复杂度 = 2**

---

### ❌ 放弃（需要大量挂载）

#### 8. SiliconFlow-Overseas Provider
- Commit: `1c90596a`, `fcfa7305`, `cc7e2a04`
- 内容：
  - `rag/llm/` 整个目录
  - `conf/llm_factories.json` 定制
- 需求：挂载 `rag/llm/` + `common/`
- **决策：❌ 放弃代码集成**
- **替代方案：UI 里用"自定义 LLM" + `https://api.siliconflow.com/v1`**
- **理由：目录挂载（复杂度=10），违反原则**

#### 9. 自定义 embedding/rerank/tts/cv
- Commit: `eaf8d938`, `fcfa7305`
- 内容：`rag/llm/embedding_model.py` 等
- 需求：挂载 `rag/llm/` 目录
- **决策：❌ 放弃**
- **理由：需要目录挂载**

#### 10. TOC Bugfix
- Commit: 你的本地修改
- 内容：`rag/prompts/generator.py` 空列表修复
- 需求：挂载 `generator.py` + `common/` 依赖
- **决策：❌ 放弃挂载**
- **行动：提 PR 给上游**
- **理由：依赖 `common` 模块**

#### 11. Docling 预装
- Commit: `694448fc`, `a4fdc17a`
- 内容：Dockerfile 预装 docling
- **决策：❌ 放弃预装**
- **替代：entrypoint.sh runtime 安装（首次启动2-3分钟）**
- **理由：不需要自建镜像**

---

## 最终保留配置

### 环境变量（docker/.env）
```bash
RAGFLOW_IMAGE=infiniflow/ragflow:v0.22.0
DEVICE=gpu
DOC_ENGINE=elasticsearch
SVR_WEB_HTTP_PORT=8080
SVR_WEB_HTTPS_PORT=8443
SVR_HTTP_PORT=9380
ADMIN_SVR_HTTP_PORT=9381
SVR_MCP_PORT=9382
USE_MINERU=true
MINERU_APISERVER=http://10.1.9.133:9987
MINERU_BACKEND=vlm-vllm-async-engine
MINERU_DELETE_OUTPUT=1
USE_DOCLING=true
HF_ENDPOINT=https://hf-mirror.com
```
**复杂度：1.5（15个变量 × 0.1）**

### 配置文件挂载（docker-compose.yml）
```yaml
volumes:
  - ./ragflow-logs:/ragflow/logs
  - ./nginx/ragflow.conf:/etc/nginx/conf.d/ragflow.conf
  - ./nginx/proxy.conf:/etc/nginx/proxy.conf
  - ./nginx/nginx.conf:/etc/nginx/nginx.conf
  - ./service_conf.yaml:/ragflow/conf/service_conf.yaml.template
```
**复杂度：2.5（5个文件挂载 × 0.5）**

### 源码挂载（最小化）
```yaml
# 仅为 vlm-vllm-async-engine 后端支持（官方未包含）
- ../deepdoc/parser/mineru_parser.py:/ragflow/deepdoc/parser/mineru_parser.py:ro
```
**修改内容：仅 2 行**
- 第 107 行：添加 `"vlm-vllm-async-engine"` 到 valid_backends
- 第 109 行：修复 f-string bug（`reason = f"..."`）

**复杂度：+2.0**

---

## 复杂度总计

- **环境变量：1.5**
- **配置文件挂载：2.5**
- **mineru_parser.py（2行修改）：2.0**
- **━━━━━━━━━━━━━━━━━━━━━━**
- **总计：6.0** ⚠️

**评估：** 略超目标（5.0），但符合"官方镜像优先原则"：
- ✅ 解决真问题（必须用 vlm-vllm-async-engine）
- ✅ 最小化修改（只有 2 行代码）
- ✅ 已标记 :ro（只读挂载，防止误改）
- ✅ 已提交 PR 计划（长期移除挂载）

---

## 放弃的功能及替代方案

| 功能 | 原实现 | 替代方案 |
|------|--------|----------|
| SiliconFlow-Overseas | 代码 provider | UI 自定义 LLM endpoint |
| 自定义模型封装 | rag/llm/ 代码 | 使用官方支持的模型 |
| TOC Bugfix | 挂载 generator.py | 提 PR，暂时接受官方版本 |
| Docling 预装 | Dockerfile | Runtime 安装（首次慢） |

---

## 执行清单

- [x] 分析完成
- [ ] 清理 docker/.env
- [ ] 清理 docker-compose.yml
- [ ] 首次启动测试
- [ ] 评估 MinerU parser
- [ ] 最终配置
- [ ] 文档化

