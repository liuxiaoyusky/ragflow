#!/bin/bash
#
# RagFlow 一键重启脚本
# 使用 GPU + Elasticsearch 配置
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
cd "$DOCKER_DIR"

echo "=========================================="
echo "RagFlow 重启脚本"
echo "配置: GPU + Elasticsearch"
echo "=========================================="
echo

# 停止服务
echo "→ 停止现有服务..."
docker compose --profile gpu --profile elasticsearch down

echo
echo "→ 等待容器完全停止..."
sleep 2

# 启动服务
echo
echo "→ 启动服务..."
docker compose --profile gpu --profile elasticsearch up -d

echo
echo "→ 等待服务启动..."
sleep 3

# 显示状态
echo
echo "=========================================="
echo "服务状态:"
echo "=========================================="
docker compose ps

echo
echo "=========================================="
echo "✓ 重启完成！"
echo "=========================================="
echo
echo "访问地址:"
echo "  - Web UI:     http://localhost:8080"
echo "  - API:        http://localhost:9380"
echo "  - Admin:      http://localhost:9381"
echo "  - MCP:        http://localhost:9382"
echo
echo "查看日志: docker compose logs -f ragflow-gpu"
echo

