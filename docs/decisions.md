# 技术决策

1. GitHub Pages 只承载 Next.js 静态导出，动态数据由外部 API 提供。
2. Render 运行 FastAPI 与调度 Worker，Neon 承载 PostgreSQL。
3. 搜索首版使用 PostgreSQL 全文检索和 `pg_trgm`，不引入向量问答。
4. 实体关系使用外键和 `entity_relations`，不引入图数据库。
5. 构建快照作为 API 故障降级，不把测试数据放进生产页面。
6. 热度公式固定为 `heat-v1`，缺失数据降低完整度，不填随机值。
