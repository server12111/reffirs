import json
from datetime import datetime, timedelta
from io import BytesIO
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import date as _date

from database.models import User, PromoCode, PromoUse, Withdrawal, BotSettings, Task, TaskCompletion, GameSession, ButtonContent, Transfer, Duel, Lottery, LotteryTicket
from handlers.withdraw import build_withdrawal_msg
from database.engine import set_setting, get_button_content, set_button_photo, set_button_text
from keyboards.admin import (
    admin_main_kb, admin_settings_kb, promo_list_kb,
    promo_actions_kb, promo_reward_type_kb, admin_back_kb,
    task_management_kb, task_type_kb, task_list_admin_kb, task_actions_kb,
    games_list_kb, game_detail_kb,
    BUTTON_KEYS, button_content_list_kb, button_edit_kb,
    retention_kb, stats_tabs_kb,
)
from keyboards.lottery import admin_lottery_kb, admin_lottery_pick_kb
from config import config

router = Router()


# ─── FSM States ──────────────────────────────────────────────────────────────

class AdminPromoStates(StatesGroup):
    code = State()
    reward_type = State()
    reward_fixed = State()
    reward_min = State()
    reward_max = State()
    usage_limit = State()


class AdminCreditStates(StatesGroup):
    user_id = State()
    amount = State()


class AdminDebitStates(StatesGroup):
    user_id = State()
    amount = State()


class AdminAddReferralStates(StatesGroup):
    user_id = State()
    count = State()


class AdminSettingsStates(StatesGroup):
    referral_reward = State()
    bonus_cooldown = State()
    bonus_min = State()
    bonus_max = State()
    payments_channel_id = State()
    payments_channel_url = State()
    stars_per_sponsor = State()


class AdminBroadcastStates(StatesGroup):
    photo = State()
    text = State()


class AdminTaskStates(StatesGroup):
    task_type = State()
    title = State()
    description = State()
    reward = State()
    channel_id = State()
    target_value = State()


class AdminBulkTaskStates(StatesGroup):
    title = State()
    description = State()
    reward = State()
    channels = State()


class AdminGameStates(StatesGroup):
    set_coeff = State()
    set_coeff1 = State()
    set_coeff2 = State()
    set_min_bet = State()
    set_daily_limit = State()
    set_bet_step = State()


class AdminButtonContentStates(StatesGroup):
    set_photo = State()
    set_text = State()


class AdminRetentionStates(StatesGroup):
    set_days = State()
    set_bonus = State()
    set_message = State()



class AdminDBImportStates(StatesGroup):
    waiting_file = State()


# ─── Guard ───────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ─── Entry ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.callback_query(lambda c: c.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.message.edit_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_main_kb())
    await callback.answer()


# ─── Stats ───────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:stats")
async def cb_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    today_start = datetime.combine(_date.today(), datetime.min.time())

    total_users = (await session.execute(select(func.count(User.user_id)))).scalar() or 0
    new_today = (await session.execute(
        select(func.count(User.user_id)).where(User.created_at >= today_start)
    )).scalar() or 0
    total_balance = (await session.execute(select(func.sum(User.stars_balance)))).scalar() or 0.0

    pending_count = (await session.execute(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == "pending")
    )).scalar() or 0
    pending_amount = (await session.execute(
        select(func.sum(Withdrawal.amount)).where(Withdrawal.status == "pending")
    )).scalar() or 0.0
    approved_amount = (await session.execute(
        select(func.sum(Withdrawal.amount)).where(Withdrawal.status == "approved")
    )).scalar() or 0.0
    rejected_count = (await session.execute(
        select(func.count(Withdrawal.id)).where(Withdrawal.status == "rejected")
    )).scalar() or 0

    total_games = (await session.execute(select(func.count(GameSession.id)))).scalar() or 0
    games_won = (await session.execute(
        select(func.count(GameSession.id)).where(GameSession.result == "win")
    )).scalar() or 0
    games_today = (await session.execute(
        select(func.count(GameSession.id)).where(GameSession.played_at >= today_start)
    )).scalar() or 0
    profit_games = (await session.execute(
        select(func.sum(GameSession.bet) - func.coalesce(func.sum(GameSession.payout), 0))
    )).scalar() or 0.0

    win_rate = round(games_won / total_games * 100) if total_games else 0

    await callback.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"<b>👥 Пользователи</b>\n"
        f"Всего: <b>{total_users}</b> | Новых сегодня: <b>{new_today}</b>\n"
        f"Звёзд на балансах: <b>{total_balance:.2f} ⭐</b>\n\n"
        f"<b>💸 Выплаты</b>\n"
        f"⏳ В ожидании: <b>{pending_count}</b> заявок (<b>{pending_amount:.2f} ⭐</b>)\n"
        f"✅ Выведено всего: <b>{approved_amount:.2f} ⭐</b>\n"
        f"❌ Отклонено: <b>{rejected_count}</b>\n\n"
        f"<b>🎮 Игры (всего)</b>\n"
        f"Всего: <b>{total_games}</b> | Сегодня: <b>{games_today}</b>\n"
        f"Побед: <b>{games_won}</b> (<b>{win_rate}%</b>)\n"
        f"Прибыль казино: <b>{profit_games:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=stats_tabs_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:stats_daily")
async def cb_stats_daily(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    lines = []
    for i in range(7):
        day = _date.today() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day + timedelta(days=1), datetime.min.time())

        new_users = (await session.execute(
            select(func.count(User.user_id)).where(
                User.created_at >= day_start, User.created_at < day_end
            )
        )).scalar() or 0
        games_count = (await session.execute(
            select(func.count(GameSession.id)).where(
                GameSession.played_at >= day_start, GameSession.played_at < day_end
            )
        )).scalar() or 0
        bets_sum = (await session.execute(
            select(func.coalesce(func.sum(GameSession.bet), 0)).where(
                GameSession.played_at >= day_start, GameSession.played_at < day_end
            )
        )).scalar() or 0.0
        payouts_sum = (await session.execute(
            select(func.coalesce(func.sum(GameSession.payout), 0)).where(
                GameSession.played_at >= day_start, GameSession.played_at < day_end,
                GameSession.result == "win",
            )
        )).scalar() or 0.0
        revenue = round(bets_sum - payouts_sum, 2)

        label = "Сегодня" if i == 0 else ("Вчера" if i == 1 else day.strftime("%d.%m"))
        lines.append(f"📅 <b>{label}</b>: 👥+{new_users} | 🎮{games_count} | 💰{revenue:.1f}⭐")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:stats")
    ]])
    await callback.message.edit_text(
        "📅 <b>Статистика по дням (7 дней)</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:stats_games")
async def cb_stats_games(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    game_icons = {
        "football": "⚽", "basketball": "🏀", "bowling": "🎳", "dice": "🎲", "slots": "🎰",
    }
    lines = []
    for game, icon in game_icons.items():
        total = (await session.execute(
            select(func.count(GameSession.id)).where(GameSession.game_type == game)
        )).scalar() or 0
        wins = (await session.execute(
            select(func.count(GameSession.id)).where(
                GameSession.game_type == game, GameSession.result == "win"
            )
        )).scalar() or 0
        bets = (await session.execute(
            select(func.coalesce(func.sum(GameSession.bet), 0)).where(GameSession.game_type == game)
        )).scalar() or 0.0
        payouts = (await session.execute(
            select(func.coalesce(func.sum(GameSession.payout), 0)).where(
                GameSession.game_type == game, GameSession.result == "win"
            )
        )).scalar() or 0.0
        profit = round(bets - payouts, 2)
        win_rate = round(wins / total * 100) if total else 0
        lines.append(
            f"{icon} <b>{game.capitalize()}</b>: {total} игр | {win_rate}% побед | +{profit:.2f}⭐"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:stats")
    ]])
    await callback.message.edit_text(
        "🎮 <b>Статистика по играм</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:stats_commissions")
async def cb_stats_commissions(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    transfer_count = (await session.execute(select(func.count(Transfer.id)))).scalar() or 0
    transfer_comm = (await session.execute(
        select(func.coalesce(func.sum(Transfer.commission), 0))
    )).scalar() or 0.0

    duel_count = (await session.execute(
        select(func.count(Duel.id)).where(Duel.status == "finished", Duel.joiner_id.isnot(None))
    )).scalar() or 0
    duel_bets_sum = (await session.execute(
        select(func.coalesce(func.sum(Duel.amount), 0)).where(
            Duel.status == "finished", Duel.joiner_id.isnot(None)
        )
    )).scalar() or 0.0
    duel_comm = round(duel_bets_sum * 2 * 0.20, 2)

    total_comm = round(transfer_comm + duel_comm, 2)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:stats")
    ]])
    await callback.message.edit_text(
        f"💰 <b>Статистика комиссий</b>\n\n"
        f"<b>💸 Переводы</b>\n"
        f"Транзакций: <b>{transfer_count}</b>\n"
        f"Комиссий собрано: <b>{transfer_comm:.2f} ⭐</b>\n\n"
        f"<b>⚔️ Дуэли</b>\n"
        f"Завершённых: <b>{duel_count}</b>\n"
        f"Комиссий собрано: <b>{duel_comm:.2f} ⭐</b>\n\n"
        f"<b>Итого комиссий: {total_comm:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=back_kb,
    )
    await callback.answer()


