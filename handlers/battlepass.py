from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BattlePassCompletion, User
from handlers.button_helper import answer_with_content
from keyboards.battlepass import battlepass_kb
from services.battlepass import TASKS, get_task_progress

router = Router()


@router.callback_query(lambda c: c.data == "menu:battlepass")
async def cb_battlepass(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
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
            lines.append(
                f"🔓 <b>{task['title']}</b>\n"
                f"   [{bar}] {capped}/{target} — <b>{reward_str}</b>"
            )
        else:
            lines.append(f"🔒 {task['title']} — <b>{reward_str}</b>")

    done = len(completed_ids)
    total = len(TASKS)
    earned = sum(t["reward"] for t in TASKS if t["id"] in completed_ids)
    total_reward = sum(t["reward"] for t in TASKS)
    lines.append(f"\n📊 Выполнено: <b>{done}/{total}</b> | Заработано: <b>{earned:.0f}/{total_reward:.0f} ⭐</b>")

    text = "\n".join(lines)
    await answer_with_content(callback, session, "menu:battlepass", text, battlepass_kb())
    await callback.answer()
