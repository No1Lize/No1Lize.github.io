# 用户新增赛道的统一处理管线

## 目标

任何通过 `config/user_tracking.json` 或网站管理后台新增的赛道，都必须在不修改页面代码、不新增迁移脚本、不修改 GitHub Actions 的前提下完成以下工作：

1. 生成稳定的 `/technology/<slug>/` 静态路由；
2. 进入公开新闻、论文、人物和公司事件搜索；
3. 生成赛道定义、子方向、产业链、中美视角、研究变量和风险；
4. 根据事件数量、来源数量和配置完整度计算热度与完整度；
5. 通过单元测试、页面内容检查和全站内部链接检查后才能部署。

## 统一数据流

```text
user_tracking.json
        ↓
normalizeTrackingConfig
        ↓
track name / keywords / people / sampleCompanies
        ↓
┌────────────────────────┬────────────────────────┐
│ crawl_with_tracking.py │ tracked-sectors.ts     │
│ 生成搜索与人物来源       │ 聚合事件与统计指标       │
└────────────────────────┴────────────────────────┘
        ↓                          ↓
articles.json              sector-profile-generator.ts
        └──────────────────────────┘
                     ↓
          /technology/<slug>/
```

## 页面画像生成优先级

`resolveSectorDefinition()` 使用以下优先级：

1. 赛道名称、关键词、样本公司、人物和已抓事件生成的通用画像；
2. `sector-definitions.ts` 中已有的人工增强内容；
3. 人工增强只覆盖专业表述，不能决定页面是否存在。

因此，未出现在 `sector-definitions.ts` 中的新赛道仍然必须得到完整页面。人工增强定义属于内容质量优化，不属于路由或抓取前置条件。

## 通用画像必须包含

- 赛道定义；
- 至少四个子方向或分析维度；
- 基础研究、关键技术与供应链、系统集成与工程验证、商业部署与治理四层产业链；
- 中国和美国两个市场视角；
- 核心性能、工程化、样本公司、关键人物、融资和监管等研究变量；
- 技术路线、工程周期、资本开支、供应链和证据覆盖风险。

## 禁止的实现方式

禁止增加以下形式的逻辑：

```text
tools/enrich_fusion_tracking.py
tools/enrich_quantum_tracking.py
tools/enrich_<any-sector>.py
```

也禁止在工作流中按赛道名称执行迁移。赛道特有内容只能作为可选的人工增强定义或用户配置保存，不能成为生成页面和抓取数据的必要条件。

## 回归检查

- `tests/sector-profile-generator.test.ts`：验证可控核聚变、脑机接口、低空经济、合成生物等任意名称都能生成完整画像；
- `tests/test_generic_track_routing.py`：验证任意赛道都能生成爬虫来源；
- `scripts/validate-tracking-pages.mjs`：验证每个启用赛道都有页面，并包含产业链、研究变量、风险和公开事件模块；
- `scripts/validate-static-links.mjs`：验证静态产物中的内部链接均有真实目标。
