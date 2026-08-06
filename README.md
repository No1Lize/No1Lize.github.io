# 丽泽路1号（VCIQ）

面向中美新兴科技与一级市场研究的公开、只读、原始信源优先网站。生产站点部署在 GitHub Pages；仓库中的已审核 JSON 是公开页面的唯一数据来源。

## 公开研究范围

站点的一级研究对象固定为四类：

| 研究对象 | 公开入口 | 研究重点 |
| --- | --- | --- |
| 核心技术 | `/technologies/` | 技术路线、性能、成本、工程成熟度与替代关系 |
| 核心赛道 | `/technology/` | 产业结构、供需、资本活动、政策与关键瓶颈 |
| 核心人物 | `/people/` | 身份、职务、公开观点、研究成果与组织关系 |
| 核心公司 | `/companies/` | 产品、技术、团队、融资、客户与商业化进展 |

投资机构、监管披露、融资事件、研究报告和媒体报道属于证据与关系层，用于支持上述四类对象，不作为新的一级对象。研究助手、收藏、搜索和公开追踪页是辅助入口。

## 架构边界

- **公开站点只读。** 浏览器端不持有仓库写入凭证，也不直接修改配置或生产数据。
- **自动任务在 GitHub Actions 内运行。** 抓取、解析、质量门、提交和部署相互分离。
- **失败保留上一版。** 生产任务默认采用 `retain-last-good`，质量门失败不会覆盖已发布快照。
- **静态发布可复核。** Pages 构建固定到触发它的 Git SHA，构建过程不得修改 `config/` 或 `public/data/`。
- **模型不能绕过证据。** Research Agent 对模型输出执行证据 ID 校验；模型不可用时发布透明的确定性降级结果。

## 自动化控制面与数据溯源

自动任务的统一契约位于：

```text
config/automation_jobs.json
```

每个任务声明：

- 唯一 `jobId`、负责人和对应 Workflow；
- 触发方式、计划时间和依赖关系；
- 输入、输出、共享产物和新鲜度 SLA；
- 超时、重试、失败策略和质量门。

控制面实现：

```text
tools/run_pipeline.py
tools/build_pipeline_health.py
```

公开溯源快照：

```text
public/data/data_lineage.json
public/data/pipeline_health.json
```

`data_lineage.json` 记录每个受管产物的 SHA-256、字节数、数据时间、生产任务、运行 ID、代码 SHA、来源 Ref 和质量门状态。`pipeline_health.json` 按任务汇总缺失、过期、降级和健康状态。

Pages 部署会在 `out/` 中重新计算当前提交对应的健康与溯源快照，并生成：

```text
out/build-provenance.json
```

因此公开部署可以同时追溯到源代码提交、控制面版本和被部署的数据快照。

### 控制面命令

```bash
# 校验注册表、已提交的溯源合同和四对象范围
npm run validate:pipeline

# 为某个生产任务建立运行上下文
python3 tools/run_pipeline.py start public-intelligence-full-refresh \
  --output /tmp/vciq-run.json

# 仅在原有质量门通过后更新溯源和健康快照
python3 tools/run_pipeline.py finalize public-intelligence-full-refresh \
  --context /tmp/vciq-run.json \
  --quality-gate passed

# 只重算观察快照，不执行任何爬虫
python3 tools/run_pipeline.py refresh

# 为静态部署生成构建溯源
python3 tools/run_pipeline.py build-provenance \
  --output out/build-provenance.json
```

## 主要自动任务

生产计划以 `config/automation_jobs.json` 和对应 Workflow 为准，主要包括：

- 每两小时检查公开情报变化；
- 每日执行完整、带质量门的公开情报刷新；
- 每日刷新核心公司档案；
- 每周扩展追踪实体与公开信源；
- 每周刷新科创板招股书投资者证据；
- 数据变化后重建机构证据层；
- 完整刷新成功后生成每日研究摘要；
- 每月生成信源效能审查；
- 任何已审核数据提交后执行只读 Pages 构建与部署。

## 本地开发

要求 Node.js 22.13+、Python 3.12。

```bash
npm ci
npm run dev
```

完整检查：

```bash
npm run lint
npm run test:unit
npm run test:crawler
npm run build:pages
```

生成静态站：

```bash
npm run build:pages
```

## 数据更新原则

1. 只访问公开、无需登录的网页、RSS、公开 API 或公开索引。
2. 不绕过登录、付费墙、验证码、robots 或访问控制。
3. 媒体与社交来源只保存研究所需的标题、短摘要、时间、分类和原始链接，不复制全文。
4. 新数据必须通过实体归属、链接、日期、来源层级、覆盖量和隐私质量门。
5. 单一来源失败时保留其上一版成功数据。
6. 纯时间戳或运行噪声不触发数据提交。
7. 自动发现与模型分析不能越过人工审核或公开发布边界。

SEC 抓取建议在仓库 Variables 中设置 `SEC_USER_AGENT`，内容应包含可联系的研究用途标识。该变量不是密钥。

## 免责声明

本站用于公开资料整理与研究，不构成投资建议。热度和事件数量只反映公开信息活动，不代表投资价值。
