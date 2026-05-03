from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import get_button_content
from utils.emoji import strip_pe as _strip_tgemoji


async def answer_with_content(
    callback: CallbackQuery,
    session: AsyncSession,
    button_key: str,
    default_text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    content = await get_button_content(session, button_key)

    has_photo = bool(content and content.photo_file_id)
    text = (content.text if content and content.text else None) or default_text

    try:
        await callback.message.delete()
    except Exception:
        pass

    if has_photo:
        try:
            await callback.message.answer_photo(
                photo=content.photo_file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            await callback.message.answer_photo(
                photo=content.photo_file_id,
                caption=_strip_tgemoji(text),
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        return

    try:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(_strip_tgemoji(text), parse_mode="HTML", reply_markup=keyboard)


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(_strip_tgemoji(text), parse_mode="HTML", reply_markup=keyboard)


async def send_with_content(
    message: Message,
    session: AsyncSession,
    button_key: str,
    default_text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    """Same as answer_with_content but for plain Message (e.g. /start command)."""
    content = await get_button_content(session, button_key)

    has_photo = bool(content and content.photo_file_id)
    text = (content.text if content and content.text else None) or default_text

    if has_photo:
        try:
            await message.answer_photo(
                photo=content.photo_file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception:
            try:
                await message.answer_photo(
                    photo=content.photo_file_id,
                    caption=_strip_tgemoji(text),
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                return
            except Exception:
                pass
    try:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await message.answer(_strip_tgemoji(text), parse_mode="HTML", reply_markup=keyboard)
