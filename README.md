# 丽泽路1号

公开访问、以原始信源为优先的中美新兴科技与创投情报网站。

## 当前范围

- 一个情报首页、六个核心频道和全局搜索；
- 51 家真实中美科技公司、20 家投资机构、15 家上市跟踪公司；
- 巴菲特、芒格、段永平、李录四个人物档案，每人至少五条材料索引；
- 10 个赛道、5 篇结构化研究报告和首批官方事件；
- FastAPI 公共只读 API、PostgreSQL/Alembic 数据层；
- OpenAI 官方页面和 SEC EDGAR 首批自动同步 Adapter；
- GitHub Pages、Render、Neon 与定时任务配置。

正式数据不包含随机生成的融资、估值、财务或引语。缺失字段保留空状态。

## 本地运行

前端：

```bash
npm install
npm run dev
```

生成 GitHub Pages 静态站：

```bash
npm run build:pages
```

后端与本地 PostgreSQL：

```bash
docker compose up --build
```

公共 API 默认位于 `http://localhost:8000/api/v1/status`。

## 内容与数据命令

```bash
npm run snapshot
python -m tools.sync --source openai
python -m tools.sync --source sec
python -m tools.recalculate_heat
```

研究报告和人物人工材料应进入 `content/`，修改通过 Git 提交审阅。实体合并、冲突裁决和修订应写入 `data_revisions`，不得直接覆盖有来源的历史值。

## GitHub Pages

仓库必须命名为 `No1Lize.github.io`，并在 **Settings → Pages → Source** 中选择 **GitHub Actions**。`.github/workflows/pages.yml` 会构建静态导出并发布根路径站点；构建失败不会执行部署步骤，因此保留上一版。

设置仓库变量：

- `NEXT_PUBLIC_API_BASE_URL`：Render API 地址；
- `API_BASE_URL`：定时任务调用的同一地址。

设置仓库密钥：

- `INTERNAL_SYNC_SECRET`：与 Render 环境变量一致。

## 后端上线

推荐组合为 Render + Neon：

1. 在 Neon 新建 PostgreSQL 数据库，复制池化连接串；
2. 在 Render 使用仓库根目录的 `render.yaml` 创建 Web Service 和 Worker；
3. 配置 `DATABASE_URL`、`SEC_USER_AGENT` 和可选 `GITHUB_TOKEN`；
4. Render 启动命令会先执行 `alembic upgrade head`；
5. 将 Render 地址写入 GitHub 仓库变量并重新运行 Pages 工作流。

完整说明见 [部署文档](docs/deployment.md)。

## 数据边界

首版已接入或配置的一级来源包括公司官网、机构官网、SEC EDGAR、上交所、深交所和港交所披露易。Crunchbase、IT 桔子、企名片、Wind 等商业数据源未授权，因此没有伪造 Adapter 或接口响应。网站不会绕过登录、付费墙、验证码或访问控制。

## 测试

```bash
npm run lint
npm run test:unit
npm run build:pages
pytest backend/tests
ruff check backend workers tools
```

## 免责声明

本站用于研究和信息整理，不构成投资建议。热度只表示公开事件和资本活动，不表示投资价值。
