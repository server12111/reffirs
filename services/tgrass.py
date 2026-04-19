import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

TGRASS_API_URL = "https://go.linkni.me/api/subscriptions"


def get_tgrass_wall_url() -> str | None:
    """
    Returns the Tgrass mini-app URL for the subscription wall.
    Format: https://t.me/linknibot/app?startapp=x_{code}
    Returns None if TGRASS_CODE is not configured.
    """
    if not config.LINKNI_CODE:
        return None
    return f"https://t.me/linknibot/app?startapp=x_{config.LINKNI_CODE}"


async def check_tgrass_subscription(user_id: int) -> bool:
    """
    Check whether the user has subscribed via Tgrass.

    Returns True if subscribed or TGRASS_CODE not set.
    Returns False if not subscribed yet.
    On any API error — returns True (allow access, don't block on network failure).
    """
    if not config.LINKNI_CODE:
        return True

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                TGRASS_API_URL,
                params={"code": config.LINKNI_CODE, "user_id": user_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    logger.error("Tgrass: HTTP %s for user %s", resp.status, user_id)
                    return True

                data = await resp.json()
                logger.debug("Tgrass response for user %s: %s", user_id, data)

                if not isinstance(data, list):
                    return True

                # If there's at least one "subscribed" entry — user completed the wall
                for entry in data:
                    if entry.get("status") == "subscribed":
                        return True

                # No subscribed entry found
                return False

    except aiohttp.ClientConnectorError as exc:
        logger.warning("Tgrass: Connection error for user %s: %s", user_id, exc)
        return True
    except aiohttp.ServerTimeoutError:
        logger.warning("Tgrass: Timeout for user %s", user_id)
        return True
    except Exception as exc:
        logger.warning("Tgrass: Unexpected error for user %s: %s", user_id, exc)
        return True
