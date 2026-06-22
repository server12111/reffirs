from datetime import datetime, date

from aiogram import Bot
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BattlePassCompletion, GameSession, Duel, User, Withdrawal

TASKS = [
    {"id":  1, "title": "Пригласить 15 пользователей",           "reward":  3.0, "type": "referrals",          "target": 15},
    {"id":  2, "title": "Сыграть в футбол 10 раз",               "reward":  3.0, "type": "football_plays",     "target": 10},
    {"id":  3, "title": "Проиграть 10 игр",                      "reward":  2.0, "type": "total_losses",       "target": 10},
    {"id":  4, "title": "Сделать 50 ставок",                     "reward":  2.0, "type": "total_bets",         "target": 50},
    {"id":  5, "title": "Выиграть 50 ⭐ за день",                "reward":  3.0, "type": "daily_win_amount",   "target": 50},
    {"id":  6, "title": "Выиграть в футбол 3 раза",              "reward":  3.0, "type": "football_wins",      "target": 3},
    {"id":  7, "title": "Накопить баланс 25 ⭐",                 "reward":  1.0, "type": "balance",            "target": 25},
    {"id":  8, "title": "Вывести 50 ⭐ за сутки",                "reward":  2.0, "type": "daily_withdrawal",   "target": 50},
    {"id":  9, "title": "Выиграть 1 раз в дуэль",               "reward":  1.0, "type": "duel_wins",          "target": 1},
    {"id": 10, "title": "Накопить баланс 50 ⭐",                 "reward":  3.0, "type": "balance",            "target": 50},
    {"id": 11, "title": "Сыграть в кубики 25 раз",              "reward":  3.0, "type": "dice_plays",         "target": 25},
    {"id": 12, "title": "Крутнуть спин 11 раз",                 "reward":  2.0, "type": "wheel_plays",        "target": 11},
    {"id": 13, "title": "Сделать 100 бросков кубиков",          "reward": 20.0, "type": "dice_plays",         "target": 100},
    {"id": 14, "title": "Забить 50 голов",                       "reward":  5.0, "type": "football_wins",      "target": 50},
    {"id": 15, "title": "Попасть в центр в дартсе",             "reward":  2.0, "type": "darts_bullseye",     "target": 1},
    {"id": 16, "title": "Получить 3 выигрыша подряд",           "reward":  4.0, "type": "win_streak",         "target": 3},
    {"id": 17, "title": "Выиграть за 1 ставку 15 ⭐",           "reward":  3.0, "type": "single_bet_net_win", "target": 15},
    {"id": 18, "title": "Выбить две шестёрки подряд",           "reward":  5.0, "type": "bowling_streak",     "target": 2},
    {"id": 19, "title": "Выбить 10 раз промах в боулинге",      "reward":  3.0, "type": "bowling_losses",     "target": 10},
    {"id": 20, "title": "Пригласить 5 пользователей с Премиум", "reward":  1.0, "type": "premium_referrals",  "target": 5},
    {"id": 21, "title": "Выбить 777 в слотах",                  "reward": 20.0, "type": "slots_777",          "target": 1},
    {"id": 22, "title": "Проиграть 50 ⭐ за 1 ставку",          "reward":  1.0, "type": "single_bet_loss",    "target": 50},
    {"id": 23, "title": "Крутнуть спин 1 раз",                  "reward": 40.0, "type": "wheel_plays",        "target": 1},
    {"id": 24, "title": "Сделать ставку 20 ⭐",                 "reward":  2.0, "type": "single_bet_amount",  "target": 20},
    {"id": 25, "title": "Сыграть в футбол 35 раз",              "reward":  4.0, "type": "football_plays",     "target": 35},
    {"id": 26, "title": "Накопить баланс 250 ⭐",               "reward": 20.0, "type": "balance",            "target": 250},
]

ALL_TASKS_BONUS = 30.0

_TASK_MAP = {t["id"]: t for t in TASKS}


def _today_start() -> datetime:
    return datetime.combine(date.today(), datetime.min.time())


