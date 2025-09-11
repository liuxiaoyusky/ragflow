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

## 💾 数据备份与恢复

### 数据卷配置
RAGFlow使用以下数据卷存储持久化数据：
- `soft_ragflow_mysql_data`: MySQL数据库 (用户、知识库、对话等)
- `soft_ragflow_minio_data`: MinIO对象存储 (上传的文件)
- `soft_ragflow_redis_data`: Redis缓存数据
- `soft_ragflow_esdata01`: Elasticsearch索引数据

### 🔧 预防措施配置

#### 1. 固定项目名称
在 `.env` 文件中添加：
```bash
COMPOSE_PROJECT_NAME=ragflow
```
这确保无论在哪个目录运行，都使用相同的数据卷名称。

#### 2. 外部数据卷配置
在 `docker-compose-base.yml` 中配置：
```yaml
volumes:
  mysql_data:
    external: true
    name: soft_ragflow_mysql_data
  minio_data:
    external: true
    name: soft_ragflow_minio_data
  # ... 其他数据卷
```

### 📦 备份操作

#### 自动备份脚本
```bash
# 创建带时间戳的备份
../backup_script.sh

# 创建自定义名称的备份
../backup_script.sh my_backup_name
```

#### 官方迁移工具
```bash
# 停止服务
docker compose -f docker-compose-gpu.yml down

# 创建备份
bash migration.sh backup backup_folder_name

# 重新启动服务
docker compose -f docker-compose-gpu.yml up -d
```

### 🔄 恢复操作

#### 从备份恢复数据
```bash
# 停止当前服务
docker compose -f docker-compose-gpu.yml down

# 从备份恢复数据
bash migration.sh restore backup_folder_name

# 重新启动服务
docker compose -f docker-compose-gpu.yml up -d
```

### 🔍 数据卷管理

```bash
# 查看所有RAGFlow相关数据卷
docker volume ls | grep ragflow

# 查看特定数据卷详情
docker inspect volume_name

# 检查容器挂载的数据卷
docker inspect ragflow-mysql | grep -A 10 "Mounts"
```

### ⚠️ 注意事项

1. **备份前必须停止服务**：避免数据不一致
2. **恢复会覆盖现有数据**：请确保备份数据的正确性
3. **定期备份**：建议每周或重要操作前进行备份
4. **测试恢复流程**：定期验证备份的完整性

### 🚨 故障排除

#### 数据卷不存在错误
```bash
# 检查数据卷是否存在
docker volume ls | grep ragflow

# 如果不存在，从备份恢复
bash migration.sh restore backup_folder_name
```

#### 容器无法启动
```bash
# 查看容器挂载信息
docker inspect container_name | grep -A 10 "Mounts"

# 检查数据卷权限 (需要sudo)
sudo ls -la /var/lib/docker/volumes/volume_name/_data
```
