from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def cases_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Кейс Бронза", callback_data="cases:open:1",
        style="primary", icon_custom_emoji_id="5427225953463972959",
    ))
    builder.row(InlineKeyboardButton(
        text="Кейс Серебро", callback_data="cases:open:3",
        style="primary", icon_custom_emoji_id="5427225953463972959",
    ))
    builder.row(InlineKeyboardButton(
        text="Кейс Золото", callback_data="cases:open:5",
        style="primary", icon_custom_emoji_id="5427225953463972959",
    ))
    builder.row(InlineKeyboardButton(
        text="Назад", callback_data="menu:games",
        style="danger", icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()


def case_confirm_kb(tier: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"Открыть за {tier}", callback_data=f"cases:confirm:{tier}",
            style="success", icon_custom_emoji_id="5462919317832082236",
        ),
        InlineKeyboardButton(
            text="Отмена", callback_data="menu:cases",
            style="danger", icon_custom_emoji_id="5210952531676504517",
        ),
    )
    return builder.as_markup()


def case_result_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Открыть ещё", callback_data="menu:cases",
        style="success", icon_custom_emoji_id="5427225953463972959",
    ))
    builder.row(InlineKeyboardButton(
        text="В меню", callback_data="menu:games",
        style="danger", icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()