# ─── Promo: Add ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:add_promo")
async def cb_add_promo(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminPromoStates.code)
    await callback.message.edit_text("🎟 Введи код промокода (латиница, без пробелов):")
    await callback.answer()


@router.message(AdminPromoStates.code)
async def msg_promo_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    code = message.text.strip().upper()
    if " " in code:
        await message.answer("❌ Код не должен содержать пробелы. Попробуй снова:")
        return
    existing = (await session.execute(select(PromoCode).where(PromoCode.code == code))).scalar_one_or_none()
    if existing:
        await message.answer("❌ Такой код уже существует. Введи другой:")
        return
    await state.update_data(code=code)
    await state.set_state(AdminPromoStates.reward_type)
    await message.answer("Выбери тип награды:", reply_markup=promo_reward_type_kb())


@router.callback_query(lambda c: c.data in ("promo_type:fixed", "promo_type:random"))
async def cb_promo_type(callback: CallbackQuery, state: FSMContext) -> None:
    is_random = callback.data == "promo_type:random"
    await state.update_data(is_random=is_random)
    if is_random:
        await state.set_state(AdminPromoStates.reward_min)
        await callback.message.edit_text("Введи минимальную награду (число):")
    else:
        await state.set_state(AdminPromoStates.reward_fixed)
        await callback.message.edit_text("Введи фиксированную награду (число):")
    await callback.answer()


@router.message(AdminPromoStates.reward_fixed)
async def msg_promo_fixed(message: Message, state: FSMContext) -> None:
    try:
        reward = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число, например: 5 или 2.5")
        return
    await state.update_data(reward=reward)
    await state.set_state(AdminPromoStates.usage_limit)
    await message.answer("Лимит использований (0 = безлимитный):")


@router.message(AdminPromoStates.reward_min)
async def msg_promo_min(message: Message, state: FSMContext) -> None:
    try:
        reward_min = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    await state.update_data(reward_min=reward_min)
    await state.set_state(AdminPromoStates.reward_max)
    await message.answer("Введи максимальную награду:")


@router.message(AdminPromoStates.reward_max)
async def msg_promo_max(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        reward_max = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    if reward_max <= data["reward_min"]:
        await message.answer("❌ Максимум должен быть больше минимума:")
        return
    await state.update_data(reward_max=reward_max, reward=0.0)
    await state.set_state(AdminPromoStates.usage_limit)
    await message.answer("Лимит использований (0 = безлимитный):")


@router.message(AdminPromoStates.usage_limit)
async def msg_promo_limit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        limit_raw = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи целое число:")
        return
    data = await state.get_data()
    await state.clear()

    promo = PromoCode(
        code=data["code"],
        reward=data.get("reward", 0.0),
        is_random=data.get("is_random", False),
        reward_min=data.get("reward_min"),
        reward_max=data.get("reward_max"),
        usage_limit=limit_raw if limit_raw > 0 else None,
    )
    session.add(promo)
    await session.commit()

    reward_desc = (
        f"{data.get('reward_min')}–{data.get('reward_max')} ⭐ (случайно)"
        if data.get("is_random")
        else f"{data.get('reward', 0):.2f} ⭐"
    )
    limit_desc = str(limit_raw) if limit_raw > 0 else "безлимитный"

    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"Код: <code>{promo.code}</code>\n"
        f"Награда: {reward_desc}\n"
        f"Лимит: {limit_desc}",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Promo: List & Actions ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:list_promos")
async def cb_list_promos(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    promos = (await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))).scalars().all()
    if not promos:
        await callback.message.edit_text("Промокодов нет.", reply_markup=admin_back_kb())
        await callback.answer()
        return
    await callback.message.edit_text("🎟 <b>Список промокодов:</b>", parse_mode="HTML", reply_markup=promo_list_kb(promos))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:promo_info:"))
async def cb_promo_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    promo_id = int(callback.data.split(":")[2])
    promo = await session.get(PromoCode, promo_id)
    if not promo:
        await callback.answer("Промокод не найден.", show_alert=True)
        return

    reward_desc = (
        f"{promo.reward_min}–{promo.reward_max} ⭐ (случайно)"
        if promo.is_random
        else f"{promo.reward:.2f} ⭐"
    )
    limit_desc = str(promo.usage_limit) if promo.usage_limit else "безлимитный"
    status = "✅ Активен" if promo.is_active else "❌ Неактивен"

    await callback.message.edit_text(
        f"🎟 <b>{promo.code}</b>\n\n"
        f"Статус: {status}\n"
        f"Награда: {reward_desc}\n"
        f"Лимит: {limit_desc}\n"
        f"Использований: {promo.usage_count}",
        parse_mode="HTML",
        reply_markup=promo_actions_kb(promo.id, promo.is_active),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:promo_toggle:"))
async def cb_promo_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    promo_id = int(callback.data.split(":")[2])
    promo = await session.get(PromoCode, promo_id)
    if promo:
        promo.is_active = not promo.is_active
        await session.commit()
        await callback.answer("Статус изменён.")
        await callback.message.edit_reply_markup(reply_markup=promo_actions_kb(promo.id, promo.is_active))


@router.callback_query(lambda c: c.data and c.data.startswith("admin:promo_delete:"))
async def cb_promo_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    promo_id = int(callback.data.split(":")[2])
    promo = await session.get(PromoCode, promo_id)
    if promo:
        await session.delete(promo)
        await session.commit()
    await callback.answer("Промокод удалён.")
    promos = (await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))).scalars().all()
    await callback.message.edit_text("🎟 <b>Список промокодов:</b>", parse_mode="HTML", reply_markup=promo_list_kb(promos))


# ─── Credit ──────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:credit")
async def cb_credit(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminCreditStates.user_id)
    await callback.message.edit_text("💳 Введи Telegram ID пользователя:")
    await callback.answer()


@router.message(AdminCreditStates.user_id)
async def msg_credit_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID:")
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Пользователь не найден. Введи другой ID:")
        return
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminCreditStates.amount)
    await message.answer(f"Пользователь: {user.first_name} (@{user.username})\nВведи сумму для начисления:")


@router.message(AdminCreditStates.amount)
async def msg_credit_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    data = await state.get_data()
    await state.clear()

    user = await session.get(User, data["target_user_id"])
    user.stars_balance += amount
    await session.commit()

    await message.answer(
        f"✅ Начислено <b>{amount} ⭐</b> пользователю {user.first_name}.\n"
        f"Новый баланс: <b>{user.stars_balance:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Debit ───────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:debit")
async def cb_debit(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminDebitStates.user_id)
    await callback.message.edit_text("➖ Введи Telegram ID пользователя, у которого нужно списать звёзды:")
    await callback.answer()


@router.message(AdminDebitStates.user_id)
async def msg_debit_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID:")
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Пользователь не найден. Введи другой ID:")
        return
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminDebitStates.amount)
    await message.answer(
        f"Пользователь: {user.first_name} (@{user.username})\n"
        f"Баланс: <b>{user.stars_balance:.2f} ⭐</b>\n\n"
        f"Введи сумму для списания:",
        parse_mode="HTML",
    )


