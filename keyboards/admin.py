from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить промокод", callback_data="admin:add_promo"))
    builder.row(InlineKeyboardButton(text="🎟 Список промокодов", callback_data="admin:list_promos"))
    builder.row(InlineKeyboardButton(text="📋 Управление заданиями", callback_data="admin:tasks"))
    builder.row(InlineKeyboardButton(text="🎮 Управление играми", callback_data="admin:games"))
    builder.row(InlineKeyboardButton(text="🖼 Фото и текст кнопок", callback_data="admin:button_content"))

    builder.row(InlineKeyboardButton(text="👥 Статистика", callback_data="admin:stats"))
    builder.row(
        InlineKeyboardButton(text="💳 Начислить звёзды", callback_data="admin:credit"),
        InlineKeyboardButton(text="➖ Списать звёзды", callback_data="admin:debit"),
    )
    builder.row(InlineKeyboardButton(text="👥 Начислить рефералов", callback_data="admin:add_referral"))
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
    )
    builder.row(InlineKeyboardButton(text="🔌 Интеграции", callback_data="admin:integrations"))
    builder.row(InlineKeyboardButton(text="🔔 Удержание", callback_data="admin:retention"))
    builder.row(
        InlineKeyboardButton(text="📤 Экспорт БД", callback_data="admin:db_export"),
        InlineKeyboardButton(text="📥 Импорт БД", callback_data="admin:db_import"),
    )
    builder.row(InlineKeyboardButton(text="🎟 Лотерея", callback_data="admin:lottery"))
    return builder.as_markup()


# ─── Game management keyboards ────────────────────────────────────────────────

_GAME_LABELS = {
    "football":   "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
    "bowling":    "🎳 Боулинг",
    "dice":       "🎲 Кубики",
    "slots":      "🎰 Слоты",
}
_GAME_TYPES = ["football", "basketball", "bowling", "dice", "slots"]


def games_list_kb(statuses: dict[str, bool]) -> InlineKeyboardMarkup:
    """statuses: {game_type: is_enabled}"""
    builder = InlineKeyboardBuilder()
    for game in _GAME_TYPES:
        icon = "✅" if statuses.get(game, True) else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {_GAME_LABELS[game]}",
            callback_data=f"agame:info:{game}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def game_detail_kb(game_type: str, is_enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Отключить" if is_enabled else "✅ Включить"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data=f"agame:toggle:{game_type}"))
    if game_type == "slots":
        builder.row(InlineKeyboardButton(text="📈 Коэф. 777 (Джекпот)", callback_data=f"agame:coeff1:{game_type}"))
        builder.row(InlineKeyboardButton(text="📈 Коэф. 3 фрукта", callback_data=f"agame:coeff2:{game_type}"))
    else:
        builder.row(InlineKeyboardButton(text="📈 Коэффициент", callback_data=f"agame:coeff:{game_type}"))
    builder.row(InlineKeyboardButton(text="💰 Мин. ставка", callback_data=f"agame:min_bet:{game_type}"))
    builder.row(InlineKeyboardButton(text="👣 Шаг ставки", callback_data=f"agame:bet_step:{game_type}"))
    builder.row(InlineKeyboardButton(text="🔢 Лимит в день (0=∞)", callback_data=f"agame:daily_limit:{game_type}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:games"))
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Награда за реферала", callback_data="settings:referral_reward"))
    builder.row(InlineKeyboardButton(text="⏱ Кулдаун бонуса (часы)", callback_data="settings:bonus_cooldown"))
    builder.row(InlineKeyboardButton(text="🎁 Мин. бонус", callback_data="settings:bonus_min"))
    builder.row(InlineKeyboardButton(text="🎁 Макс. бонус", callback_data="settings:bonus_max"))
    builder.row(InlineKeyboardButton(text="📢 ID канала выплат", callback_data="settings:payments_channel_id"))
    builder.row(InlineKeyboardButton(text="🔗 Ссылка на канал выплат", callback_data="settings:payments_channel_url"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def promo_list_kb(promos: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for promo in promos:
        status = "✅" if promo.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {promo.code} ({promo.usage_count} использований)",
                callback_data=f"admin:promo_info:{promo.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def promo_actions_kb(promo_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Деактивировать" if is_active else "✅ Активировать"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"admin:promo_toggle:{promo_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:promo_delete:{promo_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:list_promos"))
    return builder.as_markup()


def promo_reward_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Фиксированная", callback_data="promo_type:fixed"),
        InlineKeyboardButton(text="Случайная", callback_data="promo_type:random"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:main"))
    return builder.as_markup()


def withdrawal_actions_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"withdrawal:approve:{withdrawal_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"withdrawal:reject:{withdrawal_id}"),
            ]
        ]
    )


def withdrawal_return_kb(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="↩️ Вернуть на баланс", callback_data=f"withdrawal:return:{withdrawal_id}"),
                InlineKeyboardButton(text="✖️ Не возвращать", callback_data=f"withdrawal:noreturn:{withdrawal_id}"),
            ]
        ]
    )


def retention_kb(enabled: bool, days: int, bonus: float) -> InlineKeyboardMarkup:
    toggle_text = "✅ Включено" if enabled else "❌ Выключено"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data="retention:toggle"))
    builder.row(InlineKeyboardButton(text=f"📅 Дней неактивности: {days}", callback_data="retention:set_days"))
    builder.row(InlineKeyboardButton(text=f"⭐ Бонус: {bonus}", callback_data="retention:set_bonus"))
    builder.row(InlineKeyboardButton(text="✏️ Текст сообщения", callback_data="retention:set_message"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]]
    )


