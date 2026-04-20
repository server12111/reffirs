from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import get_button_content


async def answer_with_content(
    callback: CallbackQuery,
    session: AsyncSession,
    button_key: str,
    default_text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    """Send response with optional photo+text configured by admin.

    If admin set a photo for this button — deletes current message and sends
    a new photo message with caption (admin text or default_text).
    If admin set only text — shows that text instead of default.
    If nothing is configured — shows default_text via edit_text.
    """
    content = await get_button_content(session, button_key)

    has_photo = bool(content and content.photo_file_id)
    text = (content.text if content and content.text else None) or default_text

    if has_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=content.photo_file_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    """Edit message text; if it's a photo message — delete it and send a new text message."""
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


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
            pass
    try:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await message.answer(text, parse_mode="HTML")
