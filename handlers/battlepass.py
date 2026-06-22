from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BattlePassCompletion, User
from handlers.button_helper import answer_with_content
from keyboards.battlepass import battlepass_kb, battlepass_top_kb
from services.battlepass import TASKS, get_task_progress, check_and_grant

router = Router()


@router.callback_query(lambda c: c.data == "menu:battlepass")
async def cb_battlepass(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    # Check if current active task is already met (e.g. conditions were satisfied before check ran)
    try:
        await check_and_grant(db_user, session, callback.bot, [])
    except Exception:
        pass

    completed_ids = set(
        row[0] for row in (await session.execute(
            select(BattlePassCompletion.task_id).where(
                BattlePassCompletion.user_id == db_user.user_id
            )
        )).all()
    )

    # Sequential: find current active task (first incomplete in order)
    current_task = None
    for task in TASKS:
        if task["id"] not in completed_ids:
            current_task = task
            break

    lines = ["🏆 <b>Батл Пасс</b>\n"]

    for task in TASKS:
        reward_str = f"+{task['reward']:.0f} ⭐"
        if task["id"] in completed_ids:
            lines.append(f"✅ <s>{task['title']}</s> — <b>{reward_str}</b>")
        elif current_task and task["id"] == current_task["id"]:
            progress = await get_task_progress(db_user, session, task["type"])
            target = task["target"]
            capped = min(progress, target)
            pct = int(capped / target * 10)
            bar = "█" * pct + "░" * (10 - pct)
            super_badge = "\n   🌟 <b>Супер задание!</b>" if task.get("super") else ""
            lines.append(
                f"🔓 <b>{task['title']}</b>{super_badge}\n"
                f"   [{bar}] {capped}/{target} — <b>{reward_str}</b>"
            )
        else:
            if task.get("super"):
                lines.append("🔒 <b>Супер задание</b>")
            else:
                lines.append("🔒 Задание недоступно")

    done = len(completed_ids)
    total = len(TASKS)
    earned = sum(t["reward"] for t in TASKS if t["id"] in completed_ids)
    total_reward = sum(t["reward"] for t in TASKS)
    lines.append(f"\n📊 Выполнено: <b>{done}/{total}</b> | Заработано: <b>{earned:.0f}/{total_reward:.0f} ⭐</b>")

    text = "\n".join(lines)
    await answer_with_content(callback, session, "menu:battlepass", text, battlepass_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:battlepass:top")
async def cb_battlepass_top(callback: CallbackQuery, session: AsyncSession) -> None:
    rows = (await session.execute(
        select(BattlePassCompletion.user_id, func.count(BattlePassCompletion.task_id).label("cnt"))
        .group_by(BattlePassCompletion.user_id)
        .order_by(desc("cnt"))
        .limit(10)
    )).all()

    lines = ["🏆 <b>Топ Батл Пасс</b>\n"]
    medals = ["🥇", "🥈", "🥉"]

    if not rows:
        lines.append("Пока нет выполненных заданий.")
    else:
        for i, (user_id, cnt) in enumerate(rows, start=1):
            user = await session.get(User, user_id)
            if user and user.username:
                name = f"@{user.username}"
            elif user and user.first_name:
                name = user.first_name
            else:
                name = f"#{user_id}"
            medal = medals[i - 1] if i <= 3 else f"{i}."
            word = "задание" if cnt == 1 else ("задания" if 2 <= cnt <= 4 else "заданий")
            lines.append(f"{medal} {name} — <b>{cnt} {word}</b>")

    text = "\n".join(lines)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=battlepass_top_kb())
    await callback.answer()
