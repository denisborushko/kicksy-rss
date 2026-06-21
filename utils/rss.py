from __future__ import annotations
"""
RSS feed generator compatible with Yandex Dzen requirements.
Stores last 50 posts in state/rss_posts.json and renders feed.xml.
"""

import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

POSTS_FILE = Path("state/rss_posts.json")
MAX_POSTS  = 50

CHANNEL_TITLE       = "KICKSY"
CHANNEL_LINK        = "https://t.me/kicksy_poizon"
CHANNEL_DESCRIPTION = "Кроссовки, стритвир, Poizon — всё о культуре кед"


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


def add_post(post_id: str, text: str, photos: list[str],
             tg_url: str, vk_url: str = "", videos: list[str] | None = None):
    posts = _load()
    if any(p["id"] == post_id for p in posts):
        return

    title = (text.splitlines()[0] if text.strip() else f"KICKSY | Пост #{post_id}")[:100]

    posts.append({
        "id":      post_id,
        "title":   title,
        "text":    text,
        "photos":  photos or [],
        "videos":  videos or [],
        "tg_url":  tg_url,
        "vk_url":  vk_url,
        "pubdate": format_datetime(datetime.now(timezone.utc)),
    })

    posts = sorted(posts, key=lambda p: int(p["id"]) if p["id"].isdigit() else 0, reverse=True)
    _save(posts[:MAX_POSTS])


def _x(s: str) -> str:
    """Escape XML special chars."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _build_content(p: dict) -> str:
    """Build content:encoded HTML per Dzen spec."""
    lines = []

    # Title as h2 inside content
    lines.append(f"<h2>{p['title']}</h2>")

    # Images as figure/img
    for url in p.get("photos") or []:
        lines.append(f'<figure><img src="{url}"/></figure>')

    # Videos
    for url in p.get("videos") or []:
        lines.append(f'<video><source src="{url}" type="video/mp4"/></video>')

    # Text paragraphs
    if p.get("text"):
        for para in p["text"].split("\n\n"):
            para = para.strip()
            if para:
                lines.append(f"<p>{para.replace(chr(10), '<br/>')}</p>")

    # Links
    if p.get("vk_url"):
        lines.append(f'<p><a href="{p["vk_url"]}">Смотреть пост в VK</a></p>')
    lines.append(f'<p><a href="{p["tg_url"]}">Полный пост в Telegram</a></p>')

    return "\n".join(lines)


def _post_to_item(p: dict) -> str:
    title   = _x(p["title"])
    link    = _x(p["tg_url"])
    guid    = f"kicksy-{p['id']}"
    pubdate = _x(p["pubdate"])
    desc    = _x((p.get("text") or "")[:200].replace("\n", " "))

    # Cover image enclosure
    enclosure = ""
    if p.get("photos"):
        enclosure = f'\n    <enclosure url="{_x(p["photos"][0])}" type="image/jpeg"/>'

    # format-post for short content, format-article for longer
    text_len = len(p.get("text") or "")
    fmt = "format-post" if (text_len < 600 and len(p.get("photos") or []) <= 10) else "format-article"

    content = _build_content(p)

    return f"""
  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid isPermaLink="false">{guid}</guid>
    <pubDate>{pubdate}</pubDate>
    <description>{desc}</description>
    <category>{fmt}</category>
    <category>index</category>
    <category>comment-all</category>
    <media:rating scheme="urn:simple">nonadult</media:rating>{enclosure}
    <content:encoded><![CDATA[{content}]]></content:encoded>
  </item>"""


def build_feed() -> str:
    posts = _load()
    items = "".join(_post_to_item(p) for p in posts)
    now   = format_datetime(datetime.now(timezone.utc))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:media="http://search.yahoo.com/mrss/"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_x(CHANNEL_TITLE)}</title>
    <link>{_x(CHANNEL_LINK)}</link>
    <description>{_x(CHANNEL_DESCRIPTION)}</description>
    <language>ru</language>
    <lastBuildDate>{now}</lastBuildDate>
    {items}
  </channel>
</rss>"""
