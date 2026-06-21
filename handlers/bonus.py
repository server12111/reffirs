import json
import random
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, BotSettings
from handlers.button_helper import answer_with_content
from keyboards.main import back_to_menu_kb
from config import config
from utils.emoji import pe

router = Router()


async def _get_float_setting(session: AsyncSession, key: str, default: float) -> float:
    row = await session.get(BotSettings, key)
    if row:
        try:
            return float(row.value)
        except ValueError:
            pass
    return default


async def _get_unsubscribed(bot: Bot, user_id: int, sponsors: list) -> list:
    unsubscribed = []
    for s in sponsors:
        try:
            member = await bot.get_chat_member(s["id"], user_id)
            if member.status in ("left", "kicked"):
                unsubscribed.append(s)
        except Exception:
            pass
    return unsubscribed


def _build_sponsor_wall_kb(sponsors: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in sponsors:
        buttons.append([InlineKeyboardButton(text=f"📢 {s['title']}", url=s["link"])])
    buttons.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="sponsors:check_bonus")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(lambda c: c.data == "menu:bonus")
async def cb_bonus(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    # Проверка подписки на кастомных спонсоров
    sponsors_row = await session.get(BotSettings, "sponsor_channels")
    sponsors = json.loads(sponsors_row.value) if sponsors_row and sponsors_row.value and sponsors_row.value.strip() else []
    if sponsors:
        unsubscribed = await _get_unsubscribed(callback.bot, callback.from_user.id, sponsors)
        if unsubscribed:
            await callback.message.edit_text(
                "📢 <b>Подпишитесь на каналы спонсоров</b>\n\n"
                "Чтобы получить бонус, подпишитесь на все каналы ниже и нажмите «Я подписался»:",
                parse_mode="HTML",
                reply_markup=_build_sponsor_wall_kb(unsubscribed),
            )
            await callback.answer()
            return

    cooldown_row = await session.get(BotSettings, "bonus_cooldown_hours")
    cooldown_hours = int(float(cooldown_row.value)) if cooldown_row else config.BONUS_COOLDOWN_HOURS

    now = datetime.utcnow()

    if db_user.last_bonus_at:
        next_bonus = db_user.last_bonus_at + timedelta(hours=cooldown_hours)
        if now < next_bonus:
            remaining = next_bonus - now
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            cooldown_text = pe(
                f"⏳ Бонус уже получен.\n\n"
                f"Следующий бонус будет доступен через: <b>{hours:02d}:{minutes:02d}:{seconds:02d}</b>"
            )
            await answer_with_content(callback, session, "menu:bonus", cooldown_text, back_to_menu_kb())
            await callback.answer()
            return

    bonus_min = await _get_float_setting(session, "bonus_min", config.BONUS_MIN)
    bonus_max = await _get_float_setting(session, "bonus_max", config.BONUS_MAX)
    amount = round(random.uniform(bonus_min, bonus_max), 2)

    db_user.stars_balance += amount
    db_user.last_bonus_at = now
    await session.commit()

    bonus_text = pe(
        f"🎁 Вам начислено <b>{amount} ⭐</b> бонуса!\n\n"
        f"Текущий баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
    )
    await answer_with_content(callback, session, "menu:bonus", bonus_text, back_to_menu_kb())
    await callback.answer(f"+{amount} ⭐")


@router.callback_query(lambda c: c.data == "sponsors:check_bonus")
async def cb_sponsors_check_bonus(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    sponsors_row = await session.get(BotSettings, "sponsor_channels")
    sponsors = json.loads(sponsors_row.value) if sponsors_row and sponsors_row.value and sponsors_row.value.strip() else []

    unsubscribed = await _get_unsubscribed(callback.bot, callback.from_user.id, sponsors)
    if unsubscribed:
        await callback.answer(
            "❌ Вы не подписались на все каналы. Подпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=_build_sponsor_wall_kb(unsubscribed))
        except Exception:
            pass
        return

    # Все подписаны — выдаём бонус
    cooldown_row = await session.get(BotSettings, "bonus_cooldown_hours")
    cooldown_hours = int(float(cooldown_row.value)) if cooldown_row else config.BONUS_COOLDOWN_HOURS
    now = datetime.utcnow()

    if db_user.last_bonus_at:
        next_bonus = db_user.last_bonus_at + timedelta(hours=cooldown_hours)
        if now < next_bonus:
            remaining = next_bonus - now
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            await callback.answer(
                f"⏳ Бонус уже получен. Следующий через {hours:02d}:{minutes:02d}:{seconds:02d}",
                show_alert=True,
            )
            return

    bonus_min = await _get_float_setting(session, "bonus_min", config.BONUS_MIN)
    bonus_max = await _get_float_setting(session, "bonus_max", config.BONUS_MAX)
    amount = round(random.uniform(bonus_min, bonus_max), 2)

    db_user.stars_balance += amount
    db_user.last_bonus_at = now
    await session.commit()

    bonus_text = pe(
        f"🎁 Вам начислено <b>{amount} ⭐</b> бонуса!\n\n"
        f"Текущий баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
    )
    await answer_with_content(callback, session, "menu:bonus", bonus_text, back_to_menu_kb())
    await callback.answer(f"+{amount} ⭐")
