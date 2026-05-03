import asyncio
import logging

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, BotSettings
from handlers.button_helper import answer_with_content
from keyboards.botohub import build_botohub_wall_kb, build_combined_wall_kb
from keyboards.main import main_menu_kb
from services.referral import grant_referral_reward_if_pending
from services.subgram import get_subgram_sponsors
from services.botohub_views import show_botohub_views
from utils.botohub_api import check_botohub
from utils.emoji import pe

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data == "botohub:check")
async def cb_botohub_check(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await check_botohub(callback.from_user.id)

    if result["completed"] or result["skip"]:
        db_user = await session.get(User, callback.from_user.id)
        if db_user and db_user.referral_reward_pending:
            await grant_referral_reward_if_pending(db_user, session, callback.bot)

        ad_sent = await show_botohub_views(callback.from_user.id)
        if ad_sent:
            await asyncio.sleep(0.5)

        default_text = (
            "👋 <b>Главное меню</b>\n\n"
            "🌟 Зарабатывай Telegram Stars прямо здесь:\n\n"
            "• ⭐ <b>Рефералы</b> — приглашай друзей и получай звёзды за каждого\n"
            "• 📋 <b>Задания</b> — подписывайся на каналы и выполняй задачи\n"
            "• 🎮 <b>Игры</b> — испытай удачу в мини-играх\n"
            "• 🎁 <b>Бонус</b> — бесплатные звёзды каждые 24 часа\n"
            "• 💰 <b>Вывод</b> — выводи накопленное на свой Telegram\n\n"
            "Выбери раздел ниже 👇"
        )
        await answer_with_content(callback, session, "menu:main", default_text, main_menu_kb())
        await callback.answer("✅ Подписка подтверждена!")
        logger.info("BotoHub: user %s passed subscription wall", callback.from_user.id)

    else:
        await callback.answer(
            "❌ Вы не подписались на все каналы.\nПодпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        if result["tasks"]:
            wall_kb = build_botohub_wall_kb(result["tasks"])
            try:
                await callback.message.edit_reply_markup(reply_markup=wall_kb)
            except Exception:
                pass
        logger.info("BotoHub: user %s pressed check but is not subscribed yet", callback.from_user.id)


@router.callback_query(lambda c: c.data == "wall:check")
async def cb_combined_wall_check(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Unified check for the combined wall (TGrass + Subgram + BotoHub).
    PiarFlow and Flyer removed.
    """
    user_id = callback.from_user.id

    from config import config as _cfg

    async def _flag(k, default):
        r = await session.get(BotSettings, k)
        if r is None:
            return default
        return r.value == "1"

    bh_on = await _flag("integration_botohub_enabled", bool(_cfg.BOTOHUB_KEY))
    sg_on = await _flag("integration_subgram_enabled", bool(_cfg.SUBGRAM_KEY))

    sg_count_row = await session.get(BotSettings, "subgram_count")
    sg_count = int(sg_count_row.value) if sg_count_row and sg_count_row.value else 5

    async def _skip_bh(): return {"completed": True, "skip": True, "tasks": []}
    async def _skip_list(): return []

    sg_sponsors, bh_result = await asyncio.gather(
        get_subgram_sponsors(user_id, sg_count) if sg_on else _skip_list(),
        check_botohub(user_id) if bh_on else _skip_bh(),
    )

    bh_pending = bh_on and not bh_result["completed"] and not bh_result["skip"] and bool(bh_result["tasks"])
    sg_pending = sg_on and bool(sg_sponsors)

    if sg_pending or bh_pending:
        await callback.answer(
            "❌ Вы не подписались на все каналы.\nПодпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        wall_kb = build_combined_wall_kb(
            bh_result["tasks"] if bh_pending else [],
            subgram_sponsors=sg_sponsors if sg_pending else [],
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=wall_kb)
        except Exception:
            pass
        logger.info(
            "CombinedWall: user %s still blocked (sg=%s, bh=%s)",
            user_id, sg_pending, bh_pending,
        )
        return

    # All passed — referral reward + ads + main menu
    db_user = await session.get(User, user_id)
    if db_user and db_user.referral_reward_pending:
        await grant_referral_reward_if_pending(db_user, session, callback.bot)

    ad_sent = await show_botohub_views(user_id)
    if ad_sent:
        await asyncio.sleep(0.5)

    default_text = (
        "👋 <b>Главное меню</b>\n\n"
        "🌟 Зарабатывай Telegram Stars прямо здесь:\n\n"
        "• ⭐ <b>Рефералы</b> — приглашай друзей и получай звёзды за каждого\n"
        "• 📋 <b>Задания</b> — подписывайся на каналы и выполняй задачи\n"
        "• 🎮 <b>Игры</b> — испытай удачу в мини-играх\n"
        "• 🎁 <b>Бонус</b> — бесплатные звёзды каждые 24 часа\n"
        "• 💰 <b>Вывод</b> — выводи накопленное на свой Telegram\n\n"
        "Выбери раздел ниже 👇"
    )
    await answer_with_content(callback, session, "menu:main", default_text, main_menu_kb())
    await callback.answer("✅ Подписка подтверждена!")
    logger.info("CombinedWall: user %s passed all walls", user_id)
