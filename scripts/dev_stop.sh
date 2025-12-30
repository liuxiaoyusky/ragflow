#!/bin/bash

cd "$(dirname "$0")/../docker" || exit 1

echo "🛑 Stopping RAGFlow DEV environment..."

# 停止并删除所有 dev 容器（包括 volumes 选项可选）
docker compose --env-file .env.dev -p ragflow-dev -f docker-compose.yml -f docker-compose.dev.yml down

# 清理可能残留的容器（兼容 ES/Infinity 切换场景）
echo "🧹 Cleaning up orphan containers..."
docker rm -f ragflow-dev-infinity ragflow-dev-es01 ragflow-dev-opensearch01 2>/dev/null || true

echo "👋 RAGFlow DEV stopped."




