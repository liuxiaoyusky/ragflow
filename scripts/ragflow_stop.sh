#!/bin/bash
#
# RagFlow 停止脚本
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$(cd "$SCRIPT_DIR/../docker" && pwd)"
cd "$DOCKER_DIR"

echo "→ 停止 RagFlow..."
docker compose --profile gpu --profile elasticsearch down

echo
echo "✓ 已停止"

