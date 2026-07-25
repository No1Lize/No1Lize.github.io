#!/usr/bin/env python3
"""Keep capital news out of the project-background research layer."""

from __future__ import annotations

from pathlib import Path


ENRICHER = Path(__file__).with_name("enrich_venture_profiles.py")


def main() -> None:
    text = ENRICHER.read_text(encoding="utf-8")
    old = '''    aliases = company.aliases
    article_values = [
        f"{article.get('title', '')}。{article.get('summary', '')}"
        for article in articles[:20]
    ]
    raw_background = profile.get("background", "")
'''
    new = '''    aliases = company.aliases
    background_articles = []
    for article in articles[:30]:
        article_type = clean_text(article.get("type"), 60)
        article_text = clean_text(
            f"{article.get('title', '')} {article.get('summary', '')}", 1600
        )
        if article_type in {"融资", "产业投资", "IPO", "并购", "监管文件"}:
            continue
        if re.search(
            r"\\b(?:funding|financing|raises?|raised|ipo|listing|acquired|acquisition|merger)\\b|"
            r"融资|募资|领投|跟投|上市|挂牌|收购|并购|退出|估值",
            article_text,
            re.IGNORECASE,
        ):
            continue
        background_articles.append(article)
    article_values = [
        f"{article.get('title', '')}。{article.get('summary', '')}"
        for article in background_articles[:20]
    ]
    raw_background = profile.get("background", "")
'''
    if new not in text:
        if old not in text:
            raise SystemExit("project background article filter anchor not found")
        ENRICHER.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("capital news exclusion: applied")
    else:
        print("capital news exclusion: already applied")
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
