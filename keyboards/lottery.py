from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def lottery_menu_kb(can_buy: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_buy:
        builder.row(InlineKeyboardButton(text="Купить билет (5 ⭐)", callback_data="game:lottery_buy", style="success", icon_custom_emoji_id="5431653802753159903"))
    builder.row(InlineKeyboardButton(text="К играм", callback_data="menu:games", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def admin_lottery_kb(has_active: bool, has_participants: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_active:
        if has_participants:
            builder.row(InlineKeyboardButton(text="Случайный розыгрыш", callback_data="admin:lottery_random", style="primary", icon_custom_emoji_id="5384474763827620477"))
            builder.row(InlineKeyboardButton(text="Выбрать победителя", callback_data="admin:lottery_pick", style="primary", icon_custom_emoji_id="5373012449597335010"))
        builder.row(InlineKeyboardButton(text="Отменить лотерею", callback_data="admin:lottery_cancel", style="danger", icon_custom_emoji_id="5210952531676504517"))
    else:
        builder.row(InlineKeyboardButton(text="Запустить новую лотерею", callback_data="admin:lottery_new", style="success", icon_custom_emoji_id="5397916757333654639"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="admin:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def admin_lottery_pick_kb(participants: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for uid, username, first_name, cnt in participants:
        display = f"@{username}" if username else first_name
        builder.row(InlineKeyboardButton(
            text=f"{display} — {cnt} билет(ов)",
            callback_data=f"admin:lottery_winner:{uid}",
            style="primary",
        ))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="admin:lottery", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()
