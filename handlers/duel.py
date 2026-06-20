import asyncio
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from database.models import User, Duel
from database.engine import SessionFactory
from handlers.button_helper import answer_with_content, safe_edit
from keyboards.duel import (
    duel_menu_kb, active_duels_kb, duel_view_kb,
    duel_creator_kb, duel_roll_kb, back_to_duel_kb, duel_confirm_kb,
)
from keyboards.main import back_to_menu_kb

router = Router()

DUEL_EXPIRE_MINUTES = 15
DICE_TIMEOUT_MINUTES = 10
COMMISSION = 0.20

# duel_id → asyncio.Task
_expire_tasks: dict[int, asyncio.Task] = {}
_dice_tasks: dict[int, asyncio.Task] = {}


class DuelStates(StatesGroup):
    enter_amount = State()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _notify(bot: Bot, user_id: int, text: str, kb=None) -> None:
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


async def _expire_waiting_duel(duel_id: int, creator_id: int, amount: float, bot: Bot) -> None:
    """Auto-cancel waiting duel after 15 minutes."""
    await asyncio.sleep(DUEL_EXPIRE_MINUTES * 60)
    _expire_tasks.pop(duel_id, None)
    async with SessionFactory() as session:
        duel = await session.get(Duel, duel_id)
        if not duel or duel.status != "waiting":
            return
        creator = await session.get(User, creator_id)
        if creator:
            creator.stars_balance += amount
        duel.status = "cancelled"
        await session.commit()
    await _notify(
        bot, creator_id,
        f"⏰ <b>Дуэль #{duel_id} отменена</b>\n\n"
        f"Никто не присоединился за {DUEL_EXPIRE_MINUTES} минут.\n"
        f"💫 <b>{amount:.0f} ⭐</b> возвращено на баланс.",
        back_to_duel_kb(),
    )


async def _dice_timeout(duel_id: int, bot: Bot) -> None:
    """Handle case when one player doesn't roll in time."""
    await asyncio.sleep(DICE_TIMEOUT_MINUTES * 60)
    _dice_tasks.pop(duel_id, None)
    async with SessionFactory() as session:
        duel = await session.get(Duel, duel_id)
        if not duel or duel.status != "active":
            return

        creator_rolled = duel.creator_roll is not None
        joiner_rolled = duel.joiner_roll is not None

        if creator_rolled == joiner_rolled:
            # Both rolled (resolved elsewhere) or neither — cancel both
            duel.status = "finished"
            await session.commit()
            return

        duel.status = "finished"

        if creator_rolled and not joiner_rolled:
            # Joiner timed out → return creator's stake
            creator = await session.get(User, duel.creator_id)
            if creator:
                creator.stars_balance += duel.amount
            await session.commit()
            await _notify(bot, duel.creator_id,
                f"⏰ <b>Дуэль #{duel_id}</b>\n\n"
                f"Соперник не успел бросить кубик за {DICE_TIMEOUT_MINUTES} мин.\n"
                f"💫 Ваша ставка <b>{duel.amount:.0f} ⭐</b> возвращена.")
            await _notify(bot, duel.joiner_id,
                f"⏰ <b>Дуэль #{duel_id}</b>\n\n"
                f"Вы не успели бросить кубик вовремя.\n"
                f"❌ Ваша ставка <b>{duel.amount:.0f} ⭐</b> сгорела.")
        else:
            # Creator timed out → return joiner's stake
            joiner = await session.get(User, duel.joiner_id)
            if joiner:
                joiner.stars_balance += duel.amount
            await session.commit()
            await _notify(bot, duel.joiner_id,
                f"⏰ <b>Дуэль #{duel_id}</b>\n\n"
                f"Соперник не успел бросить кубик за {DICE_TIMEOUT_MINUTES} мин.\n"
                f"💫 Ваша ставка <b>{duel.amount:.0f} ⭐</b> возвращена.")
            await _notify(bot, duel.creator_id,
                f"⏰ <b>Дуэль #{duel_id}</b>\n\n"
                f"Вы не успели бросить кубик вовремя.\n"
                f"❌ Ваша ставка <b>{duel.amount:.0f} ⭐</b> сгорела.")


