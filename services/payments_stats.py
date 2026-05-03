import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select, func
from utils.emoji import pe

logger = logging.getLogger(__name__)


async def payments_stats_loop(bot: Bot) -> None:
    """Background task: update pinned stats message in payments channel every hour."""
    await asyncio.sleep(30)  # short delay after startup
    while True:
        try:
            await _update_stats(bot)
        except Exception as exc:
            logger.error("PaymentsStats loop error: %s", exc)
        await asyncio.sleep(3600)


async def _update_stats(bot: Bot) -> None:
    from database.engine import SessionFactory
    from database.models import BotSettings, Withdrawal, User

    async with SessionFactory() as session:
        # Read payments channel id
        ch_row = await session.get(BotSettings, "payments_channel_id")
        if not ch_row or not ch_row.value:
            return
        channel_id = ch_row.value.strip()

        # Query stats
        approved_result = await session.execute(
            select(func.count(Withdrawal.id), func.coalesce(func.sum(Withdrawal.amount), 0.0))
            .where(Withdrawal.status == "approved")
        )
        approved_count, approved_sum = approved_result.one()

        referrals_result = await session.execute(
            select(func.count(User.user_id)).where(User.referrer_id.is_not(None))
        )
        referrals_count = referrals_result.scalar() or 0

        users_result = await session.execute(select(func.count(User.user_id)))
        users_count = users_result.scalar() or 0

        updated_at = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
        text = pe(
            "📊 <b>Статистика выплат</b>\n\n"
            f"👥 Пользователей: <b>{users_count}</b>\n"
            f"👤 Рефералов: <b>{referrals_count}</b>\n"
            f"✅ Одобрено выплат: <b>{approved_count}</b>\n"
            f"💸 Выплачено всего: <b>{approved_sum:.0f} ⭐</b>\n\n"
            f"🕐 Обновлено: {updated_at}"
        )

        # Check if we already have a pinned message id stored
        pin_row = await session.get(BotSettings, "pinned_stats_message_id")
        pinned_msg_id = int(pin_row.value) if pin_row and pin_row.value else None

        if pinned_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=pinned_msg_id,
                    text=text,
                    parse_mode="HTML",
                )
                logger.info("PaymentsStats: updated pinned message %s in %s", pinned_msg_id, channel_id)
                return
            except Exception as exc:
                logger.warning("PaymentsStats: failed to edit pinned message: %s", exc)
                # Fall through to send a new one

        # Send and pin a new message
        try:
            sent = await bot.send_message(channel_id, text, parse_mode="HTML")
            try:
                await bot.pin_chat_message(channel_id, sent.message_id, disable_notification=True)
            except Exception as exc:
                logger.warning("PaymentsStats: could not pin message: %s", exc)

            # Persist the message id
            if pin_row:
                pin_row.value = str(sent.message_id)
            else:
                session.add(BotSettings(key="pinned_stats_message_id", value=str(sent.message_id)))
            await session.commit()
            logger.info("PaymentsStats: sent and pinned new stats message %s", sent.message_id)
        except Exception as exc:
            logger.error("PaymentsStats: failed to send stats message: %s", exc)
