import random
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Withdrawal, BotSettings
from handlers.button_helper import answer_with_content, safe_edit
from utils.emoji import pe
from keyboards.withdraw import withdraw_amounts_kb, captcha_cancel_kb, withdraw_success_kb
from keyboards.admin import withdrawal_actions_kb
from keyboards.main import back_to_menu_kb, main_menu_kb
from config import config

router = Router()

CAPTCHA_LOCKOUT_MINUTES = 10
_captcha_lockouts: dict[int, datetime] = {}


def build_withdrawal_msg(withdrawal_id: int, username: str, user_id: int, amount: float, status: str) -> str:
    status_map = {
        "pending":  "⏳ Статус: на рассмотрении",
        "approved": "✅ Статус: одобрено",
        "rejected": "❌ Статус: отклонено",
    }
    return (
        f"📌 <b>Запрос на вывод средств #{withdrawal_id}</b>\n\n"
        f"👤 Пользователь: @{username} | ID {user_id}\n"
        f"💫 Сумма: {amount:.0f} ⭐\n"
        f"{status_map.get(status, status)}"
    )


class WithdrawStates(StatesGroup):
    captcha = State()


def _gen_captcha() -> tuple[int, int]:
    a = random.randint(1, 19)
    b = random.randint(1, 20 - a)
    return a, b