async def get_task_progress(user: User, session: AsyncSession, task_type: str, **kwargs) -> int:
    uid = user.user_id

    if task_type == "referrals":
        return user.referrals_count
    if task_type == "balance":
        return int(user.stars_balance)
    if task_type == "win_streak":
        return kwargs.get("win_streak", user.win_streak or 0)
    if task_type == "bowling_streak":
        return kwargs.get("bowling_streak", user.bowling_streak or 0)
    if task_type == "darts_bullseye":
        return user.darts_bullseye_count or 0
    if task_type == "slots_777":
        return user.slots_777_count or 0
    if task_type == "premium_referrals":
        return user.premium_referrals_count or 0

    if task_type == "football_plays":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "football"))
        return r.scalar() or 0

    if task_type == "football_wins":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "football", GameSession.result == "win"))
        return r.scalar() or 0

    if task_type == "dice_plays":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "dice"))
        return r.scalar() or 0

    if task_type == "bowling_losses":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "bowling", GameSession.result == "lose"))
        return r.scalar() or 0

    if task_type == "wheel_plays":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "wheel"))
        return r.scalar() or 0

    if task_type == "total_bets":
        r = await session.execute(select(func.count(GameSession.id)).where(GameSession.user_id == uid))
        return r.scalar() or 0

    if task_type == "total_losses":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.result == "lose"))
        return r.scalar() or 0

    if task_type == "daily_win_amount":
        r = await session.execute(
            select(func.coalesce(func.sum(GameSession.payout - GameSession.bet), 0.0)).where(
                GameSession.user_id == uid,
                GameSession.result == "win",
                GameSession.played_at >= _today_start(),
            )
        )
        return int(r.scalar() or 0)

    if task_type == "daily_withdrawal":
        r = await session.execute(
            select(func.coalesce(func.sum(Withdrawal.amount), 0.0)).where(
                Withdrawal.user_id == uid,
                Withdrawal.created_at >= _today_start(),
            )
        )
        return int(r.scalar() or 0)

    if task_type == "duel_wins":
        r = await session.execute(select(func.count(Duel.id)).where(
            Duel.winner_id == uid, Duel.status == "finished"))
        return r.scalar() or 0

    if task_type == "single_bet_net_win":
        r = await session.execute(
            select(func.coalesce(func.max(GameSession.payout - GameSession.bet), 0.0)).where(
                GameSession.user_id == uid, GameSession.result == "win"))
        return int(r.scalar() or 0)

    if task_type == "single_bet_amount":
        r = await session.execute(
            select(func.coalesce(func.max(GameSession.bet), 0.0)).where(GameSession.user_id == uid))
        return int(r.scalar() or 0)

    if task_type == "single_bet_loss":
        r = await session.execute(
            select(func.coalesce(func.max(GameSession.bet), 0.0)).where(
                GameSession.user_id == uid, GameSession.result == "lose"))
        return int(r.scalar() or 0)

    return 0


async def check_and_grant(
    user: User, session: AsyncSession, bot: Bot, task_ids: list[int], **kwargs
) -> None:
    completed = set(
        row[0] for row in (await session.execute(
            select(BattlePassCompletion.task_id).where(BattlePassCompletion.user_id == user.user_id)
        )).all()
    )

    # Sequential: only the first incomplete task is active
    current_task = None
    for task in TASKS:
        if task["id"] not in completed:
            current_task = task
            break

    if current_task is None or current_task["id"] not in task_ids:
        return

    progress = await get_task_progress(user, session, current_task["type"], **kwargs)
    if progress < current_task["target"]:
        return

    # Find next task before committing (completed set doesn't include current yet)
    next_task = None
    for task in TASKS:
        if task["id"] not in completed and task["id"] != current_task["id"]:
            next_task = task
            break

    user.stars_balance += current_task["reward"]
    # All-tasks bonus
    if next_task is None:
        user.stars_balance += ALL_TASKS_BONUS
    session.add(BattlePassCompletion(user_id=user.user_id, task_id=current_task["id"]))
    await session.commit()

    msg = (
        f'🏆 <b>Батл Пасс — задание выполнено!</b>\n\n'
        f'{current_task["title"]}\n\n'
        f'<b>+{current_task["reward"]:.0f} ⭐</b> зачислено на баланс!'
    )
    if next_task:
        msg += f'\n\n🔓 Следующее задание: <b>{next_task["title"]}</b>'
    else:
        msg += f'\n\n🎉 <b>Все задания выполнены! Бонус: +{ALL_TASKS_BONUS:.0f} ⭐</b>'
    try:
        await bot.send_message(user.user_id, msg, parse_mode="HTML")
    except Exception:
        pass


async def after_game(
    user: User, session: AsyncSession, bot: Bot,
    game_type: str, result: str, bet: float, payout: float,
) -> None:
    new_win_streak = ((user.win_streak or 0) + 1) if result == "win" else 0
    user.win_streak = new_win_streak

    new_bowling_streak = user.bowling_streak or 0
    if game_type == "bowling":
        new_bowling_streak = (new_bowling_streak + 1) if result == "win" else 0
        user.bowling_streak = new_bowling_streak

    await session.commit()

    net_win = round(payout - bet, 4) if result == "win" else 0.0

    task_ids = [3, 4, 5, 7, 10, 16, 17, 22, 24, 26]
    if net_win >= 15:
        task_ids.append(17)

    _extra = {
        "football":   [2, 6, 14, 25],
        "basketball": [],
        "bowling":    [18, 19],
        "dice":       [11, 13],
        "slots":      [21],
        "wheel":      [12, 23],
        "darts":      [15],
    }
    task_ids = list(set(task_ids + _extra.get(game_type, [])))

    await check_and_grant(
        user, session, bot, task_ids,
        win_streak=new_win_streak,
        bowling_streak=new_bowling_streak,
    )


async def after_duel_win(winner: User, session: AsyncSession, bot: Bot) -> None:
    await check_and_grant(winner, session, bot, [9])


async def after_withdrawal(user: User, session: AsyncSession, bot: Bot) -> None:
    await check_and_grant(user, session, bot, [8])


async def after_referral_granted(referrer: User, session: AsyncSession, bot: Bot, is_premium: bool = False) -> None:
    await check_and_grant(referrer, session, bot, [1, 20])
