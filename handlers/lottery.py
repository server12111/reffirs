import random
import logging
from datetime import datetime

from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import User, Lottery, LotteryTicket
from handlers.button_helper import safe_edit
from keyboards.lottery import lottery_menu_kb
from utils.emoji import pe

router = Router()
logger = logging.getLogger(__name__)

COMMISSION = 0.30


async def _get_active_lottery(session: AsyncSession) -> Lottery | None:
    result = await session.execute(
        select(Lottery).where(Lottery.status == "active").order_by(Lottery.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_user_ticket_count(session: AsyncSession, lottery_id: int, user_id: int) -> int:
    result = await session.execute(
        select(func.count(LotteryTicket.id)).where(
            LotteryTicket.lottery_id == lottery_id,
            LotteryTicket.user_id == user_id,
        )
    )
    return result.scalar() or 0


async def _check_channel_sub(user_id: int, channel_id: str, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return True


def _end_condition_line(lottery: Lottery) -> str:
    if lottery.end_type == "tickets":
        return f"🎯 Розыгрыш при: <b>{int(lottery.end_value)}</b> проданных билетах"
    elif lottery.end_type == "time":
        dt = datetime.utcfromtimestamp(lottery.end_value)
        return f"🗓 Дата розыгрыша: <b>{dt.strftime('%d.%m.%Y %H:%M')} UTC</b>"
    elif lottery.end_type == "commission":
        expected_pool = round(lottery.end_value * (1 - COMMISSION), 2)
        return (
            f"🎯 Розыгрыш при сборе: <b>{lottery.end_value:.0f} ⭐</b>\n"
            f"🏆 Финальный приз: <b>~{expected_pool:.0f} ⭐</b>"
        )
    return ""


def _lottery_text(lottery: Lottery, user_tickets: int, balance: float) -> str:
    end_line = _end_condition_line(lottery)

    conditions = [f"• Цена билета: <b>{lottery.ticket_price:.0f} ⭐</b>"]
    if lottery.ticket_limit > 0:
        conditions.append(f"• Лимит билетов: <b>{lottery.ticket_limit}</b> шт. на пользователя")
    if lottery.ref_required > 0:
        conditions.append(f"• Минимум рефералов: <b>{lottery.ref_required}</b>")
    if lottery.channel_id:
        conditions.append(f"• Подписка на: <b>{lottery.channel_id}</b>")

    return pe(
        "🎟 <b>Лотерея</b>\n\n"
        f"💰 <b>Призовой пул: {lottery.prize_pool:.2f} ⭐</b>\n"
        f"🎫 Продано билетов: <b>{lottery.tickets_sold}</b>\n\n"
        f"{end_line}\n\n"
        "📋 <b>Условия участия:</b>\n"
        + "\n".join(conditions) + "\n\n"
        f"🎫 Твоих билетов: <b>{user_tickets}</b>\n"
        f"💳 Твой баланс: <b>{balance:.2f} ⭐</b>"
    )


async def finish_lottery(lottery: Lottery, winner_id: int, session: AsyncSession, bot: Bot) -> None:
    """Finish lottery and notify winner. Used by auto-draw and admin."""
    winner = await session.get(User, winner_id)
    if winner:
        winner.stars_balance = round(winner.stars_balance + lottery.prize_pool, 2)

    lottery.status = "finished"
    lottery.winner_id = winner_id
    lottery.drawn_at = datetime.utcnow()
    await session.commit()

    try:
        await bot.send_message(
            winner_id,
            pe(
                f"🎉 <b>Поздравляем! Вы выиграли лотерею!</b>\n\n"
                f"🏆 Ваш выигрыш: <b>{lottery.prize_pool:.2f} ⭐</b>\n"
                f"💰 Звёзды начислены на ваш баланс!"
            ),
        )
    except Exception:
        pass
    logger.info("Lottery %s finished, winner %s, prize %.2f", lottery.id, winner_id, lottery.prize_pool)


async def _try_auto_draw(lottery: Lottery, session: AsyncSession, bot: Bot) -> bool:
    """Check end condition; if met, pick random winner. Returns True if drawn."""
    should_draw = False
    if lottery.end_type == "tickets" and lottery.tickets_sold >= int(lottery.end_value):
        should_draw = True
    elif lottery.end_type == "commission" and lottery.total_collected >= lottery.end_value:
        should_draw = True
    elif lottery.end_type == "time" and datetime.utcnow().timestamp() >= lottery.end_value:
        should_draw = True

    if not should_draw or lottery.tickets_sold == 0:
        return False

    tickets = (await session.execute(
        select(LotteryTicket).where(LotteryTicket.lottery_id == lottery.id)
    )).scalars().all()
    if not tickets:
        return False

    winning_ticket = random.choice(tickets)
    await finish_lottery(lottery, winning_ticket.user_id, session, bot)
    return True


@router.callback_query(lambda c: c.data == "game:lottery")
async def cb_lottery(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    lottery = await _get_active_lottery(session)

    if lottery is None:
        await safe_edit(
            callback,
            pe("🎟 <b>Лотерея</b>\n\nЛотерея пока не запущена. Ожидайте объявления!"),
            lottery_menu_kb(False),
        )
        await callback.answer()
        return

    user_tickets = await _get_user_ticket_count(session, lottery.id, db_user.user_id)
    can_buy = (
        db_user.stars_balance >= lottery.ticket_price
        and (lottery.ref_required == 0 or db_user.referrals_count >= lottery.ref_required)
        and (lottery.ticket_limit == 0 or user_tickets < lottery.ticket_limit)
    )

    await safe_edit(callback, _lottery_text(lottery, user_tickets, db_user.stars_balance), lottery_menu_kb(can_buy, lottery.ticket_price))
    await callback.answer()


@router.callback_query(lambda c: c.data == "game:lottery_buy")
async def cb_lottery_buy(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot) -> None:
    lottery = await _get_active_lottery(session)
    if lottery is None:
        await callback.answer("❌ Лотерея не активна.", show_alert=True)
        return

    if lottery.ref_required > 0 and db_user.referrals_count < lottery.ref_required:
        await callback.answer(
            f"❌ Нужно минимум {lottery.ref_required} рефералов.\n"
            f"У тебя: {db_user.referrals_count}/{lottery.ref_required}",
            show_alert=True,
        )
        return

    if db_user.stars_balance < lottery.ticket_price:
        await callback.answer(
            f"❌ Недостаточно звёзд. Нужно {lottery.ticket_price:.0f} ⭐",
            show_alert=True,
        )
        return

    user_tickets = await _get_user_ticket_count(session, lottery.id, db_user.user_id)
    if lottery.ticket_limit > 0 and user_tickets >= lottery.ticket_limit:
        await callback.answer(
            f"❌ Лимит билетов достигнут ({lottery.ticket_limit} шт.).",
            show_alert=True,
        )
        return

    if lottery.channel_id:
        subscribed = await _check_channel_sub(db_user.user_id, lottery.channel_id, bot)
        if not subscribed:
            await callback.answer(
                f"❌ Для участия подпишитесь на {lottery.channel_id}",
                show_alert=True,
            )
            return

    db_user.stars_balance -= lottery.ticket_price
    prize_addition = round(lottery.ticket_price * (1 - COMMISSION), 2)
    lottery.tickets_sold += 1
    lottery.total_collected = round(lottery.total_collected + lottery.ticket_price, 2)
    lottery.prize_pool = round(lottery.prize_pool + prize_addition, 2)
    session.add(LotteryTicket(lottery_id=lottery.id, user_id=db_user.user_id))
    await session.commit()

    await callback.answer(f"✅ Билет куплен! (-{lottery.ticket_price:.0f} ⭐)")

    drawn = await _try_auto_draw(lottery, session, bot)
    if drawn:
        await safe_edit(
            callback,
            pe("🎉 <b>Розыгрыш состоялся!</b>\n\nЛотерея завершена. Победитель уже получил уведомление!"),
            lottery_menu_kb(False),
        )
        return

    user_tickets = await _get_user_ticket_count(session, lottery.id, db_user.user_id)
    can_buy = (
        db_user.stars_balance >= lottery.ticket_price
        and (lottery.ticket_limit == 0 or user_tickets < lottery.ticket_limit)
    )
    await safe_edit(
        callback,
        pe("✅ <b>Билет куплен!</b>\n\n") + _lottery_text(lottery, user_tickets, db_user.stars_balance),
        lottery_menu_kb(can_buy, lottery.ticket_price),
    )
