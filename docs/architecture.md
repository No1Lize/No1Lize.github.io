# 架构

## 系统边界

```text
GitHub Actions 定时任务
        │
        ├── 9 个公司官方新闻/投资者关系页面
        ├── SEC EDGAR submissions
        └── SEC Company Facts
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
2. 解析标题、摘要、发布日期、公司、事件类型和原始链接；
3. 从 SEC 提取最近申报及带报告期、表单口径的财务指标；
4. 规范化 URL，并用来源链接与事件指纹双重去重；
5. 合并仓库中已有的人工核验记录；
6. 仅在内容变化时写入 `public/data/articles.json`；
7. GitHub Actions 提交更新，并显式启动 Pages 工作流。

## 降级

浏览器优先直接读取 `/data/articles.json`。若请求失败，前端使用同一 JSON 在构建时打包的快照，不显示空白或虚构数据。
