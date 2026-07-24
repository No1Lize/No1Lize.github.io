# 部署

## 1. GitHub Pages

1. 创建公开仓库 `No1Lize/No1Lize.github.io`；
2. 把本仓库内容推送到默认分支 `main`；
3. 在 GitHub Pages 设置中选择 GitHub Actions；
4. 首次运行 `Build and deploy GitHub Pages`；
5. 发布地址应为 `https://No1Lize.github.io/`，不设置 `basePath`。

## 2. Neon

创建 PostgreSQL 数据库并复制带 TLS 的连接串。建议使用池化连接串给 API，非池化连接串仅用于迁移或运维。启用自动备份并定期验证恢复。

## 3. Render

Render Blueprint 读取根目录 `render.yaml`，创建：

- `lize-road-one-api`：FastAPI Web Service；
- `lize-road-one-scheduler`：定时采集 Worker。

必须配置：

- `DATABASE_URL`
- `INTERNAL_SYNC_SECRET`
- `SEC_USER_AGENT`

可选配置：

- `GITHUB_TOKEN`：数据更新后触发 Pages 构建；
- `PUBLIC_ORIGINS`：如增加自定义域名，必须同步追加。

## 4. GitHub 变量与密钥

变量：

- `NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com`
- `API_BASE_URL=https://<render-service>.onrender.com`

密钥：

- `INTERNAL_SYNC_SECRET`

## 5. 验证

- `GET /healthz` 返回 `{"status":"ok"}`；
- `GET /api/v1/status` 显示 `database=connected`；
- 手动运行 scheduled-sync；
- 检查任务扫描、新增、跳过和错误数；
- 确认 Pages 工作流完成且旧版本未因失败被覆盖。
