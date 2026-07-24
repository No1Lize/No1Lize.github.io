# 架构

## 系统边界

```text
GitHub Pages 静态前端
        │ HTTPS / 失败时使用构建快照
        ▼
Render FastAPI 公共只读 API
        │
        ├── Neon PostgreSQL
        ├── Render 定时 Worker
        ├── 官方来源 Adapter
        └── GitHub Actions 重新构建
```

前端没有用户身份、管理后台、AI 对话入口或知识图谱。内部同步接口只允许持有 Secret 的任务调用。

## 数据流

1. Adapter 只请求白名单中的公开来源；
2. 保存来源文档元数据和内容哈希；
3. URL 规范化与事件指纹去重；
4. 实体别名消歧；
5. 高等级来源形成主值，冲突值独立保存；
6. 写入 PostgreSQL 并记录任务运行；
7. 生成公开 JSON 快照；
8. 触发 GitHub Pages 新构建。

## 降级

API 未配置或不可用时，前端仍可使用构建时生成的 `data/public/dashboard.json`。页面应标记最后成功更新时间，而不是显示空白或假数据。
