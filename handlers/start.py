import asyncio

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from database.models import User, BotSettings
from handlers.button_helper import answer_with_content, send_with_content
from keyboards.botohub import build_combined_wall_kb
from keyboards.main import main_menu_kb
from config import config
from services.referral import grant_referral_reward_if_pending, notify_referrer_joined
from services.subgram import get_subgram_sponsors
from services.tgrass import check_tgrass_subscription, get_tgrass_wall_url
from services.gramads import show_gramads
from services.botohub_views import show_botohub_views
from utils.botohub_api import check_botohub
from utils.emoji import pe

router = Router()


async def _register_user(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    first_name: str,
    referrer_id: int | None,
) -> tuple[User, bool]:
    """Returns (user, is_new). Referral reward is NOT given here — it is
    granted only after the new user passes the subscription wall."""
    db_user = await session.get(User, user_id)
    if db_user is not None:
        db_user.username = username
        db_user.first_name = first_name
        await session.commit()
        return db_user, False

    # New user — assign referrer only now
    valid_referrer = None
    if referrer_id and referrer_id != user_id:
        referrer = await session.get(User, referrer_id)
        if referrer:
            valid_referrer = referrer_id

    db_user = User(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referrer_id=valid_referrer,
        referral_reward_pending=bool(valid_referrer),
    )
    session.add(db_user)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        db_user = await session.get(User, user_id)
        return db_user, False

    return db_user, True


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    referrer_id = None
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
        except ValueError:
            pass

    user, is_new = await _register_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        referrer_id,
    )

    if is_new and user.referrer_id:
        await message.answer("👋 Добро пожаловать! Ты перешёл по реферальной ссылке.")
        await notify_referrer_joined(user, session, message.bot)

    # ── Combined subscription wall (TGrass + Subgram + BotoHub) ──
    if message.from_user.id not in config.ADMIN_IDS:
        user_id = message.from_user.id

        async def _flag(k, default):
            r = await session.get(BotSettings, k)
            return (r.value == "1") if r else default

        bh_on = await _flag("integration_botohub_enabled", True)
        sg_on = await _flag("integration_subgram_enabled", False)
        tg_on = await _flag("integration_tgrass_enabled", False)

        sg_count_row = await session.get(BotSettings, "subgram_count")
        sg_count = int(sg_count_row.value) if sg_count_row and sg_count_row.value else 5

        async def _skip_bh(): return {"completed": True, "skip": True, "tasks": []}
        async def _skip_list(): return []
        async def _skip_bool(): return True

        tgrass_ok, sg_sponsors, bh_result = await asyncio.gather(
            check_tgrass_subscription(user_id) if tg_on else _skip_bool(),
            get_subgram_sponsors(user_id, sg_count) if sg_on else _skip_list(),
            check_botohub(user_id) if bh_on else _skip_bh(),
        )

        tgrass_url = get_tgrass_wall_url() if (tg_on and not tgrass_ok) else None
        bh_pending = bh_on and not bh_result["completed"] and not bh_result["skip"] and bool(bh_result["tasks"])
        sg_pending = sg_on and bool(sg_sponsors)

        if tgrass_url or sg_pending or bh_pending:
            kb = build_combined_wall_kb(
                bh_result["tasks"] if bh_pending else [],
                [],
                [],
                subgram_sponsors=sg_sponsors if sg_pending else [],
                tgrass_url=tgrass_url,
            )
            await message.answer(
                pe("📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>"),
                reply_markup=kb,
            )
            return

    # User passed subscription wall — give referral reward + show ads
    await grant_referral_reward_if_pending(user, session, message.bot)
    asyncio.create_task(show_gramads(message.from_user.id))
    asyncio.create_task(show_botohub_views(message.from_user.id, hi=True))

    default_text = pe(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Здесь ты зарабатываешь настоящие <b>Telegram Stars ⭐</b>\n\n"
        "🚀 <b>Как заработать:</b>\n"
        "• 👥 Приглашай друзей — получай звёзды за каждого\n"
        "• 📋 Выполняй задания — подписки на каналы\n"
        "• 🎮 Играй в игры — умножай баланс\n"
        "• 🎁 Забирай ежедневный бонус\n\n"
        "💰 <b>Накопил — выводи</b> прямо на свой Telegram аккаунт!\n\n"
        "Выбери раздел 👇"
    )
    await send_with_content(message, session, "menu:main", default_text, main_menu_kb())


@router.callback_query(lambda c: c.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    default_text = pe(
        "🏠 <b>Главное меню</b>\n\n"
        "Здесь ты зарабатываешь настоящие <b>Telegram Stars ⭐</b>\n\n"
        "🚀 <b>Как заработать:</b>\n"
        "• 👥 Приглашай друзей — получай звёзды за каждого\n"
        "• 📋 Выполняй задания — подписки на каналы\n"
        "• 🎮 Играй в игры — умножай баланс\n"
        "• 🎁 Забирай ежедневный бонус\n\n"
        "💰 <b>Накопил — выводи</b> прямо на свой Telegram аккаунт!\n\n"
        "Выбери раздел 👇"
    )
    await answer_with_content(callback, session, "menu:main", default_text, main_menu_kb())
    await callback.answer()
