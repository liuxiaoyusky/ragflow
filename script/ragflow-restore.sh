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
source "$COMPOSE_DIR/.env"

echo "[$(date)] Starting restore from $BACKUP_DIR"

# Stop RAGFlow
echo "Stopping RAGFlow..."
cd "$COMPOSE_DIR"
docker compose stop ragflow-gpu 2>/dev/null || docker compose stop ragflow-cpu 2>/dev/null || true
sleep 3

# 1. Restore MySQL
echo "1/4 Restoring MySQL..."
if [ -f "$BACKUP_DIR/mysql.sql.gz" ]; then
    gunzip -c "$BACKUP_DIR/mysql.sql.gz" | docker exec -i docker-mysql-1 mysql -uroot -p"${MYSQL_PASSWORD}" 2>/dev/null
    echo "✓ MySQL restored"
fi

# 2. Restore Redis
echo "2/4 Restoring Redis..."
if [ -f "$BACKUP_DIR/redis-dump.rdb.gz" ]; then
    gunzip -c "$BACKUP_DIR/redis-dump.rdb.gz" > /tmp/dump.rdb
    docker cp /tmp/dump.rdb docker-redis-1:/data/dump.rdb
    rm /tmp/dump.rdb
    docker restart docker-redis-1
    sleep 3
    echo "✓ Redis restored"
fi

# 3. Restore Elasticsearch
echo "3/4 Restoring Elasticsearch..."
if [ -f "$BACKUP_DIR/elasticsearch.tar.gz" ]; then
    docker stop docker-es01-1
    docker run --rm --volumes-from docker-es01-1 busybox sh -c "rm -rf /usr/share/elasticsearch/data/*"
    docker run --rm --volumes-from docker-es01-1 -v "$BACKUP_DIR":/backup \
        busybox tar xzf /backup/elasticsearch.tar.gz -C /
    docker start docker-es01-1
    sleep 5
    echo "✓ Elasticsearch restored"
fi

# 4. Restore MinIO
echo "4/4 Restoring MinIO..."
if [ -f "$BACKUP_DIR/minio.tar.gz" ]; then
    docker stop docker-minio-1
    docker run --rm --volumes-from docker-minio-1 busybox sh -c "rm -rf /data/*"
    docker run --rm --volumes-from docker-minio-1 -v "$BACKUP_DIR":/backup \
        busybox tar xzf /backup/minio.tar.gz -C /
    docker start docker-minio-1
    sleep 3
    echo "✓ MinIO restored"
fi

# Start RAGFlow
echo "Starting RAGFlow..."
cd "$COMPOSE_DIR"
docker compose up -d ragflow-gpu 2>/dev/null || docker compose up -d ragflow-cpu 2>/dev/null
sleep 5

echo ""
echo "✓ Restore completed!"
echo "Check logs: docker logs docker-ragflow-gpu-1"

exit 0
