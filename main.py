"""
KICKSY Agent — единая точка запуска всех ботов.

Запускает все боты конкурентно в одном asyncio event loop.
Добавление нового бота: импортировать и добавить run() в BOTS.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────

Path("logs").mkdir(exist_ok=True)
log_file = f"logs/kicksy-{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("kicksy")

# ── Боты ─────────────────────────────────────────────────────────────────────
# Чтобы добавить нового бота: импортировать модуль и добавить его run() в список

from utils import trigger
from bots.vk_bot      import run as run_vk
from bots.youtube_bot import run as run_youtube
from bots.admin_bot   import run as run_admin

BOTS = [
    ("VK Poster",      run_vk),
    ("YouTube Poster", run_youtube),
    ("Admin Bot",      run_admin),
    # ("Article Writer", run_articles),   # будущие боты
    # ("Dzen Poster",   run_dzen),
]

# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    trigger.init()
    logger.info("=" * 50)
    logger.info("🚀 KICKSY Agent запущен (%d ботов)", len(BOTS))
    for name, _ in BOTS:
        logger.info("   • %s", name)
    logger.info("=" * 50)

    tasks = [asyncio.create_task(run(), name=name) for name, run in BOTS]
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлен вручную (Ctrl+C)")
