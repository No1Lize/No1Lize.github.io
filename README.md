# 丽泽路1号

公开访问、以原始信源为优先的中美新兴科技与创投情报网站。

## 当前范围

- 一个情报首页、六个核心频道和全局搜索；
- 58 家真实中美科技公司、20 家投资机构、15 家上市跟踪公司；
- 巴菲特、芒格、段永平、李录四个人物档案，每人至少五条材料索引；
- 10 个赛道、5 篇结构化研究报告和首批官方事件；
- 9 个公司官方新闻源，以及 10 家美股公司的 SEC EDGAR 文件与 Company Facts 自动抓取；
- GitHub Actions 定时更新公开 JSON；
- GitHub Pages 零服务器静态部署。

## 本地运行

前端：

```bash
npm ci
npm run dev
```

生成 GitHub Pages 静态站：

```bash
npm run build:pages
```

## 内容与数据命令

```bash
npm run crawl
python3 tools/crawl_articles.py --source news
python3 tools/crawl_articles.py --source sec
python3 tools/crawl_articles.py --offline
```

抓取结果写入 `public/data/articles.json`。文件同时包含新闻/事件、SEC 最新申报以及带报告期的财务指标。脚本按规范化来源 URL 和事件指纹去重；没有新内容时不会改写文件或产生无意义提交。

## GitHub Pages

仓库必须命名为 `No1Lize.github.io`，并在 **Settings → Pages → Source** 中选择 **GitHub Actions**。`.github/workflows/pages.yml` 会构建静态导出并发布根路径站点；构建失败不会执行部署步骤，因此保留上一版。

`.github/workflows/scheduled-sync.yml` 每两小时执行一次：

1. 抓取 9 个公司新闻页和 SEC；
2. 合并并去重事件，提取最新监管财务指标；
3. 更新 `public/data/articles.json`；
4. 有变化时由 `github-actions[bot]` 提交到 `main`；
5. 同一任务在提交后启动 Pages 发布。

完整说明见 [部署文档](docs/deployment.md)。

## 数据边界

首版已接入或配置的一级来源包括公司官网、机构官网、SEC EDGAR、上交所、深交所和港交所披露易。Crunchbase、IT 桔子、企名片、Wind 等商业数据源未授权，因此没有伪造 Adapter 或接口响应。网站不会绕过登录、付费墙、验证码或访问控制。

SEC 建议在仓库 **Settings → Secrets and variables → Actions → Variables** 中设置 `SEC_USER_AGENT`，例如 `No1Lize research contact@example.com`。这不是密钥；未设置时脚本会使用仓库主页作为联系信息。

## 测试

```bash
npm run lint
npm run test:unit
npm run test:crawler
npm run build:pages
```

## 免责声明

本站用于研究和信息整理，不构成投资建议。热度只表示公开事件和资本活动，不表示投资价值。
