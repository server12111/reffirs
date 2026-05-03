import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

TGRASS_URL = "https://tgrass.space/offers"
TGRASS_RESET_URL = "https://tgrass.space/reset_offers"


async def get_tgrass_offers(user_id: int, user=None) -> list[dict]:
    """
    Fetch unsubscribed TGrass offers for the user.

    Returns list of offer dicts: [{"name": str, "link": str, "type": str, "offer_id": int}, ...]
    Returns [] if user passed all offers, no offers available, key not set, or on error.
    """
    if not config.TGRASS_CODE:
        return []

    payload: dict = {
        "tg_user_id": user_id,
        "is_premium": bool(getattr(user, "is_premium", False)),
        "lang": getattr(user, "language_code", "ru") or "ru",
    }
    login = getattr(user, "username", None)
    if login:
        payload["tg_login"] = login

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TGRASS_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Auth": config.TGRASS_CODE,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    logger.error("TGrass: HTTP %s for user %s", resp.status, user_id)
                    return []

                data = await resp.json()
                status = data.get("status")
                logger.debug("TGrass: status=%s for user %s", status, user_id)

                if status in ("ok", "no_offers"):
                    return []  # user passed or nothing to show

                if status == "not_ok":
                    offers = data.get("offers", [])
                    return [o for o in offers if not o.get("subscribed", False)]

                return []

    except aiohttp.ClientConnectorError as exc:
        logger.warning("TGrass: Connection error for user %s: %s", user_id, exc)
        return []
    except aiohttp.ServerTimeoutError:
        logger.warning("TGrass: Timeout for user %s", user_id)
        return []
    except Exception as exc:
        logger.warning("TGrass: Unexpected error for user %s: %s", user_id, exc)
        return []


async def reset_tgrass_offers(user_id: int) -> None:
    """Reset offer refresh timer so user gets fresh offers on next call."""
    if not config.TGRASS_CODE:
        return
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                TGRASS_RESET_URL,
                json={"tg_user_id": user_id},
                headers={
                    "Content-Type": "application/json",
                    "Auth": config.TGRASS_CODE,
                },
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception:
        pass
