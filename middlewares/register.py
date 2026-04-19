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

        # In sponsors mode — skip BotoHub + Flyer checks entirely
        _session = data.get("session")
        if _session:
            from database.models import BotSettings as _BS
            _mode_row = await _session.get(_BS, "referral_mode")
            if _mode_row and _mode_row.value == "sponsors":
                return await handler(event, data)

        try:
            from utils.botohub_api import check_botohub
            from services.flyer import get_flyer_tasks
            from services.piarflow import get_piarflow_tasks

            session2 = data.get("session")
            _bh_on = True
            _fl_on = True
            _pf_on = False
            _pf_count = 5
            if session2:
                from database.models import BotSettings as _BS2

                async def _flag(k, default):
                    r = await session2.get(_BS2, k)
                    return (r.value == "1") if r else default

                _bh_on = await _flag("integration_botohub_enabled", True)
                _fl_on = await _flag("integration_flyer_enabled", True)
                _pf_on = await _flag("integration_piarflow_enabled", False)
                _pf_row = await session2.get(_BS2, "piarflow_count")
                if _pf_row and _pf_row.value:
                    _pf_count = int(_pf_row.value)

            async def _skip_bh():
                return {"completed": True, "skip": True, "tasks": []}

            async def _skip_list():
                return []

            # Stage 1: PiarFlow
            if _pf_on:
                pf_result = await get_piarflow_tasks(user.id, _pf_count)
                pf_pending = not pf_result["completed"] and not pf_result["skip"] and bool(pf_result["tasks"])
                if pf_pending:
                    from keyboards.botohub import build_combined_wall_kb
                    wall_text = "📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>"
                    wall_kb = build_combined_wall_kb([], [], [], piarflow_tasks=pf_result["tasks"])
                    if isinstance(event, CallbackQuery):
                        try:
                            await event.answer()
                        except Exception:
                            pass
                        await event.message.answer(wall_text, reply_markup=wall_kb)
                    else:
                        await event.answer(wall_text, reply_markup=wall_kb)
                    logger.info("CombinedWall: blocked user %s (stage 1 PiarFlow)", user.id)
                    return

            # Stage 2: BotoHub + Flyer
            bh_result, flyer_tasks = await asyncio.gather(
                check_botohub(user.id) if _bh_on else _skip_bh(),
                get_flyer_tasks(user.id, user.language_code) if _fl_on else _skip_list(),
            )

            bh_pending = _bh_on and not bh_result["completed"] and not bh_result["skip"] and bool(bh_result["tasks"])
            flyer_pending = _fl_on and bool(flyer_tasks)

            if bh_pending or flyer_pending:
                from keyboards.botohub import build_combined_wall_kb
                wall_text = "📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>"
                wall_kb = build_combined_wall_kb(
                    bh_result["tasks"] if bh_pending else [],
                    flyer_tasks if flyer_pending else [],
                    [],
                )
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:
                        pass
                    await event.message.answer(wall_text, reply_markup=wall_kb)
                else:
                    await event.answer(wall_text, reply_markup=wall_kb)
                logger.info("CombinedWall: blocked user %s (stage 3 bh=%s, fl=%s)", user.id, bh_pending, flyer_pending)
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
