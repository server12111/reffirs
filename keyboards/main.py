from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Получить звёзды", callback_data="menu:earn", style="primary", icon_custom_emoji_id="5438496463044752972"))
    builder.row(InlineKeyboardButton(text="Мои рефералы", callback_data="menu:referrals", style="primary", icon_custom_emoji_id="5325533093673588447"))
    builder.row(
        InlineKeyboardButton(text="Бонус", callback_data="menu:bonus", style="primary", icon_custom_emoji_id="5427225953463972959"),
        InlineKeyboardButton(text="Профиль", callback_data="menu:profile", style="primary", icon_custom_emoji_id="5373012449597335010"),
    )
    builder.row(InlineKeyboardButton(text="Задания", callback_data="menu:tasks", style="primary", icon_custom_emoji_id="5435970940670320222"))
    builder.row(
        InlineKeyboardButton(text="Топ", callback_data="menu:top", style="primary", icon_custom_emoji_id="5280769763398671636"),
        InlineKeyboardButton(text="Игры", callback_data="menu:games", style="primary", icon_custom_emoji_id="5350708744558753862"),
    )
    builder.row(InlineKeyboardButton(text="Вывод", callback_data="menu:withdraw", style="primary", icon_custom_emoji_id="5309795500277403547"))
    builder.row(InlineKeyboardButton(text="Найти пользователя", callback_data="menu:search", style="primary", icon_custom_emoji_id="5258274739041883702"))
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533")]]
    )


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Перевести звёзды", callback_data="profile:transfer", style="primary", icon_custom_emoji_id="5391218287684116768"))
    builder.row(InlineKeyboardButton(text="Ввести промокод", callback_data="promo:enter", style="primary", icon_custom_emoji_id="5431653802753159903"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def task_single_kb(task_type: str, identifier: str, url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if url:
        btn_text = "Выполнить задание" if task_type in ("linkni", "flyerservice") else "Подписаться"
        builder.row(InlineKeyboardButton(text=btn_text, url=url, style="primary", icon_custom_emoji_id="5271604874419647061"))
    if task_type == "linkni":
        builder.row(InlineKeyboardButton(text="Проверить", callback_data=f"task:linkni:{identifier}", style="success", icon_custom_emoji_id="5462919317832082236"))
    elif task_type == "flyerservice":
        builder.row(InlineKeyboardButton(text="Проверить", callback_data="task:flyerservice:check", style="success", icon_custom_emoji_id="5462919317832082236"))
    else:
        builder.row(InlineKeyboardButton(text="Проверить", callback_data=f"task:bot:{identifier}", style="success", icon_custom_emoji_id="5462919317832082236"))
    builder.row(
        InlineKeyboardButton(text="Пропустить", callback_data="task:skip", icon_custom_emoji_id="5321335209818339164"),
        InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"),
    )
    return builder.as_markup()


def task_done_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Следующее задание", callback_data="menu:tasks", style="success", icon_custom_emoji_id="5346105514575025401"))
    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()
