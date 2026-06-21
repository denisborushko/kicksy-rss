from __future__ import annotations
"""
KICKSY Bot — Telegram → VKontakte
Reposts text, photos (as collage), and videos from a TG channel to a VK group.
"""

import asyncio
import io
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from dotenv import load_dotenv
load_dotenv()
from PIL import Image

from utils.telegram import fetch_posts, notify
from utils import trigger
from utils import rss as rss_store
from utils.gh_pages import push_feed

logger = logging.getLogger("kicksy.vk")

# ── Config (from environment / config.py) ────────────────────────────────────

TG_CHANNEL     = os.getenv("TG_CHANNEL", "kicksy_poizon")
VK_USER_TOKEN  = os.getenv("VK_TOKEN")
VK_GROUP_TOKEN = os.getenv("VK_GROUP_TOKEN")
VK_GROUP_ID    = int(os.getenv("VK_GROUP_ID", "0"))
VK_API_VER     = "5.199"

RUN_HOUR       = int(os.getenv("VK_RUN_HOUR", "23"))        # час запуска (Владивосток)
STATE_FILE     = Path("state/vk_last_post.txt")

VLK_TZ = ZoneInfo("Asia/Vladivostok")

def seconds_until_next_run(hour: int = 23) -> float:
    now    = datetime.now(VLK_TZ)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()

# Collage settings
CELL_SIZE = 600
GAP       = 6
BG_COLOR  = (13, 13, 13)

# ── State ─────────────────────────────────────────────────────────────────────

def load_last_id() -> str | None:
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip() or None
    return None

def save_last_id(post_id: str):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(post_id)

# ── Collage ───────────────────────────────────────────────────────────────────

