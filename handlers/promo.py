import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, PromoCode, PromoUse
from keyboards.main import back_to_menu_kb, profile_kb

router = Router()


class PromoStates(StatesGroup):
    waiting_code = State()


@router.callback_query(lambda c: c.data == "promo:enter")
async def cb_promo_enter(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoStates.waiting_code)
    try:
        await callback.message.edit_text("🎟 Введи промокод:", reply_markup=back_to_menu_kb())
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("🎟 Введи промокод:", reply_markup=back_to_menu_kb())
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def msg_promo_code(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    code = message.text.strip().upper()
    await state.clear()

    result = await session.execute(
        select(PromoCode).where(PromoCode.code == code, PromoCode.is_active == True)
    )
    promo = result.scalar_one_or_none()

    if promo is None:
        await message.answer(
            "❌ Промокод не найден или недействителен.",
            reply_markup=profile_kb(),
        )
        return

    # Check per-user reuse
    already_used = await session.execute(
        select(PromoUse).where(
            PromoUse.user_id == db_user.user_id,
            PromoUse.promo_id == promo.id,
        )
    )
    if already_used.scalar_one_or_none() is not None:
        await message.answer(
            "❌ Ты уже использовал этот промокод.",
            reply_markup=profile_kb(),
        )
        return

    # Check global usage limit
    if promo.usage_limit is not None and promo.usage_count >= promo.usage_limit:
        await message.answer(
            "❌ Лимит использований промокода исчерпан.",
            reply_markup=profile_kb(),
        )
        return

    # Apply
    if promo.is_random and promo.reward_min is not None and promo.reward_max is not None:
        reward = round(random.uniform(promo.reward_min, promo.reward_max), 2)
    else:
        reward = promo.reward

    db_user.stars_balance += reward
    promo.usage_count += 1
    session.add(PromoUse(user_id=db_user.user_id, promo_id=promo.id))
    await session.commit()

    await message.answer(
        f"✅ Промокод активирован!\nНачислено: <b>{reward} ⭐</b>\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )
