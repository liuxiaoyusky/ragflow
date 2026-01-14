#!/bin/bash

cd "$(dirname "$0")/../docker" || exit 1

# 默认查看 ragflow-gpu (或 cpu) 的日志，加 -f 实时跟踪
docker compose --env-file .env.dev -p ragflow-dev -f docker-compose.yml -f docker-compose.dev.yml logs -f ragflow-gpu




