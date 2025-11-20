#!/bin/bash
#
# RagFlow 状态检查脚本
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
cd "$DOCKER_DIR"

echo "=========================================="
echo "RagFlow 服务状态"
echo "=========================================="
echo
docker compose ps

echo
echo "=========================================="
echo "资源使用情况"
echo "=========================================="
CONTAINERS=$(docker compose ps -q 2>/dev/null | tr '\n' ' ')
if [ -n "$CONTAINERS" ]; then
  docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" $CONTAINERS
else
  echo "容器未运行"
fi

echo
echo "=========================================="
echo "端口监听"
echo "=========================================="
echo "  8080  - Web UI"
echo "  9380  - API"
echo "  9381  - Admin API"
echo "  9382  - MCP Server"

