from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def battlepass_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏆 Топ игроков",
        callback_data="menu:battlepass:top",
        style="primary",
        icon_custom_emoji_id="5361993818373655559",
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="menu:main",
        style="danger",
        icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()


def battlepass_top_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="menu:battlepass",
                style="danger",
                icon_custom_emoji_id="5318991467639756533",
            )
        ]]
    )
