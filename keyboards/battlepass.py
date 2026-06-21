from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def battlepass_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="menu:main",
                style="danger",
                icon_custom_emoji_id="5318991467639756533",
            )
        ]]
    )
