# 架构

## 系统边界

```text
GitHub Actions 定时任务
        │
        ├── OpenAI 官方公开页面
        └── SEC EDGAR 公开 JSON
        │
        ▼
public/data/articles.json
        │ 提交到 main
        ▼
GitHub Pages 构建并发布
```

项目没有服务器、数据库、内部 API、用户身份、管理后台、AI 对话入口或知识图谱。

## 数据流

1. 抓取脚本只请求代码中列明的公开来源；
2. 解析标题、摘要、发布日期和原始链接；
3. 规范化 URL，并以原始链接为主键去重；
4. 合并仓库中已有的人工核验记录；
5. 仅在内容变化时写入 `public/data/articles.json`；
6. GitHub Actions 提交更新，并显式启动 Pages 工作流。

## 降级

浏览器优先直接读取 `/data/articles.json`。若请求失败，前端使用同一 JSON 在构建时打包的快照，不显示空白或虚构数据。
