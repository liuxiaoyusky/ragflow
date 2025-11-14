# RAGFlow 数据库备份工具

简单的手动备份和恢复脚本，用于备份所有RAGFlow数据库。

## 备份内容

- **MySQL**: 元数据（用户、对话、知识库等）
- **Redis**: 缓存和任务队列
- **Elasticsearch**: 向量索引
- **MinIO**: 对象存储（文档文件）

## 使用方法

### 手动备份

```bash
cd /home/calvin/github/ragflow/script
./ragflow-backup.sh
```

备份将保存到 `/home/calvin/backup/YYYY-MM-DD_HH-MM-SS/` 目录。

### 恢复备份

⚠️ **警告：恢复会覆盖所有当前数据！**

```bash
# 列出可用备份
ls -lt /home/calvin/backup/

# 恢复指定备份
cd /home/calvin/github/ragflow/script
./ragflow-restore.sh /home/calvin/backup/2025-11-14_02-00-00
```

### 查看备份信息

```bash
# 查看备份详情
cat /home/calvin/backup/2025-11-14_02-00-00/backup.info

# 查看备份大小
du -sh /home/calvin/backup/*/
```

## 管理备份

### 清理旧备份

```bash
# 删除指定备份
rm -rf /home/calvin/backup/2025-11-01_02-00-00

# 只保留最近N个备份
cd /home/calvin/backup
ls -1dt [0-9]* | tail -n +6 | xargs rm -rf
```

### 监控磁盘空间

```bash
# 查看备份占用空间
du -sh /home/calvin/backup/

# 查看磁盘使用情况
df -h /home/calvin/backup
```

## 故障排查

如果备份失败，检查：

1. Docker容器是否运行：`docker ps`
2. 环境变量文件：`/home/calvin/github/ragflow/docker/.env`
3. 磁盘空间：`df -h`

---

**文件位置**：
- 脚本位置：`/home/calvin/github/ragflow/script/`
- 备份位置：`/home/calvin/backup/`
- 日志文件：`/home/calvin/backup/backup.log`
