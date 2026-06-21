import json

from aiogram import Router
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, BotSettings
from handlers.button_helper import safe_edit, answer_with_content
from keyboards.main import back_to_menu_kb

router = Router()


class SearchStates(StatesGroup):
    sponsors_wall = State()
    username = State()


def _sponsors_wall_kb(sponsors: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in sponsors:
        builder.row(InlineKeyboardButton(text=f"📢 {s['title']}", url=s["link"]))
    builder.row(InlineKeyboardButton(text="✅ Я подписался — проверить", callback_data="search:sponsors_check"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"))
    return builder.as_markup()


@router.callback_query(lambda c: c.data == "menu:search")
async def cb_search(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    mode_row = await session.get(BotSettings, "referral_mode")
    mode = mode_row.value if mode_row else "botohub_flyer"

    if mode == "sponsors":
        sponsors_row = await session.get(BotSettings, "sponsor_channels")
        sponsors = json.loads(sponsors_row.value) if sponsors_row and sponsors_row.value.strip() else []
        if sponsors:
            await state.set_state(SearchStates.sponsors_wall)
            await state.update_data(sponsors=sponsors)
            await safe_edit(
                callback,
                "📢 <b>Подпишитесь на каналы спонсоров</b>\n\n"
                "Нажмите на каждый канал и подпишитесь, затем нажмите «Я подписался».",
                _sponsors_wall_kb(sponsors),
            )
            await callback.answer()
            return

    await state.set_state(SearchStates.username)
    await answer_with_content(
        callback, session,
        "menu:search",
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введи username (без @) — и я скажу, есть ли этот человек в боте:",
        back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(SearchStates.sponsors_wall, lambda c: c.data == "search:sponsors_check")
async def cb_search_sponsors_check(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    data = await state.get_data()
    sponsors = data.get("sponsors", [])

    not_subscribed = []
    for s in sponsors:
        try:
            member = await callback.bot.get_chat_member(chat_id=s["id"], user_id=db_user.user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(s["title"])
        except Exception:
            pass  # можно не проверять — пропускаем

    if not_subscribed:
        await callback.answer(
            f"❌ Вы ещё не подписаны на: {', '.join(not_subscribed)}",
            show_alert=True,
        )
        return

    await state.set_state(SearchStates.username)
    await answer_with_content(
        callback, session,
        "menu:search",
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введи username (без @) — и я скажу, есть ли этот человек в боте:",
        back_to_menu_kb(),
    )
    await callback.answer()


@router.message(SearchStates.username)
async def msg_search_username(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    username = message.text.strip().lstrip("@")

    if not username:
        await message.answer("❌ Введи корректный username.", reply_markup=back_to_menu_kb())
        return

    user = (await session.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()

    if user:
        await message.answer(
            f"✨ <b>Пользователь найден в боте!</b>\n\n"
            f"👤 Имя: <b>{user.first_name}</b>\n"
            f"🔗 Username: @{user.username}\n"
            f"🆔 ID: <code>{user.user_id}</code>\n\n"
            f"✅ Этот пользователь зарегистрирован в нашем боте.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
    else:
        await message.answer(
            f"🔍 <b>Поиск завершён</b>\n\n"
            f"😔 Пользователь <b>@{username}</b> не найден.\n\n"
            f"Возможно, он ещё не зарегистрировался в боте.\n"
            f"Пригласи его по реферальной ссылке! 🎁",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
