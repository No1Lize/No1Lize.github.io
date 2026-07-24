# 部署

## GitHub Pages

1. 使用公开仓库 `No1Lize/No1Lize.github.io`；
2. 默认分支为 `main`；
3. **Settings → Pages → Source** 选择 **GitHub Actions**；
4. `.github/workflows/pages.yml` 从根路径执行静态构建；
5. 发布地址为 `https://No1Lize.github.io/`，不设置项目 `basePath`。

构建失败时部署任务不会运行，因此线上保留上一版。

## 自动情报刷新

`.github/workflows/scheduled-sync.yml` 每两小时运行，也支持手动选择：

`all`、`news`、`company`、`feeds`、`x`、`papers`、`discovery`、`sec`。

抓取器或来源配置更新推送到 `main` 时会自动执行一次完整刷新。流程为：

1. 并行读取允许的公开来源；
2. 按来源替换成功批次，失败来源保留历史批次；
3. 执行数据质量门；
4. 运行 13 项抓取器单元测试；
5. 仅在 `public/data/articles.json` 有变化时提交；
6. 启动 Pages 工作流。

## GitHub 设置

不需要第三方 API Secret。建议设置 Actions Variable：

- `SEC_USER_AGENT`：站点名和可联系邮箱，满足 SEC 请求标识要求。

工作流需要 `contents: write` 和 `actions: write`。如果仓库策略覆盖 YAML 权限，应在 **Settings → Actions → General → Workflow permissions** 允许读写。

## 验证

- 在 Actions 中运行 **Refresh public intelligence**；
- 确认抓取、质量门和测试全部成功；
- 检查仓库 `public/data/articles.json` 的 `generatedAt`、`articleCount`、`sourceStatus` 与 `qualityGate`；
- 确认 **Build and deploy GitHub Pages** 对最新数据提交成功；
- 打开 `https://No1Lize.github.io/data/articles.json` 和首页核对更新时间。
