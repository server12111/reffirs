import asyncio
import logging
from datetime import datetime
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import config

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseMiddleware):
    """Injects async DB session into every handler."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from database.engine import SessionFactory
        async with SessionFactory() as session:
            data["session"] = session
            return await handler(event, data)


class CombinedWallMiddleware(BaseMiddleware):
    """
    Checks BotoHub + Flyer in parallel on every request.
    Shows a single combined subscription wall if either integration requires it.

    Whitelisted commands/callbacks are always let through:
      • /admin, /start — handled by their own handlers
      • botohub:check  — legacy callback (kept for backwards compatibility)
      • wall:check     — new unified confirm button
    Admins always bypass entirely.
    In "sponsors" mode — skips both BotoHub and Flyer checks.
    """

    _SKIP_COMMANDS = {"/admin", "/start"}
    _SKIP_CALLBACKS = {"botohub:check", "wall:check"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self._SKIP_COMMANDS):
                return await handler(event, data)

        elif isinstance(event, CallbackQuery):
            user = event.from_user
            if event.data in self._SKIP_CALLBACKS:
                return await handler(event, data)

        else:
            return await handler(event, data)

        if user is None:
            return await handler(event, data)

        # Admins always bypass
        if user.id in config.ADMIN_IDS:
            return await handler(event, data)

        try:
            from utils.botohub_api import check_botohub
            from services.subgram import get_subgram_sponsors
            from services.tgrass import check_tgrass_subscription, get_tgrass_wall_url
            from utils.emoji import pe

            session2 = data.get("session")
            _bh_on = True
            _sg_on = False
            _tg_on = False
            _sg_count = 5
            if session2:
                from database.models import BotSettings as _BS2

                async def _flag(k, default):
                    r = await session2.get(_BS2, k)
                    return (r.value == "1") if r else default

                _bh_on = await _flag("integration_botohub_enabled", True)
                _sg_on = await _flag("integration_subgram_enabled", False)
                _tg_on = await _flag("integration_tgrass_enabled", False)
                _sg_row = await session2.get(_BS2, "subgram_count")
                if _sg_row and _sg_row.value:
                    _sg_count = int(_sg_row.value)

            async def _skip_bh():
                return {"completed": True, "skip": True, "tasks": []}

            async def _skip_list():
                return []

            async def _skip_bool():
                return True

            # Check TGrass + Subgram + BotoHub in parallel (PiarFlow and Flyer removed)
            tgrass_ok, sg_sponsors, bh_result = await asyncio.gather(
                check_tgrass_subscription(user.id) if _tg_on else _skip_bool(),
                get_subgram_sponsors(user.id, _sg_count) if _sg_on else _skip_list(),
                check_botohub(user.id) if _bh_on else _skip_bh(),
            )

            tgrass_url = get_tgrass_wall_url() if (_tg_on and not tgrass_ok) else None
            bh_pending = _bh_on and not bh_result["completed"] and not bh_result["skip"] and bool(bh_result["tasks"])
            sg_pending = _sg_on and bool(sg_sponsors)

            if tgrass_url or sg_pending or bh_pending:
                from keyboards.botohub import build_combined_wall_kb
                wall_text = pe("📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>")
                wall_kb = build_combined_wall_kb(
                    bh_result["tasks"] if bh_pending else [],
                    [],
                    [],
                    subgram_sponsors=sg_sponsors if sg_pending else [],
                    tgrass_url=tgrass_url,
                )
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:
                        pass
                    await event.message.answer(wall_text, reply_markup=wall_kb)
                else:
                    await event.answer(wall_text, reply_markup=wall_kb)
                logger.info(
                    "CombinedWall: blocked user %s (tg=%s, sg=%s, bh=%s)",
                    user.id, bool(tgrass_url), sg_pending, bh_pending,
                )
                return

        except Exception as exc:
            logger.error("CombinedWallMiddleware error for user %s: %s", user.id, exc)
            # On any middleware error — let the user through

        # All integrations passed — give referral reward if still pending
        session = data.get("session")
        if session:
            from database.models import User
            from services.referral import grant_referral_reward_if_pending
            db_user = await session.get(User, user.id)
            if db_user and db_user.referral_reward_pending:
                bot = data.get("bot") or getattr(event, "bot", None)
                if bot:
                    await grant_referral_reward_if_pending(db_user, session, bot)

        return await handler(event, data)


# Aliases kept for import compatibility (main.py still imports these names)
BotHubMiddleware = CombinedWallMiddleware
FlyerMiddleware = CombinedWallMiddleware


class RegisteredUserMiddleware(BaseMiddleware):
    """
    Blocks unregistered users from using the bot without /start.
    Admins always bypass this check.
    """

    SKIP_TEXT = {"/start", "/admin"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from database.models import User

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        else:
            return await handler(event, data)

        if user is None:
            return

        # Admins: try to load db_user; if not registered yet — require /start first
        if user.id in config.ADMIN_IDS:
            session = data.get("session")
            db_user = None
            if session:
                db_user = await session.get(User, user.id)
            if db_user:
                data["db_user"] = db_user
                return await handler(event, data)
            if isinstance(event, Message):
                text = event.text or ""
                if any(text.startswith(cmd) for cmd in {"/start", "/admin"}):
                    return await handler(event, data)
                await event.answer("Нажми /start чтобы начать.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сначала нажми /start.", show_alert=True)
            return

        # Skip /start and /admin for regular users
        if isinstance(event, Message):
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self.SKIP_TEXT):
                return await handler(event, data)

        # Allow botohub:check and wall:check through
        if isinstance(event, CallbackQuery) and event.data in {"botohub:check", "wall:check"}:
            session = data.get("session")
            if session:
                db_user = await session.get(User, user.id)
                if db_user:
                    data["db_user"] = db_user
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return

        db_user = await session.get(User, user.id)
        if db_user is None:
            if isinstance(event, Message):
                await event.answer("Нажми /start чтобы начать.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сначала нажми /start.", show_alert=True)
            return

        data["db_user"] = db_user

        # Update last_seen_at at most once per hour to reduce DB writes
        now = datetime.utcnow()
        if db_user.last_seen_at is None or (now - db_user.last_seen_at).total_seconds() > 3600:
            db_user.last_seen_at = now
            session = data.get("session")
            if session:
                await session.commit()

        return await handler(event, data)
