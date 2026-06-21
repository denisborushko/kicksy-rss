from __future__ import annotations
import asyncio

force_vk: asyncio.Event = None  # type: ignore
force_yt: asyncio.Event = None  # type: ignore


def init():
    global force_vk, force_yt
    force_vk = asyncio.Event()
    force_yt = asyncio.Event()
