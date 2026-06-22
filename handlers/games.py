from datetime import date, datetime

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import User, GameSession, BotSettings
from handlers.button_helper import answer_with_content, safe_edit
from keyboards.games import (
    games_menu_kb, dice_side_kb, football_side_kb, bowling_side_kb,
    basketball_side_kb, darts_side_kb,
    game_result_kb, game_cancel_kb,
    GAME_TYPES, GAME_LABELS,
)

router = Router()

GAME_EMOJIS = {
    "football":   "⚽",
    "basketball": "🏀",
    "bowling":    "🎳",
    "dice":       "🎲",
    "slots":      "🎰",
    "darts":      "🎯",
}

GAME_DEFAULTS = {
    "football":   {"coeff_goal": 1.5, "coeff_miss": 2.2, "min_bet": 1.0, "daily_limit": 0},
    "basketball": {"coeff_clean": 4.0, "coeff_any": 2.2, "coeff_stuck": 4.0, "coeff_miss": 1.5, "min_bet": 1.0, "daily_limit": 0},
    "bowling":    {"coeff_strike": 5.0, "coeff_partial": 2.0, "coeff_miss": 4.0, "min_bet": 1.0, "daily_limit": 0},
    "dice":       {"coeff": 1.5, "min_bet": 1.0, "daily_limit": 0},
    "slots":      {"coeff1": 10.0, "coeff2": 2.0, "min_bet": 1.0, "daily_limit": 0},
    "darts":      {"coeff_bullseye": 5.0, "coeff_red": 1.8, "coeff_white": 2.5, "coeff_bounce": 5.0, "min_bet": 1.0, "daily_limit": 0},
}


class GameStates(StatesGroup):
    enter_bet = State()
    choose_dice_side = State()
    choose_football_side = State()
    choose_basketball_side = State()
    choose_bowling_side = State()
    choose_darts_side = State()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_float(session: AsyncSession, key: str, default: float) -> float:
    row = await session.get(BotSettings, key)
    if row:
        try:
            return float(row.value)
        except ValueError:
            pass
    return default


async def _get_int(session: AsyncSession, key: str, default: int) -> int:
    row = await session.get(BotSettings, key)
    if row:
        try:
            return int(row.value)
        except ValueError:
            pass
    return default


async def _is_enabled(session: AsyncSession, game: str) -> bool:
    row = await session.get(BotSettings, f"game_{game}_enabled")
    return (row.value == "1") if row else True


async def _get_daily_count(session: AsyncSession, user_id: int, game: str) -> int:
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = await session.execute(
        select(func.count(GameSession.id)).where(
            GameSession.user_id == user_id,
            GameSession.game_type == game,
            GameSession.played_at >= today_start,
        )
    )
    return result.scalar() or 0


async def _load_games_config(session: AsyncSession) -> dict:
    configs = {}
    for game in GAME_TYPES:
        enabled_row = await session.get(BotSettings, f"game_{game}_enabled")
        min_bet_row = await session.get(BotSettings, f"game_{game}_min_bet")
        cfg = {
            "enabled": (enabled_row.value == "1") if enabled_row else True,
            "min_bet": float(min_bet_row.value) if min_bet_row else 1.0,
        }
        if game == "slots":
            c1 = await _get_float(session, "game_slots_coeff1", 10.0)
            c2 = await _get_float(session, "game_slots_coeff2", 2.0)
            cfg["coeff_label"] = f"x{c2:.4g}–x{c1:.4g}"
        elif game == "football":
            cg = await _get_float(session, "game_football_coeff_goal", 1.5)
            cm = await _get_float(session, "game_football_coeff_miss", 2.2)
            cfg["coeff_label"] = f"Гол x{cg:.4g} / Промах x{cm:.4g}"
        elif game == "basketball":
            lo = await _get_float(session, "game_basketball_coeff_miss", 1.5)
            hi = await _get_float(session, "game_basketball_coeff_clean", 4.0)
            cfg["coeff_label"] = f"x{lo:.4g}–x{hi:.4g}"
        elif game == "darts":
            lo = await _get_float(session, "game_darts_coeff_red", 1.8)
            hi = await _get_float(session, "game_darts_coeff_bullseye", 5.0)
            cfg["coeff_label"] = f"x{lo:.4g}–x{hi:.4g}"
        elif game == "bowling":
            cs = await _get_float(session, "game_bowling_coeff_strike",  5.0)
            cp = await _get_float(session, "game_bowling_coeff_partial", 2.0)
            cfg["coeff_label"] = f"x{cp:.4g}–x{cs:.4g}"
        else:
            default = GAME_DEFAULTS[game].get("coeff", 1.9)
            c = await _get_float(session, f"game_{game}_coeff", default)
            cfg["coeff_label"] = f"x{c:.4g}"
        configs[game] = cfg
    return configs


