---
layout: default
title: "归档"
description: "丽泽路1号所有情报文章归档，按时间倒序排列。"
permalink: /archive/
---

<div class="archive-page">
  <h1>📂 全部情报归档</h1>
  <p class="archive-intro">共 {{ site.posts.size }} 条情报，按时间倒序排列。</p>

  {% assign posts_by_year = site.posts | group_by_exp: "post", "post.date | date: '%Y'" %}
  
  {% for year_group in posts_by_year %}
    <h2 class="archive-year">{{ year_group.name }}</h2>
    <ul class="archive-list">
      {% for post in year_group.items %}
        <li class="archive-item">
          <span class="archive-date">{{ post.date | date: "%m-%d" }}</span>
          <div class="archive-info">
            <a href="{{ post.url | relative_url }}" class="archive-title">{{ post.title }}</a>
            {% if post.category %}
              <span class="category-tag">{{ post.category }}</span>
            {% endif %}
          </div>
        </li>
      {% endfor %}
    </ul>
  {% endfor %}
</div>

<style>
.archive-page h1 {
  margin-bottom: 8px;
}
.archive-intro {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-bottom: 32px;
}
.archive-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
