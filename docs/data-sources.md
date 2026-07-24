# 数据来源

## 已接入

| 来源 | 类型 | 方式 | 等级 | 默认频率 |
|---|---|---|---:|---|
| OpenAI、Anthropic、Figure、xAI | 公司官网 | 公开 HTML | 2 | 每 2 小时 |
| Pony.ai、WeRide 投资者关系 | 公司公告 | 公开 HTML | 2 | 每 2 小时 |
| Rocket Lab、IonQ、CATL | 公司官网 | 公开 HTML | 2 | 每 2 小时 |
| SEC EDGAR submissions | 监管文件 | 公开 JSON | 1 | 每 2 小时检查 |
| SEC Company Facts | 监管财务数据 | 公开 JSON | 1 | 每 2 小时检查 |
| 公司与机构官网目录 | 官方资料 | 人工种子 + 后续核验 | 2 | 每周 |
| 上交所、深交所、港交所 | 交易所 | 官方链接与后续 Adapter | 1 | 每日 |

SEC 要求请求提供可联系的 `User-Agent`。建议用 GitHub Actions Variable `SEC_USER_AGENT` 设置站点名和联系邮箱。

## 尚未接入

- Crunchbase、IT 桔子、企名片、Wind：需要商业授权或 API Key；
- 36氪、投资界：目前只作为产品参考和可人工核验的二级来源，不做批量复制；
- Coopinio：缺少明确产品地址，未虚构其页面结构；
- 微信公众号：不绕过平台访问限制，不复制受版权保护全文。

## 冲突

同一规范化来源 URL 只保留一条记录，并使用公司、日期与规范化标题形成第二层事件指纹。人工标记为 `curated` 的标题与摘要优先保留；其他记录使用来源最新元数据更新。
