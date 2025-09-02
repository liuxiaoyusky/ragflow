# RAGFlow Docker 快速启动指南

## 🚀 启动路径


### GPU启动
```bash
docker compose -f docker-compose-gpu.yml up -d
```

## 📋 核心参数

### 端口配置
- **API端口**: `${SVR_HTTP_PORT}:9380` (默认: 9380)
- **Web界面**: `8080:80` (HTTP), `8443:443` (HTTPS)
- **Elasticsearch**: `${ES_PORT}:9200` (默认: 1200)
- **MySQL**: `${MYSQL_PORT}:3306` (默认: 5455)
- **MinIO**: `${MINIO_PORT}:9000` (默认: 9000)
- **Redis**: `${REDIS_PORT}:6379` (默认: 6379)

### 镜像选择
```bash
# 轻量版 (无嵌入模型) (当前)
RAGFLOW_IMAGE=infiniflow/ragflow:v0.20.4-slim

# 完整版 (包含嵌入模型)
RAGFLOW_IMAGE=infiniflow/ragflow:v0.20.4
```

### 文档引擎
```bash
# Elasticsearch (默认)(当前)
DOC_ENGINE=elasticsearch

# Infinity
DOC_ENGINE=infinity

# OpenSearch
DOC_ENGINE=opensearch
```

## ⚙️ 个性化设置

### GPU配置 (仅GPU版本)
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all          # 使用所有GPU
          capabilities: [gpu]
```

### 内存限制
```bash
MEM_LIMIT=8073741824  # 8GB
```

### 时区设置
```bash
TIMEZONE=Asia/Shanghai
```

### 文件大小限制
```bash
MAX_CONTENT_LENGTH=134217728  # 128MB
```

### 批处理大小
```bash
DOC_BULK_SIZE=4              # 文档批处理大小
EMBEDDING_BATCH_SIZE=16      # 嵌入批处理大小
```

### HuggingFace镜像 (中国用户)
```bash
HF_ENDPOINT=https://hf-mirror.com
```

### 中国镜像源
```bash
# 华为云镜像
RAGFLOW_IMAGE=swr.cn-north-4.myhuaweicloud.com/infiniflow/ragflow:v0.20.4

# 阿里云镜像
RAGFLOW_IMAGE=registry.cn-hangzhou.aliyuncs.com/infiniflow/ragflow:v0.20.4
```

## 🔧 快速配置

### 1. 复制环境文件
```bash
cp .env.example .env
```

### 2. 编辑配置
```bash
vim .env
```

### 3. 启动服务
```bash
# 选择对应的启动文件
docker compose -f docker-compose-gpu.yml up -d
```

### 4. 检查状态
```bash
docker compose -f docker-compose-gpu.yml ps
```

## 📝 常用命令

```bash
# 查看日志
docker logs ragflow-server

# 停止服务
docker compose -f docker-compose-gpu.yml down

# 重启服务
docker compose -f docker-compose-gpu.yml restart

# 更新镜像
docker compose -f docker-compose-gpu.yml pull
```
