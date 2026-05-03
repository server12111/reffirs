from sqlalchemy import text

from database.engine import engine, SessionFactory
from database.models import Base, Duel, User


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in [
            "ALTER TABLE users ADD COLUMN referral_reward_pending BOOLEAN NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_seen_at DATETIME",
            "ALTER TABLE users ADD COLUMN last_notified_at DATETIME",
            "ALTER TABLE tasks ADD COLUMN creator_id INTEGER",
            "ALTER TABLE tasks ADD COLUMN creator_reward_rate REAL DEFAULT 0.0",
            "ALTER TABLE tasks ADD COLUMN is_approved INTEGER DEFAULT 1",
            "ALTER TABLE lotteries ADD COLUMN end_type TEXT DEFAULT 'tickets'",
            "ALTER TABLE lotteries ADD COLUMN end_value REAL DEFAULT 10.0",
            "ALTER TABLE lotteries ADD COLUMN ticket_price REAL DEFAULT 5.0",
            "ALTER TABLE lotteries ADD COLUMN ticket_limit INTEGER DEFAULT 0",
            "ALTER TABLE lotteries ADD COLUMN channel_id TEXT",
            "ALTER TABLE lotteries ADD COLUMN ref_required INTEGER DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN max_completions INTEGER DEFAULT 0",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass

    # Cancel waiting duels that expired while bot was offline
    from sqlalchemy import select
    from datetime import datetime
    async with SessionFactory() as session:
        try:
            expired = (await session.execute(
                select(Duel).where(Duel.status == "waiting", Duel.expires_at < datetime.utcnow())
            )).scalars().all()
            for d in expired:
                creator = await session.get(User, d.creator_id)
                if creator:
                    creator.stars_balance += d.amount
                d.status = "cancelled"
            if expired:
                await session.commit()
        except Exception:
            pass


__all__ = ["init_db"]
