from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, GameSession
from database.engine import get_setting
from handlers.button_helper import safe_edit
from services.casino import get_case_outcome, update_casino_profit, CASE_PRIZES
from keyboards.cases import cases_menu_kb, case_confirm_kb, case_result_kb

router = Router()

_TIER_NAMES = {1: "Бронза", 3: "Серебро", 5: "Золото"}


# ─── Entry ───────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:cases")
async def cb_cases_menu(callback: CallbackQuery, db_user: User) -> None:
    text = (
        "🎁 <b>Кейсы</b>\n\n"
        "Открой кейс и получи приз!\n\n"
        "🥉 <b>Бронза (1⭐)</b> — призы до 3.5⭐\n"
        "🥈 <b>Серебро (3⭐)</b> — призы до 5⭐\n"
        "🥇 <b>Золото (5⭐)</b> — призы до 9⭐\n"
    )
    await safe_edit(callback, text, cases_menu_kb())
    await callback.answer()


# ─── Pick tier → confirm ──────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("cases:open:"))
async def cb_cases_open(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        tier = int(callback.data.split(":")[2])
        if tier not in CASE_PRIZES:
            raise ValueError
    except (IndexError, ValueError):
        return await callback.answer("Неверный кейс.", show_alert=True)

    name = _TIER_NAMES[tier]
    prizes_preview = " / ".join(f"{p}⭐" for p in CASE_PRIZES[tier][-3:])
    text = (
        f"🎁 <b>Кейс {name}</b>\n\n"
        f"Цена открытия: <b>{tier} ⭐</b>\n"
        f"Максимальный приз: <b>{CASE_PRIZES[tier][-1]} ⭐</b>\n"
        f"Примеры призов: {prizes_preview}...\n\n"
        f"Открыть кейс?"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=case_confirm_kb(tier))
    await callback.answer()


# ─── Confirm → open ──────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("cases:confirm:"))
async def cb_cases_confirm(callback: CallbackQuery, session: AsyncSession, bot: Bot, db_user: User) -> None:
    try:
        tier = int(callback.data.split(":")[2])
        if tier not in CASE_PRIZES:
            raise ValueError
    except (IndexError, ValueError):
        return await callback.answer("Неверный кейс.", show_alert=True)

    if db_user.stars_balance < tier:
        await callback.answer("❌ Недостаточно звёзд.", show_alert=True)
        return

    prize = await get_case_outcome(session, tier)
    payout = round(prize, 2)
    bet = float(tier)

    # Update balance
    db_user.stars_balance = round(db_user.stars_balance - bet + payout, 4)

    gs = GameSession(
        user_id=db_user.user_id,
        game_type=f"case_{tier}",
        bet=bet,
        payout=payout,
        result="win" if payout > bet else "lose",
    )
    session.add(gs)

    await update_casino_profit(session, f"case_{tier}", bet, payout)
    await session.commit()

    # Determine video — per-prize key, e.g. case_1_video_0_1 for 0.1⭐
    prize_str = str(payout).replace(".", "_")
    video_key = f"case_{tier}_video_{prize_str}"
    video_file_id = await get_setting(session, video_key, "")

    name = _TIER_NAMES[tier]
    net = round(payout - bet, 2)
    sign = "+" if net >= 0 else ""

    if payout > bet:
        header = f"🎉 <b>Удача! Кейс {name}</b>"
    elif payout == bet:
        header = f"😐 <b>Ничья! Кейс {name}</b>"
    else:
        header = f"😔 <b>Не повезло. Кейс {name}</b>"

    result_text = (
        f"{header}\n\n"
        f"Цена кейса: {tier} ⭐\n"
        f"Приз: <b>{payout} ⭐</b> ({sign}{net} ⭐)\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
    )

    if video_file_id:
        try:
            await callback.message.delete()
            await bot.send_video(
                chat_id=db_user.user_id,
                video=video_file_id,
                caption=result_text,
                parse_mode="HTML",
                reply_markup=case_result_kb(),
            )
        except Exception:
            await bot.send_message(db_user.user_id, result_text, parse_mode="HTML", reply_markup=case_result_kb())
    else:
        await callback.message.edit_text(result_text, parse_mode="HTML", reply_markup=case_result_kb())

    await callback.answer()
