from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_botohub_wall_kb(tasks: list[str], limit: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    items = tasks[:limit] if limit > 0 else tasks
    for i, url in enumerate(items, start=1):
        builder.button(text=f"Канал {i}", url=url, style="primary", icon_custom_emoji_id="5370599459661045441")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="Я подписался", callback_data="botohub:check",
        style="success", icon_custom_emoji_id="5462919317832082236",
    ))
    return builder.as_markup()


def build_combined_wall_kb(
    botohub_tasks: list[str],
    subgram_sponsors: list[dict] | None = None,
    tgrass_offers: list[dict] | None = None,
    limit: int = 0,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    sponsor_buttons: list[InlineKeyboardButton] = []
    i = 1

    for sp in (subgram_sponsors or []):
        sponsor_buttons.append(InlineKeyboardButton(
            text=f"Канал {i}", url=sp["link"],
            style="primary", icon_custom_emoji_id="5370599459661045441",
        ))
        i += 1

    for offer in (tgrass_offers or []):
        sponsor_buttons.append(InlineKeyboardButton(
            text=f"Канал {i}", url=offer["link"],
            style="primary", icon_custom_emoji_id="5370599459661045441",
        ))
        i += 1

    for url in (botohub_tasks or []):
        sponsor_buttons.append(InlineKeyboardButton(
            text=f"Канал {i}", url=url,
            style="primary", icon_custom_emoji_id="5370599459661045441",
        ))
        i += 1

    if limit > 0:
        sponsor_buttons = sponsor_buttons[:limit]

    for btn in sponsor_buttons:
        builder.add(btn)
    builder.adjust(2)

    builder.row(InlineKeyboardButton(
        text="Я подписался", callback_data="wall:check",
        style="success", icon_custom_emoji_id="5462919317832082236",
    ))
    return builder.as_markup()