def task_management_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить задание", callback_data="admin:add_task"))
    builder.row(InlineKeyboardButton(text="📦 Добавить несколько каналов", callback_data="admin:add_bulk_tasks"))
    builder.row(InlineKeyboardButton(text="📋 Список заданий", callback_data="admin:list_tasks"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def task_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Подписка на канал", callback_data="task_type:subscribe"),
        InlineKeyboardButton(text="👥 Рефералы", callback_data="task_type:referrals"),
    )
    builder.row(InlineKeyboardButton(text="🔗 Linkni", callback_data="task_type:linkni"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin:tasks"))
    return builder.as_markup()


def task_list_admin_kb(tasks: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task in tasks:
        status = "✅" if task.is_active else "❌"
        type_icon = "📢" if task.task_type == "subscribe" else "👥"
        builder.row(InlineKeyboardButton(
            text=f"{status} {type_icon} {task.title}",
            callback_data=f"admin:task_info:{task.id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:tasks"))
    return builder.as_markup()


def task_actions_kb(task_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Деактивировать" if is_active else "✅ Активировать"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"admin:task_toggle:{task_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:task_delete:{task_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:list_tasks"))
    return builder.as_markup()


# ─── Button Content Management ─────────────────────────────────────────────────

BUTTON_KEYS: dict[str, str] = {
    "menu:main":           "🏠 Главное меню",
    "menu:earn":           "⭐ Получить звёзды",
    "menu:referrals":      "👥 Мои рефералы",
    "menu:bonus":          "🎁 Бонус",
    "menu:profile":        "👤 Профиль",
    "menu:tasks":          "📋 Задания",
    "menu:top":            "🏆 Топ (выбор категории)",
    "top:refs":            "👥 Топ по рефералам (выбор периода)",
    "top:stars":           "⭐ Топ по звёздам (выбор периода)",
    "menu:games":          "🎮 Игры",
    "menu:withdraw":       "💰 Вывод",
    "menu:search":         "🔍 Найти пользователя",
    "menu:how":            "ℹ️ Как это работает",
    "withdrawal:approved": "💸 Сообщение об одобрении выплаты",
    "duel:banner":         "⚔️ Баннер дуэлей",
}


def button_content_list_kb(contents: dict[str, bool]) -> InlineKeyboardMarkup:
    """contents: {button_key: has_any_content}"""
    builder = InlineKeyboardBuilder()
    for key, label in BUTTON_KEYS.items():
        icon = "🖼" if contents.get(key) else "⬜"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"admin:btn_edit:{key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def button_edit_kb(button_key: str, has_photo: bool, has_text: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🖼 Установить фото",
        callback_data=f"admin:btn_set_photo:{button_key}",
    ))
    builder.row(InlineKeyboardButton(
        text="📝 Установить текст",
        callback_data=f"admin:btn_set_text:{button_key}",
    ))
    if has_photo:
        builder.row(InlineKeyboardButton(
            text="🗑 Удалить фото",
            callback_data=f"admin:btn_del_photo:{button_key}",
        ))
    if has_text:
        builder.row(InlineKeyboardButton(
            text="🗑 Удалить текст",
            callback_data=f"admin:btn_del_text:{button_key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:button_content"))
    return builder.as_markup()


def stats_tabs_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 По дням (7 дней)", callback_data="admin:stats_daily"))
    builder.row(InlineKeyboardButton(text="🎮 По играм", callback_data="admin:stats_games"))
    builder.row(InlineKeyboardButton(text="💰 Комиссии", callback_data="admin:stats_commissions"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def integrations_kb(statuses: dict) -> InlineKeyboardMarkup:
    """
    statuses: {
        'botohub': bool, 'flyer': bool, 'piarflow': bool,
        'subgram': bool, 'gramads': bool,
    }
    """
    builder = InlineKeyboardBuilder()

    def _row(label: str, key: str) -> None:
        icon = "✅" if statuses.get(key) else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{icon} {label}",
            callback_data=f"integration:toggle:{key}",
        ))

    _row("BotoHub", "botohub")
    _row("Flyer", "flyer")
    _row("PiarFlow", "piarflow")
    _row("Subgram", "subgram")
    _row("Linkni (Tgrass)", "linkni")
    _row("GramAds (реклама)", "gramads")

    builder.row(InlineKeyboardButton(text="📊 Кількість спонсорів", callback_data="integration:counts"))
    builder.row(InlineKeyboardButton(text="🔑 API ключі", callback_data="integration:keys"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def integration_counts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="BotoHub — кількість", callback_data="integration:count:botohub"))
    builder.row(InlineKeyboardButton(text="PiarFlow — кількість", callback_data="integration:count:piarflow"))
    builder.row(InlineKeyboardButton(text="Subgram — кількість", callback_data="integration:count:subgram"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:integrations"))
    return builder.as_markup()


def integration_keys_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 BotoHub key", callback_data="integration:key:botohub"))
    builder.row(InlineKeyboardButton(text="🔑 Flyer key", callback_data="integration:key:flyer"))
    builder.row(InlineKeyboardButton(text="🔑 PiarFlow key", callback_data="integration:key:piarflow"))
    builder.row(InlineKeyboardButton(text="🔑 Subgram key", callback_data="integration:key:subgram"))
    builder.row(InlineKeyboardButton(text="🔑 Linkni code", callback_data="integration:key:linkni"))
    builder.row(InlineKeyboardButton(text="🔑 GramAds token", callback_data="integration:key:gramads"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:integrations"))
    return builder.as_markup()


