# 信源效能与误归属抽查指南

## 目的

信源等级描述证据强度，信源效能指标描述抓取和发布表现。两者不能互相替代。A/B 级来源即使抓取不稳定，也不会被系统自动停用；C/D 级来源达到阈值后只进入人工审查候选，系统不会自动删除配置。

## 自动指标

每个来源保留最近 30 次运行样本：

- `availabilityRate`：来源可访问、可解析且未沿用旧快照的运行比例；
- `productiveRate`：产生至少一条合格记录的运行比例；
- `validYieldRate`：合格记录数除以扫描候选数；
- `duplicateRate`：已接受候选在最终发布去重阶段被移除的比例；
- `averageDiscoveryLagDays`：来源发布日期到站点首次发现日期的平均日历天数；
- `publicationRate`：非隔离候选最终进入公开快照的比例。

隔离记录计入 `withheldCount`，不计为重复记录。

## 人工抽查

人工抽查写入 `config/source_quality_reviews.json`。每个来源每个月最多一条记录，字段如下：

```json
{
  "sourceId": "source-id",
  "period": "2026-08",
  "reviewedRecords": 20,
  "misattributedRecords": 1,
  "confirmedDuplicateRecords": 2,
  "reviewer": "github-login",
  "reviewedAt": "2026-08-31T10:00:00Z",
  "notes": "说明样本范围、误归属原因和处理建议"
}
```

抽样要求：

1. 至少检查 20 条可追溯记录；
2. 对照原始 URL、标题、主体、事件类型和机构/公司归属；
3. `misattributedRecords` 只统计主体或事件归属错误，不统计单纯摘要措辞差异；
4. `confirmedDuplicateRecords` 只统计人工确认的同一事件或同一原文重复；
5. 记录抽样范围和异常模式，不得只填写结论。

## 建议状态

- `retain`：指标未触发审查；
- `insufficient-data`：运行样本不足；
- `monitor`：需要观察或修复，但不建议下线；
- `downgrade-candidate`：C/D 级来源同时触发多个低效指标，应降低抓取优先级或修复适配器；
- `retire-candidate`：C/D 级来源长期不可用且无有效产出，可在人工确认后移除。

停用或降级前，必须检查是否存在 URL 失效、适配器错误、重复配置、错误证据等级或临时网络限制。月度工作流只生成审查清单，不执行删除。