async def _execute_game(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    db_user: User,
    game_type: str,
    bet: float,
    game_side: str | None = None,
) -> tuple[bool, float, int]:
    """Send dice, evaluate result, update balance and record session.
    Returns (won, payout, dice_value). Bet must be deducted before calling."""
    dice_msg = await bot.send_dice(chat_id=chat_id, emoji=GAME_EMOJIS[game_type])
    value = dice_msg.dice.value

    won = False
    payout = 0.0

    if game_type == "football":
        coeff_goal = await _get_float(session, "game_football_coeff_goal", 1.5)
        coeff_miss = await _get_float(session, "game_football_coeff_miss", 2.2)
        if value in (4, 5):  # goal
            if game_side == "goal":
                won, payout = True, round(bet * coeff_goal, 2)
        else:  # miss (values 1-3)
            if game_side == "miss":
                won, payout = True, round(bet * coeff_miss, 2)

    elif game_type == "basketball":
        c_clean = await _get_float(session, "game_basketball_coeff_clean", 4.0)
        c_any   = await _get_float(session, "game_basketball_coeff_any",   2.2)
        c_stuck = await _get_float(session, "game_basketball_coeff_stuck", 4.0)
        c_miss  = await _get_float(session, "game_basketball_coeff_miss",  1.5)
        if value == 5:
            if game_side == "clean":   won, payout = True, round(bet * c_clean, 2)
            elif game_side == "any":   won, payout = True, round(bet * c_any,   2)
        elif value == 4:
            if game_side == "any":     won, payout = True, round(bet * c_any,   2)
        elif value == 3:
            if game_side == "stuck":   won, payout = True, round(bet * c_stuck, 2)
        else:  # 1, 2
            if game_side == "miss":    won, payout = True, round(bet * c_miss,  2)

    elif game_type == "bowling":
        c_strike  = await _get_float(session, "game_bowling_coeff_strike",  5.0)
        c_partial = await _get_float(session, "game_bowling_coeff_partial", 2.0)
        c_miss    = await _get_float(session, "game_bowling_coeff_miss",    4.0)
        if value == 6:  # strike
            if game_side == "strike":   won, payout = True, round(bet * c_strike,  2)
        elif value in (2, 3, 4, 5):  # any pin knocked — partial
            if game_side == "partial":  won, payout = True, round(bet * c_partial, 2)
        else:  # 1 only — gutter ball
            if game_side == "miss":     won, payout = True, round(bet * c_miss,    2)

    elif game_type == "dice":
        coeff = await _get_float(session, "game_dice_coeff", 1.9)
        if (game_side == "high" and value > 3) or (game_side == "low" and value < 4):
            won, payout = True, round(bet * coeff, 2)

    elif game_type == "slots":
        coeff_777    = await _get_float(session, "game_slots_coeff1", 10.0)
        coeff_fruits = await _get_float(session, "game_slots_coeff2", 2.0)
        _FRUITS = {1, 22, 43}
        if value == 64:
            won, payout = True, round(bet * coeff_777, 2)
            db_user.slots_777_count = (db_user.slots_777_count or 0) + 1
        elif value in _FRUITS:
            won, payout = True, round(bet * coeff_fruits, 2)

    elif game_type == "darts":
        c_bullseye = await _get_float(session, "game_darts_coeff_bullseye", 5.0)
        c_bounce   = await _get_float(session, "game_darts_coeff_bounce",   5.0)
        if value == 6:
            if game_side == "center":
                won, payout = True, round(bet * c_bullseye, 2)
                db_user.darts_bullseye_count = (db_user.darts_bullseye_count or 0) + 1
        elif value == 1:  # bounce
            if game_side == "bounce": won, payout = True, round(bet * c_bounce,  2)

    if won:
        db_user.stars_balance += payout

    session.add(GameSession(
        user_id=db_user.user_id,
        game_type=game_type,
        bet=bet,
        result="win" if won else "lose",
        payout=payout,
    ))
    await session.commit()

    from services.battlepass import after_game as _bp_after_game
    await _bp_after_game(db_user, session, bot, game_type, "win" if won else "lose", bet, payout, dice_value=value)

    return won, payout, value


