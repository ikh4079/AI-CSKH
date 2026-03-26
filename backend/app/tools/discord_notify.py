import httpx

from app.core.config import get_settings

settings = get_settings()


async def send_discord_notification(content: str) -> bool:
    if not settings.discord_webhook_url:
        return False

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(settings.discord_webhook_url, json={"content": content})
        response.raise_for_status()
    return True
