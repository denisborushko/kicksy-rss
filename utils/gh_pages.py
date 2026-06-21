from __future__ import annotations
"""
Pushes feed.xml to the gh-pages branch of the kicksy-rss repo.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("kicksy.ghpages")

REPO_URL = "https://github.com/denisborushko/kicksy-rss.git"
WORK_DIR = Path(tempfile.gettempdir()) / "kicksy-ghpages"


async def _git(*args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(WORK_DIR),
    )
    out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
    return proc.returncode, out.decode()


async def push_feed(xml: str) -> bool:
    """Write feed.xml and push to gh-pages. Returns True on success."""
    try:
        WORK_DIR.mkdir(parents=True, exist_ok=True)

        if not (WORK_DIR / ".git").exists():
            proc = await asyncio.create_subprocess_exec(
                "git", "clone", "--branch", "gh-pages", "--single-branch",
                REPO_URL, str(WORK_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode != 0:
                logger.warning("gh-pages clone failed: %s", out.decode()[:300])
                return False
        else:
            await _git("pull", "--rebase", "origin", "gh-pages")

        (WORK_DIR / "feed.xml").write_text(xml, encoding="utf-8")

        await _git("config", "user.email", "bot@kicksy.ru")
        await _git("config", "user.name", "KICKSY Bot")
        await _git("add", "feed.xml")

        code, out = await _git("commit", "-m", "Update RSS feed")
        if code != 0 and "nothing to commit" in out:
            return True

        code, out = await _git("push", "origin", "gh-pages")
        if code != 0:
            logger.warning("gh-pages push failed: %s", out[:300])
            return False

        logger.info("RSS feed опубликован → https://denisborushko.github.io/kicksy-rss/feed.xml")
        return True

    except Exception as e:
        logger.error("gh_pages push error: %s", e)
        return False
