# 专业投融资与工商数据源

创业案例页可选接入企查查、天眼查和鲸准，用于补充融资轮次、金额、投资方、工商登记、股东出资、股权变更和对外投资信息。

## 合规边界

- 不抓取登录后网页，不绕过验证码、访问频率控制或付费墙。
- 企查查与天眼查只通过各自正式开放平台 API 调用。
- 鲸准仅发现搜索引擎已公开索引且可直接打开的页面；此类记录标记为待交叉验证。
- 没有可核对来源时保留空状态，不生成推测股比、金额或投资方。

## GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中配置：

| Secret | 用途 |
|---|---|
| `QCC_APP_KEY` | 企查查开放平台 AppKey |
| `QCC_SECRET_KEY` | 企查查开放平台 SecretKey |
| `TIANYANCHA_TOKEN` | 天眼查开放平台 Authorization Token |

## GitHub Variables

| Variable | 默认行为 | 说明 |
|---|---|---|
| `PROFESSIONAL_SOURCE_ENABLE_PAID` | `false` | 只有设为 `true` 才调用企查查、天眼查付费 API |
| `PROFESSIONAL_SOURCE_PUBLIC_DISCOVERY` | `true` | 是否发现鲸准公开页面 |
| `PROFESSIONAL_SOURCE_MAX_COMPANIES` | `20` | 每轮最多处理的中国公司数量，最高 30 |
| `PROFESSIONAL_SOURCE_COMPANY_SLUGS` | 空 | 逗号分隔的公司 slug 白名单；建议付费试运行时明确设置 |
| `PROFESSIONAL_SOURCE_INCLUDE_EXTERNAL_INVESTMENTS` | `false` | 是否调用企查查对外投资接口 |
| `PROFESSIONAL_SOURCE_INCLUDE_BENEFICIARIES` | `false` | 是否调用天眼查最终受益人接口 |

## 建议的付费试运行配置

首次启用时使用：

```text
PROFESSIONAL_SOURCE_ENABLE_PAID=true
PROFESSIONAL_SOURCE_MAX_COMPANIES=1
PROFESSIONAL_SOURCE_COMPANY_SLUGS=agibot
PROFESSIONAL_SOURCE_INCLUDE_EXTERNAL_INVESTMENTS=false
PROFESSIONAL_SOURCE_INCLUDE_BENEFICIARIES=false
```

确认接口套餐、字段映射和单次费用后，再逐步扩大公司白名单。不要在未确认套餐计费规则时直接对全部公司启用可选接口。

## 页面字段

公司详情页新增“股权与工商核验”部分，显示：

- 工商登记名称、统一社会信用代码、登记状态；
- 法定代表人、注册资本、实缴资本；
- 股东、持股比例、认缴与实缴出资；
- 最终受益人与实际控制线索；
- 股东和股权变更；
- 可选的对外投资及持股；
- 企查查、天眼查、鲸准各自的执行状态和结构化记录数量。

两家专业数据库同时提供一致的可核对事实时，页面标记为“至少两个专业来源交叉一致”；只有一个来源时标记为“目前仅有一个专业来源”。