def _result_text(
    game_type: str,
    won: bool,
    bet: float,
    payout: float,
    value: int,
    new_balance: float,
    game_side: str | None = None,
) -> str:
    label = GAME_LABELS[game_type]
    net = round(payout - bet, 2)
    sign = "+" if net >= 0 else ""

    if game_type == "football":
        outcome = "⚽ Гол!" if value in (4, 5) else "🥅 Промах."
        if won:
            result_line = f"🎉 <b>Угадал! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            chose = "гол" if game_side == "goal" else "промах"
            result_line = f"😞 <b>Не угадал.</b> Поставил на {chose} — -{bet:.2f} ⭐"

    elif game_type == "basketball":
        if value == 5:
            outcome = "🏀 Чистый гол!"
        elif value == 4:
            outcome = "🏀 Гол!"
        elif value == 3:
            outcome = "😬 Застрял мяч..."
        else:
            outcome = "🏀 Промах."
        _sides = {"clean": "чистый гол", "any": "любой гол", "stuck": "застрял", "miss": "промах"}
        chose = _sides.get(game_side, game_side or "")
        if won:
            result_line = f"🎉 <b>Угадал! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            result_line = f"😞 <b>Не угадал.</b> Поставил на {chose} — -{bet:.2f} ⭐"

    elif game_type == "bowling":
        if value == 6:
            outcome = "🎳 Страйк! Все кегли сбиты!"
        elif value in (2, 3, 4, 5):
            outcome = "🎳 Попал — несколько кеглей сбито."
        else:
            outcome = "🎳 Промах."
        _bsides = {"strike": "страйк", "partial": "попал", "miss": "промах"}
        chose = _bsides.get(game_side, game_side or "")
        if won:
            result_line = f"🎉 <b>Угадал! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            result_line = f"😞 <b>Не угадал.</b> Поставил на {chose} — -{bet:.2f} ⭐"

    elif game_type == "dice":
        outcome = f"🎲 Выпало: <b>{value}</b> | {'📈 Больше 3' if game_side == 'high' else '📉 Меньше 4'}"
        if won:
            result_line = f"🎉 <b>Выигрыш! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            result_line = f"😞 <b>Проигрыш. -{bet:.2f} ⭐</b>"

    elif game_type == "slots":
        if value == 64:
            outcome = "🎰 <b>777 — Джекпот! 🏆</b>"
        elif value in (1, 22, 43):
            outcome = "🎰 <b>3 одинаковых — Выигрыш! 🍀</b>"
        else:
            outcome = "🎰 Нет совпадений"
        if won:
            result_line = f"🎉 <b>Выигрыш! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            result_line = f"😞 <b>Проигрыш. -{bet:.2f} ⭐</b>"

    elif game_type == "darts":
        if value == 6:
            outcome = "🎯 Прямо в центр!"
        elif value in (2, 3, 4, 5):
            outcome = "🎯 Красный сектор."
        else:
            outcome = "🎯 Отскок дротика!"
        _dsides = {"center": "центр", "red": "красный", "bounce": "отскок"}
        chose = _dsides.get(game_side, game_side or "")
        if won:
            result_line = f"🎉 <b>Угадал! +{payout:.2f} ⭐</b> (чистая прибыль: {sign}{net:.2f} ⭐)"
        else:
            result_line = f"😞 <b>Не угадал.</b> Поставил на {chose} — -{bet:.2f} ⭐"

    else:
        outcome = ""
        result_line = f"🎉 <b>+{payout:.2f} ⭐</b>" if won else f"😞 <b>-{bet:.2f} ⭐</b>"

    parts = [
        f"<b>{label}</b>",
        "",
        outcome,
        result_line,
        f"\n💰 Баланс: <b>{new_balance:.2f} ⭐</b>",
    ]
    return "\n".join(parts)


# ─── Games menu ───────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:games")
async def cb_games_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    # Refund bet if user cancels during side selection
    fsm_state = await state.get_state()
    if fsm_state in (
        GameStates.choose_dice_side,
        GameStates.choose_football_side,
        GameStates.choose_basketball_side,
        GameStates.choose_bowling_side,
        GameStates.choose_darts_side,
    ):
        data = await state.get_data()
        bet = data.get("bet", 0.0)
        if bet:
            db_user.stars_balance += bet
            await session.commit()
    await state.clear()

    configs = await _load_games_config(session)
    has_any = any(cfg["enabled"] for cfg in configs.values())

    if has_any:
        default_text = (
            f"🎮 <b>Игры</b>\n\n"
            f"Твой баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
            f"Выбери игру:"
        )
    else:
        default_text = "🎮 <b>Игры</b>\n\nИгры временно недоступны."

    await answer_with_content(callback, session, "menu:games", default_text, games_menu_kb(configs))
    await callback.answer()


