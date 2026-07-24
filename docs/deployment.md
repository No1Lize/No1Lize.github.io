# 部署

## 1. GitHub Pages

1. 创建公开仓库 `No1Lize/No1Lize.github.io`；
2. 把本仓库内容推送到默认分支 `main`；
3. 在 GitHub Pages 设置中选择 GitHub Actions；
4. 首次运行 `Build and deploy GitHub Pages`；
5. 发布地址应为 `https://No1Lize.github.io/`，不设置 `basePath`。

## 2. 自动抓取

`.github/workflows/scheduled-sync.yml` 每两小时运行一次。任务直接执行 Python 标准库抓取脚本，不需要安装依赖，不需要服务器或数据库。

任务完成后：

1. 读取现有 `public/data/articles.json`；
2. 抓取 OpenAI 官方页面与 SEC EDGAR；
3. 规范化 URL、去重并保留人工核验摘要；
4. 只在数据变化时提交；
5. 提交成功后显式启动 Pages 工作流。

## 3. GitHub 设置

不需要 GitHub Secret。建议设置一个普通 Actions Variable：

- `SEC_USER_AGENT`：包含站点或联系邮箱的 SEC 请求标识。

路径：**Settings → Secrets and variables → Actions → Variables**。

仓库工作流需要 `contents: write`，配置已写在 YAML 中。如仓库把默认 `GITHUB_TOKEN` 权限强制设为只读，需要在 **Settings → Actions → General → Workflow permissions** 选择 **Read and write permissions**。

## 4. 验证

- 在 Actions 手动运行 `Refresh public articles`；
- 检查 `public/data/articles.json` 是否产生新提交；
- 确认该提交自动触发 `Build and deploy GitHub Pages`；
- 打开首页，状态应显示“自动更新 JSON”和最后更新时间；
- 无新内容时任务应输出 `No article changes`，不产生提交。
