from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SponsorEvent


async def log_wall_show(session: AsyncSession, *services: str) -> None:
    """Log that a sponsor wall was shown (one event per active service)."""
    for svc in services:
        session.add(SponsorEvent(service=svc, event_type="show"))
    await session.commit()


async def log_wall_pass(session: AsyncSession, *services: str) -> None:
    """Log that a user passed the sponsor wall check for given services."""
    for svc in services:
        session.add(SponsorEvent(service=svc, event_type="pass"))
    await session.commit()
