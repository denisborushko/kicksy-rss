import asyncio
import aiohttp
from dotenv import load_dotenv
load_dotenv()
from utils.telegram import notify

async def main():
    async with aiohttp.ClientSession() as session:
        await notify(session, (
            "✅ <b>VK</b> | Пост #4194 опубликован\n"
            "Тестовый пост KICKSY — всё работает!\n\n"
            "🔗 VK: https://vk.com/wall-123456_789\n"
            "📢 TG: https://t.me/kicksy_poizon/4194"
        ))
        print("VK уведомление отправлено")

        await notify(session, (
            "✅ <b>YouTube</b> | Пост #4194 опубликован\n"
            "Тестовый пост KICKSY — всё работает!\n\n"
            "🎬 YT: https://youtube.com/watch?v=ERhRW9dWVKE\n"
            "📢 TG: https://t.me/kicksy_poizon/4194"
        ))
        print("YouTube уведомление отправлено")

        await notify(session, "❌ <b>VK</b> | Ошибка публикации\nTesting error notification")
        print("Ошибка уведомление отправлено")

asyncio.run(main())
