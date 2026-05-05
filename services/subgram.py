import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

SUBGRAM_URL = "https://api.subgram.org"


async def get_subgram_sponsors(user_id: int, max_sponsors: int = 5, user=None) -> list[dict]:
    """
    Fetch unsubscribed Subgram sponsors for the user.

    Returns list of sponsor dicts:
        [{"link": str, "title": str, "button_text": str, "ads_id": str}, ...]
    Returns [] if SUBGRAM_KEY not set, service unavailable, or all subscribed.
    """
    if not config.SUBGRAM_KEY:
        return []

    headers = {
        "Auth": config.SUBGRAM_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "user_id": user_id,
        "chat_id": user_id,
        "action": "subscribe",
        "max_sponsors": max(1, min(max_sponsors, 10)),
        "get_links": 1,
    }
    if user:
        payload["first_name"] = getattr(user, "first_name", "") or ""
        payload["username"] = getattr(user, "username", "") or ""
        payload["language_code"] = getattr(user, "language_code", "ru") or "ru"
        payload["is_premium"] = bool(getattr(user, "is_premium", False))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SUBGRAM_URL}/get-sponsors",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Subgram get-sponsors: HTTP %s for user %s | body: %s", resp.status, user_id, body[:300])
                    return []

                data = await resp.json()
                if data.get("status") != "ok":
                    logger.warning("Subgram get-sponsors error for user %s: %s", user_id, data)
                    return []

                result = data.get("result", [])
                if not isinstance(result, list):
                    return []

                sponsors = []
                for item in result:
                    link = item.get("link", "")
                    if not link:
                        continue
                    sponsors.append({
                        "link": link,
                        "title": item.get("resource_name") or item.get("button_text") or "Канал",
                        "button_text": item.get("button_text") or item.get("resource_name") or "Подписаться",
                        "ads_id": item.get("ads_id", ""),
                    })

                logger.debug("Subgram: %d sponsors for user %s", len(sponsors), user_id)
                return sponsors

    except aiohttp.ClientConnectorError as exc:
        logger.warning("Subgram: Connection error for user %s: %s", user_id, exc)
        return []
    except aiohttp.ServerTimeoutError:
        logger.warning("Subgram: Timeout for user %s", user_id)
        return []
    except Exception as exc:
        logger.warning("Subgram: Unexpected error for user %s: %s", user_id, exc)
        return []


async def check_subgram_subscriptions(user_id: int, ads_ids: list[str]) -> bool:
    """
    Check whether the user has subscribed to all given Subgram sponsors.

    Returns True if all subscribed (or ads_ids is empty / key not set).
    """
    if not config.SUBGRAM_KEY or not ads_ids:
        return True

    headers = {
        "Auth": config.SUBGRAM_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "user_id": user_id,
        "ads_ids": ads_ids,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SUBGRAM_URL}/get-user-subscriptions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    logger.error("Subgram check: HTTP %s for user %s", resp.status, user_id)
                    return True  # allow on error

                data = await resp.json()
                if data.get("status") != "ok":
                    return True

                result = data.get("result", [])
                if not isinstance(result, list):
                    return True

                # All must be subscribed
                for item in result:
                    if item.get("status") not in ("subscribed",):
                        return False
                return True

    except Exception as exc:
        logger.warning("Subgram check error for user %s: %s", user_id, exc)
        return True