@router.callback_query(lambda c: c.data == "menu:withdraw")
async def cb_withdraw(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    if not db_user.username:
        await answer_with_content(
            callback, session, "menu:withdraw",
            "❗ Для вывода средств необходимо задать username в Telegram.\n\n"
            "Установи username в настройках Telegram и попробуй снова.",
            back_to_menu_kb(),
        )
        await callback.answer()
        return

    default_text = pe(
        f"💰 <b>Вывод звёзд</b>\n\n"
        f"Твой баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
        f"Выбери сумму для вывода:"
    )
    await answer_with_content(callback, session, "menu:withdraw", default_text, withdraw_amounts_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("withdraw:") and c.data.split(":")[1].isdigit())
async def cb_withdraw_amount(callback: CallbackQuery, db_user: User, state: FSMContext) -> None:
    amount = int(callback.data.split(":")[1])

    if db_user.stars_balance < amount:
        await callback.answer(
            f"❌ Недостаточно звёзд. Баланс: {db_user.stars_balance:.2f} ⭐",
            show_alert=True,
        )
        return

    # Check anti-bot lockout
    locked_until = _captcha_lockouts.get(db_user.user_id)
    if locked_until and datetime.utcnow() < locked_until:
        remaining = locked_until - datetime.utcnow()
        minutes = int(remaining.total_seconds() // 60) + 1
        await callback.answer(
            f"⛔ Слишком много попыток. Попробуйте через {minutes} мин.",
            show_alert=True,
        )
        return

    a, b = _gen_captcha()
    await state.set_state(WithdrawStates.captcha)
    await state.update_data(withdraw_amount=amount, captcha_a=a, captcha_b=b, captcha_attempts=0)

    await safe_edit(
        callback,
        f"🛡 <b>Подтвердите, что вы не бот.</b>\n\n"
        f"Сколько будет:\n<b>{a} + {b} = ?</b>",
        captcha_cancel_kb(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "withdraw:cancel")
async def cb_captcha_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("👋 Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(WithdrawStates.captcha)
async def msg_captcha_answer(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    fsm_data = await state.get_data()
    a = fsm_data["captcha_a"]
    b = fsm_data["captcha_b"]
    amount = fsm_data["withdraw_amount"]
    attempts = fsm_data.get("captcha_attempts", 0)

    try:
        answer = int(message.text.strip())
    except ValueError:
        await message.answer(
            f"❌ Введи число. Сколько будет: <b>{a} + {b} = ?</b>",
            parse_mode="HTML",
            reply_markup=captcha_cancel_kb(),
        )
        return

    if answer == a + b:
        await state.clear()

        db_user.stars_balance -= amount
        withdrawal = Withdrawal(user_id=db_user.user_id, amount=amount)
        session.add(withdrawal)
        await session.flush()

        # Admin channel: simple message with buttons
        admin_text = (
            f"💸 <b>Новая заявка #{withdrawal.id}</b>\n\n"
            f"👤 @{db_user.username} | ID: <code>{db_user.user_id}</code>\n"
            f"💰 Сумма: <b>{amount} ⭐</b>\n\n"
            f"🔗 iOS: <code>tg://user?id={db_user.user_id}</code>\n"
            f"🔗 Android: https://t.me/{db_user.username}"
        )
        try:
            sent = await message.bot.send_message(
                chat_id=config.ADMIN_CHANNEL_ID,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=withdrawal_actions_kb(withdrawal.id),
            )
            withdrawal.channel_message_id = sent.message_id
        except Exception:
            pass

        # Payments channel: formatted message with status for users
        pch_row = await session.get(BotSettings, "payments_channel_id")
        if pch_row and pch_row.value:
            try:
                pay_sent = await message.bot.send_message(
                    chat_id=pch_row.value,
                    text=build_withdrawal_msg(withdrawal.id, db_user.username, db_user.user_id, amount, "pending"),
                    parse_mode="HTML",
                )
                withdrawal.payments_message_id = pay_sent.message_id
            except Exception:
                pass

        await session.commit()

        # Get payments channel URL for the confirmation message
        pch_url_row = await session.get(BotSettings, "payments_channel_url")
        channel_url = pch_url_row.value if pch_url_row and pch_url_row.value else None

        # If no explicit URL, auto-build from payments_channel_id (@username)
        if not channel_url:
            pch_id_row = await session.get(BotSettings, "payments_channel_id")
            if pch_id_row and pch_id_row.value:
                ch_id = pch_id_row.value.strip()
                if ch_id.startswith("@"):
                    channel_url = f"https://t.me/{ch_id[1:]}"

        await message.answer(
            f"✅ <b>Заявка #{withdrawal.id} принята!</b>\n\n"
            f"Сумма: <b>{amount} ⭐</b>\n"
            f"Статус: ⏳ На рассмотрении\n\n"
            f"Одобренные выплаты публикуются в нашем канале 👇",
            parse_mode="HTML",
            reply_markup=withdraw_success_kb(channel_url),
        )
    else:
        attempts += 1
        if attempts >= 3:
            _captcha_lockouts[db_user.user_id] = datetime.utcnow() + timedelta(minutes=CAPTCHA_LOCKOUT_MINUTES)
            await state.clear()
            await message.answer(
                f"⛔ Попробуйте позже.\n\n"
                f"Слишком много неверных попыток. Повторите через {CAPTCHA_LOCKOUT_MINUTES} минут.",
                reply_markup=back_to_menu_kb(),
            )
        else:
            await state.update_data(captcha_attempts=attempts)
            remaining_attempts = 3 - attempts
            await message.answer(
                f"❌ Неверный ответ. Попробуйте ещё раз.\n\n"
                f"Сколько будет: <b>{a} + {b} = ?</b>\n"
                f"Осталось попыток: <b>{remaining_attempts}</b>",
                parse_mode="HTML",
                reply_markup=captcha_cancel_kb(),
            )


@router.callback_query(lambda c: c.data and c.data.startswith("withdrawal:return:"))
async def cb_withdrawal_return(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    try:
        withdrawal_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    withdrawal = await session.get(Withdrawal, withdrawal_id)
    if not withdrawal or withdrawal.user_id != db_user.user_id:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if withdrawal.status != "rejected":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    db_user.stars_balance += withdrawal.amount
    withdrawal.status = "refunded"
    await session.commit()

    try:
        await callback.message.edit_text(
            f"✅ <b>{withdrawal.amount:.0f} ⭐ возвращены на баланс.</b>\n\n"
            f"Текущий баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer("✅ Звёзды возвращены!")


@router.callback_query(lambda c: c.data and c.data.startswith("withdrawal:noreturn:"))
async def cb_withdrawal_noreturn(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_text("✖️ Заявка закрыта.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()
