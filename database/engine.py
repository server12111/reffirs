import os
import pathlib
import shutil

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database.models import ButtonContent, BotSettings


def _resolve_db_path() -> str:
    # Explicit env var always wins (set DATABASE_PATH in your hosting env)
    env = os.environ.get("DATABASE_PATH", "").strip()
    if env:
        return os.path.abspath(env)
    # Auto-detect persistent volume mounts used by Railway, Render, Fly.io, etc.
    for candidate in ("/data/database.db", "/var/data/database.db"):
        if os.path.isdir(os.path.dirname(candidate)):
            return candidate
    # VPS default: store OUTSIDE the git checkout (SrvNkreferal/database.db)
    # Lives one level above the test/ directory — survives git pull and redeployment
    preferred = pathlib.Path(__file__).resolve().parent.parent.parent / "database.db"
    # One-time migration: if old path (test/database.db) exists and new doesn't, copy it
    old_path = pathlib.Path(__file__).resolve().parent.parent / "database.db"
    if not preferred.exists() and old_path.exists():
        try:
            preferred.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(old_path), str(preferred))
        except Exception:
            pass
    return str(preferred)


_db_path = _resolve_db_path()
DATABASE_URL = f"sqlite+aiosqlite:///{_db_path}"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.get(BotSettings, key)
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(BotSettings, key)
    if row:
        row.value = value
    else:
        session.add(BotSettings(key=key, value=value))
    await session.commit()


async def get_button_content(session: AsyncSession, key: str) -> ButtonContent | None:
    return await session.get(ButtonContent, key)


async def set_button_photo(session: AsyncSession, key: str, file_id: str | None) -> None:
    row = await session.get(ButtonContent, key)
    if row:
        row.photo_file_id = file_id
    else:
        session.add(ButtonContent(key=key, photo_file_id=file_id))
    await session.commit()


async def set_button_text(session: AsyncSession, key: str, text: str | None) -> None:
    row = await session.get(ButtonContent, key)
    if row:
        row.text = text
    else:
        session.add(ButtonContent(key=key, text=text))
    await session.commit()
