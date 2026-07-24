# 技术决策

1. GitHub Pages 承载 Next.js 静态导出，浏览器直接读取公开 JSON。
2. GitHub Actions 负责定时抓取、去重、提交数据与触发重新发布。
3. 不使用 FastAPI、Render、PostgreSQL、Neon、数据库迁移或后台 Worker。
4. 搜索在浏览器端完成；首版数据规模不需要搜索服务器。
5. `public/data/articles.json` 既是公开接口，也是可回退的版本化快照。
6. 热度公式固定为 `heat-v1`，缺失数据降低完整度，不填随机值。
