from __future__ import annotations
"""
RSS feed generator for Yandex Dzen.
Stores last 50 posts in state/rss_posts.json and renders feed.xml.
"""

import json
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

POSTS_FILE = Path("state/rss_posts.json")
MAX_POSTS  = 50

CHANNEL_TITLE       = "KICKSY"
CHANNEL_DESCRIPTION = "Кроссовки, стритвир, Poizon — всё о культуре кед"
CHANNEL_LINK        = "https://t.me/kicksy_poizon"


def _load() -> list[dict]:
    if POSTS_FILE.exists():
        try:
            return json.loads(POSTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(posts: list[dict]):
    POSTS_FILE.parent.mkdir(exist_ok=True)
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def add_post(post_id: str, text: str, photos: list[str], tg_url: str, vk_url: str = ""):
    """Add a post to the RSS history. Call after successful VK publish."""
    posts = _load()
    # Skip duplicates
    if any(p["id"] == post_id for p in posts):
        return

    title = (text.splitlines()[0] if text.strip() else f"KICKSY | Пост #{post_id}")[:100]

    posts.append({
        "id":      post_id,
        "title":   title,
        "text":    text,
        "photos":  photos,
        "tg_url":  tg_url,
        "vk_url":  vk_url,
        "pubdate": format_datetime(datetime.now(timezone.utc)),
    })

    # Keep newest MAX_POSTS
    posts = sorted(posts, key=lambda p: int(p["id"]) if p["id"].isdigit() else 0, reverse=True)
    _save(posts[:MAX_POSTS])


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _post_to_item(p: dict) -> str:
    title   = _escape(p["title"])
    tg_url  = _escape(p["tg_url"])
    pubdate = _escape(p["pubdate"])

    # Build HTML description
    body = _escape(p["text"]).replace("\n", "<br/>")
    images_html = "".join(
        f'<img src="{_escape(url)}"/>' for url in (p.get("photos") or [])[:4]
    )
    if p.get("vk_url"):
        body += f'<br/><br/><a href="{_escape(p["vk_url"])}">Смотреть в VK</a>'
    body += f'<br/><a href="{tg_url}">Полный пост в Telegram</a>'

    description = f"<![CDATA[{images_html}<p>{body}</p>]]>"

    enclosure = ""
    if p.get("photos"):
        enclosure = f'<enclosure url="{_escape(p["photos"][0])}" type="image/jpeg"/>'

    return f"""
  <item>
    <title>{title}</title>
    <link>{tg_url}</link>
    <guid isPermaLink="false">kicksy-{p["id"]}</guid>
    <pubDate>{pubdate}</pubDate>
    <description>{description}</description>
    {enclosure}
  </item>"""


def build_feed() -> str:
    posts = _load()
    items = "".join(_post_to_item(p) for p in posts)
    now   = format_datetime(datetime.now(timezone.utc))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>{_escape(CHANNEL_TITLE)}</title>
    <link>{_escape(CHANNEL_LINK)}</link>
    <description>{_escape(CHANNEL_DESCRIPTION)}</description>
    <language>ru</language>
    <lastBuildDate>{now}</lastBuildDate>
    {items}
  </channel>
</rss>"""
