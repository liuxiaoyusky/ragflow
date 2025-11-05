# RagFlow 管理脚本集合

统一的 RagFlow 管理工具集，包含 Docker 服务管理、数据备份和版本同步功能。

## 🚀 快速使用

```bash
cd /home/calvin/github/ragflow/scripts

# Docker 服务管理
./ragflow_restart.sh    # 重启 RagFlow (最常用)
./ragflow_start.sh      # 启动服务
./ragflow_stop.sh       # 停止服务
./ragflow_status.sh     # 查看状态
./ragflow_logs.sh       # 查看日志

# 数据备份
./backup_database.sh    # 备份所有数据（MySQL + MinIO + Elasticsearch）

# 版本同步
./sync_upstream.sh      # 同步上游版本并自动备份
```

## 📋 脚本说明

### Docker 服务管理

| 脚本 | 功能 | 说明 |
|------|------|------|
| `ragflow_restart.sh` | 一键重启 | 完整的停止→启动流程，显示详细状态 |
| `ragflow_start.sh` | 启动服务 | 使用 GPU + Elasticsearch 配置启动 |
| `ragflow_stop.sh` | 停止服务 | 优雅停止所有 RagFlow 容器 |
| `ragflow_status.sh` | 查看状态 | 显示容器状态、资源使用和端口信息 |
| `ragflow_logs.sh` | 查看日志 | 实时跟踪服务日志 (Ctrl+C 退出) |

**配置说明**：所有 Docker 管理脚本使用以下配置
- 计算设备: **GPU**
- 向量引擎: **Elasticsearch**
- 配置文件: `docker/.env`

### 数据管理

| 脚本 | 功能 | 说明 |
|------|------|------|
| `backup_database.sh` | 数据备份 | 备份 MySQL、MinIO、Elasticsearch 数据 |
| `sync_upstream.sh` | 版本同步 | 同步上游更新，自动备份，安全升级 |

## 📖 详细用法

### 1. Docker 服务管理

#### 重启服务（推荐）
```bash
./ragflow_restart.sh
```
输出示例：
```
==========================================
RagFlow 重启脚本
配置: GPU + Elasticsearch
==========================================

→ 停止现有服务...
→ 启动服务...
→ 服务状态:

✓ 重启完成！
访问地址:
  - Web UI:  http://localhost:8080
  - API:     http://localhost:9380
```

#### 查看状态
```bash
./ragflow_status.sh
```

#### 查看日志
```bash
# 查看 RagFlow 主服务日志
./ragflow_logs.sh

# 查看其他服务日志
./ragflow_logs.sh mysql        # MySQL 日志
./ragflow_logs.sh redis        # Redis 日志
./ragflow_logs.sh es01         # Elasticsearch 日志
```

### 2. 数据备份

#### 手动备份
```bash
./backup_database.sh
```

备份内容包括：
- MySQL 数据库
- MinIO 对象存储
- Elasticsearch 索引
- Docker volumes

备份位置：`$HOME/backup/ragflow_backup_YYYYMMDD_HHMMSS/`

### 3. 版本同步

#### 同步上游更新
```bash
./sync_upstream.sh
```

自动流程：
1. 自动备份当前数据
2. 从上游仓库拉取最新代码
3. 检查冲突并提示处理
4. 可选择是否重启服务应用更新

## ⚙️ 配置信息

### 端口映射

```
8080  → Web UI (HTTP)
8443  → Web UI (HTTPS)
9380  → API Server
9381  → Admin Server
9382  → MCP Server
5455  → MySQL
6379  → Redis
9000  → MinIO API
9001  → MinIO Console
1200  → Elasticsearch
```

### 环境配置

配置文件位置：`/home/calvin/github/ragflow/docker/.env`

关键配置项：
- `DEVICE=gpu` - 使用 GPU 模式
- `DOC_ENGINE=elasticsearch` - 使用 Elasticsearch 引擎
- `SVR_WEB_HTTP_PORT=8080` - Web HTTP 端口
- `RAGFLOW_IMAGE=infiniflow/ragflow:v0.21.1` - Docker 镜像版本

## 🔧 高级用法

### 直接使用 Docker Compose

如果需要更细粒度的控制：

```bash
cd /home/calvin/github/ragflow/docker

# 启动指定服务
docker compose --profile gpu --profile elasticsearch up -d

# 停止服务
docker compose --profile gpu --profile elasticsearch down

# 查看日志
docker compose logs -f ragflow-gpu

# 重新构建并启动
docker compose --profile gpu --profile elasticsearch up -d --build

# 查看所有容器状态
docker compose ps
```

### 切换到 CPU 模式

编辑 `docker/.env`：
```bash
DEVICE=cpu
```

然后使用：
```bash
cd /home/calvin/github/ragflow/docker
docker compose --profile cpu --profile elasticsearch up -d
```

### 修改配置后应用

1. 编辑 `docker/.env` 文件
2. 运行 `./ragflow_restart.sh` 使配置生效

## 🛠️ 故障排查

### 服务无法启动

```bash
# 查看详细日志
./ragflow_logs.sh

# 检查容器状态
./ragflow_status.sh

# 完全重建
cd /home/calvin/github/ragflow/docker
docker compose --profile gpu --profile elasticsearch down -v
docker compose --profile gpu --profile elasticsearch up -d
```

### 端口冲突

检查端口占用：
```bash
sudo netstat -tunlp | grep -E ":(8080|9380|9381|9382)"
```

修改 `docker/.env` 中的端口配置。

### 恢复备份

```bash
# 找到备份目录
ls -lh $HOME/backup/

# 根据 backup_database.sh 中的说明恢复数据
```

## 📚 设计原则

这些脚本遵循以下设计原则：

1. **简洁直接** - 每个脚本职责单一，功能明确
2. **零魔法** - 所有操作透明可见，用户清楚发生了什么
3. **可组合** - 脚本可以独立使用，也可以组合调用
4. **容错性** - 关键操作前检查状态，提供清晰的错误信息
5. **幂等性** - 重复执行不会造成问题

## 🔗 相关链接

- [RagFlow 官方文档](https://ragflow.io/docs)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [项目主页](https://github.com/infiniflow/ragflow)

