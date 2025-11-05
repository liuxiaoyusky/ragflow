#!/bin/bash
#
# RagFlow 启动脚本
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
cd "$DOCKER_DIR"

echo "→ 启动 RagFlow (GPU + Elasticsearch)..."
docker compose --profile gpu --profile elasticsearch up -d

echo
echo "✓ 启动完成！"
echo
echo "访问地址: http://localhost:8080"