async def _delayed_resolve(duel_id: int, bot: Bot) -> None:
    await asyncio.sleep(4)  # wait for dice animation
    async with SessionFactory() as session:
        duel = await session.get(Duel, duel_id)
        if duel and duel.creator_roll is not None and duel.joiner_roll is not None:
            await _resolve_duel(duel, session, bot)


async def _resolve_duel(duel: Duel, session: AsyncSession, bot: Bot) -> None:
    """Determine winner and distribute pot after both players rolled."""
    task = _dice_tasks.pop(duel.id, None)
    if task:
        task.cancel()

    creator_roll = duel.creator_roll
    joiner_roll = duel.joiner_roll
    total_pot = duel.amount * 2
    winner_amount = round(total_pot * (1 - COMMISSION), 2)
    commission_amount = round(total_pot * COMMISSION, 2)

    duel.status = "finished"

    if creator_roll == joiner_roll:
        # Draw — return stakes to both
        creator = await session.get(User, duel.creator_id)
        joiner = await session.get(User, duel.joiner_id)
        if creator:
            creator.stars_balance += duel.amount
        if joiner:
            joiner.stars_balance += duel.amount
        duel.winner_id = None
        await session.commit()
        draw_text = (
            f"🤝 <b>Дуэль #{duel.id} — Ничья!</b>\n\n"
            f"🎲 Результат: <b>{creator_roll}</b> vs <b>{joiner_roll}</b>\n"
            f"💫 Ставки возвращены обоим игрокам."
        )
        await _notify(bot, duel.creator_id, draw_text, back_to_duel_kb())
        await _notify(bot, duel.joiner_id, draw_text, back_to_duel_kb())
        return

    winner_id = duel.creator_id if creator_roll > joiner_roll else duel.joiner_id
    loser_id = duel.joiner_id if creator_roll > joiner_roll else duel.creator_id

    winner = await session.get(User, winner_id)
    winner_name = winner.first_name if winner else "Игрок"
    if winner:
        winner.stars_balance += winner_amount
    duel.winner_id = winner_id
    await session.commit()

    result_text = (
        f"🏆 <b>Дуэль #{duel.id} завершена!</b>\n\n"
        f"🎲 Броски: <b>{creator_roll}</b> vs <b>{joiner_roll}</b>\n"
        f"🥇 Победитель: <b>{winner_name}</b>\n\n"
        f"💰 Выигрыш: <b>{winner_amount:.2f} ⭐</b>\n"
        f"🏦 Комиссия (20%): <b>{commission_amount:.2f} ⭐</b>"
    )
    await _notify(bot, duel.creator_id, result_text, back_to_duel_kb())
    await _notify(bot, duel.joiner_id, result_text, back_to_duel_kb())


# ─── Duel menu ────────────────────────────────────────────────────────────────

_MIN_REFS = 3


