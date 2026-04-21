import logging

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import config
from database.models import User, Task, TaskCompletion, FlyerServiceCompletion
from utils.emoji import pe
from handlers.button_helper import safe_edit
from keyboards.main import task_single_kb, task_done_kb, tasks_all_done_kb

router = Router()
logger = logging.getLogger(__name__)

TASK_REWARD = 0.25
FS_REWARD = 0.25


async def _show_next_task(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext | None = None,
) -> None:
    user_id = db_user.user_id

    done_bot_ids = set((await session.execute(
        select(TaskCompletion.task_id).where(TaskCompletion.user_id == user_id)
    )).scalars().all())

    fsm_data = ((await state.get_data()) or {}) if state else {}
    skipped_bot = set(fsm_data.get("skipped_bot", []))

    all_tasks = (await session.execute(
        select(Task).where(Task.is_active == True).order_by(Task.created_at)
    )).scalars().all()
    pending_bot = [t for t in all_tasks if t.id not in done_bot_ids and t.id not in skipped_bot]

    fs_available = bool(config.FLYERSERVICE_KEY)

    # FlyerService first, then bot tasks
    if fs_available:
        if state:
            await state.update_data(current_task_type="flyerservice", current_task_id="flyerservice")
        url = config.FLYERSERVICE_URL or None
        kb = task_single_kb("flyerservice", "0", url)
        text = pe(
            f"📋 <b>Задание FlyerService</b>\n\n"
            f"🔗 Выполни задания в FlyerService и нажми «Проверить».\n\n"
            f"💰 Награда: <b>{FS_REWARD} ⭐ за каждое выполненное задание</b>"
        )
        await safe_edit(callback, text, kb)
        await callback.answer()
        return

    if pending_bot:
        task = pending_bot[0]
        if state:
            await state.update_data(current_task_type="bot", current_task_id=str(task.id))
        url = None
        if task.task_type == "subscribe" and task.channel_id:
            url = f"https://t.me/{task.channel_id.lstrip('@').lstrip('-100')}"
        elif task.task_type == "linkni" and task.channel_id:
            url = f"https://t.me/linknibot/app?startapp=x_{task.channel_id}_"
        kb = task_single_kb(task.task_type, str(task.id), url)
        extra = ""
        if task.task_type == "referrals" and task.target_value:
            extra = f"\n🎯 Нужно рефералов: <b>{task.target_value}</b> (у тебя: <b>{db_user.referrals_count}</b>)"
        text = pe(
            f"📋 <b>{task.title}</b>\n\n"
            f"{task.description}{extra}\n\n"
            f"💰 Награда: <b>{TASK_REWARD} ⭐</b>"
        )
        await safe_edit(callback, text, kb)
        await callback.answer()
        return

    await safe_edit(
        callback,
        pe("📋 <b>Задания</b>\n\nВсе задания выполнены! Заходи позже."),
        tasks_all_done_kb(show_flyerservice=fs_available),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:tasks")
async def cb_tasks_menu(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    await _show_next_task(callback, session, db_user, state)


@router.callback_query(lambda c: c.data == "task:skip")
async def cb_task_skip(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    fsm_data = await state.get_data()
    task_type = fsm_data.get("current_task_type")
    task_id = fsm_data.get("current_task_id")

    if task_type == "bot" and task_id:
        skipped = set(fsm_data.get("skipped_bot", []))
        skipped.add(int(task_id))
        await state.update_data(skipped_bot=list(skipped))

    await callback.answer("⏭ Пропущено")
    await _show_next_task(callback, session, db_user, state)


@router.callback_query(lambda c: c.data in ("task:flyerservice:check", "flyerservice:claim"))
async def cb_verify_flyerservice(
    callback: CallbackQuery, session: AsyncSession, db_user: User
) -> None:
    """Immediately check get_completed_tasks and credit all new completions."""
    from services.flyerservice import get_completed_tasks

    if not config.FLYERSERVICE_KEY:
        await callback.answer("FlyerService не настроен.", show_alert=True)
        return

    completions = await get_completed_tasks(db_user.user_id)
    if not completions:
        await callback.answer(
            "❌ Нет выполненных заданий FlyerService.\nВыполни задания и нажми «Проверить».",
            show_alert=True,
        )
        return

    credited = 0
    for item in completions:
        sig = str(item.get("signature") or item.get("id") or "")
        if not sig:
            continue
        already = (await session.execute(
            select(FlyerServiceCompletion).where(
                FlyerServiceCompletion.user_id == db_user.user_id,
                FlyerServiceCompletion.signature == sig,
            )
        )).scalar_one_or_none()
        if not already:
            session.add(FlyerServiceCompletion(user_id=db_user.user_id, signature=sig))
            db_user.stars_balance += FS_REWARD
            credited += 1

    if credited:
        await session.commit()
        await safe_edit(
            callback,
            pe(
                f"✅ <b>+{credited * FS_REWARD:.2f} ⭐ получено!</b>\n\n"
                f"Засчитано заданий: <b>{credited}</b>\n"
                f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
            ),
            task_done_kb(),
        )
        await callback.answer(f"+{credited * FS_REWARD:.2f} ⭐")
        logger.info("FlyerService: credited %d tasks to user %s", credited, db_user.user_id)
    else:
        await callback.answer(
            "✅ Все задания уже засчитаны.\nВыполни новые задания в FlyerService.",
            show_alert=True,
        )


@router.callback_query(lambda c: c.data and c.data.startswith("task:bot:"))
async def cb_verify_bot(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot) -> None:
    try:
        task_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    task = await session.get(Task, task_id)
    if not task or not task.is_active:
        await callback.answer("Задание не найдено или деактивировано.", show_alert=True)
        return

    already = (await session.execute(
        select(TaskCompletion).where(
            TaskCompletion.user_id == db_user.user_id,
            TaskCompletion.task_id == task_id,
        )
    )).scalar_one_or_none()
    if already:
        await callback.answer("Ты уже выполнил это задание!", show_alert=True)
        return

    if task.task_type == "subscribe":
        if not task.channel_id:
            await callback.answer("Ошибка конфигурации задания.", show_alert=True)
            return
        try:
            member = await bot.get_chat_member(task.channel_id, db_user.user_id)
            if member.status in ("left", "kicked", "banned"):
                await callback.answer(
                    "❌ Вы не подписаны на канал.\nПодпишитесь и нажмите «Проверить».",
                    show_alert=True,
                )
                return
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("bot is not a member", "chat not found", "forbidden", "kicked")):
                task.is_active = False
                await session.commit()
                logger.warning("Task %s auto-deactivated: %s", task.id, e)
                await callback.answer(
                    "⚠️ Задание недоступно — бот был удалён из канала.",
                    show_alert=True,
                )
            else:
                await callback.answer("❌ Не удалось проверить подписку. Попробуйте позже.", show_alert=True)
            return

    elif task.task_type == "referrals":
        target = task.target_value or 0
        if db_user.referrals_count < target:
            await callback.answer(
                f"❌ Недостаточно рефералов.\nНужно: {target}, у тебя: {db_user.referrals_count}",
                show_alert=True,
            )
            return

    elif task.task_type == "linkni":
        if not task.channel_id:
            await callback.answer("Ошибка конфигурации задания.", show_alert=True)
            return
        from services.linkni import check_linkni_subscription_by_code
        done = await check_linkni_subscription_by_code(db_user.user_id, task.channel_id)
        if not done:
            await callback.answer(
                "❌ Вы не выполнили задание.\nПерейдите по ссылке и нажмите «Проверить».",
                show_alert=True,
            )
            return

    session.add(TaskCompletion(user_id=db_user.user_id, task_id=task_id))
    db_user.stars_balance += TASK_REWARD
    await session.commit()

    await safe_edit(
        callback,
        pe(
            f"✅ <b>+{TASK_REWARD} ⭐ получено!</b>\n\n"
            f"<b>{task.title}</b>\n"
            f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
        ),
        task_done_kb(),
    )
    await callback.answer(f"+{TASK_REWARD} ⭐")
    logger.info("Bot task %s completed by user %s", task_id, db_user.user_id)
