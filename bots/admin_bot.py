from __future__ import annotations
"""
KICKSY Admin Bot — кнопки принудительного постинга в Telegram.
Использует тот же NOTIFY_BOT_TOKEN что и уведомления.
"""

import asyncio
import logging
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()

from utils import trigger

logger = logging.getLogger("kicksy.admin")

BOT_TOKEN = os.getenv("NOTIFY_BOT_TOKEN", "")
ADMIN_ID  = int(os.getenv("NOTIFY_CHAT_ID", "0"))

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def tg_get(session: aiohttp.ClientSession, method: str, **params):
    async with session.get(f"{API}/{method}", params=params,
                           timeout=aiohttp.ClientTimeout(total=60)) as r:
        data = await r.json()
        return data


async def tg_post(session: aiohttp.ClientSession, method: str, **payload):
    async with session.post(f"{API}/{method}", json=payload,
                            timeout=aiohttp.ClientTimeout(total=15)) as r:
        data = await r.json()
        if not data.get("ok"):
            logger.warning("TG API %s: %s", method, data.get("description"))
        return data


async def send_menu(session: aiohttp.ClientSession, chat_id: int):
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "▶️ Постить в VK",      "callback_data": "post_vk"},
                {"text": "▶️ Постить на YouTube", "callback_data": "post_yt"},
            ],
            [
                {"text": "⚡ Везде сразу", "callback_data": "post_all"},
            ],
        ]
    }
    await tg_post(session, "sendMessage",
                  chat_id=chat_id,
                  text="🎛 <b>Панель управления KICKSY</b>\n\nВыбери куда постить прямо сейчас:",
                  parse_mode="HTML",
                  reply_markup=keyboard)


async def handle_update(session: aiohttp.ClientSession, update: dict):
    if msg := update.get("message"):
        user_id = msg["from"]["id"]
        if user_id != ADMIN_ID:
            return
        text = msg.get("text", "")
        if text.startswith("/start") or text.startswith("/menu"):
            await send_menu(session, msg["chat"]["id"])

    elif cb := update.get("callback_query"):
        if cb["from"]["id"] != ADMIN_ID:
            await tg_post(session, "answerCallbackQuery",
                          callback_query_id=cb["id"], text="⛔ Нет доступа")
            return

        chat_id = cb["message"]["chat"]["id"]
        data    = cb.get("data", "")

        if data == "post_vk":
            trigger.force_vk.set()
            await tg_post(session, "answerCallbackQuery",
                          callback_query_id=cb["id"], text="✅ Запускается...")
            await tg_post(session, "sendMessage", chat_id=chat_id,
                          text="⚡ Принудительный постинг в <b>VK</b> запущен.",
                          parse_mode="HTML")

        elif data == "post_yt":
            trigger.force_yt.set()
            await tg_post(session, "answerCallbackQuery",
                          callback_query_id=cb["id"], text="✅ Запускается...")
            await tg_post(session, "sendMessage", chat_id=chat_id,
                          text="⚡ Принудительный постинг на <b>YouTube</b> запущен.",
                          parse_mode="HTML")

        elif data == "post_all":
            trigger.force_vk.set()
            trigger.force_yt.set()
            await tg_post(session, "answerCallbackQuery",
                          callback_query_id=cb["id"], text="✅ Запускается...")
            await tg_post(session, "sendMessage", chat_id=chat_id,
                          text="⚡ Принудительный постинг запущен: <b>VK + YouTube</b>.",
                          parse_mode="HTML")


async def run():
    if not BOT_TOKEN or not ADMIN_ID:
        logger.error("Admin бот: NOTIFY_BOT_TOKEN или NOTIFY_CHAT_ID не заданы")
        return

    logger.info("Admin бот запущен (chat_id=%d)", ADMIN_ID)
    offset = 0

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                resp = await tg_get(session, "getUpdates",
                                    offset=offset, timeout=30,
                                    allowed_updates='["message","callback_query"]')
                for update in resp.get("result", []):
                    offset = update["update_id"] + 1
                    await handle_update(session, update)
            except Exception as e:
                logger.error("Admin бот: %s", e)
                await asyncio.sleep(5)
