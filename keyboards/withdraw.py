from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

WITHDRAW_AMOUNTS = [15, 25, 50, 100]

_GIFT_EMOJI_IDS = [
    "5345935030143196497",
    "5224628072619216265",
    "5289761157173775507",
    "5379850840691476775",
    "5226661632259691727",
    "5359736160224586485",
    "5393309541620291208",
    "5447213743417105726",
    "5317000922096769303",
]


def withdraw_amounts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in WITHDRAW_AMOUNTS:
        builder.add(InlineKeyboardButton(text=f"{amount} ⭐", callback_data=f"withdraw:{amount}", style="primary", icon_custom_emoji_id="5438496463044752972"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="Подарки — 65 ⭐", callback_data="withdraw:gift",
        style="primary", icon_custom_emoji_id="5224628072619216265",
    ))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def gift_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for emoji_id in _GIFT_EMOJI_IDS:
        builder.button(
            text=" ",
            callback_data=f"withdraw:giftselect:{emoji_id}",
            style="primary",
            icon_custom_emoji_id=emoji_id,
        )
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:withdraw", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def withdraw_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533")]]
    )


def captcha_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="withdraw:cancel", style="danger", icon_custom_emoji_id="5210952531676504517")]]
    )


def withdraw_success_kb(channel_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.row(InlineKeyboardButton(text="Канал выплат", url=channel_url, style="primary", icon_custom_emoji_id="5370599459661045441"))
    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()
