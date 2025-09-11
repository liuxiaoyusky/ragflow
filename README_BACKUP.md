# RAGFlow 数据备份与恢复指南

## 🔄 数据丢失问题总结

在切换RAGFlow使用本地repo后，可能会遇到数据丢失的问题。主要原因是：

1. **Docker Compose项目命名机制**：Docker Compose根据项目目录名为资源（数据卷）添加前缀
2. **数据卷隔离**：不同项目名称会创建独立的数据卷集合
3. **数据库重新初始化**：某些情况下MySQL会重新创建数据库结构

## 🛡️ 预防措施

### 1. 固定项目名称

在 `docker/.env` 文件中已添加：
```bash
COMPOSE_PROJECT_NAME=ragflow
```

这确保无论在哪个目录运行，都使用相同的数据卷名称。

### 2. 使用外部数据卷

在 `docker/docker-compose-base.yml` 中已配置：
```yaml
volumes:
  mysql_data:
    external: true
    name: soft_ragflow_mysql_data
  minio_data:
    external: true
    name: soft_ragflow_minio_data
  # ... 其他数据卷
```

这样可以明确指定使用现有的数据卷。

## 📦 备份操作

### 自动备份脚本

使用提供的自动备份脚本：

```bash
# 创建带时间戳的备份
bash backup_script.sh

# 创建自定义名称的备份
bash backup_script.sh my_backup_name
```

### 手动备份

使用RAGFlow官方迁移工具：

```bash
# 停止服务
docker-compose -f docker/docker-compose.yml down

# 创建备份
bash docker/migration.sh backup backup_folder_name

# 重新启动服务
docker-compose -f docker/docker-compose.yml up -d
```

## 🔄 恢复操作

### 从备份恢复

```bash
# 停止当前服务
docker-compose -f docker/docker-compose.yml down

# 从备份恢复数据
bash docker/migration.sh restore backup_folder_name

# 重新启动服务
docker-compose -f docker/docker-compose.yml up -d
```

### 注意事项

1. **备份前必须停止服务**：避免数据不一致
2. **恢复会覆盖现有数据**：请确保备份数据的正确性
3. **定期备份**：建议每周或重要操作前进行备份

## 🔍 数据卷管理

### 查看数据卷

```bash
# 查看所有RAGFlow相关数据卷
docker volume ls | grep ragflow

# 查看特定数据卷详情
docker inspect volume_name
```

### 数据卷位置

RAGFlow使用以下数据卷：
- `soft_ragflow_mysql_data`: MySQL数据库
- `soft_ragflow_minio_data`: 文件存储
- `soft_ragflow_redis_data`: 缓存数据
- `soft_ragflow_esdata01`: Elasticsearch索引

## 💡 技术解释

### Docker Compose项目命名

Docker Compose使用以下优先级确定项目名称：
1. `COMPOSE_PROJECT_NAME` 环境变量
2. `docker-compose.yml` 文件所在目录的名称
3. 当前工作目录的名称

### 数据卷命名规则

格式：`{项目名}_{服务名}_data`

例如：
- 项目名 `ragflow` + 服务名 `mysql` = `ragflow_mysql_data`
- 项目名 `soft_ragflow` + 服务名 `mysql` = `soft_ragflow_mysql_data`

## 🚨 故障排除

### 数据卷不存在

如果遇到数据卷不存在的错误：

```bash
# 检查数据卷是否存在
docker volume ls | grep ragflow

# 如果不存在，从备份恢复
bash docker/migration.sh restore backup_folder_name
```

### 容器无法启动

检查数据卷挂载：

```bash
# 查看容器挂载信息
docker inspect container_name | grep -A 10 "Mounts"

# 检查数据卷权限
ls -la /var/lib/docker/volumes/volume_name/_data
```

## 📅 定期维护建议

1. **每周备份**：使用自动备份脚本
2. **重要操作前备份**：升级、迁移前必须备份
3. **监控数据卷空间**：定期清理不必要的数据
4. **测试恢复流程**：定期验证备份的完整性

---

*本文档基于RAGFlow数据丢失问题的实际解决经验编写，旨在帮助用户避免类似问题。*
