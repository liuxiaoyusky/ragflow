#!/bin/bash

cd "$(dirname "$0")/../docker" || exit 1

echo "🛑 Stopping RAGFlow DEV environment..."

# 只需要指定 project name 和 env file 即可找到对应的容器
docker compose --env-file .env.dev -p ragflow-dev -f docker-compose.yml -f docker-compose.dev.yml down

echo "👋 RAGFlow DEV stopped."

