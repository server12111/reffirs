from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

GAME_TYPES = ["football", "basketball", "bowling", "dice", "slots"]

GAME_LABELS = {
    "football":   "Футбол",
    "basketball": "Баскетбол",
    "bowling":    "Боулинг",
    "dice":       "Кубики",
    "slots":      "Слоты",
}

GAME_ICONS = {
    "football":   "5375159220280762629",
    "basketball": "5384088040677319401",
    "bowling":    "5370853837689070338",
    "dice":       "5384474763827620477",
    "slots":      "5915833712368424979",
}


def games_menu_kb(configs: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for game in GAME_TYPES:
        cfg = configs.get(game, {})
        if cfg.get("enabled"):
            min_bet = cfg.get("min_bet", 1.0)
            coeff_label = cfg.get("coeff_label", "")
            builder.row(InlineKeyboardButton(
                text=f"{GAME_LABELS[game]} — от {min_bet:.0f} ⭐ | {coeff_label}",
                callback_data=f"game:play:{game}",
                style="primary",
                icon_custom_emoji_id=GAME_ICONS[game],
            ))
    builder.row(InlineKeyboardButton(text="Лотерея", callback_data="game:lottery", style="primary", icon_custom_emoji_id="5431653802753159903"))
    builder.row(InlineKeyboardButton(text="Дуэль", callback_data="duel:menu", style="primary", icon_custom_emoji_id="5453991094435997597"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533"))
    return builder.as_markup()


def dice_side_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Больше 3", callback_data="game:dice:high", style="primary", icon_custom_emoji_id="5269460053651366623"),
        InlineKeyboardButton(text="Меньше 4", callback_data="game:dice:low", style="primary", icon_custom_emoji_id="5271811599785534382"),
    )
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="menu:games", style="danger", icon_custom_emoji_id="5210952531676504517"))
    return builder.as_markup()


def game_result_kb(game_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Сыграть ещё раз", callback_data=f"game:play:{game_type}", style="primary", icon_custom_emoji_id="5361993818373655559"))
    builder.row(InlineKeyboardButton(text="К играм", callback_data="menu:games", style="danger", icon_custom_emoji_id="5350708744558753862"))
    return builder.as_markup()


def game_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="menu:games", style="danger", icon_custom_emoji_id="5210952531676504517")]]
    )
