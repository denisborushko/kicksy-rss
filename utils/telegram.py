from __future__ import annotations
"""
Shared Telegram channel parser.
Parses posts from t.me/s/<channel> (public web view).
"""

import os
import re
import aiohttp
from bs4 import BeautifulSoup, NavigableString

NOTIFY_BOT_TOKEN = os.getenv("NOTIFY_BOT_TOKEN")
NOTIFY_CHAT_ID   = os.getenv("NOTIFY_CHAT_ID")


async def notify(session: aiohttp.ClientSession, text: str) -> None:
    """Send a Telegram notification to the owner."""
    if not NOTIFY_BOT_TOKEN or not NOTIFY_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    try:
        await session.post(url, data={"chat_id": NOTIFY_CHAT_ID, "text": text, "parse_mode": "HTML"})
    except Exception:
        pass


def parse_tg_text(el) -> str:
    """Extract plain text from a Telegram message element, preserving line breaks."""
    if el is None:
        return ""
    result = []
    for node in el.children:
        if isinstance(node, NavigableString):
            result.append(str(node))
        elif node.name == "br":
            result.append("\n")
        else:
            result.append(node.get_text())
    text = "".join(result)
    text = re.sub(r'\n{3,}', "\n\n", text)
    return text.strip()


async def fetch_posts(session: aiohttp.ClientSession, channel: str) -> list[dict]:
    """
    Fetch recent posts from a public Telegram channel.

    Returns a list of dicts sorted by post ID (ascending):
        {
            "id":        str,          # post number, e.g. "4120"
            "text":      str,          # post text
            "photos":    list[str],    # photo URLs (CSS background-image)
            "videos":    list[str],    # direct video src URLs
            "has_video": bool,         # True if any video player wrapper found
        }
    """
    url = f"https://t.me/s/{channel}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; KICSYBot/1.0)"}

    async with session.get(url, headers=headers) as r:
        html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for msg in soup.select(".tgme_widget_message"):
        post_id = msg.get("data-post", "").split("/")[-1]
        if not post_id:
            continue

        text_el = msg.select_one(".tgme_widget_message_text")
        text = parse_tg_text(text_el)

        # Photos
        photos = []
        for img in msg.select(".tgme_widget_message_photo_wrap"):
            m = re.search(r"url\('(.+?)'\)", img.get("style", ""))
            if m:
                photos.append(m.group(1))

        # Videos — explicit <video src> and <source src>
        videos = []
        has_video = False
        for vid in msg.select("video"):
            has_video = True
            src = vid.get("src")
            if src:
                videos.append(src)
        for src_el in msg.select("video source"):
            has_video = True
            s = src_el.get("src")
            if s:
                videos.append(s)
        # Video player wrappers (no direct src in t.me/s/ HTML)
        for _ in msg.select(
            ".tgme_widget_message_video_player, "
            ".tgme_widget_message_video_wrap, "
            ".tgme_widget_message_roundvideo_wrap, "
            ".tgme_widget_message_roundvideo, "
            ".tgme_widget_message_video"
        ):
            has_video = True

        posts.append({
            "id":        post_id,
            "text":      text,
            "photos":    list(dict.fromkeys(photos)),
            "videos":    list(dict.fromkeys(videos)),
            "has_video": has_video,
        })

    posts.sort(key=lambda p: int(p["id"]) if p["id"].isdigit() else 0)
    return posts