def make_collage(images: list[bytes], cols: int) -> bytes:
    rows = (len(images) + cols - 1) // cols
    w = cols * CELL_SIZE + (cols - 1) * GAP
    h = rows * CELL_SIZE + (rows - 1) * GAP
    canvas = Image.new("RGB", (w, h), BG_COLOR)
    for i, img_bytes in enumerate(images):
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        iw, ih = img.size
        side = min(iw, ih)
        left = (iw - side) // 2
        top  = (ih - side) // 2
        img  = img.crop((left, top, left + side, top + side))
        img  = img.resize((CELL_SIZE, CELL_SIZE), Image.LANCZOS)
        canvas.paste(img, ((i % cols) * (CELL_SIZE + GAP), (i // cols) * (CELL_SIZE + GAP)))
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()


def choose_photos(photos: list) -> tuple[list, int]:
    if len(photos) >= 9:
        return photos[:9], 3
    elif len(photos) >= 6:
        return photos[:6], 3
    elif len(photos) >= 4:
        return photos[:4], 2
    elif len(photos) >= 2:
        return photos[:2], 2
    return photos[:1], 1

# ── VK API ────────────────────────────────────────────────────────────────────

async def vk(session: aiohttp.ClientSession, token: str, method: str, **params):
    params.update({"access_token": token, "v": VK_API_VER})
    async with session.post(f"https://api.vk.com/method/{method}", data=params) as r:
        data = await r.json(content_type=None)
    if "error" in data:
        raise RuntimeError(f"VK {method}: {data['error']}")
    return data["response"]


async def upload_photo_bytes(session: aiohttp.ClientSession, img_bytes: bytes) -> str:
    srv = await vk(session, VK_USER_TOKEN, "photos.getWallUploadServer", group_id=VK_GROUP_ID)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(img_bytes)
        tmp = f.name
    try:
        with open(tmp, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("photo", f, filename="photo.jpg", content_type="image/jpeg")
            async with session.post(srv["upload_url"], data=form) as r:
                up = await r.json(content_type=None)
        saved = await vk(session, VK_USER_TOKEN, "photos.saveWallPhoto",
                         group_id=VK_GROUP_ID, photo=up["photo"],
                         server=up["server"], hash=up["hash"])
        p = saved[0]
        return f"photo{p['owner_id']}_{p['id']}"
    finally:
        os.unlink(tmp)


async def download_bytes(session: aiohttp.ClientSession, url: str,
                         max_bytes: int = 512 * 1024 * 1024) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; KICSYBot/1.0)"}
    async with session.get(url, headers=headers) as r:
        if r.status != 200:
            raise RuntimeError(f"download {url} → HTTP {r.status}")
        buf = bytearray()
        async for chunk in r.content.iter_chunked(64 * 1024):
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise RuntimeError("video too large")
        return bytes(buf)


async def upload_video_bytes(session: aiohttp.ClientSession, video_bytes: bytes,
                             name: str = "Видео", description: str = "") -> str:
    save = await vk(
        session, VK_USER_TOKEN, "video.save",
        group_id=VK_GROUP_ID,
        name=(name or "Видео")[:128],
        description=(description or "")[:500],
        wallpost=0, is_private=0,
    )
    upload_url = save["upload_url"]
    owner_id   = save["owner_id"]
    video_id   = save["video_id"]
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(video_bytes)
        tmp = f.name
    try:
        with open(tmp, "rb") as fh:
            data = aiohttp.FormData()
            data.add_field("video_file", fh, filename="video.mp4", content_type="video/mp4")
            async with session.post(upload_url, data=data) as r:
                up = await r.json(content_type=None)
        if isinstance(up, dict) and up.get("error"):
            raise RuntimeError(f"video upload error: {up}")
        return f"video{owner_id}_{video_id}"
    finally:
        os.unlink(tmp)

# ── Post logic ────────────────────────────────────────────────────────────────

async def post_to_vk(session: aiohttp.ClientSession, post: dict):
    text = post["text"]
    tg_photo_link = f"\n\n👉 Больше фото в Telegram: https://t.me/{TG_CHANNEL}/{post['id']}"
    tg_video_link = f"\n\n🎬 Смотреть видео в Telegram: https://t.me/{TG_CHANNEL}/{post['id']}"
    attachments = []

    # Photos → collage
    if post["photos"]:
        selected, cols = choose_photos(post["photos"])
        logger.info("Фото: %d → коллаж %dx%d", len(post["photos"]), cols,
                    (len(selected) + cols - 1) // cols)
        img_bytes_list = []
        for url in selected:
            try:
                async with session.get(url) as r:
                    img_bytes_list.append(await r.read())
            except Exception as e:
                logger.warning("Не скачалось фото: %s", e)
        if img_bytes_list:
            collage = make_collage(img_bytes_list, cols)
            att = await upload_photo_bytes(session, collage)
            attachments.append(att)
            logger.info("Коллаж загружен: %s", att)
            text += tg_photo_link

    # Video
    has_video = post.get("has_video") or bool(post.get("videos"))
    if has_video:
        uploaded = False
        for vurl in (post.get("videos") or []):
            try:
                logger.info("Качаю видео: %s", vurl[:80])
                vbytes = await download_bytes(session, vurl)
                logger.info("Загружаю в VK (%d KB)...", len(vbytes) // 1024)
                vatt = await upload_video_bytes(
                    session, vbytes,
                    name=(text.splitlines()[0] if text.strip() else f"Пост {post['id']}"),
                    description=f"Источник: https://t.me/{TG_CHANNEL}/{post['id']}",
                )
                attachments.append(vatt)
                logger.info("Видео загружено: %s", vatt)
                uploaded = True
                break
            except Exception as e:
                logger.warning("Не получилось залить видео: %s", e)
        if tg_video_link not in text and tg_photo_link not in text:
            text += tg_video_link
        if not uploaded:
            logger.info("Фолбэк: только ссылка на Telegram (видео не залилось)")

    result = await vk(session, VK_USER_TOKEN, "wall.post",
                      owner_id=f"-{VK_GROUP_ID}", from_group=1,
                      message=text, attachments=",".join(attachments))
    vk_post_id = result.get("post_id", "")
    vk_link    = f"https://vk.com/wall-{VK_GROUP_ID}_{vk_post_id}" if vk_post_id else ""
    logger.info("✅ Пост #%s опубликован в VK → %s", post["id"], vk_link)

    # Обновляем RSS и пушим на GitHub Pages
    tg_url = f"https://t.me/{TG_CHANNEL}/{post['id']}"
    rss_store.add_post(post["id"], post["text"], post.get("photos", []), tg_url, vk_link, post.get("videos", []))
    await push_feed(rss_store.build_feed())

    preview = (post["text"] or "")[:80].replace("\n", " ")
    await notify(session, f"✅ <b>VK</b> | Пост #{post['id']} опубликован\n{preview}\n\n🔗 VK: {vk_link}\n📢 TG: {tg_url}")

# ── Main loop ─────────────────────────────────────────────────────────────────

async def run():
    logger.info("VK бот запущен | канал @%s | запуск в %02d:00 (Владивосток)", TG_CHANNEL, RUN_HOUR)
    async with aiohttp.ClientSession() as session:
        while True:
            trigger.force_vk.clear()
            wait = seconds_until_next_run(RUN_HOUR)
            next_run = datetime.now(VLK_TZ) + timedelta(seconds=wait)
            logger.info("VK: следующая проверка в %s (Владивосток)", next_run.strftime("%Y-%m-%d %H:%M"))
            try:
                await asyncio.wait_for(trigger.force_vk.wait(), timeout=wait)
                logger.info("VK: принудительный запуск по команде из Telegram")
            except asyncio.TimeoutError:
                pass

            try:
                posts = await fetch_posts(session, TG_CHANNEL)
                last_id = load_last_id()
                new_posts = [
                    p for p in posts
                    if last_id is None or (p["id"].isdigit() and int(p["id"]) > int(last_id))
                ]
                if not new_posts:
                    logger.info("VK: новых постов нет (последний #%s)", last_id)
                else:
                    logger.info("VK: найдено новых постов: %d", len(new_posts))
                    for post in new_posts:
                        await post_to_vk(session, post)
                        save_last_id(post["id"])
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error("VK бот: ошибка: %s", e, exc_info=True)
                await notify(session, f"❌ <b>VK</b> | Ошибка публикации\n{e}")
