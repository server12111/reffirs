from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User
from handlers.button_helper import answer_with_content
from keyboards.main import back_to_menu_kb
from config import config
from database.engine import get_button_content

router = Router()


@router.callback_query(lambda c: c.data == "menu:earn")
async def cb_earn(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    ref_link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{db_user.user_id}"

    # Расчёт/отображение награды за реферала
    import json
    from database.models import BotSettings
    rt_row = await session.get(BotSettings, "reward_type")
    reward_type = rt_row.value if rt_row else "per_sponsor"
    sps_row = await session.get(BotSettings, "stars_per_sponsor")
    stars_per_sponsor = float(sps_row.value) if sps_row and sps_row.value else 0.45

    if reward_type == "fixed":
        rr_row = await session.get(BotSettings, "referral_reward")
        reward = float(rr_row.value) if rr_row and rr_row.value else 0.0
        reward_line = f"💰 <b>Награда за реферала: {reward} ⭐</b>"
    else:
        reward_line = (
            f"💰 <b>Награда за реферала — динамическая</b>\n"
            f"Бот назначит тебе каналы спонсоров для подписки.\n"
            f"За каждый канал ты получишь <b>{stars_per_sponsor} ⭐</b>.\n"
            f"Чем больше спонсоров назначит бот — тем выше твоя награда! 🚀"
        )

    ref_suffix = (
        f"👥 Ты пригласил: <b>{db_user.referrals_count}</b> чел.\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    default_body = (
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
        await callback.message.answer_photo(photo=content.photo_file_id, caption=text, parse_mode="HTML", reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:referrals")
async def cb_referrals(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    from sqlalchemy import asc
    result = await session.execute(
        select(User)
        .where(User.referrer_id == db_user.user_id, User.referral_reward_pending == False)
        .order_by(asc(User.created_at))
    )
    refs = result.scalars().all()

    lines = []
    for i, ref in enumerate(refs[:20], start=1):
        name = ref.first_name or "—"
        uname = f" @{ref.username}" if ref.username else ""
        date_str = ref.created_at.strftime("%d.%m.%Y") if ref.created_at else "—"
        lines.append(f"{i}. {name}{uname} — {date_str}")

    body = "\n".join(lines) if lines else "Рефералов пока нет."
    default_text = (
        f"👥 <b>Мои рефералы</b>\n\n"
        f"Всего: <b>{db_user.referrals_count}</b>\n\n"
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
