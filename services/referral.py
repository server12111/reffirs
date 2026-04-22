from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BotSettings, User


async def _get_fixed_reward(session: AsyncSession) -> float:
    rr_row = await session.get(BotSettings, "referral_reward")
    return float(rr_row.value) if rr_row and rr_row.value else 0.0


async def notify_referrer_joined(
    new_user: User, session: AsyncSession, bot: Bot
) -> None:
    """Stage 1: notify referrer that someone joined via their link."""
    if not new_user.referrer_id:
        return
    referrer = await session.get(User, new_user.referrer_id)
    if not referrer:
        return

    reward = await _get_fixed_reward(session)
    name = f"@{new_user.username}" if new_user.username else new_user.first_name

    try:
        await bot.send_message(
            new_user.referrer_id,
            f'<tg-emoji emoji-id="5258203794772085854">⚡️</tg-emoji> '
            f'Пользователь {name} присоединился по твоей ссылке!\n\n'
            f'Ты получишь <b>{reward} <tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji></b> '
            f'как только он подпишется на спонсоров',
            parse_mode="HTML",
        )
    except Exception:
        pass


async def grant_referral_reward_if_pending(
    user: User, session: AsyncSession, bot: Bot
) -> None:
    """Stage 2: give reward to referrer after new user passes subscription wall."""
    if not user.referral_reward_pending or not user.referrer_id:
        return

    referrer = await session.get(User, user.referrer_id)
    if not referrer:
        user.referral_reward_pending = False
        await session.commit()
        return

    reward = await _get_fixed_reward(session)

    referrer.referrals_count += 1
    referrer.stars_balance += reward
    user.referral_reward_pending = False
    await session.commit()

    name = f"@{user.username}" if user.username else user.first_name
    try:
        await bot.send_message(
            user.referrer_id,
            f'+{reward} <tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji> '
            f'Начисление за приглашённого пользователя {name}',
            parse_mode="HTML",
        )
    except Exception:
        pass
