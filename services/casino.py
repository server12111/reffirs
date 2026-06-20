import random
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BotSettings


# ─── Wheel config ─────────────────────────────────────────────────────────────

WHEEL_OUTCOMES = [0.1, 50.0]

_WHEEL_NORMAL  = [98.5, 1.5]
_WHEEL_PUNISH  = [99.5, 0.5]


# ─── Case config ──────────────────────────────────────────────────────────────

CASE_PRIZES = {
    1: [0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 3.5],
    3: [0.5, 0.7, 0.9, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
    5: [1.0, 3.0, 5.0, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0],
}

_CASE_NORMAL = {
    1: [30, 20, 15, 10, 8, 5, 4, 3, 2, 1, 1, 0.5, 0.3, 0.2],
    3: [25, 20, 15, 12, 10, 7, 4, 3, 2, 1, 1],
    5: [30, 25, 20, 8, 5, 4, 3, 3, 2],
}

_CASE_PUNISH = {
    1: [50, 25, 12, 6, 3, 2, 1, 0.5, 0.3, 0.1, 0.05, 0.03, 0.01, 0.01],
    3: [45, 25, 15, 8, 4, 2, 0.5, 0.3, 0.1, 0.05, 0.05],
    5: [55, 25, 12, 4, 2, 1, 0.5, 0.4, 0.1],
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_float(session: AsyncSession, key: str, default: float = 0.0) -> float:
    row = await session.get(BotSettings, key)
    if row:
        try:
            return float(row.value)
        except (ValueError, TypeError):
            pass
    return default


async def _add_float(session: AsyncSession, key: str, delta: float) -> None:
    row = await session.get(BotSettings, key)
    current = 0.0
    if row:
        try:
            current = float(row.value)
        except (ValueError, TypeError):
            pass
        row.value = str(round(current + delta, 4))
    else:
        session.add(BotSettings(key=key, value=str(round(delta, 4))))


def _weighted_choice(items: list, weights: list):
    return random.choices(items, weights=weights, k=1)[0]


# ─── Wheel ────────────────────────────────────────────────────────────────────

async def get_wheel_outcome(session: AsyncSession) -> float:
    """Pick 0.1 or 50.0, using punish mode if house is losing."""
    total_bet = await _get_float(session, "wheel_total_bet")
    total_pay = await _get_float(session, "wheel_total_payout")

    weights = _WHEEL_PUNISH if total_pay >= total_bet and total_bet > 0 else _WHEEL_NORMAL
    return _weighted_choice(WHEEL_OUTCOMES, weights)


async def update_casino_profit(
    session: AsyncSession,
    game_type: str,  # "wheel" | "case_1" | "case_3" | "case_5"
    bet: float,
    payout: float,
) -> None:
    """Increment BotSettings profit counters (totals only; GameSession is saved by the handler)."""
    prefix = game_type
    await _add_float(session, f"{prefix}_total_bet", bet)
    await _add_float(session, f"{prefix}_total_payout", payout)


# ─── Cases ────────────────────────────────────────────────────────────────────

async def get_case_outcome(session: AsyncSession, tier: int) -> float:
    """Pick a prize for a case of given tier (1/3/5), using punish if house losing."""
    total_bet = await _get_float(session, f"case_{tier}_total_bet")
    total_pay = await _get_float(session, f"case_{tier}_total_payout")

    weights = _CASE_PUNISH[tier] if total_pay >= total_bet and total_bet > 0 else _CASE_NORMAL[tier]
    prizes  = CASE_PRIZES[tier]
    return _weighted_choice(prizes, weights)