@router.message(AdminDebitStates.amount)
async def msg_debit_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    data = await state.get_data()
    await state.clear()

    user = await session.get(User, data["target_user_id"])
    if user.stars_balance < amount:
        await message.answer(
            f"❌ Недостаточно звёзд у пользователя.\n"
            f"Баланс: <b>{user.stars_balance:.2f} ⭐</b>, списать: <b>{amount} ⭐</b>",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
        return
    user.stars_balance -= amount
    await session.commit()

    await message.answer(
        f"✅ Списано <b>{amount} ⭐</b> у пользователя {user.first_name}.\n"
        f"Новый баланс: <b>{user.stars_balance:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Add Referrals ───────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:add_referral")
async def cb_add_referral(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminAddReferralStates.user_id)
    await callback.message.edit_text("👥 Введи Telegram ID пользователя, которому начислить рефералов:")
    await callback.answer()


@router.message(AdminAddReferralStates.user_id)
async def msg_add_referral_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID:")
        return
    user = await session.get(User, uid)
    if not user:
        await message.answer("❌ Пользователь не найден. Введи другой ID:")
        return
    await state.update_data(target_user_id=uid)
    await state.set_state(AdminAddReferralStates.count)
    await message.answer(
        f"Пользователь: {user.first_name} (@{user.username})\n"
        f"Текущее кол-во рефералов: <b>{user.referrals_count}</b>\n\n"
        f"Введи количество рефералов для начисления:",
        parse_mode="HTML",
    )


@router.message(AdminAddReferralStates.count)
async def msg_add_referral_count(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        count = int(message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное целое число:")
        return
    data = await state.get_data()
    await state.clear()

    user = await session.get(User, data["target_user_id"])
    user.referrals_count += count
    await session.commit()

    await message.answer(
        f"✅ Начислено <b>{count}</b> рефералов пользователю {user.first_name}.\n"
        f"Новое кол-во рефералов: <b>{user.referrals_count}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Settings ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:settings")
async def cb_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    rr = (await session.get(BotSettings, "referral_reward"))
    bc = (await session.get(BotSettings, "bonus_cooldown_hours"))
    bmin = (await session.get(BotSettings, "bonus_min"))
    bmax = (await session.get(BotSettings, "bonus_max"))
    pch = (await session.get(BotSettings, "payments_channel_id"))
    pch_url = (await session.get(BotSettings, "payments_channel_url"))
    mode_row = await session.get(BotSettings, "referral_mode")
    mode = mode_row.value if mode_row else "botohub_flyer"
    sps_row = await session.get(BotSettings, "stars_per_sponsor")
    stars_per_sponsor = float(sps_row.value) if sps_row and sps_row.value else 0.45
    rt_row = await session.get(BotSettings, "reward_type")
    reward_type = rt_row.value if rt_row else "per_sponsor"
    mode_label = "🔵 Спонсоры" if mode == "sponsors" else "🟢 Флаер + БотоХаб"
    rt_label = "💰 Фиксированная" if reward_type == "fixed" else "📊 За спонсоров"

    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"⭐ Фикс. награда за реферала: <b>{rr.value if rr else '?'}</b>\n"
        f"💫 Тип награды: <b>{rt_label}</b>\n"
        f"⏱ Кулдаун бонуса: <b>{bc.value if bc else '?'} ч</b>\n"
        f"🎁 Бонус мин: <b>{bmin.value if bmin else '?'}</b>\n"
        f"🎁 Бонус макс: <b>{bmax.value if bmax else '?'}</b>\n"
        f"📢 ID канала выплат: <b>{pch.value if pch and pch.value else 'не задан'}</b>\n"
        f"🔗 Ссылка канала: <b>{pch_url.value if pch_url and pch_url.value else 'не задана'}</b>\n"
        f"🔄 Режим рефералов: <b>{mode_label}</b>\n"
        f"⭐ Звёзд за спонсора: <b>{stars_per_sponsor}</b>",
        parse_mode="HTML",
        reply_markup=admin_settings_kb(),
    )
    await callback.answer()


async def _ask_setting(callback: CallbackQuery, state: FSMContext, state_obj: State, prompt: str) -> None:
    await state.set_state(state_obj)
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.callback_query(lambda c: c.data == "settings:referral_reward")
async def cb_set_rr(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await _ask_setting(callback, state, AdminSettingsStates.referral_reward, "Введи новую награду за реферала (число):")


@router.callback_query(lambda c: c.data == "settings:bonus_cooldown")
async def cb_set_cooldown(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await _ask_setting(callback, state, AdminSettingsStates.bonus_cooldown, "Введи кулдаун бонуса в часах (целое):")


@router.callback_query(lambda c: c.data == "settings:bonus_min")
async def cb_set_bmin(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await _ask_setting(callback, state, AdminSettingsStates.bonus_min, "Введи минимальный бонус (число):")


@router.callback_query(lambda c: c.data == "settings:bonus_max")
async def cb_set_bmax(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await _ask_setting(callback, state, AdminSettingsStates.bonus_max, "Введи максимальный бонус (число):")


@router.callback_query(lambda c: c.data == "settings:payments_channel_id")
async def cb_set_payments_channel(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminSettingsStates.payments_channel_id)
    await callback.message.edit_text(
        "📢 Введи ID канала выплат:\n"
        "Примеры: <code>-1001234567890</code> или <code>@mychannel</code>\n\n"
        "Бот должен быть администратором этого канала.",
        parse_mode="HTML",
    )
    await callback.answer()


async def _save_setting(message: Message, state: FSMContext, session: AsyncSession, key: str) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    await state.clear()
    await set_setting(session, key, str(val))
    await message.answer(f"✅ Настройка обновлена: <b>{key}</b> = {val}", parse_mode="HTML", reply_markup=admin_main_kb())


@router.message(AdminSettingsStates.referral_reward)
async def msg_set_rr(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _save_setting(message, state, session, "referral_reward")


@router.message(AdminSettingsStates.bonus_cooldown)
async def msg_set_cooldown(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _save_setting(message, state, session, "bonus_cooldown_hours")


@router.message(AdminSettingsStates.bonus_min)
async def msg_set_bmin(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _save_setting(message, state, session, "bonus_min")


@router.message(AdminSettingsStates.bonus_max)
async def msg_set_bmax(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _save_setting(message, state, session, "bonus_max")


@router.message(AdminSettingsStates.payments_channel_id)
async def msg_set_payments_channel(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    value = message.text.strip()
    await set_setting(session, "payments_channel_id", value)
    await message.answer(
        f"✅ ID канала выплат установлен: <code>{value}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(lambda c: c.data == "settings:payments_channel_url")
async def cb_set_payments_channel_url(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminSettingsStates.payments_channel_url)
    await callback.message.edit_text(
        "🔗 Введи публичную ссылку на канал выплат:\n"
        "Пример: <code>https://t.me/mychannel</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminSettingsStates.payments_channel_url)
async def msg_set_payments_channel_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    value = message.text.strip()
    await set_setting(session, "payments_channel_url", value)
    await message.answer(
        f"✅ Ссылка на канал выплат установлена: <code>{value}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Settings: Referral mode toggle ─────────────────────────────────────────

@router.callback_query(lambda c: c.data == "settings:referral_mode")
async def cb_settings_referral_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    row = await session.get(BotSettings, "referral_mode")
    current = row.value if row else "botohub_flyer"
    new_mode = "sponsors" if current == "botohub_flyer" else "botohub_flyer"
    await set_setting(session, "referral_mode", new_mode)
    await session.commit()
    mode_label = "🔵 Спонсоры" if new_mode == "sponsors" else "🟢 Флаер + БотоХаб"
    await callback.answer(f"Режим изменён: {mode_label}", show_alert=True)
    await cb_settings(callback, session)


@router.callback_query(lambda c: c.data == "settings:stars_per_sponsor")
async def cb_settings_stars_per_sponsor(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    row = await session.get(BotSettings, "stars_per_sponsor")
    current = float(row.value) if row and row.value else 0.45
    await state.set_state(AdminSettingsStates.stars_per_sponsor)
    await callback.message.edit_text(
        f"⭐ Текущее значение звёзд за спонсора: <b>{current}</b>\n\n"
        f"Введи новое значение (например: 0.45 или 1):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminSettingsStates.stars_per_sponsor)
async def msg_set_stars_per_sponsor(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    await state.clear()
    await set_setting(session, "stars_per_sponsor", str(val))
    await session.commit()
    await message.answer(
        f"✅ Звёзд за спонсора: <b>{val}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Settings: Reward type toggle ────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "settings:reward_type")
async def cb_settings_reward_type(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return
    row = await session.get(BotSettings, "reward_type")
    current = row.value if row else "per_sponsor"
    new_type = "fixed" if current == "per_sponsor" else "per_sponsor"
    await set_setting(session, "reward_type", new_type)
    await session.commit()
    label = "💰 Фиксированная" if new_type == "fixed" else "📊 За спонсоров"
    await callback.answer(f"Тип награды изменён: {label}", show_alert=True)
    await cb_settings(callback, session)


# ─── Broadcast ───────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminBroadcastStates.photo)
    await callback.message.edit_text(
        "📢 <b>Рассылка — шаг 1/2</b>\n\n"
        "Отправь фото для рассылки.\n"
        "Если фото не нужно — напиши <code>/skip</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminBroadcastStates.photo)
async def msg_broadcast_photo(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() == "/skip":
        await state.update_data(photo_id=None)
    elif message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    else:
        await message.answer("❌ Отправь фото или напиши /skip:")
        return
    await state.set_state(AdminBroadcastStates.text)
    await message.answer(
        "📢 <b>Рассылка — шаг 2/2</b>\n\n"
        "Введи текст рассылки (HTML поддерживается):",
        parse_mode="HTML",
    )


@router.message(AdminBroadcastStates.text)
async def msg_broadcast(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    text = message.text or message.caption or ""
    photo_id = data.get("photo_id")

    users = (await session.execute(select(User.user_id))).scalars().all()
    sent, failed = 0, 0
    for uid in users:
        try:
            if photo_id:
                await bot.send_photo(uid, photo_id, caption=text, parse_mode="HTML")
            else:
                await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена.\nДоставлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Withdrawal: Approve / Reject (from admin channel) ───────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("withdrawal:"))
async def cb_withdrawal_action(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    parts = callback.data.split(":")
    action, withdrawal_id = parts[1], int(parts[2])

    withdrawal = await session.get(Withdrawal, withdrawal_id)
    if not withdrawal:
        return await callback.answer("Заявка не найдена.", show_alert=True)
    if withdrawal.status != "pending":
        return await callback.answer(f"Заявка уже обработана: {withdrawal.status}", show_alert=True)

    withdrawal.status = "approved" if action == "approve" else "rejected"
    withdrawal.processed_at = datetime.utcnow()

    user = await session.get(User, withdrawal.user_id)
    if action == "reject" and user:
        user.stars_balance += withdrawal.amount

    await session.commit()

    status_text = "✅ Принята" if action == "approve" else "❌ Отклонена"

    # Update admin channel message (remove buttons, keep text)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(status_text)

    # Edit payments channel message with updated status
    uname = user.username if user else "unknown"
    uid = withdrawal.user_id
    if withdrawal.payments_message_id:
        pch = await session.get(BotSettings, "payments_channel_id")
        if pch and pch.value:
            try:
                await bot.edit_message_text(
                    chat_id=pch.value,
                    message_id=withdrawal.payments_message_id,
                    text=build_withdrawal_msg(withdrawal.id, uname, uid, withdrawal.amount, withdrawal.status),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # Notify user
    try:
        if user:
            if action == "approve":
                approve_content = await get_button_content(session, "withdrawal:approved")
                if approve_content and (approve_content.text or approve_content.photo_file_id):
                    raw_text = approve_content.text or ""
                    notify_text = raw_text.replace("{amount}", f"{withdrawal.amount:.0f}") or None
                    if approve_content.photo_file_id:
                        await bot.send_photo(
                            withdrawal.user_id,
                            approve_content.photo_file_id,
                            caption=notify_text,
                            parse_mode="HTML" if notify_text else None,
                        )
                    else:
                        await bot.send_message(withdrawal.user_id, notify_text, parse_mode="HTML")
                else:
                    await bot.send_message(
                        withdrawal.user_id,
                        f"💸 Ваша заявка на вывод <b>{withdrawal.amount:.0f} ⭐</b> одобрена!",
                        parse_mode="HTML",
                    )
            else:
                await bot.send_message(
                    withdrawal.user_id,
                    f"❌ Ваша заявка на вывод <b>{withdrawal.amount:.0f} ⭐</b> отклонена.",
                    parse_mode="HTML",
                )
    except Exception:
        pass


# ─── Tasks: Management ───────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:tasks")
async def cb_admin_tasks(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "📋 <b>Управление заданиями</b>",
        parse_mode="HTML",
        reply_markup=task_management_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:list_tasks")
async def cb_list_tasks(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    tasks = (await session.execute(select(Task).order_by(Task.created_at.desc()))).scalars().all()
    if not tasks:
        await callback.message.edit_text("Заданий нет.", reply_markup=task_management_kb())
        await callback.answer()
        return
    await callback.message.edit_text(
        "📋 <b>Список заданий:</b>",
        parse_mode="HTML",
        reply_markup=task_list_admin_kb(tasks),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:task_info:"))
async def cb_task_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    task_id = int(callback.data.split(":")[2])
    task = await session.get(Task, task_id)
    if not task:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    completions_count = (await session.execute(
        select(func.count(TaskCompletion.id)).where(TaskCompletion.task_id == task_id)
    )).scalar()

    type_label = {"subscribe": "📢 Подписка на канал", "referrals": "👥 Рефералы", "linkni": "🔗 Linkni"}.get(task.task_type, task.task_type)
    status = "✅ Активно" if task.is_active else "❌ Неактивно"

    extra = ""
    if task.task_type == "subscribe":
        extra = f"\nКанал: <code>{task.channel_id}</code>"
    elif task.task_type == "referrals":
        extra = f"\nЦель: {task.target_value} рефералов"
    elif task.task_type == "linkni":
        extra = f"\nLinkni code: <code>{task.channel_id}</code>"

    await callback.message.edit_text(
        f"📌 <b>{task.title}</b>\n\n"
        f"{task.description}\n\n"
        f"Тип: {type_label}\n"
        f"Награда: <b>{task.reward} ⭐</b>\n"
        f"Статус: {status}\n"
        f"Выполнений: <b>{completions_count}</b>"
        f"{extra}",
        parse_mode="HTML",
        reply_markup=task_actions_kb(task.id, task.is_active),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:task_toggle:"))
async def cb_task_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    task_id = int(callback.data.split(":")[2])
    task = await session.get(Task, task_id)
    if task:
        task.is_active = not task.is_active
        await session.commit()
        await callback.answer("Статус изменён.")
        await callback.message.edit_reply_markup(reply_markup=task_actions_kb(task.id, task.is_active))


@router.callback_query(lambda c: c.data and c.data.startswith("admin:task_delete:"))
async def cb_task_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    task_id = int(callback.data.split(":")[2])
    task = await session.get(Task, task_id)
    if task:
        await session.delete(task)
        await session.commit()
    await callback.answer("Задание удалено.")
    tasks = (await session.execute(select(Task).order_by(Task.created_at.desc()))).scalars().all()
    if not tasks:
        await callback.message.edit_text("Заданий нет.", reply_markup=task_management_kb())
    else:
        await callback.message.edit_text(
            "📋 <b>Список заданий:</b>",
            parse_mode="HTML",
            reply_markup=task_list_admin_kb(tasks),
        )


# ─── Tasks: Add (FSM) ────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:add_task")
async def cb_add_task(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminTaskStates.task_type)
    await callback.message.edit_text("📋 Выбери тип задания:", reply_markup=task_type_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("task_type:"))
async def cb_task_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    task_type = callback.data.split(":")[1]
    await state.update_data(task_type=task_type)
    await state.set_state(AdminTaskStates.title)
    await callback.message.edit_text("✏️ Введи название задания:")
    await callback.answer()


@router.message(AdminTaskStates.title)
async def msg_task_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminTaskStates.description)
    await message.answer("📝 Введи описание задания:")


@router.message(AdminTaskStates.description)
async def msg_task_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminTaskStates.reward)
    await message.answer("💰 Введи награду (число, например: 5 или 2.5):")


@router.message(AdminTaskStates.reward)
async def msg_task_reward(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        reward = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    data = await state.get_data()
    await state.update_data(reward=reward)

    if data["task_type"] == "subscribe":
        await state.set_state(AdminTaskStates.channel_id)
        await message.answer(
            "📢 Введи ID или username канала:\n"
            "Примеры: <code>@mychannel</code> или <code>-1001234567890</code>\n\n"
            "<b>Важно:</b> бот должен быть администратором канала для проверки подписки.",
            parse_mode="HTML",
        )
    elif data["task_type"] == "linkni":
        await state.set_state(AdminTaskStates.channel_id)
        await message.answer(
            "🔗 Введи Linkni code для задания:\n"
            "Пример: <code>2o2i</code>\n\n"
            "Код берётся из ссылки: <code>https://t.me/linknibot/app?startapp=x_<b>КОД</b></code>",
            parse_mode="HTML",
        )
    elif data["task_type"] == "referrals":
        await state.set_state(AdminTaskStates.target_value)
        await message.answer("👥 Введи необходимое количество рефералов (целое число):")
    else:
        await _save_task(message, state, session)


@router.message(AdminTaskStates.channel_id)
async def msg_task_channel(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    channel_id = message.text.strip()
    data = await state.get_data()

    # Linkni tasks use channel_id as the Linkni code — no channel admin check needed
    if data.get("task_type") == "linkni":
        await state.update_data(channel_id=channel_id, reward=0.25)
        await _save_task(message, state, session)
        return

    # Verify bot is an admin of the channel before saving the task
    try:
        bot_me = await bot.get_me()
        member = await bot.get_chat_member(channel_id, bot_me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                "❌ <b>Бот не является администратором канала.</b>\n\n"
                "Назначьте бота администратором с правом просмотра участников и повторите попытку.",
                parse_mode="HTML",
            )
            return
    except Exception as e:
        await message.answer(
            f"❌ <b>Не удалось получить доступ к каналу</b> <code>{channel_id}</code>\n\n"
            "Убедитесь, что:\n"
            "• Бот добавлен в канал\n"
            "• Бот назначен администратором\n"
            "• ID канала введён верно (например: <code>@mychannel</code> или <code>-1001234567890</code>)",
            parse_mode="HTML",
        )
        import logging
        logging.getLogger(__name__).warning("Channel access check failed for %s: %s", channel_id, e)
        return

    await state.update_data(channel_id=channel_id)
    await _save_task(message, state, session)


@router.message(AdminTaskStates.target_value)
async def msg_task_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        target = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи целое число:")
        return
    await state.update_data(target_value=target)
    await _save_task(message, state, session)


async def _save_task(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()

    task = Task(
        task_type=data["task_type"],
        title=data["title"],
        description=data["description"],
        reward=data["reward"],
        channel_id=data.get("channel_id"),
        target_value=data.get("target_value"),
    )
    session.add(task)
    await session.commit()

    type_label = {"subscribe": "📢 Подписка на канал", "referrals": "👥 Рефералы", "linkni": "🔗 Linkni"}.get(data["task_type"], data["task_type"])
    extra = ""
    if data.get("channel_id"):
        extra = f"\nКанал: <code>{data['channel_id']}</code>"
    elif data.get("target_value"):
        extra = f"\nЦель: {data['target_value']} рефералов"

    await message.answer(
        f"✅ Задание создано!\n\n"
        f"<b>{data['title']}</b>\n"
        f"Тип: {type_label}\n"
        f"Награда: <b>{data['reward']} ⭐</b>"
        f"{extra}",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Tasks: Bulk Add (FSM) ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "admin:add_bulk_tasks")
async def cb_add_bulk_tasks(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminBulkTaskStates.title)
    await callback.message.edit_text(
        "📦 <b>Массовое добавление каналов</b>\n\n"
        "Введи общее название для всех заданий:\n"
        "<i>(например: Подписаться на канал)</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminBulkTaskStates.title)
async def msg_bulk_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminBulkTaskStates.description)
    await message.answer("📝 Введи общее описание для всех заданий:")


@router.message(AdminBulkTaskStates.description)
async def msg_bulk_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminBulkTaskStates.reward)
    await message.answer("💰 Введи награду для каждого задания (число, например: 5):")


@router.message(AdminBulkTaskStates.reward)
async def msg_bulk_reward(message: Message, state: FSMContext) -> None:
    try:
        reward = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число:")
        return
    await state.update_data(reward=reward)
    await state.set_state(AdminBulkTaskStates.channels)
    await message.answer(
        "📢 Введи ID или username каналов — <b>каждый с новой строки</b>:\n\n"
        "Пример:\n"
        "<code>@channel1\n@channel2\n-1001234567890\n@channel4</code>\n\n"
        "<b>Важно:</b> бот должен быть администратором каждого канала.",
        parse_mode="HTML",
    )


@router.message(AdminBulkTaskStates.channels)
async def msg_bulk_channels(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()

    lines = [line.strip() for line in message.text.strip().splitlines() if line.strip()]
    if not lines:
        await message.answer("❌ Нет каналов для добавления.")
        return

    ok = []
    failed = []

    bot_me = await bot.get_me()
    for channel_id in lines:
        try:
            member = await bot.get_chat_member(channel_id, bot_me.id)
            if member.status not in ("administrator", "creator"):
                failed.append(f"<code>{channel_id}</code> — бот не админ")
                continue
            task = Task(
                task_type="subscribe",
                title=data["title"],
                description=data["description"],
                reward=data["reward"],
                channel_id=channel_id,
            )
            session.add(task)
            ok.append(f"<code>{channel_id}</code>")
        except Exception as e:
            failed.append(f"<code>{channel_id}</code> — ошибка доступа")
            import logging
            logging.getLogger(__name__).warning("Bulk task channel error %s: %s", channel_id, e)

    if ok:
        await session.commit()

    lines_out = []
    if ok:
        lines_out.append(f"✅ Создано заданий: <b>{len(ok)}</b>\n" + "\n".join(ok))
    if failed:
        lines_out.append(f"❌ Не добавлены ({len(failed)}):\n" + "\n".join(failed))

    await message.answer(
        "📦 <b>Результат массового добавления</b>\n\n" + "\n\n".join(lines_out),
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Games: Management ────────────────────────────────────────────────────────

_GAME_LABELS_ADMIN = {
    "football":   "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
    "bowling":    "🎳 Боулинг",
    "dice":       "🎲 Кубики",
    "slots":      "🎰 Слоты",
}
_GAME_TYPES_ADMIN = ["football", "basketball", "bowling", "dice", "slots"]


async def _get_game_float(session: AsyncSession, key: str, default: float) -> float:
    row = await session.get(BotSettings, key)
    if row:
        try:
            return float(row.value)
        except ValueError:
            pass
    return default


@router.callback_query(lambda c: c.data == "admin:games")
async def cb_admin_games(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    statuses = {}
    for game in _GAME_TYPES_ADMIN:
        row = await session.get(BotSettings, f"game_{game}_enabled")
        statuses[game] = (row.value == "1") if row else True

    await callback.message.edit_text(
        "🎮 <b>Управление играми</b>\n\nВыбери игру для настройки:",
        parse_mode="HTML",
        reply_markup=games_list_kb(statuses),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:info:"))
async def cb_admin_game_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    game_type = callback.data.split(":")[2]
    label = _GAME_LABELS_ADMIN.get(game_type, game_type)

    enabled_row = await session.get(BotSettings, f"game_{game_type}_enabled")
    is_enabled = (enabled_row.value == "1") if enabled_row else True
    min_bet = await _get_game_float(session, f"game_{game_type}_min_bet", 1.0)
    bet_step = await _get_game_float(session, f"game_{game_type}_bet_step", 1.0)
    daily_limit_row = await session.get(BotSettings, f"game_{game_type}_daily_limit")
    daily_limit = int(daily_limit_row.value) if daily_limit_row else 0

    if game_type == "slots":
        c1 = await _get_game_float(session, "game_slots_coeff1", 5.0)
        c2 = await _get_game_float(session, "game_slots_coeff2", 2.0)
        coeff_line = f"📈 Коэф. Tier 1 (1–3): <b>x{c1}</b>\n📈 Коэф. Tier 2 (4–10): <b>x{c2}</b>"
    else:
        coeff = await _get_game_float(session, f"game_{game_type}_coeff", 1.0)
        coeff_line = f"📈 Коэффициент: <b>x{coeff}</b>"

    status_text = "✅ Включена" if is_enabled else "❌ Отключена"
    limit_text = str(daily_limit) if daily_limit > 0 else "∞ (без лимита)"
    step_text = f"{bet_step:.4g} ⭐" if bet_step != 1.0 else "1 ⭐ (без ограничений)"

    await callback.message.edit_text(
        f"🎮 <b>{label}</b>\n\n"
        f"Статус: {status_text}\n"
        f"{coeff_line}\n"
        f"💰 Мин. ставка: <b>{min_bet:.0f} ⭐</b>\n"
        f"👣 Шаг ставки: <b>{step_text}</b>\n"
        f"🔢 Лимит в день: <b>{limit_text}</b>",
        parse_mode="HTML",
        reply_markup=game_detail_kb(game_type, is_enabled),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:toggle:"))
async def cb_admin_game_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    game_type = callback.data.split(":")[2]
    key = f"game_{game_type}_enabled"
    row = await session.get(BotSettings, key)
    new_val = "0" if (row and row.value == "1") else "1"
    await set_setting(session, key, new_val)

    await callback.answer("Статус изменён.")
    # Refresh info page
    callback.data = f"agame:info:{game_type}"
    await cb_admin_game_info(callback, session)


@router.callback_query(lambda c: c.data and c.data.startswith("agame:coeff:"))
async def cb_admin_game_coeff(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    game_type = callback.data.split(":")[2]
    await state.set_state(AdminGameStates.set_coeff)
    await state.update_data(game_type=game_type)
    await callback.message.edit_text(
        f"📈 Введи новый коэффициент для {_GAME_LABELS_ADMIN[game_type]} (например: 3.0):"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:coeff1:"))
async def cb_admin_game_coeff1(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminGameStates.set_coeff1)
    await state.update_data(game_type="slots")
    await callback.message.edit_text("📈 Введи коэффициент Tier 1 🎰 (значения 1–3), например: 5.0:")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:coeff2:"))
async def cb_admin_game_coeff2(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminGameStates.set_coeff2)
    await state.update_data(game_type="slots")
    await callback.message.edit_text("📈 Введи коэффициент Tier 2 🎰 (значения 4–10), например: 2.0:")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:min_bet:"))
async def cb_admin_game_min_bet(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    game_type = callback.data.split(":")[2]
    await state.set_state(AdminGameStates.set_min_bet)
    await state.update_data(game_type=game_type)
    await callback.message.edit_text(f"💰 Введи минимальную ставку для {_GAME_LABELS_ADMIN[game_type]} (например: 1):")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:daily_limit:"))
async def cb_admin_game_daily_limit(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    game_type = callback.data.split(":")[2]
    await state.set_state(AdminGameStates.set_daily_limit)
    await state.update_data(game_type=game_type)
    await callback.message.edit_text(
        f"🔢 Введи лимит игр в день для {_GAME_LABELS_ADMIN[game_type]}:\n(0 = без ограничений)"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("agame:bet_step:"))
async def cb_admin_game_bet_step(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    game_type = callback.data.split(":")[2]
    await state.set_state(AdminGameStates.set_bet_step)
    await state.update_data(game_type=game_type)
    await callback.message.edit_text(
        f"👣 Введи шаг ставки для {_GAME_LABELS_ADMIN[game_type]}:\n"
        f"(1 = любая сумма, 5 = кратно 5, 10 = кратно 10 и т.д.)"
    )
    await callback.answer()


@router.message(AdminGameStates.set_coeff)
async def msg_admin_game_coeff(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    data = await state.get_data()
    await state.clear()
    game_type = data["game_type"]
    await set_setting(session, f"game_{game_type}_coeff", str(val))
    await message.answer(
        f"✅ Коэффициент {_GAME_LABELS_ADMIN[game_type]} установлен: <b>x{val}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(AdminGameStates.set_coeff1)
async def msg_admin_game_coeff1(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    await state.clear()
    await set_setting(session, "game_slots_coeff1", str(val))
    await message.answer(
        f"✅ Коэффициент Tier 1 🎰 установлен: <b>x{val}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(AdminGameStates.set_coeff2)
async def msg_admin_game_coeff2(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    await state.clear()
    await set_setting(session, "game_slots_coeff2", str(val))
    await message.answer(
        f"✅ Коэффициент Tier 2 🎰 установлен: <b>x{val}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(AdminGameStates.set_min_bet)
async def msg_admin_game_min_bet(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return
    data = await state.get_data()
    await state.clear()
    game_type = data["game_type"]
    await set_setting(session, f"game_{game_type}_min_bet", str(val))
    await message.answer(
        f"✅ Мин. ставка {_GAME_LABELS_ADMIN[game_type]}: <b>{val:.0f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(AdminGameStates.set_daily_limit)
async def msg_admin_game_daily_limit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = int(message.text.strip())
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое неотрицательное число (0 = без лимита):")
        return
    data = await state.get_data()
    await state.clear()
    game_type = data["game_type"]
    await set_setting(session, f"game_{game_type}_daily_limit", str(val))
    limit_text = str(val) if val > 0 else "∞ (без лимита)"
    await message.answer(
        f"✅ Лимит в день {_GAME_LABELS_ADMIN[game_type]}: <b>{limit_text}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(AdminGameStates.set_bet_step)
async def msg_admin_game_bet_step(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = float(message.text.strip().replace(",", "."))
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число (например: 1, 5, 10):")
        return
    data = await state.get_data()
    await state.clear()
    game_type = data["game_type"]
    await set_setting(session, f"game_{game_type}_bet_step", str(val))
    step_text = f"{val:.4g} ⭐" if val != 1.0 else "1 ⭐ (без ограничений)"
    await message.answer(
        f"✅ Шаг ставки {_GAME_LABELS_ADMIN[game_type]}: <b>{step_text}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Button Content Management ────────────────────────────────────────────────

async def _show_button_content_list(target, session: AsyncSession) -> None:
    contents = {}
    for key in BUTTON_KEYS:
        row = await get_button_content(session, key)
        contents[key] = bool(row and (row.photo_file_id or row.text))

    text = (
        "🖼 <b>Фото и текст кнопок</b>\n\n"
        "🖼 — настроено  |  ⬜ — пусто\n\n"
        "Нажми на кнопку, чтобы настроить фото и текст для неё:"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=button_content_list_kb(contents))
        await target.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=button_content_list_kb(contents))


@router.callback_query(lambda c: c.data == "admin:button_content")
async def cb_button_content(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await _show_button_content_list(callback, session)


async def _show_button_edit(target, session: AsyncSession, button_key: str) -> None:
    label = BUTTON_KEYS.get(button_key, button_key)
    row = await get_button_content(session, button_key)
    has_photo = bool(row and row.photo_file_id)
    has_text = bool(row and row.text)

    photo_status = "✅ Установлено" if has_photo else "❌ Не установлено"
    text_status = f"✅ Установлен ({len(row.text)} симв.)" if has_text else "❌ Не установлен"

    info = (
        f"🖼 <b>{label}</b>\n\n"
        f"Фото: {photo_status}\n"
        f"Текст: {text_status}"
    )

    send = target.message.edit_text if isinstance(target, CallbackQuery) else target.answer
    kb = button_edit_kb(button_key, has_photo, has_text)
    await send(info, parse_mode="HTML", reply_markup=kb)
    if isinstance(target, CallbackQuery):
        await target.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:btn_edit:"))
async def cb_btn_edit(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    button_key = callback.data[len("admin:btn_edit:"):]
    if button_key not in BUTTON_KEYS:
        return await callback.answer("Кнопка не найдена.", show_alert=True)
    await _show_button_edit(callback, session, button_key)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:btn_set_photo:"))
async def cb_btn_set_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    button_key = callback.data[len("admin:btn_set_photo:"):]
    await state.set_state(AdminButtonContentStates.set_photo)
    await state.update_data(button_key=button_key)
    await callback.message.edit_text(
        f"🖼 Отправь фото для кнопки <b>{BUTTON_KEYS.get(button_key, button_key)}</b>:\n\n"
        "Просто пришли изображение в этот чат.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminButtonContentStates.set_photo)
async def msg_btn_set_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.photo:
        await message.answer("❌ Пришли именно фото (изображение), а не файл или текст.")
        return
    data = await state.get_data()
    await state.clear()
    button_key = data["button_key"]
    file_id = message.photo[-1].file_id
    await set_button_photo(session, button_key, file_id)
    await message.answer(
        f"✅ Фото для кнопки <b>{BUTTON_KEYS.get(button_key, button_key)}</b> установлено!",
        parse_mode="HTML",
        reply_markup=button_edit_kb(
            button_key,
            has_photo=True,
            has_text=bool((await get_button_content(session, button_key)) and
                          (await get_button_content(session, button_key)).text),
        ),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("admin:btn_set_text:"))
async def cb_btn_set_text(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    button_key = callback.data[len("admin:btn_set_text:"):]
    await state.set_state(AdminButtonContentStates.set_text)
    await state.update_data(button_key=button_key)
    await callback.message.edit_text(
        f"📝 Введи текст для кнопки <b>{BUTTON_KEYS.get(button_key, button_key)}</b>:\n\n"
        "Поддерживается HTML-разметка: <b>жирный</b>, <i>курсив</i>, <code>моноширинный</code>.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminButtonContentStates.set_text)
async def msg_btn_set_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    button_key = data["button_key"]
    await set_button_text(session, button_key, message.text or message.caption or "")
    row = await get_button_content(session, button_key)
    await message.answer(
        f"✅ Текст для кнопки <b>{BUTTON_KEYS.get(button_key, button_key)}</b> установлен!",
        parse_mode="HTML",
        reply_markup=button_edit_kb(
            button_key,
            has_photo=bool(row and row.photo_file_id),
            has_text=True,
        ),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("admin:btn_del_photo:"))
async def cb_btn_del_photo(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    button_key = callback.data[len("admin:btn_del_photo:"):]
    await set_button_photo(session, button_key, None)
    await callback.answer("Фото удалено.")
    await _show_button_edit(callback, session, button_key)


@router.callback_query(lambda c: c.data and c.data.startswith("admin:btn_del_text:"))
async def cb_btn_del_text(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    button_key = callback.data[len("admin:btn_del_text:"):]
    await set_button_text(session, button_key, None)
    await callback.answer("Текст удалён.")
    await _show_button_edit(callback, session, button_key)


# ─── Retention ────────────────────────────────────────────────────────────────

async def _show_retention(callback: CallbackQuery, session: AsyncSession) -> None:
    enabled_row = await session.get(BotSettings, "retention_enabled")
    days_row = await session.get(BotSettings, "retention_days")
    bonus_row = await session.get(BotSettings, "retention_bonus")

    enabled = enabled_row and enabled_row.value == "1"
    days = int(days_row.value) if days_row else 3
    bonus = float(bonus_row.value) if bonus_row else 1.0

    await callback.message.edit_text(
        "🔔 <b>Удержание пользователей</b>\n\n"
        "Бот автоматически отправляет сообщение пользователям,\n"
        "которые не заходили N дней, и начисляет бонус.\n\n"
        "В тексте сообщения используй <code>{bonus}</code> для подстановки суммы бонуса.",
        parse_mode="HTML",
        reply_markup=retention_kb(enabled, days, bonus),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:retention")
async def cb_admin_retention(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await _show_retention(callback, session)


@router.callback_query(lambda c: c.data == "retention:toggle")
async def cb_retention_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    row = await session.get(BotSettings, "retention_enabled")
    new_val = "0" if (row and row.value == "1") else "1"
    await set_setting(session, "retention_enabled", new_val)
    await _show_retention(callback, session)


@router.callback_query(lambda c: c.data == "retention:set_days")
async def cb_retention_set_days(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminRetentionStates.set_days)
    await callback.message.edit_text("📅 Введи количество дней неактивности (целое число, например: 3):")
    await callback.answer()


@router.message(AdminRetentionStates.set_days)
async def msg_retention_days(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        days = int(message.text.strip())
        if days < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи целое число больше 0:")
        return
    await state.clear()
    await set_setting(session, "retention_days", str(days))
    await message.answer(f"✅ Дней неактивности: <b>{days}</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.callback_query(lambda c: c.data == "retention:set_bonus")
async def cb_retention_set_bonus(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminRetentionStates.set_bonus)
    await callback.message.edit_text("⭐ Введи размер бонуса (число, 0 — без бонуса):")
    await callback.answer()


@router.message(AdminRetentionStates.set_bonus)
async def msg_retention_bonus(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        bonus = float(message.text.strip().replace(",", "."))
        if bonus < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число 0 или больше:")
        return
    await state.clear()
    await set_setting(session, "retention_bonus", str(bonus))
    await message.answer(f"✅ Бонус: <b>{bonus} ⭐</b>", parse_mode="HTML", reply_markup=admin_main_kb())


@router.callback_query(lambda c: c.data == "retention:set_message")
async def cb_retention_set_message(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminRetentionStates.set_message)
    await callback.message.edit_text(
        "✏️ Введи текст сообщения для неактивных пользователей.\n\n"
        "Используй <code>{bonus}</code> для подстановки суммы бонуса.\n"
        "HTML-теги поддерживаются.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminRetentionStates.set_message)
async def msg_retention_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    text = message.text or ""
    await set_setting(session, "retention_message", text)
    await message.answer("✅ Текст сообщения сохранён.", reply_markup=admin_main_kb())


# ─── Lottery: Admin Management ────────────────────────────────────────────────

async def _show_admin_lottery(callback: CallbackQuery, session: AsyncSession) -> None:
    lottery = (await session.execute(
        select(Lottery).where(Lottery.status == "active").order_by(Lottery.id.desc()).limit(1)
    )).scalar_one_or_none()

    if lottery is None:
        last = (await session.execute(
            select(Lottery).order_by(Lottery.id.desc()).limit(1)
        )).scalar_one_or_none()
        if last:
            winner = await session.get(User, last.winner_id) if last.winner_id else None
            winner_display = f"@{winner.username}" if (winner and winner.username) else (winner.first_name if winner else "—")
            text = (
                "🎟 <b>Лотерея (завершена)</b>\n\n"
                f"🎫 Продано билетов: <b>{last.tickets_sold}</b>\n"
                f"💰 Собрано (с комиссией): <b>{last.total_collected:.2f} ⭐</b>\n"
                f"🏆 Призовой пул (выплачено): <b>{last.prize_pool:.2f} ⭐</b>\n"
                f"💸 Комиссия бота: <b>{round(last.total_collected - last.prize_pool, 2):.2f} ⭐</b>\n\n"
                f"🏆 Победитель: <b>{winner_display}</b>"
            )
        else:
            text = "🎟 <b>Лотерея</b>\n\nЛотерей пока не было."
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_lottery_kb(False, False))
        await callback.answer()
        return

    participants_count = (await session.execute(
        select(func.count(LotteryTicket.id.distinct())).where(LotteryTicket.lottery_id == lottery.id)
    )).scalar() or 0

    text = (
        "🎟 <b>Лотерея (активна)</b>\n\n"
        f"🎫 Продано билетов: <b>{lottery.tickets_sold}</b>\n"
        f"👤 Участников: <b>{participants_count}</b>\n"
        f"💰 Собрано (с комиссией): <b>{lottery.total_collected:.2f} ⭐</b>\n"
        f"🏆 Призовой пул (70%): <b>{lottery.prize_pool:.2f} ⭐</b>\n"
        f"💸 Комиссия бота: <b>{round(lottery.total_collected - lottery.prize_pool, 2):.2f} ⭐</b>"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=admin_lottery_kb(True, participants_count > 0),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin:lottery")
async def cb_admin_lottery(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await _show_admin_lottery(callback, session)


@router.callback_query(lambda c: c.data == "admin:lottery_new")
async def cb_admin_lottery_new(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    existing = (await session.execute(
        select(Lottery).where(Lottery.status == "active").limit(1)
    )).scalar_one_or_none()
    if existing:
        await callback.answer("Активная лотерея уже существует!", show_alert=True)
        return

    session.add(Lottery())
    await session.commit()
    await callback.answer("✅ Новая лотерея запущена!")
    await _show_admin_lottery(callback, session)


@router.callback_query(lambda c: c.data == "admin:lottery_cancel")
async def cb_admin_lottery_cancel(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    lottery = (await session.execute(
        select(Lottery).where(Lottery.status == "active").limit(1)
    )).scalar_one_or_none()
    if not lottery:
        await callback.answer("Активной лотереи нет.", show_alert=True)
        return

    # Refund all tickets
    tickets = (await session.execute(
        select(LotteryTicket).where(LotteryTicket.lottery_id == lottery.id)
    )).scalars().all()
    for ticket in tickets:
        user = await session.get(User, ticket.user_id)
        if user:
            user.stars_balance = round(user.stars_balance + 5.0, 2)

    lottery.status = "finished"
    lottery.drawn_at = datetime.utcnow()
    await session.commit()

    await callback.answer("Лотерея отменена. Все билеты возвращены.", show_alert=True)
    await _show_admin_lottery(callback, session)


@router.callback_query(lambda c: c.data == "admin:lottery_random")
async def cb_admin_lottery_random(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    lottery = (await session.execute(
        select(Lottery).where(Lottery.status == "active").limit(1)
    )).scalar_one_or_none()
    if not lottery or lottery.tickets_sold == 0:
        await callback.answer("Нет активной лотереи или нет билетов.", show_alert=True)
        return

    import random
    tickets = (await session.execute(
        select(LotteryTicket).where(LotteryTicket.lottery_id == lottery.id)
    )).scalars().all()
    winning_ticket = random.choice(tickets)
    await _finish_lottery(lottery, winning_ticket.user_id, session, bot)

    winner = await session.get(User, winning_ticket.user_id)
    winner_display = f"@{winner.username}" if (winner and winner.username) else (winner.first_name if winner else str(winning_ticket.user_id))
    await callback.answer(f"🏆 Победитель: {winner_display}", show_alert=True)
    await _show_admin_lottery(callback, session)


@router.callback_query(lambda c: c.data == "admin:lottery_pick")
async def cb_admin_lottery_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    lottery = (await session.execute(
        select(Lottery).where(Lottery.status == "active").limit(1)
    )).scalar_one_or_none()
    if not lottery:
        await callback.answer("Нет активной лотереи.", show_alert=True)
        return

    rows = (await session.execute(
        select(LotteryTicket.user_id, func.count(LotteryTicket.id).label("cnt"))
        .where(LotteryTicket.lottery_id == lottery.id)
        .group_by(LotteryTicket.user_id)
        .order_by(func.count(LotteryTicket.id).desc())
        .limit(20)
    )).all()

    participants = []
    for row in rows:
        uid, cnt = row.user_id, row.cnt
        user = await session.get(User, uid)
        participants.append((uid, user.username if user else None, user.first_name if user else str(uid), cnt))

    await callback.message.edit_text(
        "👤 <b>Выбери победителя:</b>",
        parse_mode="HTML",
        reply_markup=admin_lottery_pick_kb(participants),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("admin:lottery_winner:"))
async def cb_admin_lottery_winner(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    winner_id = int(callback.data.split(":")[2])
    lottery = (await session.execute(
        select(Lottery).where(Lottery.status == "active").limit(1)
    )).scalar_one_or_none()
    if not lottery:
        await callback.answer("Нет активной лотереи.", show_alert=True)
        return

    await _finish_lottery(lottery, winner_id, session, bot)
    winner = await session.get(User, winner_id)
    winner_display = f"@{winner.username}" if (winner and winner.username) else (winner.first_name if winner else str(winner_id))
    await callback.answer(f"🏆 Победитель: {winner_display}", show_alert=True)
    await _show_admin_lottery(callback, session)


async def _finish_lottery(lottery: Lottery, winner_id: int, session: AsyncSession, bot: Bot) -> None:
    winner = await session.get(User, winner_id)
    if winner:
        winner.stars_balance = round(winner.stars_balance + lottery.prize_pool, 2)

    lottery.status = "finished"
    lottery.winner_id = winner_id
    lottery.drawn_at = datetime.utcnow()
    await session.commit()

    # Notify winner
    try:
        if winner:
            await bot.send_message(
                winner_id,
                f"🎉 <b>Поздравляем! Вы выиграли лотерею!</b>\n\n"
                f"🏆 Ваш выигрыш: <b>{lottery.prize_pool:.2f} ⭐</b>\n"
                f"💰 Звёзды начислены на ваш баланс!",
                parse_mode="HTML",
            )
    except Exception:
        pass


# ─── DB Export / Import ───────────────────────────────────────────────────────

_EXPORT_MODELS = [
    User, BotSettings, PromoCode, PromoUse, Withdrawal,
    Task, TaskCompletion, GameSession, ButtonContent,
    Duel, Transfer, Lottery, LotteryTicket,
]

_DELETE_ORDER = [
    LotteryTicket, Lottery, Transfer, Duel, GameSession,
    TaskCompletion, Task, Withdrawal, PromoUse, PromoCode,
    ButtonContent, BotSettings, User,
]


def _serialize_row(row, model) -> dict:
    result = {}
    for col in model.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        result[col.name] = val
    return result


@router.callback_query(lambda c: c.data == "admin:db_export")
async def cb_admin_db_export(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    await callback.answer()
    await callback.message.answer("⏳ Формую бекап...")

    data = {}
    for model in _EXPORT_MODELS:
        rows = (await session.execute(select(model))).scalars().all()
        data[model.__tablename__] = [_serialize_row(r, model) for r in rows]

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"backup_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json"

    await bot.send_document(
        callback.from_user.id,
        BufferedInputFile(json_bytes, filename=filename),
        caption=f"✅ Бекап БД\n📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n📊 Таблиць: {len(data)}",
    )


@router.callback_query(lambda c: c.data == "admin:db_import")
async def cb_admin_db_import(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    await state.set_state(AdminDBImportStates.waiting_file)
    await callback.answer()
    await callback.message.answer(
        "📥 <b>Імпорт бази даних</b>\n\n"
        "Надішліть JSON-файл бекапу.\n"
        "⚠️ <b>Увага!</b> Всі поточні дані будуть замінені!\n\n"
        "Для скасування надішліть /admin",
        parse_mode="HTML",
    )


@router.message(AdminDBImportStates.waiting_file)
async def msg_admin_db_import_file(message: Message, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        return

    if not message.document or not message.document.file_name.endswith(".json"):
        await message.answer("❌ Надішліть файл з розширенням .json")
        return

    await message.answer("⏳ Обробляю файл...")
    await state.clear()

    try:
        file_io = BytesIO()
        await bot.download(message.document.file_id, destination=file_io)
        file_io.seek(0)
        data = json.loads(file_io.read().decode("utf-8"))
    except Exception as e:
        await message.answer(f"❌ Помилка читання файлу:\n<code>{e}</code>", parse_mode="HTML")
        return

    try:
        from sqlalchemy import DateTime as _DateTime
        for model in _DELETE_ORDER:
            await session.execute(delete(model))

        for model in _EXPORT_MODELS:
            table_name = model.__tablename__
            if table_name not in data:
                continue
            for row_dict in data[table_name]:
                converted = {}
                for col in model.__table__.columns:
                    val = row_dict.get(col.name)
                    if val is not None and isinstance(col.type, _DateTime):
                        val = datetime.fromisoformat(val)
                    converted[col.name] = val
                session.add(model(**converted))

        await session.commit()
        await message.answer("✅ <b>Імпорт успішний!</b>\nБаза даних відновлена.", parse_mode="HTML")
    except Exception as e:
        await session.rollback()
        await message.answer(f"❌ Помилка імпорту:\n<code>{e}</code>", parse_mode="HTML")


# ─── Integrations management ─────────────────────────────────────────────────

from keyboards.admin import integrations_kb, integration_counts_kb, integration_keys_kb


class AdminIntegrationStates(StatesGroup):
    set_count = State()
    set_key = State()


_INTEGRATION_LABELS = {
    "botohub": "BotoHub",
    "flyer": "Flyer",
    "piarflow": "PiarFlow",
    "subgram": "Subgram",
    "gramads": "GramAds",
}


async def _get_integration_statuses(session: AsyncSession) -> dict:
    statuses = {}
    for key in _INTEGRATION_LABELS:
        row = await session.get(BotSettings, f"integration_{key}_enabled")
        # Default: BotoHub and Flyer enabled, others disabled until key is set
        default = key in ("botohub", "flyer")
        statuses[key] = row.value == "1" if row else default
    return statuses


@router.callback_query(lambda c: c.data == "admin:integrations")
async def cb_integrations(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    statuses = await _get_integration_statuses(session)
    text = (
        "🔌 <b>Управління інтеграціями</b>\n\n"
        "Натисніть на інтеграцію щоб увімкнути/вимкнути.\n"
        "«📊 Кількість спонсорів» — налаштувати скільки каналів показувати від кожної інтеграції.\n"
        "«🔑 API ключі» — вказати ключі для нових інтеграцій."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=integrations_kb(statuses))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("integration:toggle:"))
async def cb_integration_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    key = callback.data.split(":")[2]
    if key not in _INTEGRATION_LABELS:
        return await callback.answer("Невідома інтеграція.", show_alert=True)

    db_key = f"integration_{key}_enabled"
    row = await session.get(BotSettings, db_key)
    default = key in ("botohub", "flyer")
    current = row.value == "1" if row else default
    new_val = "0" if current else "1"
    await set_setting(session, db_key, new_val)
    await session.commit()

    label = _INTEGRATION_LABELS[key]
    state_txt = "увімкнено ✅" if new_val == "1" else "вимкнено ❌"
    await callback.answer(f"{label}: {state_txt}", show_alert=False)
    await cb_integrations(callback, session)


@router.callback_query(lambda c: c.data == "integration:counts")
async def cb_integration_counts(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "📊 <b>Кількість спонсорів</b>\n\n"
        "Оберіть інтеграцію для зміни кількості каналів (1–10):",
        parse_mode="HTML",
        reply_markup=integration_counts_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("integration:count:"))
async def cb_integration_count_set(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    key = callback.data.split(":")[2]
    db_key = f"{key}_count"
    row = await session.get(BotSettings, db_key)
    current = int(row.value) if row and row.value else 5
    label = _INTEGRATION_LABELS.get(key, key)

    await state.set_state(AdminIntegrationStates.set_count)
    await state.update_data(count_key=db_key)
    await callback.message.edit_text(
        f"📊 <b>{label} — кількість спонсорів</b>\n\n"
        f"Поточне значення: <b>{current}</b>\n"
        f"Введи нове значення (1–10):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminIntegrationStates.set_count)
async def msg_integration_count(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        val = int(message.text.strip())
        if not 1 <= val <= 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи ціле число від 1 до 10:")
        return

    data = await state.get_data()
    await state.clear()
    db_key = data["count_key"]
    await set_setting(session, db_key, str(val))
    await session.commit()
    await message.answer(
        f"✅ Кількість спонсорів встановлено: <b>{val}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(lambda c: c.data == "integration:keys")
async def cb_integration_keys(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "🔑 <b>API ключі інтеграцій</b>\n\n"
        "Оберіть інтеграцію для введення ключа:",
        parse_mode="HTML",
        reply_markup=integration_keys_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("integration:key:"))
async def cb_integration_key_set(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return await callback.answer("Нет доступа.", show_alert=True)

    key = callback.data.split(":")[2]
    label = _INTEGRATION_LABELS.get(key, key)
    key_names = {
        "botohub": "BOTOHUB_KEY",
        "flyer": "FLYER_KEY",
        "piarflow": "PIARFLOW_KEY",
        "subgram": "SUBGRAM_KEY",
        "linkni": "LINKNI_CODE",
        "gramads": "GRAMADS_TOKEN",
    }
    env_name = key_names.get(key, key.upper() + "_KEY")

    await state.set_state(AdminIntegrationStates.set_key)
    await state.update_data(integration_key=key, env_name=env_name)
    await callback.message.edit_text(
        f"🔑 <b>{label}</b>\n\n"
        f"Введи значення для <code>{env_name}</code>:\n"
        f"(Ключ збережеться в базі даних і буде використовуватись до перезапуску бота)",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminIntegrationStates.set_key)
async def msg_integration_key(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()

    key = data["integration_key"]
    env_name = data["env_name"]
    value = message.text.strip()

    # Save to DB so it persists across bot restarts (applied at next restart)
    await set_setting(session, f"integration_{key}_key", value)
    await session.commit()

    # Also apply to current runtime config
    from config import config as _cfg
    key_map = {
        "botohub": "BOTOHUB_KEY",
        "flyer": "FLYER_KEY",
        "piarflow": "PIARFLOW_KEY",
        "subgram": "SUBGRAM_KEY",
        "linkni": "LINKNI_CODE",
        "gramads": "GRAMADS_TOKEN",
    }
    attr = key_map.get(key)
    if attr and hasattr(_cfg, attr):
        setattr(_cfg, attr, value)

    await message.answer(
        f"✅ Ключ <code>{env_name}</code> збережено!\n"
        f"Значення: <code>{value[:20]}{'...' if len(value) > 20 else ''}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )
