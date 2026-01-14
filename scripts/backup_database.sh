#!/bin/bash
# RAGFlow 数据库备份脚本
# 用于在版本同步前备份所有关键数据

BACKUP_DIR="$HOME/backup"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="ragflow_backup_$DATE"

# 创建备份目录
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

echo "开始备份 RAGFlow 数据..."
echo "备份目录: $BACKUP_DIR/$BACKUP_NAME"

# 1. 备份MySQL数据库
echo "备份MySQL数据库..."
if docker ps | grep -q ragflow-mysql; then
    docker exec ragflow-mysql mysqldump -u root -p$MYSQL_ROOT_PASSWORD ragflow > "$BACKUP_DIR/$BACKUP_NAME/mysql_backup.sql"
    echo "MySQL数据库备份完成"
else
    echo "警告: 未找到ragflow-mysql容器，跳过MySQL备份"
fi

# 2. 备份MinIO对象存储
echo "备份MinIO对象存储..."
if docker volume ls | grep -q ragflow_minio_data; then
    docker run --rm -v ragflow_minio_data:/data -v "$BACKUP_DIR/$BACKUP_NAME":/backup alpine tar czf /backup/minio_backup.tar.gz -C /data .
    echo "MinIO对象存储备份完成"
else
    echo "警告: 未找到ragflow_minio_data卷，跳过MinIO备份"
fi

# 3. 备份Elasticsearch数据
echo "备份Elasticsearch数据..."
if docker ps | grep -q ragflow-es01; then
    # 创建快照仓库目录
    docker exec ragflow-es01 mkdir -p /usr/share/elasticsearch/backup
    
    # 注册快照仓库
    curl -X PUT "localhost:9200/_snapshot/backup_repo" -H 'Content-Type: application/json' -d'
    {
      "type": "fs",
      "settings": {
        "location": "/usr/share/elasticsearch/backup"
      }
    }' 2>/dev/null
    
    # 创建快照
    curl -X PUT "localhost:9200/_snapshot/backup_repo/snapshot_$DATE?wait_for_completion=true" 2>/dev/null
    
    # 备份快照数据
    docker run --rm -v ragflow_esdata01:/usr/share/elasticsearch/data -v "$BACKUP_DIR/$BACKUP_NAME":/backup alpine tar czf /backup/es_backup.tar.gz -C /usr/share/elasticsearch/data backup
    
    echo "Elasticsearch数据备份完成"
else
    echo "警告: 未找到ragflow-es01容器，跳过Elasticsearch备份"
fi

# 4. 备份Redis数据
echo "备份Redis数据..."
if docker ps | grep -q ragflow-redis; then
    docker exec ragflow-redis redis-cli --rdb /data/dump_$DATE.rdb
    docker run --rm -v ragflow_redis_data:/data -v "$BACKUP_DIR/$BACKUP_NAME":/backup alpine tar czf /backup/redis_backup.tar.gz -C /data dump_$DATE.rdb
    echo "Redis数据备份完成"
else
    echo "警告: 未找到ragflow-redis容器，跳过Redis备份"
fi

# 5. 备份配置文件
echo "备份配置文件..."
cp docker/.env "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || echo "警告: 未找到.env文件"
cp docker/docker-compose.yml "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || echo "警告: 未找到docker-compose.yml文件"

# 6. 创建备份信息文件
cat > "$BACKUP_DIR/$BACKUP_NAME/backup_info.txt" << EOF
备份时间: $(date)
RAGFlow版本: $(git rev-parse HEAD 2>/dev/null || echo "未知")
分支: $(git branch --show-current 2>/dev/null || echo "未知")
备份内容:
- MySQL数据库
- MinIO对象存储
- Elasticsearch数据
- Redis数据
- 配置文件
EOF

# 7. 创建压缩包
echo "创建压缩包..."
cd "$BACKUP_DIR"
tar czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

echo "备份完成: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
echo "备份大小: $(du -h "$BACKUP_NAME.tar.gz" | cut -f1)"

# 8. 清理旧备份（保留最近4周）
echo "清理旧备份..."
find "$BACKUP_DIR" -name "ragflow_backup_*.tar.gz" -mtime +28 -delete 2>/dev/null

echo "备份脚本执行完成"
