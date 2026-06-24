from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"),
    )
    builder.row(
        InlineKeyboardButton(text="💳 Пользователи", callback_data="admin:users"),
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:list_promos"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Задания", callback_data="admin:tasks"),
        InlineKeyboardButton(text="🎮 Игры", callback_data="admin:games"),
    )
    builder.row(
        InlineKeyboardButton(text="🔌 Интеграции", callback_data="admin:integrations"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings"),
    )
    builder.row(
        InlineKeyboardButton(text="🎟 Лотерея", callback_data="admin:lottery"),
        InlineKeyboardButton(text="🔔 Удержание", callback_data="admin:retention"),
    )
    builder.row(
        InlineKeyboardButton(text="🗄 База данных", callback_data="admin:database"),
        InlineKeyboardButton(text="🖼 Кнопки/фото", callback_data="admin:button_content"),
    )
    builder.row(InlineKeyboardButton(text="🎡 Колесо / Кейсы", callback_data="admin:casino"))
    return builder.as_markup()


def admin_users_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Начислить звёзды", callback_data="admin:credit"),
        InlineKeyboardButton(text="➖ Списать звёзды", callback_data="admin:debit"),
    )
    builder.row(InlineKeyboardButton(text="👥 Начислить рефералов", callback_data="admin:add_referral"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_database_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Экспорт БД", callback_data="admin:db_export"),
        InlineKeyboardButton(text="📥 Импорт БД", callback_data="admin:db_import"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


# ─── Game management keyboards ────────────────────────────────────────────────

_GAME_LABELS = {
    "football":   "⚽ Футбол",
    "basketball": "🏀 Баскетбол",
    "bowling":    "🎳 Боулинг",
    "dice":       "🎲 Кубики",
    "slots":      "🎰 Слоты",
    "darts":      "🎯 Дартс",
}
_GAME_TYPES = ["football", "basketball", "bowling", "dice", "slots", "darts"]


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
    elif game_type == "football":
        builder.row(InlineKeyboardButton(text="⚽ Коэф. Гол", callback_data="agame:cg:football:goal"))
        builder.row(InlineKeyboardButton(text="🥅 Коэф. Промах", callback_data="agame:cg:football:miss"))
    elif game_type == "basketball":
        builder.row(InlineKeyboardButton(text="🏀 Коэф. Чистый гол", callback_data="agame:cg:basketball:clean"))
        builder.row(InlineKeyboardButton(text="🏀 Коэф. Любой гол", callback_data="agame:cg:basketball:any"))
        builder.row(InlineKeyboardButton(text="🏀 Коэф. Застрял мяч", callback_data="agame:cg:basketball:stuck"))
        builder.row(InlineKeyboardButton(text="🏀 Коэф. Промах", callback_data="agame:cg:basketball:miss"))
    elif game_type == "bowling":
        builder.row(InlineKeyboardButton(text="🎳 Коэф. Страйк", callback_data="agame:cg:bowling:strike"))
        builder.row(InlineKeyboardButton(text="🎳 Коэф. Промах", callback_data="agame:cg:bowling:miss"))
    elif game_type == "darts":
        builder.row(InlineKeyboardButton(text="🎯 Коэф. В центр", callback_data="agame:cg:darts:bullseye"))
        builder.row(InlineKeyboardButton(text="🎯 Коэф. Красный сектор", callback_data="agame:cg:darts:red"))
        builder.row(InlineKeyboardButton(text="🎯 Коэф. Белый сектор", callback_data="agame:cg:darts:white"))
        builder.row(InlineKeyboardButton(text="🎯 Коэф. Отскок", callback_data="agame:cg:darts:bounce"))
    else:
        builder.row(InlineKeyboardButton(text="📈 Коэффициент", callback_data=f"agame:coeff:{game_type}"))
    builder.row(InlineKeyboardButton(text="💰 Мин. ставка", callback_data=f"agame:min_bet:{game_type}"))
    builder.row(InlineKeyboardButton(text="👣 Шаг ставки", callback_data=f"agame:bet_step:{game_type}"))
    builder.row(InlineKeyboardButton(text="🔢 Лимит в день (0=∞)", callback_data=f"agame:daily_limit:{game_type}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:games"))
    return builder.as_markup()


def admin_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Награда за реферала (фикс.)", callback_data="settings:referral_reward"))
    builder.row(InlineKeyboardButton(text="🔄 Режим награды", callback_data="settings:reward_mode"))
    builder.row(InlineKeyboardButton(text="💰 Цена 1 спонсора", callback_data="settings:reward_per_sponsor"))
    builder.row(InlineKeyboardButton(text="🔢 Мин. спонсоров для выплаты", callback_data="settings:min_sponsors"))
    builder.row(InlineKeyboardButton(text="⏱ Кулдаун бонуса (часы)", callback_data="settings:bonus_cooldown"))
    builder.row(InlineKeyboardButton(text="🎁 Мин. бонус", callback_data="settings:bonus_min"))
    builder.row(InlineKeyboardButton(text="🎁 Макс. бонус", callback_data="settings:bonus_max"))
    builder.row(InlineKeyboardButton(text="📢 ID канала выплат", callback_data="settings:payments_channel_id"))
    builder.row(InlineKeyboardButton(text="🔗 Ссылка на канал выплат", callback_data="settings:payments_channel_url"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def reward_mode_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📌 Фиксированная", callback_data="reward_mode:fixed"),
        InlineKeyboardButton(text="📊 За спонсоров", callback_data="reward_mode:per_sponsor"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:settings"))
    return builder.as_markup()


def promo_list_kb(promos: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить промокод", callback_data="admin:add_promo"))
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
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data=f"withdrawal:stats:{withdrawal_id}"),
            ],
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
    builder.row(
        InlineKeyboardButton(text="📅 По дням", callback_data="admin:stats_daily"),
        InlineKeyboardButton(text="📣 Спонсоры", callback_data="admin:stats_sponsors"),
    )
    builder.row(
        InlineKeyboardButton(text="🎮 По играм", callback_data="admin:stats_games"),
        InlineKeyboardButton(text="💰 Комиссии", callback_data="admin:stats_commissions"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def integrations_kb(statuses: dict) -> InlineKeyboardMarkup:
    """
    statuses: {
        'botohub': bool, 'subgram': bool, 'tgrass': bool, 'gramads': bool,
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
    _row("Subgram", "subgram")
    _row("TGrass", "tgrass")
    _row("GramAds (реклама)", "gramads")

    builder.row(InlineKeyboardButton(text="📊 Количество спонсоров", callback_data="integration:counts"))
    builder.row(InlineKeyboardButton(text="🔑 API ключи", callback_data="integration:keys"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def integration_counts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="BotoHub — количество", callback_data="integration:count:botohub"))
    builder.row(InlineKeyboardButton(text="Subgram — количество", callback_data="integration:count:subgram"))
    builder.row(InlineKeyboardButton(text="🔢 Лимит спонсоров (всего)", callback_data="integration:count:wall"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:integrations"))
    return builder.as_markup()


def integration_keys_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 BotoHub key", callback_data="integration:key:botohub"))
    builder.row(InlineKeyboardButton(text="🔑 Subgram key", callback_data="integration:key:subgram"))
    builder.row(InlineKeyboardButton(text="🔑 TGrass code", callback_data="integration:key:tgrass"))
    builder.row(InlineKeyboardButton(text="🔑 GramAds token", callback_data="integration:key:gramads"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:integrations"))
    return builder.as_markup()


# ─── Casino (Wheel + Cases) admin keyboards ────────────────────────────────────

def admin_casino_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎡 Колесо — видео", callback_data="casino:wheel_videos"))
    builder.row(InlineKeyboardButton(text="🎁 Кейсы — видео", callback_data="casino:cases_videos"))
    builder.row(InlineKeyboardButton(text="📊 Прибыль казино", callback_data="casino:profit"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main"))
    return builder.as_markup()


def admin_wheel_videos_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎬 Видео для 0.1x (проигрыш)", callback_data="casino:set_video:wheel_video_01x"))
    builder.row(InlineKeyboardButton(text="🎬 Видео для 50x (джекпот)", callback_data="casino:set_video:wheel_video_50x"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:casino"))
    return builder.as_markup()


def admin_cases_videos_kb() -> InlineKeyboardMarkup:
    """Tier selector — pick which case to configure."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🥉 Бронза — 1⭐ (14 призов)", callback_data="casino:cases_tier:1"))
    builder.row(InlineKeyboardButton(text="🥈 Серебро — 3⭐ (11 призов)", callback_data="casino:cases_tier:3"))
    builder.row(InlineKeyboardButton(text="🥇 Золото — 5⭐ (9 призов)", callback_data="casino:cases_tier:5"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:casino"))
    return builder.as_markup()


_CASE_PRIZES_LIST: dict[int, list[float]] = {
    1: [0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0, 3.5],
    3: [0.5, 0.7, 0.9, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
    5: [1.0, 3.0, 5.0, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0],
}

_TIER_ICONS = {1: "🥉", 3: "🥈", 5: "🥇"}


def prize_to_key(tier: int, prize: float) -> str:
    """BotSettings key for a specific prize video: case_1_video_0_1"""
    return f"case_{tier}_video_{str(prize).replace('.', '_')}"


def admin_case_prizes_kb(tier: int) -> InlineKeyboardMarkup:
    """Prize buttons for a tier — each opens a video upload."""
    builder = InlineKeyboardBuilder()
    prizes = _CASE_PRIZES_LIST.get(tier, [])
    for prize in prizes:
        key = prize_to_key(tier, prize)
        builder.button(text=f"{prize}⭐", callback_data=f"casino:set_video:{key}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="casino:cases_videos"))
    return builder.as_markup()


def casino_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin:casino")]]
    )


