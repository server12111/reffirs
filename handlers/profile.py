from datetime import datetime, date

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import User, Transfer
from handlers.button_helper import answer_with_content, safe_edit
from keyboards.main import profile_kb, back_to_menu_kb
from utils.emoji import pe

router = Router()

TRANSFER_COMMISSION = 0.10   # 10%
TRANSFER_REF_REQUIRED = 3    # referrals invited today


class TransferStates(StatesGroup):
    username = State()
    amount = State()


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    uname = f"@{db_user.username}" if db_user.username else "не указан"
    default_text = pe(
        "👤 <b>Профиль</b>\n\n"
        f"Имя: {db_user.first_name}\n"
        f"ID: <code>{db_user.user_id}</code>\n"
        f"Username: {uname}\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n"
        f"Рефералов: <b>{db_user.referrals_count}</b>"
    )
    await answer_with_content(callback, session, "menu:profile", default_text, profile_kb())
    await callback.answer()


# ─── Transfer: start ──────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "profile:transfer")
async def cb_transfer_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    if db_user.referrals_count < TRANSFER_REF_REQUIRED:
        await callback.answer(
            f"❌ Для перевода нужно иметь {TRANSFER_REF_REQUIRED} реферала.\n"
            f"У вас: {db_user.referrals_count}/{TRANSFER_REF_REQUIRED}",
            show_alert=True,
        )
        return

    await state.set_state(TransferStates.username)
    await safe_edit(
        callback,
        f"💸 <b>Перевод звёзд</b>\n\n"
        f"💰 Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
        f"📋 Условия:\n"
        f"• 3 реферала всего — ✅ ({db_user.referrals_count}/3)\n"
        f"• Комиссия перевода: <b>10%</b> (вычитается из суммы)\n\n"
        f"Введи username получателя (без @):",
        back_to_menu_kb(),
    )
    await callback.answer()


# ─── Transfer: enter recipient ────────────────────────────────────────────────

@router.message(TransferStates.username)
async def msg_transfer_username(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("❌ Введи корректный username:")
        return

    if username.lower() == (db_user.username or "").lower():
        await message.answer("❌ Нельзя переводить звёзды самому себе:")
        return

    from sqlalchemy import func as _func
    target = (await session.execute(
        select(User).where(_func.lower(User.username) == username.lower())
    )).scalar_one_or_none()

    if not target:
        await message.answer(
            f"❌ Пользователь <b>@{username}</b> не найден в боте.\n"
            f"Проверь username и попробуй снова:",
            parse_mode="HTML",
        )
        return

    await state.update_data(target_user_id=target.user_id, target_username=target.username, target_name=target.first_name)
    await state.set_state(TransferStates.amount)
    await message.answer(
        f"💸 Перевод пользователю <b>{target.first_name}</b> (@{target.username})\n\n"
        f"💰 Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n"
        f"⚠️ Комиссия 10% вычитается из суммы (получатель получит меньше).\n\n"
        f"Введи сумму перевода:",
        parse_mode="HTML",
    )


# ─── Transfer: enter amount ───────────────────────────────────────────────────

@router.message(TransferStates.amount)
async def msg_transfer_amount(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи положительное число:")
        return

    commission = round(amount * TRANSFER_COMMISSION, 2)
    received = round(amount - commission, 2)

    if db_user.stars_balance < amount:
        await message.answer(
            f"❌ Недостаточно звёзд.\n"
            f"Нужно: <b>{amount:.2f} ⭐</b>\n"
            f"Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    await state.clear()

    target = await session.get(User, data["target_user_id"])
    if not target:
        await message.answer("❌ Пользователь не найден.", reply_markup=back_to_menu_kb())
        return

    db_user.stars_balance -= amount
    target.stars_balance += received

    transfer = Transfer(
        from_user_id=db_user.user_id,
        to_user_id=target.user_id,
        amount=received,
        commission=commission,
    )
    session.add(transfer)
    await session.commit()

    await message.answer(
        f"✅ <b>Перевод выполнен!</b>\n\n"
        f"💸 Отправлено: <b>{amount:.2f} ⭐</b> → @{target.username}\n"
        f"🏦 Комиссия (10%): <b>{commission:.2f} ⭐</b>\n"
        f"📩 Получатель получит: <b>{received:.2f} ⭐</b>\n"
        f"💰 Ваш новый баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )

    # Notify recipient
    try:
        await message.bot.send_message(
            target.user_id,
            f"💸 <b>Вам перевели звёзды!</b>\n\n"
            f"От: @{db_user.username or db_user.first_name}\n"
            f"Сумма: <b>+{received:.2f} ⭐</b>\n"
            f"💰 Ваш баланс: <b>{target.stars_balance:.2f} ⭐</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
