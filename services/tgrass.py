import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

TGRASS_OFFERS_URL = "https://tgrass.space/offers"
TGRASS_RESET_URL = "https://tgrass.space/reset_offers"


async def get_tgrass_offers(user_id: int, user=None) -> list[dict]:
    """
    Fetch TGrass offers for the user.

    Returns list of offer dicts when user hasn't subscribed to all:
      [{"name": str, "link": str, "type": str, "offer_id": int, "subscribed": bool}, ...]

    Returns [] when:
      - status "ok"       → user subscribed to everything
      - status "no_offers" → nothing to show right now
      - TGRASS_CODE not configured or any network error
    """
    if not config.TGRASS_CODE:
        return []

    payload: dict = {
        "tg_user_id": user_id,
        "is_premium": bool(getattr(user, "is_premium", False) or False),
        "lang": "ru",
    }
    username = getattr(user, "username", None)
    if username:
        payload["tg_login"] = username

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TGRASS_OFFERS_URL,
                json=payload,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json",
                    "Auth": config.TGRASS_CODE,
                },
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=False,
            ) as resp:
                if resp.status != 200:
                    logger.error("TGrass: HTTP %s for user %s", resp.status, user_id)
                    return []

                data = await resp.json()
                status = data.get("status")
                logger.debug("TGrass: status=%s for user %s", status, user_id)

                if status == "not_ok":
                    return data.get("offers", [])

                return []

    except aiohttp.ClientConnectorError as exc:
        logger.warning("TGrass: connection error for user %s: %s", user_id, exc)
        return []
    except aiohttp.ServerTimeoutError:
        logger.warning("TGrass: timeout for user %s", user_id)
        return []
    except Exception as exc:
        logger.warning("TGrass: unexpected error for user %s: %s", user_id, exc)
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
                ssl=False,
            )
    except Exception:
        pass
