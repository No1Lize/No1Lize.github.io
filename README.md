# 丽泽路1号

公开访问、以原始信源为优先的中美新兴科技与创投情报网站。

## 当前范围

- 一个情报首页、六个核心频道和全局搜索；
- 58 家真实中美科技公司、20 家投资机构、15 家上市跟踪公司；
- 巴菲特、芒格、段永平、李录、何恺明和姚顺雨人物档案，每人至少五条材料索引；
- 10 个赛道、5 篇结构化研究报告和可追溯的公开情报；
- 公司/机构官网、SEC EDGAR、金融创投媒体、新浪、X 公开资料、OpenAlex、arXiv，以及严格域名白名单内的微信和金融媒体公开索引；
- GitHub Actions 定时生成 `public/data/articles.json`；
- GitHub Pages 零服务器静态部署。

项目没有 API 服务、数据库、Render 或 Neon 依赖。数据更新由 GitHub Actions 完成，仓库 JSON 是公开站点的唯一运行时数据源。

## 本地运行

```bash
npm ci
npm run dev
```

生成 GitHub Pages 静态站：

```bash
npm run build:pages
```

## 情报抓取

```bash
npm run crawl
python3 tools/crawl_articles.py --source company
python3 tools/crawl_articles.py --source feeds
python3 tools/crawl_articles.py --source x
python3 tools/crawl_articles.py --source papers
python3 tools/crawl_articles.py --source discovery
python3 tools/crawl_articles.py --source sec
python3 tools/crawl_articles.py --validate-only
```

来源、筛选关键词、域名白名单和质量门配置位于 `config/intelligence_sources.json`。抓取结果写入 `public/data/articles.json`，并按规范化 URL 与事件指纹去重。

更新策略：

1. 成功刷新某来源时，用本次批次替换该来源的旧生成数据；
2. 单一来源失败或返回空结果时，保留它的上一版成功数据；
3. 人工编辑种子不被自动批次删除；
4. 日期、链接、分类、地区、信源层级、来源集中度和最低覆盖量均通过质量门检查；
5. 质量门失败时不覆盖上一版快照。

## GitHub Pages

仓库必须命名为 `No1Lize.github.io`，并在 **Settings → Pages → Source** 中选择 **GitHub Actions**。`.github/workflows/pages.yml` 构建并发布根路径站点；构建失败不会替换上一版。

`.github/workflows/scheduled-sync.yml` 每两小时执行一次，也支持手动选择来源。抓取逻辑或来源配置更新推送到 `main` 时会自动执行一次完整刷新。数据变化由 `github-actions[bot]` 提交，并触发 Pages 再发布。

SEC 建议在 **Settings → Secrets and variables → Actions → Variables** 中设置 `SEC_USER_AGENT`，例如 `No1Lize research contact@example.com`。它不是密钥；未设置时脚本使用仓库主页作为联系信息。

## 数据与合规边界

- 只请求公开、无需登录的页面、RSS、公开 API 或公开索引；
- 不绕过登录、付费墙、验证码、robots 或访问控制；
- 媒体、微信和 X 只保存标题、必要短摘要、时间、分类与原始链接，不复制全文；
- 公开索引的目标链接必须命中配置中的域名白名单；
- 微信索引无合格结果时记录 `empty`，不使用替代内容伪装成功；
- 商业数据库未授权时不伪造接口响应。

## 测试

```bash
npm run lint
npm run test:unit
npm run test:crawler
npm run build:pages
```

## 免责声明

本站用于研究和信息整理，不构成投资建议。热度只表示公开事件和资本活动，不表示投资价值。
