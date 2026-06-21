from __future__ import annotations
"""
KICKSY Bot — Telegram → YouTube
Uploads videos from a TG channel to YouTube.
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from utils.telegram import fetch_posts, notify
from utils import trigger

load_dotenv()
logger = logging.getLogger("kicksy.youtube")

# ── Config ────────────────────────────────────────────────────────────────────

TG_CHANNEL     = os.getenv("TG_CHANNEL", "kicksy_poizon")
CLIENT_SECRETS = os.getenv("YT_CLIENT_SECRETS", "client_secrets.json")
TOKEN_FILE     = os.getenv("YT_TOKEN_FILE", "youtube_token.json")
SCOPES         = ["https://www.googleapis.com/auth/youtube.upload"]

RUN_HOUR       = int(os.getenv("YT_RUN_HOUR", "23"))        # час запуска (Владивосток)
STATE_FILE     = Path("state/yt_last_post.txt")

YT_TAGS        = ["KICKSY", "кроссовки", "sneakers", "streetwear", "poizon"]
YT_CATEGORY_ID = "22"   # People & Blogs

# ── Scheduler ────────────────────────────────────────────────────────────────

VLK_TZ = ZoneInfo("Asia/Vladivostok")

def seconds_until_next_run(hour: int = 23) -> float:
    now    = datetime.now(VLK_TZ)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()

# ── State ─────────────────────────────────────────────────────────────────────

def load_last_id() -> str | None:
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip() or None
    return None

def save_last_id(post_id: str):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(post_id)

# ── YouTube auth ──────────────────────────────────────────────────────────────

def get_youtube_client():
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except RefreshError as e:
                logger.warning("Refresh token недействителен (%s). Повторная авторизация...", e)
                try:
                    Path(TOKEN_FILE).unlink()
                except FileNotFoundError:
                    pass
                creds = None
        if not refreshed:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ── Upload ────────────────────────────────────────────────────────────────────

def upload_to_youtube(youtube, video_path: str, title: str, description: str) -> str:
    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        YT_TAGS,
            "categoryId":  YT_CATEGORY_ID,
        },
        "status": {"privacyStatus": "public"},
    }
    media   = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part=",".join(body.keys()), body=body, media_body=media
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Загружено: %d%%", int(status.progress() * 100))
    return response["id"]


async def post_to_youtube(session: aiohttp.ClientSession, post: dict, youtube):
    video_url = post["videos"][0]
    text      = post["text"]
    tg_link   = f"\n\n👉 Полный пост в Telegram: https://t.me/{TG_CHANNEL}/{post['id']}"

    title       = text[:80] if text else f"KICKSY | Пост #{post['id']}"
    description = text + tg_link

    logger.info("Скачиваем видео из поста #%s...", post["id"])
    async with session.get(video_url) as r:
        video_bytes = await r.read()

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        tmp = f.name

    try:
        logger.info("Загружаем на YouTube...")
        video_id = upload_to_youtube(youtube, tmp, title, description)
        logger.info("✅ Пост #%s → https://youtube.com/watch?v=%s", post["id"], video_id)
        preview = (post["text"] or "")[:80].replace("\n", " ")
        await notify(session, f"✅ <b>YouTube</b> | Пост #{post['id']} опубликован\n{preview}\n\n🎬 YT: https://youtube.com/watch?v={video_id}\n📢 TG: https://t.me/{TG_CHANNEL}/{post['id']}")
    finally:
        os.unlink(tmp)

# ── Main loop ─────────────────────────────────────────────────────────────────

async def run():
    logger.info("YouTube бот запущен | канал @%s | запуск в %02d:00 (Владивосток)", TG_CHANNEL, RUN_HOUR)
    try:
        youtube = get_youtube_client()
    except Exception as e:
        logger.error("YouTube авторизация провалилась: %s", e)
        async with aiohttp.ClientSession() as s:
            await notify(s, f"⚠️ <b>YouTube</b> | Требуется переавторизация!\nЗапусти на Mac Mini:\n<code>cd ~/kicksy-agent/kicksy-agent && source venv/bin/activate && python -c \"from dotenv import load_dotenv; load_dotenv()\nfrom google_auth_oauthlib.flow import InstalledAppFlow\nfrom pathlib import Path\nflow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', ['https://www.googleapis.com/auth/youtube.upload'])\ncreds = flow.run_local_server(port=0)\nPath('youtube_token.json').write_text(creds.to_json())\nprint('OK')\"</code>")
        return

    async with aiohttp.ClientSession() as session:
        while True:
            trigger.force_yt.clear()
            wait = seconds_until_next_run(RUN_HOUR)
            next_run = datetime.now(VLK_TZ) + timedelta(seconds=wait)
            logger.info("YT: следующая проверка в %s (Владивосток)", next_run.strftime("%Y-%m-%d %H:%M"))
            try:
                await asyncio.wait_for(trigger.force_yt.wait(), timeout=wait)
                logger.info("YT: принудительный запуск по команде из Telegram")
            except asyncio.TimeoutError:
                pass

            try:
                posts = await fetch_posts(session, TG_CHANNEL)
                video_posts = [p for p in posts if p["videos"]]
                last_id = load_last_id()
                new_posts = [
                    p for p in video_posts
                    if last_id is None or (p["id"].isdigit() and int(p["id"]) > int(last_id))
                ]
                if not new_posts:
                    logger.info("YT: новых видео нет (последний #%s)", last_id)
                else:
                    logger.info("YT: найдено новых видео: %d", len(new_posts))
                    for post in new_posts:
                        await post_to_youtube(session, post, youtube)
                        save_last_id(post["id"])
                        await asyncio.sleep(5)
            except Exception as e:
                logger.error("YouTube бот: ошибка: %s", e, exc_info=True)
                await notify(session, f"❌ <b>YouTube</b> | Ошибка публикации\n{e}")
