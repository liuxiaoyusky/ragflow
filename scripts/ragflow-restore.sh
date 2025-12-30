#!/bin/bash
#
# RAGFlow Database Restore Script
# Usage: ./ragflow-restore.sh <backup_directory>
#

set -e

COMPOSE_DIR="/home/calvin/github/ragflow/docker"

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo ""
    echo "Available backups:"
    ls -1dt /home/calvin/backup/[0-9]* 2>/dev/null | head -10 || echo "No backups found"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "[ERROR] Backup directory does not exist: $BACKUP_DIR"
    exit 1
fi

# Show backup info
[ -f "$BACKUP_DIR/backup.info" ] && cat "$BACKUP_DIR/backup.info" && echo ""

# Confirmation
echo "⚠️  WARNING: This will OVERWRITE all current RAGFlow data!"
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled"
    exit 0
fi

# Load environment
. "$COMPOSE_DIR/.env"

echo "[$(date)] Starting restore from $BACKUP_DIR"

# Stop RAGFlow
echo "Stopping RAGFlow..."
cd "$COMPOSE_DIR"
docker compose down
sleep 3

# 1. Restore MySQL
echo "1/4 Restoring MySQL..."
docker compose up -d mysql
sleep 10
if [ -f "$BACKUP_DIR/mysql.sql.gz" ]; then
    docker exec -i ragflow-mysql mysql -uroot -p"${MYSQL_PASSWORD}" -e "DROP DATABASE IF EXISTS rag_flow; CREATE DATABASE rag_flow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null
    gunzip -c "$BACKUP_DIR/mysql.sql.gz" | docker exec -i ragflow-mysql mysql -uroot -p"${MYSQL_PASSWORD}" rag_flow 2>/dev/null
    echo "✓ MySQL restored"
fi

# 2. Restore Redis
echo "2/4 Restoring Redis..."
if [ -f "$BACKUP_DIR/redis-dump.rdb.gz" ]; then
    docker compose stop redis
    docker run --rm -v docker_redis_data:/data alpine sh -c "rm -rf /data/*"
    gunzip -c "$BACKUP_DIR/redis-dump.rdb.gz" | docker run --rm -i -v docker_redis_data:/data alpine sh -c "cat > /data/dump.rdb"
    docker compose up -d redis
    sleep 3
    echo "✓ Redis restored"
fi

# 3. Restore Elasticsearch
echo "3/4 Restoring Elasticsearch..."
if [ -f "$BACKUP_DIR/elasticsearch.tar.gz" ]; then
    docker compose stop es01
    docker run --rm -v docker_esdata01:/data alpine sh -c "rm -rf /data/*"
    docker run --rm -v docker_esdata01:/data -v "$BACKUP_DIR":/backup alpine sh -c "cd /data && tar -xzf /backup/elasticsearch.tar.gz"
    docker compose up -d es01
    sleep 5
    echo "✓ Elasticsearch restored"
fi

# 4. Restore MinIO
echo "4/4 Restoring MinIO..."
if [ -f "$BACKUP_DIR/minio.tar.gz" ]; then
    docker compose stop minio
    docker run --rm -v docker_minio_data:/data alpine sh -c "rm -rf /data/*"
    docker run --rm -v docker_minio_data:/data -v "$BACKUP_DIR":/backup alpine sh -c "cd /data && tar -xzf /backup/minio.tar.gz"
    docker compose up -d minio
    sleep 3
    echo "✓ MinIO restored"
fi

# Start RAGFlow
echo "Starting RAGFlow..."
cd "$COMPOSE_DIR"
docker compose --profile gpu --profile elasticsearch up -d
sleep 5

echo ""
echo "✓ Restore completed!"
echo "Check logs: docker logs docker-ragflow-gpu-1"

exit 0
