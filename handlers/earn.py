from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import User, TaskCompletion
from handlers.button_helper import answer_with_content
from keyboards.main import back_to_menu_kb
from config import config
from database.engine import get_button_content
from utils.emoji import pe, strip_pe

router = Router()


@router.callback_query(lambda c: c.data == "menu:earn")
async def cb_earn(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    ref_link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{db_user.user_id}"

    from database.models import BotSettings
    rr_row = await session.get(BotSettings, "referral_reward")
    reward = float(rr_row.value) if rr_row and rr_row.value else 0.0
    reward_line = f"💰 <b>Награда за реферала: {reward} ⭐</b>"

    tasks_done = (await session.execute(
        select(func.count(TaskCompletion.task_id)).where(TaskCompletion.user_id == db_user.user_id)
    )).scalar() or 0

    ref_suffix = pe(
        f"👥 Ты пригласил: <b>{db_user.referrals_count}</b> чел.\n"
        f"📋 Выполнено заданий: <b>{tasks_done}</b>\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    default_body = pe(
        "⭐ <b>Заработать звёзды</b>\n\n"
        "Приглашай друзей — получай <b>Telegram Stars</b> за каждого!\n\n"
        f"{reward_line}\n\n"
        "📌 <b>Условия:</b>\n"
        "• Друг должен запустить бота по твоей ссылке\n"
        "• Один пользователь засчитывается только один раз\n"
        "• Выплата — мгновенно после регистрации\n\n"
    )

    content = await get_button_content(session, "menu:earn")
    has_photo = bool(content and content.photo_file_id)
    text = ((content.text if content and content.text else None) or default_body) + ref_suffix

    kb = back_to_menu_kb()
    if has_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await callback.message.answer_photo(photo=content.photo_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await callback.message.answer_photo(photo=content.photo_file_id, caption=strip_pe(text), parse_mode="HTML", reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await callback.message.answer(strip_pe(text), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:referrals")
async def cb_referrals(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from sqlalchemy import asc
    result = await session.execute(
        select(User)
        .where(User.referrer_id == db_user.user_id)
        .order_by(asc(User.created_at))
    )
    all_refs = result.scalars().all()

    completed = [r for r in all_refs if not r.referral_reward_pending]
    pending = [r for r in all_refs if r.referral_reward_pending]

    lines = []
    for i, ref in enumerate(completed[:20], start=1):
        name = ref.first_name or "—"
        uname = f" @{ref.username}" if ref.username else ""
        date_str = ref.created_at.strftime("%d.%m.%Y") if ref.created_at else "—"
        lines.append(f"{i}. {name}{uname} — {date_str} ✅")

    body = "\n".join(lines) if lines else "Рефералов пока нет."
    pending_line = f"\n⏳ Ожидают подтверждения: <b>{len(pending)}</b>" if pending else ""
    default_text = pe(
        f"👥 <b>Мои рефералы</b>\n\n"
        f"Всего: <b>{len(all_refs)}</b> | Подтверждено: <b>{len(completed)}</b>{pending_line}\n\n"
        f"{body}"
    )
    await answer_with_content(callback, session, "menu:referrals", default_text, back_to_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:how")
async def cb_how(callback: CallbackQuery, session: AsyncSession) -> None:
    default_text = (
        "ℹ️ <b>Как это работает</b>\n\n"
        "1. Получи свою реферальную ссылку в разделе «⭐ Заработать звёзды»\n"
        "2. Отправь ссылку друзьям\n"
        "3. Когда друг запустит бота — тебе начислятся Telegram Stars\n"
        "4. Накопи нужную сумму и выведи через «💰 Вывод»\n\n"
        "🎁 Не забывай получать ежедневный бонус!\n"
        "🎟 Используй промокоды для дополнительных звёзд."
    )
    await answer_with_content(callback, session, "menu:how", default_text, back_to_menu_kb())
    await callback.answer()
