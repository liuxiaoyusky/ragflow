#!/bin/bash
#
# RAGFlow Database Backup Script
# Usage: ./ragflow-backup.sh
#

set -e

# Configuration
BACKUP_BASE="/home/calvin/backup"
TIMESTAMP=$(TZ='Asia/Shanghai' date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="$BACKUP_BASE/$TIMESTAMP"
COMPOSE_DIR="/home/calvin/github/ragflow/docker"
LOG_FILE="$BACKUP_BASE/backup.log"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create backup directory
log "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Load environment variables
if [ -f "$COMPOSE_DIR/.env" ]; then
    . "$COMPOSE_DIR/.env"
else
    log "[ERROR] .env file not found at $COMPOSE_DIR/.env"
    exit 1
fi

log "Starting RAGFlow backup..."

# 1. MySQL Backup
log "1/4 Backing up MySQL..."
docker exec ragflow-mysql mysqldump \
    -uroot -p"${MYSQL_PASSWORD}" \
    --all-databases \
    --single-transaction \
    --quick \
    --lock-tables=false \
    2>/dev/null | gzip > "$BACKUP_DIR/mysql.sql.gz"
log "MySQL: $(du -h $BACKUP_DIR/mysql.sql.gz | cut -f1)"

# 2. Redis Backup
log "2/4 Backing up Redis..."
docker exec ragflow-redis redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning SAVE >/dev/null 2>&1
sleep 2
docker cp ragflow-redis:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null || log "[WARN] Redis backup failed"
[ -f "$BACKUP_DIR/redis-dump.rdb" ] && gzip "$BACKUP_DIR/redis-dump.rdb" && log "Redis: $(du -h $BACKUP_DIR/redis-dump.rdb.gz | cut -f1)"

# 3. Elasticsearch Backup
log "3/4 Backing up Elasticsearch..."
if docker ps | grep -q "ragflow-es01"; then
    docker run --rm --volumes-from ragflow-es01 -v "$BACKUP_DIR":/backup \
        busybox tar czf /backup/elasticsearch.tar.gz /usr/share/elasticsearch/data 2>/dev/null
    log "Elasticsearch: $(du -h $BACKUP_DIR/elasticsearch.tar.gz | cut -f1)"
else
    log "[WARN] Elasticsearch container not running"
fi

# 4. MinIO Backup
log "4/4 Backing up MinIO..."
if docker ps | grep -q "ragflow-minio"; then
    docker run --rm --volumes-from ragflow-minio -v "$BACKUP_DIR":/backup \
        busybox tar czf /backup/minio.tar.gz /data 2>/dev/null
    log "MinIO: $(du -h $BACKUP_DIR/minio.tar.gz | cut -f1)"
else
    log "[WARN] MinIO container not running"
fi

# Create backup info
cat > "$BACKUP_DIR/backup.info" <<EOF
RAGFlow Backup
Date: $(date '+%Y-%m-%d %H:%M:%S')
Location: $BACKUP_DIR
Total Size: $(du -sh "$BACKUP_DIR" | cut -f1)

Files:
$(ls -lh "$BACKUP_DIR" | tail -n +2)
EOF

# Summary
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backup completed: $TOTAL_SIZE"
log "Location: $BACKUP_DIR"

# Disk usage warning
DISK_USAGE=$(df -h "$BACKUP_BASE" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "${DISK_USAGE}" -gt 80 ]; then
    log "[WARN] Disk usage: ${DISK_USAGE}%"
fi

exit 0
