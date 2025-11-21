# 双环境 OIDC 验证清单

## 前提条件

1. **飞书后台配置**：确保在飞书应用 OIDC 配置中添加了两条 redirect_uri：
   - `https://10.1.9.133:8443/v1/user/oauth/callback/feishu`（stable）
   - `https://10.1.9.133:18443/v1/user/oauth/callback/feishu`（dev）

2. **手动编辑 `.env.dev`**：在 `/home/calvin/github/ragflow/docker/.env.dev` 中添加：
   ```bash
   FEISHU_REDIRECT_URI=https://10.1.9.133:18443/v1/user/oauth/callback/feishu
   ```

3. **停掉旧环境**：停掉 `/home/calvin/apps/soft_ragflow` 避免端口冲突
   ```bash
   cd /home/calvin/apps/soft_ragflow
   docker compose down
   ```

---

## 验证步骤

### 1. 验证 stable 环境（8443）

#### 1.1 启动 stable
```bash
cd /home/calvin/github/ragflow
./scripts/ragflow_restart.sh
```

#### 1.2 检查容器状态
```bash
docker compose ps
```
应该看到：
- `ragflow-mysql`
- `ragflow-redis`
- `ragflow-minio`
- `ragflow-es01`
- `ragflow-gpu`
- 等等（都是 `ragflow-*` 前缀，无 `-dev` 后缀）

#### 1.3 检查网络
```bash
docker network ls | grep ragflow
```
应该看到：
- `ragflow` 网络（不是 `ragflow-dev-net`）

#### 1.4 测试 Feishu OIDC
1. 浏览器访问 `https://10.1.9.133:8443`
2. 点击"飞书登录"按钮
3. 跳转到飞书登录页面
4. 扫码授权
5. 应该回调到 `https://10.1.9.133:8443/v1/user/oauth/callback/feishu`
6. 成功登录 RagFlow

#### 1.5 验证配置加载
```bash
docker exec ragflow-gpu cat /ragflow/conf/service_conf.yaml | grep -A 10 "oauth:"
```
应该看到 `redirect_uri: "https://10.1.9.133:8443/v1/user/oauth/callback/feishu"`

---

### 2. 验证 dev 环境（18443）

#### 2.1 启动 dev（不停 stable）
```bash
cd /home/calvin/github/ragflow
./scripts/dev_start.sh
```

#### 2.2 检查容器状态
```bash
docker compose -p ragflow-dev ps
```
应该看到：
- `ragflow-dev-mysql`
- `ragflow-dev-redis`
- `ragflow-dev-minio`
- `ragflow-dev-es01`
- `ragflow-dev-gpu`
- 等等（都是 `ragflow-dev-*` 前缀）

#### 2.3 检查网络
```bash
docker network ls | grep ragflow
```
应该看到：
- `ragflow` 网络（stable 用）
- `ragflow-dev-net` 网络（dev 用）

#### 2.4 测试 Feishu OIDC
1. 浏览器访问 `https://10.1.9.133:18443`
2. 点击"飞书登录"按钮
3. 跳转到飞书登录页面
4. 扫码授权
5. 应该回调到 `https://10.1.9.133:18443/v1/user/oauth/callback/feishu`
6. 成功登录 RagFlow

#### 2.5 验证配置加载
```bash
docker exec ragflow-dev-gpu cat /ragflow/conf/service_conf.yaml | grep -A 10 "oauth:"
```
应该看到 `redirect_uri: "https://10.1.9.133:18443/v1/user/oauth/callback/feishu"`

---

### 3. 交叉验证

#### 3.1 两个环境同时运行
```bash
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep ragflow
```
应该看到：
- stable 容器：`8080->80`, `8443->443`, `9380-9382`
- dev 容器：`10080->80`, `18443->443`, `19380-19382`

#### 3.2 网络隔离
```bash
# stable 的 GPU 容器应该在 ragflow 网络
docker inspect ragflow-gpu | grep -A 5 "Networks"

# dev 的 GPU 容器应该在 ragflow-dev-net 网络
docker inspect ragflow-dev-gpu | grep -A 5 "Networks"
```

#### 3.3 数据隔离
两个环境应该使用完全独立的：
- MySQL 数据库（不同容器）
- MinIO 存储（不同容器）
- Elasticsearch 索引（不同容器）

---

## 预期结果

✅ **成功标志**：
1. stable（8443）和 dev（18443）可以同时运行
2. 两个环境都能成功完成 Feishu OIDC 登录
3. 容器名、网络、端口完全隔离
4. 停掉 soft_ragflow 后，stable 环境接管 8080/8443 端口

❌ **失败情况**：
1. 端口冲突（8080/8443 被占用）→ 检查 soft_ragflow 是否真的停了
2. redirect_uri 不匹配 → 检查飞书后台配置和 `.env.dev`
3. 容器名冲突 → 检查 `CONTAINER_PREFIX` 和 `NETWORK_NAME` 环境变量

---

## 验证完成后

如果一切正常，你可以：
1. **彻底卸载** `/home/calvin/apps/soft_ragflow`（备份数据后）
2. 把 `~/github/ragflow` 作为唯一的 RagFlow 部署环境
3. stable 和 dev 通过启动脚本切换，互不干扰


