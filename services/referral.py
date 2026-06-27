from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BotSettings, User


async def _get_fixed_reward(session: AsyncSession) -> float:
    rr_row = await session.get(BotSettings, "referral_reward")
    return float(rr_row.value) if rr_row and rr_row.value else 0.0


async def _get_mode(session: AsyncSession) -> str:
    row = await session.get(BotSettings, "referral_reward_mode")
    return row.value if row and row.value in ("fixed", "per_sponsor") else "fixed"


async def _get_reward_tiers(session: AsyncSession) -> dict[int, float]:
    import json
    row = await session.get(BotSettings, "referral_reward_tiers")
    if not row or not row.value:
        return {}
    try:
        data = json.loads(row.value)
        return {int(k): min(5.0, float(v)) for k, v in data.items()}
    except Exception:
        return {}


async def _get_min_sponsors(session: AsyncSession) -> int:
    row = await session.get(BotSettings, "referral_min_sponsors")
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    return 3


async def _calc_reward(session: AsyncSession, user: User) -> float:
    mode = await _get_mode(session)
    if mode == "per_sponsor":
        count = user.pending_sponsor_count or 0
        tiers = await _get_reward_tiers(session)
        if not tiers or count == 0:
            return 0.0
        reward = 0.0
        for k, v in tiers.items():
            if k <= count:
                reward = max(reward, v)
        return min(5.0, reward)
    return await _get_fixed_reward(session)


async def notify_referrer_joined(
    new_user: User, session: AsyncSession, bot: Bot
) -> None:
    """Stage 1: notify referrer that someone joined via their link."""
    if not new_user.referrer_id:
        return
    referrer = await session.get(User, new_user.referrer_id)
    if not referrer:
        return

    name = f"@{new_user.username}" if new_user.username else new_user.first_name
    mode = await _get_mode(session)

    if mode == "per_sponsor":
        tiers = await _get_reward_tiers(session)
        min_s = await _get_min_sponsors(session)
        if tiers:
            tiers_text = ", ".join(
                f'{k}→{v}<tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji>'
                for k, v in sorted(tiers.items())
            )
            reward_text = f'<b>тиры: {tiers_text}</b> (мин. {min_s} спонс.)'
        else:
            reward_text = f'(тиры не настроены, мин. {min_s} спонс.)'
    else:
        reward = await _get_fixed_reward(session)
        reward_text = (
            f'<b>{reward} <tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji></b>'
            f' как только он подпишется на спонсоров'
        )

    try:
        await bot.send_message(
            new_user.referrer_id,
            f'<tg-emoji emoji-id="5258203794772085854">⚡️</tg-emoji> '
            f'Пользователь {name} присоединился по твоей ссылке!\n\n'
            f'Ты получишь {reward_text}',
            parse_mode="HTML",
        )
    except Exception:
        pass


async def cancel_referral_no_sponsors(
    user: User, session: AsyncSession, bot: Bot
) -> None:
    """Called when new user sees no sponsors at /start.
    Cancels the pending reward and notifies the referrer."""
    if not user.referral_reward_pending or not user.referrer_id:
        return

    referrer = await session.get(User, user.referrer_id)
    user.referral_reward_pending = False
    await session.commit()

    if referrer:
        name = f"@{user.username}" if user.username else user.first_name
        try:
            await bot.send_message(
                user.referrer_id,
                f'<tg-emoji emoji-id="5258203794772085854">⚡️</tg-emoji> '
                f'Пользователь {name} зарегистрировался по твоей ссылке, но награда не начислена — '
                f'на момент регистрации не было активных спонсоров для подписки.',
                parse_mode="HTML",
            )
        except Exception:
            pass


async def grant_referral_reward_if_pending(
    user: User, session: AsyncSession, bot: Bot, is_premium: bool = False
) -> None:
    """Stage 2: give reward to referrer after new user passes subscription wall."""
    if not user.referral_reward_pending or not user.referrer_id:
        return

    referrer = await session.get(User, user.referrer_id)
    if not referrer:
        user.referral_reward_pending = False
        await session.commit()
        return

    name = f"@{user.username}" if user.username else user.first_name
    count = user.pending_sponsor_count or 0
    min_s = await _get_min_sponsors(session)

    # Check minimum sponsor threshold
    if count < min_s:
        user.referral_reward_pending = False
        await session.commit()
        try:
            await bot.send_message(
                user.referrer_id,
                f'<tg-emoji emoji-id="5258203794772085854">⚡️</tg-emoji> '
                f'Пользователь {name} подписался на <b>{count}</b> спонсора(ов), '
                f'но для получения награды нужно минимум <b>{min_s}</b>.\n'
                f'Награда не начислена.',
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    reward = await _calc_reward(session, user)

    referrer.referrals_count += 1
    referrer.stars_balance += reward
    user.referral_reward_pending = False
    user.referral_reward_given = reward
    if is_premium:
        referrer.premium_referrals_count = (referrer.premium_referrals_count or 0) + 1
    await session.commit()

    from services.battlepass import after_referral_granted
    await after_referral_granted(referrer, session, bot, is_premium=is_premium)

    mode = await _get_mode(session)
    detail = f" (тир {count} сп.)" if mode == "per_sponsor" and count > 0 else ""

    try:
        await bot.send_message(
            user.referrer_id,
            f'+{reward} <tg-emoji emoji-id="5438496463044752972">⭐️</tg-emoji>'
            f'{detail} Начисление за приглашённого пользователя {name}',
            parse_mode="HTML",
        )
    except Exception:
        pass
