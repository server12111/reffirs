from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def top_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Топ по рефералам", callback_data="top:type:refs", style="primary", icon_custom_emoji_id="5325533093673588447"))
    builder.row(InlineKeyboardButton(text="Топ по звёздам", callback_data="top:type:stars", style="primary", icon_custom_emoji_id="5438496463044752972"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def top_period_kb(top_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сегодня", callback_data=f"top:{top_type}:day", style="primary", icon_custom_emoji_id="5462912132351797094"),
        InlineKeyboardButton(text="Неделя", callback_data=f"top:{top_type}:week", style="primary", icon_custom_emoji_id="5431897022456145283"),
    )
    builder.row(
        InlineKeyboardButton(text="Месяц", callback_data=f"top:{top_type}:month", style="primary", icon_custom_emoji_id="5413879192267805083"),
        InlineKeyboardButton(text="Всё время", callback_data=f"top:{top_type}:all", style="primary", icon_custom_emoji_id="5280769763398671636"),
    )
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:top", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def top_result_kb(top_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад", callback_data=f"top:type:{top_type}", style="danger", icon_custom_emoji_id="5318991467639756533")
    ]])
