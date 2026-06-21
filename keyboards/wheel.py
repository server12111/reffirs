from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def wheel_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Крутить колесо", callback_data="wheel:choose_bet",
        style="success", icon_custom_emoji_id="5361993818373655559",
    ))
    builder.row(InlineKeyboardButton(
        text="Назад", callback_data="menu:games",
        style="danger", icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()


def wheel_bet_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amt in [1, 5, 10, 25, 50]:
        builder.button(
            text=f"{amt} ⭐", callback_data=f"wheel:bet:{amt}",
            style="primary", icon_custom_emoji_id="5438496463044752972",
        )
    builder.adjust(3, 2)
    builder.row(InlineKeyboardButton(
        text="Своя сумма", callback_data="wheel:bet:custom",
        style="primary", icon_custom_emoji_id="5397916757333654639",
    ))
    builder.row(InlineKeyboardButton(
        text="Назад", callback_data="menu:wheel",
        style="danger", icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()


def wheel_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text="Отмена", callback_data="menu:wheel",
            style="danger", icon_custom_emoji_id="5210952531676504517",
        )]]
    )


def wheel_result_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Крутить ещё", callback_data="wheel:choose_bet",
        style="success", icon_custom_emoji_id="5361993818373655559",
    ))
    builder.row(InlineKeyboardButton(
        text="В меню", callback_data="menu:games",
        style="danger", icon_custom_emoji_id="5318991467639756533",
    ))
    return builder.as_markup()
