#!/bin/bash

# RAGFlow 自动备份脚本
# RAGFlow Automatic Backup Script
# 
# 使用方法 Usage:
#   bash backup_script.sh              # 创建带时间戳的备份
#   bash backup_script.sh my_backup    # 创建自定义名称的备份

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAGFLOW_DIR="$SCRIPT_DIR"

# 默认备份文件夹名称（带时间戳）
DEFAULT_BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="${1:-$DEFAULT_BACKUP_NAME}"

echo "🚀 开始 RAGFlow 数据备份..."
echo "📁 备份文件夹: $BACKUP_NAME"
echo "📍 RAGFlow 目录: $RAGFLOW_DIR"
echo ""

# 切换到 RAGFlow 目录
cd "$RAGFLOW_DIR"

# 检查是否存在 migration.sh
if [ ! -f "docker/migration.sh" ]; then
    echo "❌ 错误: 找不到 docker/migration.sh 文件"
    echo "请确保在 RAGFlow 项目根目录运行此脚本"
    exit 1
fi

# 执行备份
echo "📦 执行备份操作..."
bash docker/migration.sh backup "$BACKUP_NAME"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 备份完成成功！"
    echo "📍 备份位置: $(pwd)/$BACKUP_NAME"
    echo ""
    echo "💡 恢复数据时使用以下命令:"
    echo "   bash docker/migration.sh restore $BACKUP_NAME"
    echo ""
    echo "📋 备份内容包括:"
    echo "   - MySQL 数据库 (用户、知识库、对话等)"
    echo "   - MinIO 对象存储 (上传的文件)"
    echo "   - Redis 缓存数据"
    echo "   - Elasticsearch 索引数据"
else
    echo ""
    echo "❌ 备份失败！"
    echo "请检查错误信息并重试"
    exit 1
fi
