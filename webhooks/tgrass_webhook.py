import logging

from aiohttp import web

from config import config
from database.engine import SessionFactory
from database.models import User

logger = logging.getLogger(__name__)


async def tgrass_unsubscribe(request: web.Request) -> web.Response:
    # Optional signature verification
    if config.TGRASS_WEBHOOK_SECRET:
        secret = request.headers.get("X-Secret") or request.headers.get("Authorization", "")
        if secret != config.TGRASS_WEBHOOK_SECRET:
            logger.warning("TGrass webhook: invalid secret")
            return web.Response(status=403)

    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)

    tg_user_id = data.get("tg_user_id")
    if not tg_user_id:
        return web.Response(status=400)

    bot = request.app["bot"]
    try:
        async with SessionFactory() as session:
            user = await session.get(User, int(tg_user_id))
            if not user or not user.referrer_id:
                return web.Response(status=200)

            referrer = await session.get(User, user.referrer_id)
            name = f"@{user.username}" if user.username else user.first_name

            if referrer and (user.referral_reward_given or 0) > 0 and not user.reward_clawed_back:
                referrer.stars_balance = max(0.0, (referrer.stars_balance or 0) - user.referral_reward_given)
                referrer.referrals_count = max(0, (referrer.referrals_count or 1) - 1)
                user.reward_clawed_back = True
                await session.commit()
                logger.info(
                    "TGrass unsubscribe: clawed back %.2f from referrer %s (referral %s)",
                    user.referral_reward_given, referrer.user_id, user.user_id,
                )
                try:
                    await bot.send_message(
                        referrer.user_id,
                        f"⚠️ <b>{name}</b> отписался от спонсора.\n"
                        f"С вашего баланса снято <b>-{user.referral_reward_given:.2f} ⭐</b> "
                        f"(отзыв награды за реферала).",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            elif referrer:
                try:
                    await bot.send_message(
                        referrer.user_id,
                        f"ℹ️ <b>{name}</b> отписался от спонсора.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.error("TGrass webhook error: %s", e)
        return web.Response(status=500)

    return web.Response(status=200)


def create_webhook_app(bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/webhook/tgrass", tgrass_unsubscribe)
    app.router.add_post("/unsubscribe", tgrass_unsubscribe)
    return app
