# 后续重构计划（Refactoring Roadmap）

本文档记录了当前配置体系的遗留问题和未来优化方向。这些优化**不在当前轮次实现**，但应该作为技术债务跟踪。

---

## 1. 统一 `service_conf` 权威源

### 当前问题
- 存在两个文件：
  - `docker/service_conf.yaml.template`：模板，支持环境变量替换
  - `docker/service_conf.yaml`：静态配置，作为"人看的参考"
- 容器启动时，实际加载的是 `service_conf.yaml.template` 渲染后的结果
- 两个文件容易不同步，导致混淆

### 目标方案
**方案 A：Template 为唯一源**
1. 删除 `docker/service_conf.yaml`
2. 修改 `docker-compose-base.yml`：
   ```yaml
   volumes:
     - ./service_conf.yaml.template:/ragflow/conf/service_conf.yaml.template:ro
   ```
3. 容器 entrypoint 负责在启动时渲染环境变量，生成 `/ragflow/conf/service_conf.yaml`

**方案 B：YAML 为唯一源**
1. 删除 `docker/service_conf.yaml.template`
2. 修改挂载，直接用 `service_conf.yaml`
3. 环境变量通过应用代码内部读取（而不是 YAML 模板替换）

**推荐**：方案 A（保持当前 template 机制，删除冗余的 `.yaml`）

### 优先级
🟡 Medium（不影响功能，但影响可维护性）

---

## 2. 参数化所有 redirect_uri 组件

### 当前问题
- Feishu OIDC 的 `redirect_uri` 现在是硬编码 IP：
  ```yaml
  redirect_uri: "${FEISHU_REDIRECT_URI:-https://10.1.9.133:8443/v1/user/oauth/callback/feishu}"
  ```
- 如果换机器、换端口、换域名，需要手动改这个默认值

### 目标方案
**环境变量拼接**：
```yaml
redirect_uri: "${RAGFLOW_PROTOCOL:-https}://${RAGFLOW_HOST:-10.1.9.133}:${RAGFLOW_HTTPS_PORT:-8443}/v1/user/oauth/callback/feishu"
```

**.env（stable）**：
```bash
# 不设置，使用默认值
# RAGFLOW_PROTOCOL=https
# RAGFLOW_HOST=10.1.9.133
# RAGFLOW_HTTPS_PORT=8443
```

**.env.dev**：
```bash
RAGFLOW_PROTOCOL=https
RAGFLOW_HOST=10.1.9.133
RAGFLOW_HTTPS_PORT=18443
```

### 好处
- 支持多机部署（改一个 `RAGFLOW_HOST` 就够）
- 支持域名（如 `ragflow.example.com`）
- dev/stable/prod 通过环境变量区分，不用改模板

### 优先级
🟢 Low（Nice to have，但当前硬编码 IP 也能用）

---

## 3. 清理前端登录页多余校验和日志

### 当前问题
用户反馈：点击"飞书登录"后，页面立即闪现 email/password 输入框的红色错误提示，并打印大量 React 元素到控制台。

### 根本原因
`web/src/pages/login/index.tsx`：
1. **初始化校验**：
   ```tsx
   useEffect(() => {
     form.validateFields(['nickname']).catch(() => {});
   }, [form]);
   ```
   - 组件挂载时就校验 `nickname` 字段，导致表单立即显示错误状态

2. **SSO 点击未重置表单**：
   ```tsx
   const handleLoginWithChannel = (channel: string) => {
     loginWithChannel(channel);  // 没有先 form.resetFields()
   };
   ```
   - 用户点击 SSO 按钮时，表单保持之前的校验状态

3. **调试日志**：
   ```tsx
   console.log('Failed:', errorInfo);
   ```
   - 开发调试遗留的 console.log

### 目标方案
**最小改动**（3 行代码）：
```tsx
// 1. 删除初始化校验
// useEffect(() => {
//   form.validateFields(['nickname']).catch(() => {});
// }, [form]);

// 2. SSO 点击前重置表单
const handleLoginWithChannel = (channel: string) => {
  form.resetFields();  // 👈 新增
  loginWithChannel(channel);
};

// 3. （可选）删除调试日志
// console.log('Failed:', errorInfo);
```

### 优先级
🟡 Medium（不影响功能，但影响用户体验）

---

## 4. Docker Compose 端口映射改进

### 当前问题
- dev 环境的端口映射是"平移"（+10000）：
  - stable: 8080/8443/9380-9382
  - dev: 10080/18443/19380-19382
- 其中 **18443 是例外**（不是 10443），增加了记忆负担

### 目标方案
**统一规则**：dev 环境所有端口都 +10000：
- stable: 8080/8443/9380-9382
- dev: 18080/18443/19380-19382

或者：**参数化端口偏移量**：
```yaml
# docker-compose.dev.yml
services:
  ragflow-gpu:
    ports:
      - "${HTTP_PORT:-18080}:80"
      - "${HTTPS_PORT:-18443}:443"
```

```bash
# .env.dev
HTTP_PORT=18080
HTTPS_PORT=18443
API_PORT=19380
```

### 优先级
🟢 Low（当前配置能用，只是不够"对称"）

---

## 5. 自动化测试脚本增强

### 当前问题
- 手动验证 OIDC 流程繁琐（浏览器点击、扫码、检查）
- 没有自动化健康检查

### 目标方案
**增强 `scripts/test_feishu_oidc.sh`**：
1. 检查 `/v1/user/login/channels` 是否返回 `feishu`
2. 检查 `/v1/user/login/feishu` 的 302 Location 是否正确
3. （可选）使用无头浏览器模拟完整 OIDC 流程

**新增 `scripts/health_check.sh`**：
```bash
#!/bin/bash
# 检查所有服务健康状态
curl -f http://localhost:9380/v1/health || exit 1
curl -f http://localhost:9000/minio/health/live || exit 1
# ...
```

### 优先级
🟡 Medium（对 CI/CD 有价值）

---

## 6. 文档完善

### 缺失内容
- [ ] 快速开始指南（README.md）
- [ ] stable 和 dev 环境的使用场景说明
- [ ] Feishu OIDC 配置图文教程
- [ ] 故障排查手册（端口冲突、网络隔离、配置不生效等）

### 优先级
🟢 Low（当前有验证清单足够用）

---

## 总结

### 立即行动（本轮已完成）
✅ 参数化 Feishu redirect_uri（默认 stable 8443）  
✅ 明确 stable/dev 启动脚本语义  
✅ 输出双环境验证清单  

### 下一轮优化（按优先级）
1. 🟡 统一 `service_conf` 权威源（删除冗余文件）
2. 🟡 清理前端登录页多余校验/日志
3. 🟡 增强自动化测试脚本
4. 🟢 参数化 redirect_uri 所有组件（支持域名部署）
5. 🟢 Docker Compose 端口映射规则统一
6. 🟢 补充用户文档

### 技术债务跟踪
- 可以在 GitHub Issues 里创建对应 issue，贴上这个 roadmap 链接
- 每次优化完成后更新本文档，标记状态


