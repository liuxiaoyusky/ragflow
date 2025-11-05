#!/bin/bash
#
# RagFlow 日志查看脚本
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
cd "$DOCKER_DIR"

# 默认跟踪 ragflow-gpu 日志，可通过参数指定其他服务
SERVICE=${1:-ragflow-gpu}

echo "→ 查看 $SERVICE 日志 (Ctrl+C 退出)..."
echo
docker compose logs -f "$SERVICE"

