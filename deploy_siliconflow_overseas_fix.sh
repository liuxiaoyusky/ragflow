#!/bin/bash

# SILICONFLOW-Overseas 配置修复部署脚本
# 功能：增量更新 Docker 容器中的 Python 类和配置文件

set -e  # 遇到错误立即退出

SCRIPT_DIR="/home/calvin/github/ragflow"
CONTAINER_NAME="ragflow-gpu"
COMPOSE_FILE="docker/docker-compose.yml"

echo "=========================================="
echo "SILICONFLOW-Overseas 配置修复部署"
echo "=========================================="
echo ""

# 1. 检查容器是否运行
echo "[1/5] 检查容器状态..."
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ 错误: 容器 $CONTAINER_NAME 未运行"
    echo "请先启动容器: docker compose -f $COMPOSE_FILE up -d $CONTAINER_NAME"
    exit 1
fi
echo "✓ 容器 $CONTAINER_NAME 正在运行"
echo ""

# 2. 备份容器中的现有文件
echo "[2/5] 备份容器中的现有文件..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
docker cp "$CONTAINER_NAME:/ragflow/rag/llm/rerank_model.py" "$BACKUP_DIR/" 2>/dev/null || echo "  - rerank_model.py 备份失败（可能不存在）"
docker cp "$CONTAINER_NAME:/ragflow/rag/llm/cv_model.py" "$BACKUP_DIR/" 2>/dev/null || echo "  - cv_model.py 备份失败（可能不存在）"
docker cp "$CONTAINER_NAME:/ragflow/rag/llm/tts_model.py" "$BACKUP_DIR/" 2>/dev/null || echo "  - tts_model.py 备份失败（可能不存在）"
docker cp "$CONTAINER_NAME:/ragflow/conf/llm_factories.json" "$BACKUP_DIR/" 2>/dev/null || echo "  - llm_factories.json 备份失败（可能不存在）"
echo "✓ 备份完成，保存在: $BACKUP_DIR"
echo ""

# 3. 复制修改后的 Python 文件到容器
echo "[3/5] 复制修改后的 Python 文件到容器..."
docker cp "$SCRIPT_DIR/rag/llm/rerank_model.py" "$CONTAINER_NAME:/ragflow/rag/llm/"
echo "  ✓ rerank_model.py (新增 SILICONFLOWOverseasRerank 类)"
docker cp "$SCRIPT_DIR/rag/llm/cv_model.py" "$CONTAINER_NAME:/ragflow/rag/llm/"
echo "  ✓ cv_model.py (新增 SILICONFLOWOverseasCV 类)"
docker cp "$SCRIPT_DIR/rag/llm/tts_model.py" "$CONTAINER_NAME:/ragflow/rag/llm/"
echo "  ✓ tts_model.py (新增 SILICONFLOWOverseasTTS 类)"
echo ""

# 4. 复制修改后的配置文件到容器
echo "[4/5] 复制修改后的配置文件到容器..."
docker cp "$SCRIPT_DIR/conf/llm_factories.json" "$CONTAINER_NAME:/ragflow/conf/"
echo "  ✓ llm_factories.json (已删除 Pro/BAAI/bge-m3 配置)"
echo ""

# 5. 重启服务使配置生效
echo "[5/5] 重启服务使配置生效..."
docker compose -f "$COMPOSE_FILE" restart "$CONTAINER_NAME"
echo "✓ 服务重启完成"
echo ""

# 等待服务启动
echo "等待服务启动（10 秒）..."
sleep 10
echo ""

echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "【修改内容总结】"
echo "1. 新增 SILICONFLOWOverseasRerank 类 (rag/llm/rerank_model.py)"
echo "2. 新增 SILICONFLOWOverseasCV 类 (rag/llm/cv_model.py)"
echo "3. 新增 SILICONFLOWOverseasTTS 类 (rag/llm/tts_model.py)"
echo "4. 删除 Pro/BAAI/bge-m3 配置 (conf/llm_factories.json)"
echo ""
echo "【下一步】"
echo "1. 查看日志确认无错误:"
echo "   docker compose -f $COMPOSE_FILE logs -f $CONTAINER_NAME"
echo ""
echo "2. 在 Web UI 测试:"
echo "   - 添加 Qwen/Qwen3-Embedding-8B 模型（应该正常）"
echo "   - 确认 Pro/BAAI/bge-m3 不再出现在列表中"
echo "   - 测试 Rerank 功能 (Pro/BAAI/bge-reranker-v2-m3)"
echo "   - 测试 Image2Text 功能 (Qwen2.5-VL / QVQ)"
echo ""
echo "【回滚方法】"
echo "如需回滚，执行以下命令:"
echo "  docker cp $BACKUP_DIR/rerank_model.py $CONTAINER_NAME:/ragflow/rag/llm/"
echo "  docker cp $BACKUP_DIR/cv_model.py $CONTAINER_NAME:/ragflow/rag/llm/"
echo "  docker cp $BACKUP_DIR/tts_model.py $CONTAINER_NAME:/ragflow/rag/llm/"
echo "  docker cp $BACKUP_DIR/llm_factories.json $CONTAINER_NAME:/ragflow/conf/"
echo "  docker compose -f $COMPOSE_FILE restart $CONTAINER_NAME"
echo ""

