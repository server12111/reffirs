import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

BOTOHUB_VIEWS_URL = "https://views.botohub.me/ad/SendPost"


async def show_botohub_views(user_id: int, hi: bool = False) -> bool:
    """
    Send a BotoHub Views advertisement to the user.
    Called after the user passes all subscription walls.

    hi=True  — greeting mode, only on /start, max once per 24h per user.
    hi=False — regular mode, after meaningful user actions.

    Silent on any error — ads are non-critical.
    """
    if not config.BOTOHUB_VIEWS_KEY:
        return False

    try:
        payload: dict = {"SendToChatId": user_id}
        if hi:
            payload["hi"] = True

        async with aiohttp.ClientSession() as session:
            async with session.post(
                BOTOHUB_VIEWS_URL,
                headers={
                    "Authorization": config.BOTOHUB_VIEWS_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                data = await response.json()
                result = data.get("SendPostResult") if isinstance(data, dict) else None
                if result == 1:
                    logger.debug("BotoHubViews: ad sent to user %s", user_id)
                    return True
                elif result == 2:
                    logger.error("BotoHubViews: revoked token")
                elif result == 3:
                    logger.debug("BotoHubViews: user %s has blocked the bot", user_id)
                elif result == 4:
                    logger.warning("BotoHubViews: too many requests for user %s", user_id)
                else:
                    logger.debug("BotoHubViews: result %s for user %s", result, user_id)

    except Exception as exc:
        logger.warning("BotoHubViews: error for user %s: %s", user_id, exc)
    return False
