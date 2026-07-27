# 丽泽路1号｜科技与创投情报站

[![Build and Deploy Jekyll](https://github.com/no1lize/no1lize.github.io/actions/workflows/pages.yml/badge.svg)](https://github.com/no1lize/no1lize.github.io/actions/workflows/pages.yml)

> DAILY INTELLIGENCE DESK · 中美双轨

持续读取公司与监管披露、金融创投媒体、新浪、X、微信公开索引及开放论文数据库，连接中美科技公司的产品、融资、经营、研究与资本市场进展。

## 🛠 技术栈

- **静态站点生成器**：Jekyll 4.x
- **托管**：GitHub Pages
- **搜索**：Pagefind（客户端全文搜索，支持中文）
- **主题**：自定义（CSS 变量驱动亮色/暗色双主题）
- **RSS**：jekyll-feed 插件（全文输出）

## 📁 目录结构

```
.
├── .github/
│   └── workflows/
│       └── pages.yml          # GitHub Actions 自动构建部署
├── _config.yml                 # Jekyll 全局配置
├── _layouts/
│   ├── default.html            # 全站基础布局（导航+Footer）
│   ├── home.html               # 首页布局
│   ├── post.html               # 文章页布局（含信息卡片）
│   ├── category_page.html      # 分类归档布局
│   └── tag_page.html           # 标签归档布局
├── _includes/
│   └── head-seo.html           # SEO 与社交分享标签
├── _posts/                     # 情报文章（Markdown）
│   ├── 2026-07-26-xxx.md
│   ├── 2026-07-25-xxx.md
│   └── ...
├── categories/                 # 赛道分类页
├── assets/
│   ├── css/
│   │   └── main.css           # 主样式表（双主题）
│   ├── js/
│   │   ├── dark-mode.js       # 暗色模式切换
│   │   └── search.js          # Pagefind 与备用搜索逻辑
│   └── images/
│       └── og-default.svg     # 默认 OG 分享图
├── archive.md                  # 归档页
├── tags.md                     # 标签页
├── about.md                    # 关于页
├── index.md                    # 首页
├── pagefind.yml                # Pagefind 索引配置
├── Gemfile                     # Ruby 依赖
└── README.md
```

## ✍️ 文章写作规范

每篇情报文章使用以下 Front Matter 模板：

```yaml
---
title: "文章标题"
date: 2026-07-25
category: "赛道名称"           # AI芯片/大模型/半导体/商业航天/人形机器人
tags: [标签1, 标签2]
company: "公司名"
round: "轮次"                   # 天使轮/Pre-A/A轮/B轮/...
amount: "金额"
lead_investor: "领投方"
follow_investors: ["跟投1", "跟投2"]
business: "业务一句话描述"
source: "信源"
source_url: "https://..."
importance: "为什么这条值得关注（编辑判断）"
description: "SEO描述，≤160字"
---
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| title | ✅ | 文章标题 |
| date | ✅ | ISO 格式日期 |
| category | ✅ | 赛道分类，用于归档 |
| tags | ✅ | 多标签，用于筛选 |
| company | ⭕ | 涉及公司名 |
| round | ⭕ | 融资轮次 |
| amount | ⭕ | 融资金额 |
| lead_investor | ⭕ | 领投方 |
| importance | ✅ | 编辑判断，差异化核心 |
| source | ✅ | 信源（可溯源） |
| description | ✅ | SEO 摘要 |

> ⭕ = 非融资类文章可省略

## 🚀 本地开发

需要预先安装 Ruby 3.2、Bundler 和 Node.js 22。

```bash
# 1. 克隆仓库
git clone https://github.com/no1lize/no1lize.github.io.git
cd no1lize.github.io

# 2. 安装依赖并启动本地服务（带热更新）
bundle install && bundle exec jekyll serve --livereload

# 3. 浏览器访问
# http://127.0.0.1:4000
```

## 🔨 构建与部署

- **自动部署**：推送到 `main` 分支后，GitHub Actions 自动构建并部署到 `gh-pages` 分支
- **手动构建**：`bundle exec jekyll build`，产物在 `_site/` 目录
- **搜索索引**：构建后运行 `npx --yes pagefind@1.5.2 --site _site` 生成搜索索引

本地执行完整生产构建：

```bash
JEKYLL_ENV=production bundle exec jekyll build
npx --yes pagefind@1.5.2 --site _site
```

### GitHub Pages 发布来源

首次推送到 `main`、工作流创建 `gh-pages` 分支后，在仓库 `Settings → Pages → Build and deployment` 中设置：

- **Source**：`Deploy from a branch`
- **Branch**：`gh-pages`
- **Folder**：`/(root)`

工作流只在 `main` 分支 push 时发布；Pull Request 仅执行 Jekyll 构建，不改动线上站点。

## 📋 验收清单

- [ ] GitHub Actions 中 `bundle exec jekyll build` 零错误零警告
- [ ] GitHub Pages Source 已设置为 `gh-pages / (root)`
- [x] 移动端（375px）无横向滚动
- [x] 暗色模式切换正常且刷新后保持
- [x] RSS `feed.xml` 可访问且包含全文
- [x] 搜索框可用（输入关键词能出结果）
- [x] 文章信息卡片正确渲染
- [x] OG meta 标签在页面源码中可见

## ⚠️ 免责声明

本站内容来源于公开信息渠道，仅供研究参考，**不构成任何投资建议**。融资数据以官方公告和工商变更为准，如有出入欢迎指正。

## 📬 联系

- GitHub：[@no1lize](https://github.com/no1lize)
- RSS：[/feed.xml](/feed.xml)
- 邮件订阅：即将上线
