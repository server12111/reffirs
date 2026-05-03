from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_botohub_wall_kb(tasks: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for i, url in enumerate(tasks, start=1):
        buttons.append([InlineKeyboardButton(text=f"Канал {i}", url=url, style="primary", icon_custom_emoji_id="5370599459661045441")])
    buttons.append(
        [InlineKeyboardButton(text="Я подписался", callback_data="botohub:check", style="success", icon_custom_emoji_id="5462919317832082236")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_combined_wall_kb(
    botohub_tasks: list[str],
    subgram_sponsors: list[dict] | None = None,
) -> InlineKeyboardMarkup:
    buttons = []
    i = 1

    # Subgram first
    for sp in (subgram_sponsors or []):
        label = sp.get("button_text") or sp.get("title") or f"Канал {i}"
        buttons.append([InlineKeyboardButton(text=label, url=sp["link"], style="primary", icon_custom_emoji_id="5370599459661045441")])
        i += 1

    # BotoHub second
    for url in (botohub_tasks or []):
        buttons.append([InlineKeyboardButton(text=f"Канал {i}", url=url, style="primary", icon_custom_emoji_id="5370599459661045441")])
        i += 1

    buttons.append(
        [InlineKeyboardButton(text="Я подписался", callback_data="wall:check", style="success", icon_custom_emoji_id="5462919317832082236")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