@router.callback_query(lambda c: c.data == "duel:menu")
async def cb_duel_menu(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    if db_user.referrals_count < _MIN_REFS:
        await callback.answer(
            f"❌ Нужно минимум {_MIN_REFS} реферала.\nТвоих: {db_user.referrals_count}/{_MIN_REFS}",
            show_alert=True,
        )
        return
    default_text = (
        "⚔️ <b>Дуэли</b>\n\n"
        "Бросьте кубик против другого игрока!\n\n"
        f"💰 Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
        "Победитель получает <b>80%</b> общего банка.\n"
        "Комиссия: <b>20%</b>"
    )
    await answer_with_content(callback, session, "duel:banner", default_text, duel_menu_kb())
    await callback.answer()


# ─── Create duel ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "duel:create")
async def cb_duel_create(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.set_state(DuelStates.enter_amount)
    await safe_edit(
        callback,
        f"⚔️ <b>Создать дуэль</b>\n\n"
        f"💰 Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
        f"Введи сумму ставки:\n"
        f"(Ставка сразу спишется с баланса)",
        back_to_duel_kb(),
    )
    await callback.answer()


@router.message(DuelStates.enter_amount)
async def msg_duel_amount(
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

    if db_user.stars_balance < amount:
        await message.answer(
            f"❌ Недостаточно звёзд. Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
            parse_mode="HTML",
        )
        return

    await state.clear()
    db_user.stars_balance -= amount
    expires_at = datetime.utcnow() + timedelta(days=365)
    duel = Duel(creator_id=db_user.user_id, amount=amount, expires_at=expires_at)
    session.add(duel)
    await session.flush()
    await session.commit()

    await message.answer(
        f"⚔️ <b>Дуэль #{duel.id} создана!</b>\n\n"
        f"💰 Ставка: <b>{amount:.0f} ⭐</b>\n"
        f"⏳ Ожидание соперника...\n\n"
        f"Как только кто-то присоединится — вы получите уведомление для подтверждения.",
        parse_mode="HTML",
        reply_markup=duel_creator_kb(duel.id),
    )


# ─── Cancel duel (creator) ────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("duel:cancel:"))
async def cb_duel_cancel(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "waiting":
        await callback.answer("❌ Дуэль уже недоступна для отмены.", show_alert=True)
        return
    if duel.creator_id != db_user.user_id:
        await callback.answer("❌ Вы не создатель этой дуэли.", show_alert=True)
        return

    db_user.stars_balance += duel.amount
    duel.status = "cancelled"
    await session.commit()

    task = _expire_tasks.pop(duel_id, None)
    if task:
        task.cancel()

    await safe_edit(
        callback,
        f"❌ <b>Дуэль #{duel_id} отменена.</b>\n\n"
        f"💫 <b>{duel.amount:.0f} ⭐</b> возвращено на баланс.",
        back_to_duel_kb(),
    )
    await callback.answer()


# ─── Active duels ─────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "duel:active")
async def cb_duel_active(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    now = datetime.utcnow()
    duels = (await session.execute(
        select(Duel).where(
            Duel.status == "waiting",
            Duel.creator_id != db_user.user_id,
            Duel.expires_at > now,
        ).order_by(Duel.created_at.desc())
    )).scalars().all()

    if not duels:
        await safe_edit(
            callback,
            "⚔️ <b>Активные дуэли</b>\n\n"
            "😔 Сейчас нет доступных дуэлей.\n"
            "Создай свою — и другие игроки смогут вступить!",
            back_to_duel_kb(),
        )
        await callback.answer()
        return

    await safe_edit(
        callback,
        f"⚔️ <b>Активные дуэли</b> — {len(duels)} шт.\n\n"
        f"Нажми на дуэль чтобы вступить:",
        active_duels_kb(duels),
    )
    await callback.answer()


# ─── View & Join duel ─────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("duel:view:"))
async def cb_duel_view(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "waiting" or duel.expires_at < datetime.utcnow():
        await callback.answer("❌ Дуэль уже недоступна.", show_alert=True)
        return
    if duel.creator_id == db_user.user_id:
        await callback.answer("❌ Нельзя вступить в свою дуэль.", show_alert=True)
        return

    creator = await session.get(User, duel.creator_id)
    creator_name = creator.first_name if creator else "Игрок"
    mins_left = max(0, int((duel.expires_at - datetime.utcnow()).total_seconds() // 60))

    await safe_edit(
        callback,
        f"⚔️ <b>Дуэль #{duel.id}</b>\n\n"
        f"👤 Создатель: <b>{creator_name}</b>\n"
        f"💰 Ставка: <b>{duel.amount:.0f} ⭐</b>\n"
        f"⏳ Истекает через: <b>{mins_left} мин</b>\n\n"
        f"Вступая в дуэль, с вашего баланса спишется <b>{duel.amount:.0f} ⭐</b>.\n"
        f"Победитель получит <b>{duel.amount * 2 * 0.8:.0f} ⭐</b>.",
        duel_view_kb(duel.id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("duel:join:"))
async def cb_duel_join(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "waiting" or duel.expires_at < datetime.utcnow():
        await callback.answer("❌ Дуэль уже недоступна.", show_alert=True)
        return
    if duel.creator_id == db_user.user_id:
        await callback.answer("❌ Нельзя вступить в свою дуэль.", show_alert=True)
        return
    if db_user.stars_balance < duel.amount:
        await callback.answer(
            f"❌ Недостаточно звёзд. Нужно: {duel.amount:.0f} ⭐", show_alert=True
        )
        return

    db_user.stars_balance -= duel.amount
    duel.joiner_id = db_user.user_id
    duel.status = "confirming"
    await session.commit()

    task = _expire_tasks.pop(duel_id, None)
    if task:
        task.cancel()

    creator = await session.get(User, duel.creator_id)
    creator_name = creator.first_name if creator else "Игрок"

    # Ask creator to confirm
    await _notify(
        callback.bot, duel.creator_id,
        f"⚔️ <b>Дуэль #{duel_id} — запрос на участие!</b>\n\n"
        f"👤 <b>{db_user.first_name}</b> хочет вступить в дуэль!\n"
        f"💰 Ставка: <b>{duel.amount:.0f} ⭐</b>\n\n"
        f"Подтвердить дуэль?",
        duel_confirm_kb(duel_id),
    )

    await safe_edit(
        callback,
        f"⏳ <b>Ожидание подтверждения</b>\n\n"
        f"⚔️ Соперник: <b>{creator_name}</b>\n"
        f"💰 Ставка: <b>{duel.amount:.0f} ⭐</b>\n\n"
        f"Ждём пока создатель дуэли подтвердит участие...",
        back_to_duel_kb(),
    )
    await callback.answer()


# ─── Confirm / Decline join ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("duel:confirm:"))
async def cb_duel_confirm(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "confirming":
        await callback.answer("❌ Дуэль уже недоступна.", show_alert=True)
        return
    if duel.creator_id != db_user.user_id:
        await callback.answer("❌ Вы не создатель этой дуэли.", show_alert=True)
        return

    duel.status = "active"
    await session.commit()

    roll_kb = duel_roll_kb(duel_id)
    joiner = await session.get(User, duel.joiner_id)
    joiner_name = joiner.first_name if joiner else "Игрок"

    await safe_edit(
        callback,
        f"🔥 <b>Дуэль #{duel_id} началась!</b>\n\n"
        f"⚔️ Соперник: <b>{joiner_name}</b>\n"
        f"💰 Ставка: <b>{duel.amount:.0f} ⭐</b>\n\n"
        f"🎲 Бросьте кубик — кто выше, тот и победит!",
        roll_kb,
    )
    await callback.answer()

    await _notify(
        callback.bot, duel.joiner_id,
        f"🔥 <b>Дуэль #{duel_id} подтверждена!</b>\n\n"
        f"⚔️ Соперник: <b>{db_user.first_name}</b>\n"
        f"💰 Ставка: <b>{duel.amount:.0f} ⭐</b>\n\n"
        f"🎲 Бросьте кубик — кто выше, тот и победит!",
        roll_kb,
    )

    dice_task = asyncio.create_task(_dice_timeout(duel_id, callback.bot))
    _dice_tasks[duel_id] = dice_task


@router.callback_query(lambda c: c.data and c.data.startswith("duel:decline_join:"))
async def cb_duel_decline_join(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "confirming":
        await callback.answer("❌ Дуэль уже недоступна.", show_alert=True)
        return
    if duel.creator_id != db_user.user_id:
        await callback.answer("❌ Вы не создатель этой дуэли.", show_alert=True)
        return

    # Refund both players
    creator = await session.get(User, duel.creator_id)
    joiner = await session.get(User, duel.joiner_id)
    if creator:
        creator.stars_balance += duel.amount
    if joiner:
        joiner.stars_balance += duel.amount
    joiner_id = duel.joiner_id
    duel.status = "cancelled"
    await session.commit()

    await safe_edit(
        callback,
        f"❌ <b>Дуэль #{duel_id} отклонена.</b>\n\n"
        f"💫 <b>{duel.amount:.0f} ⭐</b> возвращено на ваш баланс.",
        back_to_duel_kb(),
    )
    await callback.answer()

    await _notify(
        callback.bot, joiner_id,
        f"❌ <b>Дуэль #{duel_id} отклонена создателем.</b>\n\n"
        f"💫 <b>{duel.amount:.0f} ⭐</b> возвращено на ваш баланс.",
        back_to_duel_kb(),
    )


# ─── Roll dice ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("duel:roll:"))
async def cb_duel_roll(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duel_id = int(callback.data.split(":")[2])
    duel = await session.get(Duel, duel_id)

    if not duel or duel.status != "active":
        await callback.answer("❌ Дуэль уже завершена.", show_alert=True)
        return

    is_creator = duel.creator_id == db_user.user_id
    is_joiner = duel.joiner_id == db_user.user_id

    if not (is_creator or is_joiner):
        await callback.answer("❌ Вы не участник этой дуэли.", show_alert=True)
        return
    if is_creator and duel.creator_roll is not None:
        await callback.answer("Вы уже бросили кубик! Ждите соперника.", show_alert=True)
        return
    if is_joiner and duel.joiner_roll is not None:
        await callback.answer("Вы уже бросили кубик! Ждите соперника.", show_alert=True)
        return

    # Remove roll button so user can't click again
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer()

    dice_msg = await callback.bot.send_dice(chat_id=callback.message.chat.id, emoji="🎲")
    value = dice_msg.dice.value

    if is_creator:
        duel.creator_roll = value
    else:
        duel.joiner_roll = value
    await session.commit()

    other_id = duel.joiner_id if is_creator else duel.creator_id

    if duel.creator_roll is not None and duel.joiner_roll is not None:
        # Both rolled — resolve after animation
        asyncio.create_task(_delayed_resolve(duel_id, callback.bot))
    else:
        await _notify(
            callback.bot, other_id,
            f"⚔️ <b>Дуэль #{duel_id}</b>\n\n"
            f"🎲 Соперник уже бросил кубик! Выпало: <b>{value}</b>\n\n"
            f"Теперь ваша очередь! (осталось {DICE_TIMEOUT_MINUTES} мин)",
            duel_roll_kb(duel_id),
        )


# ─── History ──────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "duel:history")
async def cb_duel_history(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    duels = (await session.execute(
        select(Duel).where(
            Duel.status == "finished",
        ).order_by(Duel.created_at.desc()).limit(20)
    )).scalars().all()

    if not duels:
        await safe_edit(
            callback,
            "📜 <b>История дуэлей</b>\n\nЗавершённых дуэлей ещё нет.",
            back_to_duel_kb(),
        )
        await callback.answer()
        return

    lines = []
    for d in duels:
        creator = await session.get(User, d.creator_id)
        creator_name = creator.first_name if creator else "Игрок"
        joiner = await session.get(User, d.joiner_id) if d.joiner_id else None
        joiner_name = joiner.first_name if joiner else "?"

        if d.winner_id is None:
            result = "🤝 Ничья"
        else:
            winner = await session.get(User, d.winner_id)
            result = f"🏆 {winner.first_name if winner else 'Игрок'}"

        lines.append(f"⚔️ #{d.id} | {creator_name} vs {joiner_name} | {d.amount:.0f}⭐ | {result}")

    text = "📜 <b>История дуэлей (последние 20)</b>\n\n" + "\n".join(lines)
    await safe_edit(callback, text, back_to_duel_kb())
    await callback.answer()
