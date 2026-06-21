from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, GameSession
from database.engine import get_setting
from services.casino import get_wheel_outcome, update_casino_profit
from keyboards.wheel import wheel_menu_kb, wheel_bet_kb, wheel_cancel_kb, wheel_result_kb

router = Router()

_MIN_REFS = 3


class WheelStates(StatesGroup):
    entering_bet = State()


# ─── Entry ───────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:wheel")
async def cb_wheel_menu(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    await state.clear()
    if db_user.referrals_count < _MIN_REFS:
        await callback.answer(
            f"❌ Нужно минимум {_MIN_REFS} реферала.\nТвоих: {db_user.referrals_count}/{_MIN_REFS}",
            show_alert=True,
        )
        return
    text = (
        "🎡 <b>Все или ничего</b>\n\n"
        "Два исхода:\n"
        "• <b>0.1x</b> — потеря 90% ставки\n"
        "• <b>50x</b> — джекпот!\n\n"
        "Выбери ставку и испытай удачу!"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=wheel_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "wheel:choose_bet")
async def cb_wheel_choose_bet(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎡 <b>Все или ничего</b>\n\nВыбери ставку:",
        parse_mode="HTML",
        reply_markup=wheel_bet_kb(),
    )
    await callback.answer()


# ─── Preset bet ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("wheel:bet:") and c.data != "wheel:bet:custom")
async def cb_wheel_bet(callback: CallbackQuery, session: AsyncSession, bot: Bot, db_user: User) -> None:
    try:
        bet = float(callback.data.split(":")[2])
    except (IndexError, ValueError):
        return await callback.answer("Неверная ставка.", show_alert=True)

    await _do_spin(callback, session, bot, bet, db_user)


# ─── Custom bet ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "wheel:bet:custom")
async def cb_wheel_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "🎡 Введи сумму ставки (минимум 1 ⭐):",
        reply_markup=wheel_cancel_kb(),
    )
    await state.set_state(WheelStates.entering_bet)
    await callback.answer()


@router.message(WheelStates.entering_bet)
async def msg_wheel_bet(message: Message, state: FSMContext, session: AsyncSession, bot: Bot, db_user: User) -> None:
    try:
        bet = float(message.text.strip().replace(",", "."))
        if bet < 1:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("⚠️ Введи число 1 или больше.", reply_markup=wheel_cancel_kb())
        return

    await state.clear()
    if db_user.stars_balance < bet:
        await message.answer("❌ Недостаточно звёзд.", reply_markup=wheel_cancel_kb())
        return

    await _spin_and_send(message, None, session, bot, db_user, bet)


# ─── Core spin logic ─────────────────────────────────────────────────────────

async def _do_spin(callback: CallbackQuery, session: AsyncSession, bot: Bot, bet: float, db_user: User) -> None:
    if db_user.stars_balance < bet:
        await callback.answer("❌ Недостаточно звёзд.", show_alert=True)
        return
    await _spin_and_send(None, callback, session, bot, db_user, bet)


async def _spin_and_send(
    message: Message | None,
    callback: CallbackQuery | None,
    session: AsyncSession,
    bot: Bot,
    user: User,
    bet: float,
) -> None:
    coeff = await get_wheel_outcome(session)
    payout = round(bet * coeff, 2)

    # Update balance
    user.stars_balance = round(user.stars_balance - bet + payout, 4)

    # Save game session
    gs = GameSession(
        user_id=user.user_id,
        game_type="wheel",
        bet=bet,
        payout=payout,
        result="win" if payout > bet else "lose",
    )
    session.add(gs)

    # Update profit counters
    await update_casino_profit(session, "wheel", bet, payout)
    await session.commit()

    from services.battlepass import after_game as _bp_after_game
    await _bp_after_game(user, session, bot, "wheel", "win" if payout > bet else "lose", bet, payout)

    # Determine video key
    video_key = "wheel_video_50x" if coeff == 50.0 else "wheel_video_01x"
    video_file_id = await get_setting(session, video_key, "")

    net = round(payout - bet, 2)
    sign = "+" if net >= 0 else ""
    if coeff == 50.0:
        result_text = (
            f"🎉 <b>ДЖЕКПОТ! 50x!</b>\n\n"
            f"Ставка: {bet} ⭐\n"
            f"Выигрыш: <b>{payout} ⭐</b> ({sign}{net} ⭐)\n"
            f"Баланс: <b>{user.stars_balance:.2f} ⭐</b>"
        )
    else:
        result_text = (
            f"😔 <b>0.1x — не повезло</b>\n\n"
            f"Ставка: {bet} ⭐\n"
            f"Вернулось: <b>{payout} ⭐</b> ({sign}{net} ⭐)\n"
            f"Баланс: <b>{user.stars_balance:.2f} ⭐</b>"
        )

    chat_id = user.user_id
    if video_file_id:
        try:
            if callback:
                await callback.message.delete()
            await bot.send_video(
                chat_id=chat_id,
                video=video_file_id,
                caption=result_text,
                parse_mode="HTML",
                reply_markup=wheel_result_kb(),
            )
        except Exception:
            await bot.send_message(chat_id, result_text, parse_mode="HTML", reply_markup=wheel_result_kb())
    else:
        if callback:
            await callback.message.edit_text(result_text, parse_mode="HTML", reply_markup=wheel_result_kb())
        else:
            await bot.send_message(chat_id, result_text, parse_mode="HTML", reply_markup=wheel_result_kb())

    if callback:
        await callback.answer()
