import asyncio
import logging
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import ErrorEvent

from config import config
from database import init_db
from handlers import routers
from middlewares import SessionMiddleware, RegisteredUserMiddleware
from middlewares.register import CombinedWallMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=SQLStorage("fsm_storage.db"))

    # Middlewares — order matters: session → combined wall → user check
    dp.message.middleware(SessionMiddleware())
    dp.callback_query.middleware(SessionMiddleware())
    dp.message.middleware(CombinedWallMiddleware())
    dp.callback_query.middleware(CombinedWallMiddleware())
    dp.message.middleware(RegisteredUserMiddleware())
    dp.callback_query.middleware(RegisteredUserMiddleware())

    @dp.errors()
    async def error_handler(event: ErrorEvent) -> None:
        if isinstance(event.exception, TelegramForbiddenError):
            return
        logger.error("Handler error: %s\n%s", event.exception, traceback.format_exc())

    for router in routers:
        dp.include_router(router)

    from services.retention import retention_loop
    from services.payments_stats import payments_stats_loop
    asyncio.create_task(retention_loop(bot))
    asyncio.create_task(payments_stats_loop(bot))
    asyncio.create_task(_lottery_time_check_loop(bot))

    logger.info("Bot started")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


async def _lottery_time_check_loop(bot) -> None:
    """Check time-based lotteries every 60 seconds and auto-draw if expired."""
    import random
    from datetime import datetime
    from database.engine import SessionFactory
    from database.models import Lottery, LotteryTicket
    from sqlalchemy import select
    from handlers.lottery import finish_lottery

    await asyncio.sleep(60)
    while True:
        try:
            async with SessionFactory() as session:
                lottery = (await session.execute(
                    select(Lottery).where(Lottery.status == "active", Lottery.end_type == "time")
                )).scalar_one_or_none()
                if lottery and datetime.utcnow().timestamp() >= lottery.end_value and lottery.tickets_sold > 0:
                    tickets = (await session.execute(
                        select(LotteryTicket).where(LotteryTicket.lottery_id == lottery.id)
                    )).scalars().all()
                    if tickets:
                        winner = random.choice(tickets)
                        await finish_lottery(lottery, winner.user_id, session, bot)
        except Exception as exc:
            logging.getLogger(__name__).error("LotteryTimeCheck error: %s", exc)
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