# ─── Select game → enter bet ──────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("game:play:"))
async def cb_game_play(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    await state.clear()
    game_type = callback.data.split(":")[2]

    if game_type not in GAME_TYPES:
        await callback.answer("Неизвестная игра.", show_alert=True)
        return

    if not await _is_enabled(session, game_type):
        await callback.answer("Эта игра временно отключена.", show_alert=True)
        return

    daily_limit = await _get_int(session, f"game_{game_type}_daily_limit", 0)
    if daily_limit > 0:
        daily_count = await _get_daily_count(session, db_user.user_id, game_type)
        if daily_count >= daily_limit:
            await callback.answer(
                f"⛔ Достигнут дневной лимит ({daily_limit} игр). Попробуй завтра.",
                show_alert=True,
            )
            return

    min_bet = await _get_float(session, f"game_{game_type}_min_bet", 1.0)
    bet_step = await _get_float(session, f"game_{game_type}_bet_step", 1.0)

    if db_user.stars_balance < min_bet:
        await callback.answer(
            f"❌ Недостаточно звёзд. Минимальная ставка: {min_bet:.0f} ⭐",
            show_alert=True,
        )
        return

    await state.set_state(GameStates.enter_bet)
    await state.update_data(game_type=game_type, bet_step=bet_step)

    step_line = f"👣 Шаг ставки: <b>{bet_step:.4g} ⭐</b>\n" if bet_step > 1.0 else ""
    await safe_edit(
        callback,
        f"<b>{GAME_LABELS[game_type]}</b>\n\n"
        f"💰 Твой баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n"
        f"Минимальная ставка: <b>{min_bet:.0f} ⭐</b>\n"
        f"{step_line}"
        f"\nВведи сумму ставки:",
        game_cancel_kb(),
    )
    await callback.answer()


# ─── Bet entered ──────────────────────────────────────────────────────────────

@router.message(GameStates.enter_bet)
async def msg_bet_enter(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    game_type = data["game_type"]
    bet_step = data.get("bet_step", 1.0)

    try:
        bet = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(
            "❌ Введи число — сумму ставки:",
            reply_markup=game_cancel_kb(),
        )
        return

    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше нуля:", reply_markup=game_cancel_kb())
        return

    min_bet = await _get_float(session, f"game_{game_type}_min_bet", 1.0)
    if bet < min_bet:
        await message.answer(
            f"❌ Минимальная ставка: <b>{min_bet:.0f} ⭐</b>",
            parse_mode="HTML",
            reply_markup=game_cancel_kb(),
        )
        return

    if bet_step > 1.0 and abs(bet % bet_step) > 0.001:
        await message.answer(
            f"❌ Ставка должна быть кратна <b>{bet_step:.4g} ⭐</b>\n"
            f"Примеры: {bet_step:.4g}, {bet_step*2:.4g}, {bet_step*3:.4g}...",
            parse_mode="HTML",
            reply_markup=game_cancel_kb(),
        )
        return

    if db_user.stars_balance < bet:
        await message.answer(
            f"❌ Недостаточно звёзд. Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
            parse_mode="HTML",
            reply_markup=game_cancel_kb(),
        )
        return

    # Deduct bet before game starts
    db_user.stars_balance -= bet
    await session.commit()

    # Games that need side selection first
    if game_type == "dice":
        await state.set_state(GameStates.choose_dice_side)
        await state.update_data(bet=bet)
        await message.answer(
            f"🎲 <b>Кубики</b>\n\n"
            f"Ставка: <b>{bet:.0f} ⭐</b>\n\n"
            f"Выбери условие победы:",
            parse_mode="HTML",
            reply_markup=dice_side_kb(),
        )
        return

    if game_type == "football":
        await state.set_state(GameStates.choose_football_side)
        await state.update_data(bet=bet)
        await message.answer(
            f"⚽ <b>Футбол</b>\n\n"
            f"Ставка: <b>{bet:.0f} ⭐</b>\n\n"
            f"Сделай ставку — мяч попадёт в ворота или нет?",
            parse_mode="HTML",
            reply_markup=football_side_kb(),
        )
        return

    if game_type == "basketball":
        await state.set_state(GameStates.choose_basketball_side)
        await state.update_data(bet=bet)
        await message.answer(
            f"🏀 <b>Баскетбол</b>\n\n"
            f"Ставка: <b>{bet:.0f} ⭐</b>\n\n"
            f"Поставь на исход броска:",
            parse_mode="HTML",
            reply_markup=basketball_side_kb(),
        )
        return

    if game_type == "bowling":
        await state.set_state(GameStates.choose_bowling_side)
        await state.update_data(bet=bet)
        await message.answer(
            f"🎳 <b>Боулинг</b>\n\n"
            f"Ставка: <b>{bet:.0f} ⭐</b>\n\n"
            f"Поставь на страйк или промах:",
            parse_mode="HTML",
            reply_markup=bowling_side_kb(),
        )
        return

    if game_type == "darts":
        await state.set_state(GameStates.choose_darts_side)
        await state.update_data(bet=bet)
        await message.answer(
            f"🎯 <b>Дартс</b>\n\n"
            f"Ставка: <b>{bet:.0f} ⭐</b>\n\n"
            f"Поставь на зону попадания:",
            parse_mode="HTML",
            reply_markup=darts_side_kb(),
        )
        return

    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=message.bot,
            chat_id=message.chat.id,
            session=session,
            db_user=db_user,
            game_type=game_type,
            bet=bet,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        return

    await message.answer(
        _result_text(game_type, won, bet, payout, value, db_user.stars_balance),
        parse_mode="HTML",
        reply_markup=game_result_kb(game_type),
    )


# ─── Dice: choose side ────────────────────────────────────────────────────────

@router.callback_query(GameStates.choose_dice_side, lambda c: c.data and c.data.startswith("game:dice:"))
async def cb_dice_side(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    game_side = callback.data.split(":")[2]
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            session=session,
            db_user=db_user,
            game_type="dice",
            bet=bet,
            game_side=game_side,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await callback.message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        await callback.answer()
        return

    await callback.message.answer(
        _result_text("dice", won, bet, payout, value, db_user.stars_balance, game_side),
        parse_mode="HTML",
        reply_markup=game_result_kb("dice"),
    )
    await callback.answer()


# ─── Football: choose side ────────────────────────────────────────────────────

@router.callback_query(GameStates.choose_football_side, lambda c: c.data and c.data.startswith("game:football:"))
async def cb_football_side(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    game_side = callback.data.split(":")[2]
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            session=session,
            db_user=db_user,
            game_type="football",
            bet=bet,
            game_side=game_side,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await callback.message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        await callback.answer()
        return

    await callback.message.answer(
        _result_text("football", won, bet, payout, value, db_user.stars_balance, game_side),
        parse_mode="HTML",
        reply_markup=game_result_kb("football"),
    )
    await callback.answer()


# ─── Bowling: choose side ─────────────────────────────────────────────────────

@router.callback_query(GameStates.choose_bowling_side, lambda c: c.data and c.data.startswith("game:bowling:"))
async def cb_bowling_side(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    game_side = callback.data.split(":")[2]
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            session=session,
            db_user=db_user,
            game_type="bowling",
            bet=bet,
            game_side=game_side,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await callback.message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        await callback.answer()
        return

    await callback.message.answer(
        _result_text("bowling", won, bet, payout, value, db_user.stars_balance, game_side),
        parse_mode="HTML",
        reply_markup=game_result_kb("bowling"),
    )
    await callback.answer()


# ─── Basketball: choose side ──────────────────────────────────────────────────

@router.callback_query(GameStates.choose_basketball_side, lambda c: c.data and c.data.startswith("game:basketball:"))
async def cb_basketball_side(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    game_side = callback.data.split(":")[2]
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            session=session,
            db_user=db_user,
            game_type="basketball",
            bet=bet,
            game_side=game_side,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await callback.message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        await callback.answer()
        return

    await callback.message.answer(
        _result_text("basketball", won, bet, payout, value, db_user.stars_balance, game_side),
        parse_mode="HTML",
        reply_markup=game_result_kb("basketball"),
    )
    await callback.answer()


# ─── Darts: choose side ───────────────────────────────────────────────────────

@router.callback_query(GameStates.choose_darts_side, lambda c: c.data and c.data.startswith("game:darts:"))
async def cb_darts_side(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    game_side = callback.data.split(":")[2]
    data = await state.get_data()
    bet = data["bet"]
    await state.clear()

    try:
        won, payout, value = await _execute_game(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            session=session,
            db_user=db_user,
            game_type="darts",
            bet=bet,
            game_side=game_side,
        )
    except Exception:
        db_user.stars_balance += bet
        await session.commit()
        await callback.message.answer("⚠️ Ошибка при отправке игры. Ставка возвращена.", reply_markup=game_cancel_kb())
        await callback.answer()
        return

    await callback.message.answer(
        _result_text("darts", won, bet, payout, value, db_user.stars_balance, game_side),
        parse_mode="HTML",
        reply_markup=game_result_kb("darts"),
    )
    await callback.answer()
