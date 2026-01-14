#!/bin/bash

# 进入 docker 目录，确保相对路径正确
cd "$(dirname "$0")/../docker" || exit 1

# 读取当前配置的 DOC_ENGINE
DOC_ENGINE=$(grep "^DOC_ENGINE=" .env.dev | cut -d'=' -f2)
DOC_ENGINE=${DOC_ENGINE:-elasticsearch}

echo "🚀 Starting RAGFlow DEV environment..."
echo "   - Project: ragflow-dev"
echo "   - DOC_ENGINE: $DOC_ENGINE"
echo "   - Ports: 10080 (Web), 15455 (MySQL)"
if [ "$DOC_ENGINE" = "infinity" ]; then
    echo "   - Infinity: 33817 (Thrift), 33820 (HTTP)"
else
    echo "   - Elasticsearch: 19200"
fi
echo "   - Config: .env.dev"

# 核心命令
# --env-file: 指定环境变量文件
# -p: 指定项目名（隔离关键）
# -f: 堆叠配置文件 (Base + Dev Patch)
docker compose --env-file .env.dev -p ragflow-dev -f docker-compose.yml -f docker-compose.dev.yml up -d

echo "✅ RAGFlow DEV is running at http://localhost:10080"
echo "   Using $DOC_ENGINE as document store"




