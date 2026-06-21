from datetime import datetime, date

from aiogram import Bot
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BattlePassCompletion, GameSession, Duel, User, Withdrawal

TASKS = [
    {"id": 1,  "title": "Пригласить 15 пользователей",        "reward": 3.0, "type": "referrals",          "target": 15},
    {"id": 2,  "title": "Сыграть в футбол 10 раз",            "reward": 3.0, "type": "football_plays",     "target": 10},
    {"id": 3,  "title": "Выиграть в футбол 3 раза",           "reward": 3.0, "type": "football_wins",      "target": 3},
    {"id": 4,  "title": "Накопить баланс 100 ⭐",              "reward": 5.0, "type": "balance",            "target": 100},
    {"id": 5,  "title": "Выиграть в играх за 1 ставку 15 ⭐", "reward": 3.0, "type": "single_bet_net_win", "target": 15},
    {"id": 6,  "title": "Выиграть 1 раз в дуэль",             "reward": 2.0, "type": "duel_wins",          "target": 1},
    {"id": 7,  "title": "Вывести 15 ⭐ за сутки",              "reward": 3.0, "type": "daily_withdrawal",   "target": 15},
    {"id": 8,  "title": "Сделать 50 ставок",                  "reward": 2.0, "type": "total_bets",         "target": 50},
    {"id": 9,  "title": "Выиграть подряд 3 игры",             "reward": 4.0, "type": "win_streak",         "target": 3},
    {"id": 10, "title": "Проиграть 10 игр",                   "reward": 2.0, "type": "total_losses",       "target": 10},
    {"id": 11, "title": "Выиграть 50 ⭐ за день",             "reward": 4.0, "type": "daily_win_amount",   "target": 50},
    {"id": 12, "title": "Сыграть в кубики 25 раз",            "reward": 3.0, "type": "dice_plays",         "target": 25},
    {"id": 13, "title": "Выпасть числу 6 пять раз",           "reward": 4.0, "type": "bowling_wins",       "target": 5},
    {"id": 14, "title": "Сделать ставку 20 ⭐",               "reward": 2.0, "type": "single_bet_amount",  "target": 20},
    {"id": 15, "title": "Сыграть в футбол 25 раз",            "reward": 4.0, "type": "football_plays",     "target": 25},
    {"id": 16, "title": "Сделать 100 бросков кубиков",        "reward": 5.0, "type": "dice_plays",         "target": 100},
    {"id": 17, "title": "Выбить две шестёрки подряд",         "reward": 5.0, "type": "bowling_streak",     "target": 2},
    {"id": 18, "title": "Крутнуть 11 раз спин",               "reward": 5.0, "type": "wheel_plays",        "target": 11},
    {"id": 19, "title": "Забить 50 голов",                    "reward": 5.0, "type": "football_wins",      "target": 50},
    {"id": 20, "title": "Получить 3 выигрыша подряд",         "reward": 4.0, "type": "win_streak",         "target": 3},
]

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

    if task_type == "bowling_wins":
        r = await session.execute(select(func.count(GameSession.id)).where(
            GameSession.user_id == uid, GameSession.game_type == "bowling", GameSession.result == "win"))
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

    return 0


async def check_and_grant(
    user: User, session: AsyncSession, bot: Bot, task_ids: list[int], **kwargs
) -> None:
    completed = set(
        row[0] for row in (await session.execute(
            select(BattlePassCompletion.task_id).where(BattlePassCompletion.user_id == user.user_id)
        )).all()
    )

    grants = []
    for tid in task_ids:
        if tid in completed:
            continue
        task = _TASK_MAP.get(tid)
        if not task:
            continue
        progress = await get_task_progress(user, session, task["type"], **kwargs)
        if progress >= task["target"]:
            grants.append(task)
            user.stars_balance += task["reward"]
            session.add(BattlePassCompletion(user_id=user.user_id, task_id=tid))

    if grants:
        await session.commit()
        for task in grants:
            try:
                await bot.send_message(
                    user.user_id,
                    f'🏆 <b>Батл Пасс — задание выполнено!</b>\n\n'
                    f'{task["title"]}\n\n'
                    f'<b>+{task["reward"]:.0f} ⭐</b> зачислено на баланс!',
                    parse_mode="HTML",
                )
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

    task_ids = [4, 8, 9, 10, 20]  # balance, total_bets, win_streak×2, total_losses
    if bet >= 20:
        task_ids.append(14)
    if net_win >= 15:
        task_ids.append(5)

    _extra = {
        "football":   [2, 3, 11, 15, 19],
        "basketball": [11],
        "bowling":    [11, 13, 17],
        "dice":       [11, 12, 16],
        "slots":      [11],
        "wheel":      [11, 18],
    }
    task_ids = list(set(task_ids + _extra.get(game_type, [11])))

    await check_and_grant(
        user, session, bot, task_ids,
        win_streak=new_win_streak,
        bowling_streak=new_bowling_streak,
    )


async def after_duel_win(winner: User, session: AsyncSession, bot: Bot) -> None:
    await check_and_grant(winner, session, bot, [6])


async def after_withdrawal(user: User, session: AsyncSession, bot: Bot) -> None:
    await check_and_grant(user, session, bot, [7])


async def after_referral_granted(referrer: User, session: AsyncSession, bot: Bot) -> None:
    await check_and_grant(referrer, session, bot, [1])
