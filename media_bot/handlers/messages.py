# ── i18n ─────────────────────────────────────────────
SUPPORTED_LANGUAGES = {"ru", "en"}
DEFAULT_LANGUAGE = "ru"


def msg(key: str, lang: str = "ru"):
    """Возвращает текст на нужном языке.

    Приоритет: _TRANSLATIONS[lang][key] → globals()[key] (русский fallback).
    """
    if lang != "ru" and lang in SUPPORTED_LANGUAGES:
        val = _TRANSLATIONS.get(lang, {}).get(key)
        if val is not None:
            return val
    # fallback — русская константа
    return globals().get(key)


# ── Русские тексты (оригинал) ────────────────────────

WELCOME = """
👋 <b>Скачивай премиум с Envato, Freepik и Motion Array — бесплатно!</b>

🎁 У тебя <b>2 бесплатных скачивания</b> в неделю.

Нажми команду → кидай ссылку → готово!
/envato · /freepik · /motion

👇
"""

MAINTENANCE_MESSAGE = """
🔧 <b>Технические работы</b>

Приносим свои извинения за временные неудобства.

Сейчас проводятся серьёзные технические работы по улучшению сервиса.

⏰ Бот будет доступен в ближайшее время.

💬 По вопросам: <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

APPLY_DOWNLOAD = """
✅ <b>Envato Elements</b>

Кидай ссылку на файл 👇

Пример: <code>elements.envato.com/ru/...</code>

🎁 Осталось бесплатных скачиваний: <b>{credit}</b>
"""

APPLY_DOWNLOAD_FREEPIK = """
✅ <b>Freepik</b>

Кидай ссылку на файл 👇

Пример: <code>freepik.com/free-photo/...</code>

🎁 Осталось бесплатных: <b>{credit}</b>
"""

CANCLE_DOWNLOAD_PAYMENT_OFF = """
❌ <b>Бесплатные скачивания закончились</b>

Оформи подписку и качай без ограничений 👇

💳 Нажми <b>"Оплата"</b> и выбери тариф

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

BAD_URL = """
❌ <b>Некорректная ссылка</b>

Скопируй полную ссылку из браузера и отправь ещё раз.

Пример: <code>elements.envato.com/ru/...</code>

💬 Нужна помощь? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

BAD_URL_FREEPIK = """
❌ <b>Некорректная ссылка</b>

Скопируй полную ссылку из браузера и отправь ещё раз.

Пример: <code>freepik.com/free-photo/...</code>

💬 Нужна помощь? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

DOWNLOAD_FILE = """
Нажми <b>"Скачать файл 📁"</b>

⚠️ Ссылка действует <b>30 секунд</b>

🎁 Осталось бесплатных: <b>{credit}</b>

Хочешь ещё? Просто кидай следующую ссылку 👇
"""

CHANEL_CHECK = """
🎁 <b>+2 бесплатных скачивания</b>

Подпишись на наш канал — и они твои!

1. Жми <b>"Подписаться"</b>
2. Потом <b>"Проверить подписку"</b>

👇
"""

CHANEL_APPLY = """
✅ <b>Подписка подтверждена!</b>

🎁 +2 скачивания начислены

Выбирай сервис и кидай ссылку 👇
/envato · /freepik · /motion
"""


CHANEL_CANCLE = """
🤔 <b>Хм, подписка не найдена</b>

Жми <b>"Подписаться"</b> на <a href="https://t.me/footagehub_channel">канал</a>, потом <b>"Проверить"</b>
"""

SUB_PAYMENT_MONTHLY_50 = """
💎 <b>Lite — Доступ на месяц</b>

📦 <b>Что входит:</b>
- До 50 загрузок за период
- Envato Elements
- Freepik
- Motion Array
- Без дневных лимитов

⚠️ Срок действия 30 дней

💰 <b>{_price} ₽</b>
<i>Списание по курсу банка вашей карты</i>

Жми для оплаты 👇

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

SUB_PAYMENT_MONTHLY_150 = """
💎 <b>Standard — Доступ на месяц - лимиты X3</b>

📦 <b>Что входит:</b>
- До 150 загрузок за период (X3)
- Envato Elements
- Freepik
- Motion Array
- Без дневных лимитов

⚠️ Срок действия 30 дней

💰 <b>{_price} ₽</b>
<i>Списание по курсу банка вашей карты</i>

Жми для оплаты 👇

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

SUB_PAYMENT_MONTHLY_400 = """
💎 <b>Pro — Доступ на месяц - лимиты X8</b>

📦 <b>Что входит:</b>
- До 400 загрузок за период (X8)
- Envato Elements
- Freepik
- Motion Array
- Без дневных лимитов

⚠️ Срок действия 30 дней

💰 <b>{_price} ₽</b>
<i>Списание по курсу банка вашей карты</i>

Жми для оплаты 👇

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

SUB_PAYMENT_DAILY = """
💎 <b>Дневная подписка (30/день)</b>

📦 <b>Что входит:</b>
- 30 скачиваний каждый день
- Период: 30 дней
- Envato Elements
- Freepik
- Motion Array
- Лимит обновляется ежедневно

⚠️ Срок действия 30 дней

💰 <b>{_price} ₽</b>

Жми для оплаты 👇

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

# Сообщения об ошибках и статусах
USER_NOT_REGISTERED = """
❌ <b>Ты не зарегистрирован</b>

Нажми /start чтобы начать

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

USER_NOT_FOUND = """
❌ <b>Пользователь не найден</b>

Нажми /start чтобы начать

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

DOWNLOAD_FAILED = """
❌ <b>Не удалось скачать файл</b>

Проверь ссылку и попробуй ещё раз.

💬 Не получается? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

DOWNLOAD_RETRY = """
Попробуй ещё раз или напиши в <a href="https://t.me/FootageHub_support">поддержку</a>
"""

LINK_NOT_FOUND = """
❌ <b>Не удалось получить файл</b>

Попробуй позже или напиши в <a href="https://t.me/FootageHub_support">поддержку</a>
"""

LINK_READY = """
✅ <b>Готово!</b>

⚠️ Ссылка действует <b>30 секунд</b>
"""

PROCESSING_LINK = """
⏳ Секунду...
"""

PROCESSING_COMPLETE = """
✅ Готово!
"""

ALREADY_DOWNLOADED = """
✅ Этот файл уже в вашей истории загрузок
📎 Отправляем новую ссылку для скачивания
"""

NO_SUBSCRIPTION_FOR_LICENSE = """
🔒 <b>Требуется подписка</b>

Скачивание с лицензией доступно только для подписчиков.

<b>У вас есть два варианта:</b>
✓ Скачать без лицензии (бесплатно) — уберите точку в начале ссылки
✓ Получить лицензию — оформите подписку от $6/мес

💎 Оформить подписку
"""

ALREADY_HAS_SUBSCRIPTION = """
✅ <b>У вас уже есть активная подписка!</b>

📋 <b>Ваша подписка:</b>
- Тариф: {subscription_type}
- Действует до: {end_date}
- Осталось загрузок: {credits}

Продолжайте пользоваться текущей подпиской. Продление или смена тарифа станут доступны после её окончания.

💬 Есть вопросы? Напишите в <a href="https://t.me/FootageHub_support">поддержку</a>
"""

SUBSCRIPTION_ACTIVATED = """
🎉 <b>Всё готово! Подписка активирована</b>

📋 <b>Ваша подписка:</b>
- Тариф: {subscription_type}
- Период: {period_days} дней (до {end_date})
- Доступно: {credits} загрузок

✅ <b>Доступные платформы:</b>
- Envato Elements — видео, графика, музыка
- Freepik — векторы, фото, PSD
- Motion Array — футажи и эффекты

🚀 Начните прямо сейчас — выберите сервис в меню!

💬 <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

# Motion Array messages
APPLY_DOWNLOAD_MOTION = """
✅ <b>Motion Array</b>

Кидай ссылку на файл 👇

Пример: <code>motionarray.com/...</code>

🎁 Осталось бесплатных: <b>{credit}</b>
"""

BAD_URL_MOTION = """
❌<b>Некорректная ссылка!</b>

Проверь, чтобы ссылка из
браузера была полностью
скопирована, а затем вновь
отправь её мне.

вот пример правильной ссылки:
https://\u200bmotionarray\u200b.\u200bcom/stock-motion-
graphics/pack-of-16-colorful-
inflated-icons-3434542/

Либо нажми на кнопку
"Посмотреть инструкцию"

💬 Нужна помощь? Пиши в <a href="https://t.me/FootageHub_support">поддержку</a>
"""

# Поштучная покупка загрузок
PERPETUAL_CREDITS_PROMPT = """
💎 <b>Покупка поштучно</b>

📌 <b>Что это?</b>
Загрузки, которые <b>никогда не сгорают</b> — используй когда удобно!

💰 <b>Цена:</b> 30 ₽ за 1 загрузку
📦 <b>Минимум:</b> 3 загрузки (90 ₽)
📦 <b>Максимум:</b> 90 загрузок (2700 ₽)

✅ Введите количество загрузок, которое хотите купить:
"""

PERPETUAL_CREDITS_CONFIRMATION = """
💎 <b>Подтверждение покупки</b>

📦 Количество: <b>{quantity}</b> загрузок
💰 Стоимость: <b>{price} ₽</b>
<i>Списание по курсу банка вашей карты</i>

✅ Кредиты будут начислены сразу после оплаты
⚡️ Не сгорают, используй когда удобно

Жми для оплаты 👇

💬 Вопросы? → <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

PERPETUAL_CREDITS_PURCHASED = """
🎉 <b>Загрузки получены!</b>

✅ Начислено: <b>{quantity}</b> загрузок
💎 Всего у вас: <b>{total_credits}</b> загрузок

Используйте их для скачивания с:
- Envato Elements
- Freepik
- Motion Array

🚀 Выберите сервис в меню и кидайте ссылку!

💬 <a href="https://t.me/FootageHub_support">Поддержка</a>
"""

PERPETUAL_CREDITS_INVALID_QUANTITY = """
❌ <b>Некорректное количество</b>

Минимальное количество: <b>3 загрузки</b>

Пожалуйста, введите число не меньше 3.
"""

PERPETUAL_CREDITS_INVALID_INPUT = """
❌ <b>Некорректный ввод</b>

Пожалуйста, введите целое число (минимум 3).

Пример: <code>10</code>
"""

# Главное меню
MAIN_MENU = "📋 <b>Главное меню</b>\n\nВыберите нужный раздел:"

# Короткое сообщение "не найден"
USER_NOT_FOUND_SHORT = "Пользователь не найден."

# Профиль пользователя
INFO_MESSAGE = (
    "👤 <b>Ваш профиль</b>\n\n"
    "🎁 Бесплатно: <b>{credits}</b>\n"
    "💼 Статус: {sub_status}\n"
    "⏰ До: {sub_until}\n"
    "📊 Доступно: {sub_limits}\n"
    "✅ Скачано: <b>{downloads_count}</b>\n\n"
    "──────────────────────────────\n\n"
    "📊 <b>Сегодня в FootageHub</b>\n"
    "⚡️ Загрузок за 24ч: <b>{downloads_24h}</b>\n"
)

# Реферальная система
REFERRAL_NEW_NOTIFICATION = (
    "🎉 <b>У вас новый реферал!</b>\n\n"
    "По вашей реферальной ссылке зарегистрировался новый пользователь.\n\n"
    "💰 Вам начислено <b>{credits_granted} скачиваний</b>\n\n"
    "Узнайте подробнее в разделе /referral"
)

REFERRAL_MAIN = (
    "🎁 <b>Реферальная программа</b>\n\n"
    "👥 Приглашено рефералов: <b>{total_referrals}</b>\n"
    "💰 Заработано бонусов: <b>{total_credits_earned} скачиваний</b>\n"
    "✅ Активных рефералов: <b>{active_referrals}</b>\n\n"
    "📋 <b>Ваша реферальная ссылка:</b>\n"
    "<code>{referral_link}</code>\n\n"
    "🎯 <b>Как это работает:</b>\n"
    "1️⃣ Поделитесь ссылкой с друзьями\n"
    "2️⃣ Когда друг регистрируется — вы получаете <b>3 скачивания</b>\n"
    "3️⃣ Когда друг совершает первую покупку — вы получаете <b>5 скачиваний</b>\n\n"
)

REFERRAL_MILESTONES = (
    "🏆 <b>Milestone награды:</b>\n"
    "• 5 рефералов → +5 скачиваний\n"
    "• 10 рефералов → +10 скачиваний\n"
    "• 25 рефералов → +25 скачиваний\n"
    "• 50 рефералов → +50 скачиваний\n"
    "• 100 рефералов → +100 скачиваний\n"
)

REFERRAL_TRIGGER_NAMES = {
    "REGISTRATION": "Регистрация реферала",
    "FIRST_PAYMENT": "Первая покупка реферала",
    "SUBSCRIPTION": "Подписка реферала",
    "MILESTONE": "Milestone награда",
}

REFERRAL_NO_REFERRALS = (
    "📭 <b>У вас пока нет рефералов</b>\n\n"
    "Используйте команду /referral чтобы получить вашу реферальную ссылку!"
)

REFERRAL_LIST_HEADER = (
    "👥 <b>Ваши рефералы ({count})</b>\n\n"
    "✅ Активных: {active_referrals}\n"
    "💰 Заработано: {total_credits_earned} скачиваний\n\n"
)

REFERRAL_NO_REWARDS = (
    "📭 <b>История наград пуста</b>\n\n"
    "Приглашайте друзей, чтобы получать бонусы!\n"
    "Используйте команду /referral для получения реферальной ссылки."
)

REFERRAL_REWARDS_HEADER = (
    "💎 <b>История реферальных наград</b>\n\n"
    "Всего заработано: <b>{total_earned} скачиваний</b>\n"
    "Всего наград: <b>{total_rewards}</b>\n\n"
)

REFERRAL_REWARDS_FOOTER = (
    "\n\nℹ️ Используйте /referral для просмотра текущей статистики "
    "и реферальной ссылки."
)

REFERRAL_ERROR_STATS = "❌ Ошибка при получении статистики рефералов."
REFERRAL_ERROR_LIST = "❌ Ошибка при получении списка рефералов."
REFERRAL_ERROR_REWARDS = "❌ Ошибка при получении истории наград."
REFERRAL_ERROR_MENU = "❌ Ошибка при возврате в меню."
REFERRAL_USER_NOT_FOUND = "❌ Пользователь не найден. Используйте /start для регистрации."

# Оплата
PAYMENT_USER_NOT_FOUND = "❌ Пользователь не найден"

PAYMENT_HAS_SUBSCRIPTION = (
    "✅ <b>У вас активная подписка!</b>\n\n"
    "📋 <b>Ваша подписка:</b>\n"
    "- Тариф: {subscription_type}\n"
    "- Действует до: {end_date}\n"
    "- Доступно: {credits} загрузок\n\n"
    "⚠️ <b>Новую подписку нельзя купить, пока действует текущая.</b>\n\n"
    "💎 Но вы можете докупить загрузки поштучно — они не сгорают и всегда доступны!\n\n"
    '❓ Есть вопросы? Напишите в <a href="https://t.me/FootageHub_support">поддержку</a>'
)

PAYMENT_PLANS_MENU = """💎 <b>Выберите тарифный план</b>

<b>Lite</b> · 50 шт. · ~8₽/файл
Базовый

<b>Standard</b> · 150 шт. · ~6₽/файл ⭐️
Популярный

<b>Pro</b> · 400 шт. · ~4.5₽/файл
Для активной работы

<i>Чем больше план — тем выгоднее!</i>"""

PAYMENT_PLANS_LOAD_ERROR = "❌ Ошибка загрузки списка подписок."
PAYMENT_CONFIG_ERROR = "❌ Ошибка конфигурации. Обратитесь к администратору."
PAYMENT_INVALID_PLAN = "❌ Неверный тариф подписки. Попробуйте снова."
PAYMENT_INVOICE_ERROR = "❌ Ошибка при создании инвойса. Попробуйте позже."
PAYMENT_SAVE_ERROR = "❌ Ошибка при сохранении платежа. Попробуйте позже."
PAYMENT_USER_START = "❌ Пользователь не найден. Начните с /start"

# Бонусы за подписку на канал
CHANNEL_BONUS_GIVEN = "💰 Вам начислено {credits} скачивания за подписку!"
CHANNEL_BONUS_ALREADY = "✅ Бонус за подписку вы уже получали ранее."
CHANNEL_BONUS_ALREADY_ALT = "❌ Бонус за подписку вы уже получали ранее."

# Поштучная покупка — превышен максимум
PERPETUAL_MAX_EXCEEDED = (
    "❌ <b>Превышен максимум</b>\n\n"
    "Максимальное количество: <b>{max_quantity} загрузок</b> за один раз.\n\n"
    "Пожалуйста, введите число не больше {max_quantity}."
)

# Кнопки
BTN_DOWNLOAD_ENVATO = "Скачать Envato"
BTN_DOWNLOAD_FREEPIK = "Скачать Freepik"
BTN_DOWNLOAD_MOTION = "Скачать Motion Array"
BTN_INFO = "Информация"
BTN_SUBSCRIBE = "Оформить подписку 💳"
BTN_CANCEL = "❌ Отменить"
BTN_SUBSCRIBE_CHANNEL = "Подписаться ✅"
BTN_CHECK_SUBSCRIPTION = "Проверить подписку 🔍"
BTN_BUY_SUBSCRIPTION = "💳 Оформить подписку"
BTN_DOWNLOAD_FILE = "Cкачать файл 📁"
BTN_DOWNLOAD_MORE = "Cкачать ещё"
BTN_BACK_TO_PLANS = "⬅️ Назад к выбору"

# Кнопки навигации
BTN_BACK = "« Назад"
BTN_DOWNLOAD = "⬇️ Скачать"
BTN_PAY = "💳 Оплатить"
BTN_BUY_PERPETUAL = "💎 Купить поштучно"
BTN_MY_REFERRALS = "👥 Мои рефералы"
BTN_REFERRAL_HISTORY = "💎 История наград"
BTN_SEPARATOR_OR = "─────────── или ───────────"
BTN_LANG_RU = "🇷🇺 Русский"
BTN_LANG_EN = "🇬🇧 English"

# Кнопки тарифов
BTN_PLAN_LITE = "Lite · 50 шт · {price} ₽/мес"
BTN_PLAN_STANDARD = "Standard · 150 шт · {price} ₽/мес ⭐️"
BTN_PLAN_PRO = "Pro · 400 шт · {price} ₽/мес"
BTN_PLAN_OTHER = "{name} · {limit} шт · {price} ₽/мес"

# Статусы подписки (info.py)
SUB_STATUS_ACTIVE = "✅ Активна"
SUB_STATUS_INACTIVE = "❌ Неактивна"
SUB_LIMITS_UNLIMITED = "♾️ Безлимит"
SUB_LIMITS_DAILY = "{used}/{limit} (сегодня)"

# Реферальная система — дополнительные строки
REFERRAL_RECENT_HEADER = "\n💎 <b>Последние награды:</b>\n"
REFERRAL_REWARD_LINE = "{emoji} {trigger}: +{value} скачиваний\n"
REFERRAL_OTHER = "Другое"
REFERRAL_LIST_TITLE = "<b>Список рефералов:</b>\n"
REFERRAL_ITEM = "{idx}. ID: <b>{tid}</b>\n   Канал: {ch} | Покупка: {pay} | {date}\n"
REFERRAL_AND_MORE = "\n<i>... и еще {count}</i>\n"
REFERRAL_TRIGGER_NAMES_EXT = {
    "REGISTRATION": "📝 Регистрации рефералов",
    "FIRST_PAYMENT": "💳 Первые покупки",
    "SUBSCRIPTION": "🔔 Подписки",
    "MILESTONE": "🏆 Milestone награды",
}
REFERRAL_TRIGGER_STATS = "{name}\nКоличество: {count} | Сумма: {sum} скачиваний\n"

# Описания инвойсов
INVOICE_SUBSCRIPTION = "Покупка подписки {name}"
INVOICE_PERPETUAL = "Покупка {quantity} несгораемых загрузок"

# Ошибки download_service
ERR_INSUFFICIENT_CREDITS = "Недостаточно кредитов. Осталось: {remaining}"
ERR_SUBSCRIPTION_REQUIRED = "Для загрузки требуется активная подписка"
ERR_AUTH_FAILED = "Ошибка авторизации {provider}. Обратитесь к администратору."
ERR_DOWNLOAD_FAILED = "Не удалось загрузить файл"
ERR_DOWNLOAD_GENERIC = "Ошибка загрузки: {error}"

# Ошибки subscription_repository
ERR_SUB_EXPIRED = "Подписка истекла"
ERR_TOTAL_LIMIT = "Достигнут общий лимит скачиваний"
ERR_DAILY_LIMIT = "Достигнут дневной лимит скачиваний"

# Команды бота
CMD_MENU = "Меню"
CMD_ENVATO = "Скачать Envato"
CMD_FREEPIK = "Скачать Freepik"
CMD_MOTION = "Скачать Motion Array"
CMD_INFO = "Информация"
CMD_PAY = "Оформить подписку"
CMD_REFERRAL = "Реферальная программа"
CMD_LANG = "Язык / Language"

# Выбор языка
LANG_CHOOSE = "🌐 <b>Выберите язык / Choose language:</b>"
LANG_SET = "✅ Язык установлен: <b>Русский</b> 🇷🇺"

# ── Английские переводы ──────────────────────────────
_TRANSLATIONS = {
    "en": {
        "WELCOME": """
👋 <b>Download premium from Envato, Freepik & Motion Array — for free!</b>

🎁 You have <b>2 free downloads</b> per week.

Tap a command → send a link → done!
/envato · /freepik · /motion

👇
""",
        "MAINTENANCE_MESSAGE": """
🔧 <b>Maintenance</b>

We apologize for the temporary inconvenience.

Major maintenance is currently in progress to improve the service.

⏰ The bot will be available shortly.

💬 Questions: <a href="https://t.me/FootageHub_support">Support</a>
""",
        "APPLY_DOWNLOAD": """
✅ <b>Envato Elements</b>

Send the file link 👇

Example: <code>elements.envato.com/ru/...</code>

🎁 Free downloads left: <b>{credit}</b>
""",
        "APPLY_DOWNLOAD_FREEPIK": """
✅ <b>Freepik</b>

Send the file link 👇

Example: <code>freepik.com/free-photo/...</code>

🎁 Free downloads left: <b>{credit}</b>
""",
        "CANCLE_DOWNLOAD_PAYMENT_OFF": """
❌ <b>Free downloads exhausted</b>

Get a subscription and download without limits 👇

💳 Tap <b>"Payment"</b> and choose a plan

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "BAD_URL": """
❌ <b>Invalid link</b>

Copy the full link from your browser and send it again.

Example: <code>elements.envato.com/ru/...</code>

💬 Need help? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "BAD_URL_FREEPIK": """
❌ <b>Invalid link</b>

Copy the full link from your browser and send it again.

Example: <code>freepik.com/free-photo/...</code>

💬 Need help? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "DOWNLOAD_FILE": """
Tap <b>"Download file 📁"</b>

⚠️ Link expires in <b>30 seconds</b>

🎁 Free downloads left: <b>{credit}</b>

Want more? Just send the next link 👇
""",
        "CHANEL_CHECK": """
🎁 <b>+2 free downloads</b>

Subscribe to our channel and they're yours!

1. Tap <b>"Subscribe"</b>
2. Then <b>"Check subscription"</b>

👇
""",
        "CHANEL_APPLY": """
✅ <b>Subscription confirmed!</b>

🎁 +2 downloads credited

Choose a service and send a link 👇
/envato · /freepik · /motion
""",
        "CHANEL_CANCLE": """
🤔 <b>Hmm, subscription not found</b>

Tap <b>"Subscribe"</b> to <a href="https://t.me/footagehub_channel">channel</a>, then <b>"Check"</b>
""",
        "SUB_PAYMENT_MONTHLY_50": """
💎 <b>Lite — Monthly access</b>

📦 <b>Includes:</b>
- Up to 50 downloads per period
- Envato Elements
- Freepik
- Motion Array
- No daily limits

⚠️ Valid for 30 days

💰 <b>{_price} ₽</b>
<i>Charged at your bank's exchange rate</i>

Tap to pay 👇

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "SUB_PAYMENT_MONTHLY_150": """
💎 <b>Standard — Monthly access — limits X3</b>

📦 <b>Includes:</b>
- Up to 150 downloads per period (X3)
- Envato Elements
- Freepik
- Motion Array
- No daily limits

⚠️ Valid for 30 days

💰 <b>{_price} ₽</b>
<i>Charged at your bank's exchange rate</i>

Tap to pay 👇

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "SUB_PAYMENT_MONTHLY_400": """
💎 <b>Pro — Monthly access — limits X8</b>

📦 <b>Includes:</b>
- Up to 400 downloads per period (X8)
- Envato Elements
- Freepik
- Motion Array
- No daily limits

⚠️ Valid for 30 days

💰 <b>{_price} ₽</b>
<i>Charged at your bank's exchange rate</i>

Tap to pay 👇

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "SUB_PAYMENT_DAILY": """
💎 <b>Daily subscription (30/day)</b>

📦 <b>Includes:</b>
- 30 downloads every day
- Period: 30 days
- Envato Elements
- Freepik
- Motion Array
- Limit resets daily

⚠️ Valid for 30 days

💰 <b>{_price} ₽</b>

Tap to pay 👇

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "USER_NOT_REGISTERED": """
❌ <b>You are not registered</b>

Press /start to begin

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "USER_NOT_FOUND": """
❌ <b>User not found</b>

Press /start to begin

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "DOWNLOAD_FAILED": """
❌ <b>Failed to download the file</b>

Check the link and try again.

💬 Having trouble? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "DOWNLOAD_RETRY": """
Try again or contact <a href="https://t.me/FootageHub_support">support</a>
""",
        "LINK_NOT_FOUND": """
❌ <b>Failed to get the file</b>

Try again later or contact <a href="https://t.me/FootageHub_support">support</a>
""",
        "LINK_READY": """
✅ <b>Done!</b>

⚠️ Link expires in <b>30 seconds</b>
""",
        "PROCESSING_LINK": """
⏳ One moment...
""",
        "PROCESSING_COMPLETE": """
✅ Done!
""",
        "ALREADY_DOWNLOADED": """
✅ This file is already in your download history
📎 Sending a new download link
""",
        "NO_SUBSCRIPTION_FOR_LICENSE": """
🔒 <b>Subscription required</b>

Downloading with a license is only available for subscribers.

<b>You have two options:</b>
✓ Download without license (free) — remove the dot at the beginning of the link
✓ Get a license — subscribe from $6/mo

💎 Get a subscription
""",
        "ALREADY_HAS_SUBSCRIPTION": """
✅ <b>You already have an active subscription!</b>

📋 <b>Your subscription:</b>
- Plan: {subscription_type}
- Active until: {end_date}
- Downloads left: {credits}

Continue using your current subscription. Renewal or plan change will be available after it expires.

💬 Questions? Contact <a href="https://t.me/FootageHub_support">support</a>
""",
        "SUBSCRIPTION_ACTIVATED": """
🎉 <b>All set! Subscription activated</b>

📋 <b>Your subscription:</b>
- Plan: {subscription_type}
- Period: {period_days} days (until {end_date})
- Available: {credits} downloads

✅ <b>Available platforms:</b>
- Envato Elements — video, graphics, music
- Freepik — vectors, photos, PSD
- Motion Array — footage and effects

🚀 Start now — choose a service in the menu!

💬 <a href="https://t.me/FootageHub_support">Support</a>
""",
        "APPLY_DOWNLOAD_MOTION": """
✅ <b>Motion Array</b>

Send the file link 👇

Example: <code>motionarray.com/...</code>

🎁 Free downloads left: <b>{credit}</b>
""",
        "BAD_URL_MOTION": """
❌<b>Invalid link!</b>

Make sure the link from
the browser is fully
copied, then send
it again.

Here is an example of a correct link:
https://\u200bmotionarray\u200b.\u200bcom/stock-motion-
graphics/pack-of-16-colorful-
inflated-icons-3434542/

Or tap the button
"View instructions"

💬 Need help? Contact <a href="https://t.me/FootageHub_support">support</a>
""",
        "PERPETUAL_CREDITS_PROMPT": """
💎 <b>Buy per download</b>

📌 <b>What is this?</b>
Downloads that <b>never expire</b> — use whenever you want!

💰 <b>Price:</b> 30 ₽ per download
📦 <b>Minimum:</b> 3 downloads (90 ₽)
📦 <b>Maximum:</b> 90 downloads (2700 ₽)

✅ Enter the number of downloads you want to buy:
""",
        "PERPETUAL_CREDITS_CONFIRMATION": """
💎 <b>Purchase confirmation</b>

📦 Quantity: <b>{quantity}</b> downloads
💰 Cost: <b>{price} ₽</b>
<i>Charged at your bank's exchange rate</i>

✅ Credits will be added immediately after payment
⚡️ They never expire — use whenever you want

Tap to pay 👇

💬 Questions? → <a href="https://t.me/FootageHub_support">Support</a>
""",
        "PERPETUAL_CREDITS_PURCHASED": """
🎉 <b>Downloads received!</b>

✅ Credited: <b>{quantity}</b> downloads
💎 Total: <b>{total_credits}</b> downloads

Use them to download from:
- Envato Elements
- Freepik
- Motion Array

🚀 Choose a service in the menu and send a link!

💬 <a href="https://t.me/FootageHub_support">Support</a>
""",
        "PERPETUAL_CREDITS_INVALID_QUANTITY": """
❌ <b>Invalid quantity</b>

Minimum quantity: <b>3 downloads</b>

Please enter a number no less than 3.
""",
        "PERPETUAL_CREDITS_INVALID_INPUT": """
❌ <b>Invalid input</b>

Please enter a whole number (minimum 3).

Example: <code>10</code>
""",
        "MAIN_MENU": "📋 <b>Main menu</b>\n\nChoose a section:",
        "USER_NOT_FOUND_SHORT": "User not found.",
        "INFO_MESSAGE": (
            "👤 <b>Your profile</b>\n\n"
            "🎁 Free: <b>{credits}</b>\n"
            "💼 Status: {sub_status}\n"
            "⏰ Until: {sub_until}\n"
            "📊 Available: {sub_limits}\n"
            "✅ Downloaded: <b>{downloads_count}</b>\n\n"
            "──────────────────────────────\n\n"
            "📊 <b>Today at FootageHub</b>\n"
            "⚡️ Downloads in 24h: <b>{downloads_24h}</b>\n"
        ),
        "REFERRAL_NEW_NOTIFICATION": (
            "🎉 <b>You have a new referral!</b>\n\n"
            "A new user has registered via your referral link.\n\n"
            "💰 You received <b>{credits_granted} downloads</b>\n\n"
            "Learn more in /referral"
        ),
        "REFERRAL_MAIN": (
            "🎁 <b>Referral program</b>\n\n"
            "👥 Referrals invited: <b>{total_referrals}</b>\n"
            "💰 Bonuses earned: <b>{total_credits_earned} downloads</b>\n"
            "✅ Active referrals: <b>{active_referrals}</b>\n\n"
            "📋 <b>Your referral link:</b>\n"
            "<code>{referral_link}</code>\n\n"
            "🎯 <b>How it works:</b>\n"
            "1️⃣ Share the link with friends\n"
            "2️⃣ When a friend registers — you get <b>3 downloads</b>\n"
            "3️⃣ When a friend makes first purchase — you get <b>5 downloads</b>\n\n"
        ),
        "REFERRAL_MILESTONES": (
            "🏆 <b>Milestone rewards:</b>\n"
            "• 5 referrals → +5 downloads\n"
            "• 10 referrals → +10 downloads\n"
            "• 25 referrals → +25 downloads\n"
            "• 50 referrals → +50 downloads\n"
            "• 100 referrals → +100 downloads\n"
        ),
        "REFERRAL_TRIGGER_NAMES": {
            "REGISTRATION": "Referral registration",
            "FIRST_PAYMENT": "Referral first purchase",
            "SUBSCRIPTION": "Referral subscription",
            "MILESTONE": "Milestone reward",
        },
        "REFERRAL_NO_REFERRALS": (
            "📭 <b>You have no referrals yet</b>\n\n"
            "Use the /referral command to get your referral link!"
        ),
        "REFERRAL_LIST_HEADER": (
            "👥 <b>Your referrals ({count})</b>\n\n"
            "✅ Active: {active_referrals}\n"
            "💰 Earned: {total_credits_earned} downloads\n\n"
        ),
        "REFERRAL_NO_REWARDS": (
            "📭 <b>Rewards history is empty</b>\n\n"
            "Invite friends to earn bonuses!\n"
            "Use the /referral command to get your referral link."
        ),
        "REFERRAL_REWARDS_HEADER": (
            "💎 <b>Referral rewards history</b>\n\n"
            "Total earned: <b>{total_earned} downloads</b>\n"
            "Total rewards: <b>{total_rewards}</b>\n\n"
        ),
        "REFERRAL_REWARDS_FOOTER": (
            "\n\nℹ️ Use /referral to view current stats "
            "and your referral link."
        ),
        "REFERRAL_ERROR_STATS": "❌ Error getting referral stats.",
        "REFERRAL_ERROR_LIST": "❌ Error getting referrals list.",
        "REFERRAL_ERROR_REWARDS": "❌ Error getting rewards history.",
        "REFERRAL_ERROR_MENU": "❌ Error returning to menu.",
        "REFERRAL_USER_NOT_FOUND": "❌ User not found. Use /start to register.",
        "PAYMENT_USER_NOT_FOUND": "❌ User not found",
        "PAYMENT_HAS_SUBSCRIPTION": (
            "✅ <b>You have an active subscription!</b>\n\n"
            "📋 <b>Your subscription:</b>\n"
            "- Plan: {subscription_type}\n"
            "- Active until: {end_date}\n"
            "- Available: {credits} downloads\n\n"
            "⚠️ <b>You cannot buy a new subscription while the current one is active.</b>\n\n"
            "💎 But you can buy extra downloads — they never expire and are always available!\n\n"
            '❓ Questions? Contact <a href="https://t.me/FootageHub_support">support</a>'
        ),
        "PAYMENT_PLANS_MENU": """💎 <b>Choose a plan</b>

<b>Lite</b> · 50 pcs. · ~8₽/file
Basic

<b>Standard</b> · 150 pcs. · ~6₽/file ⭐️
Popular

<b>Pro</b> · 400 pcs. · ~4.5₽/file
For heavy use

<i>The bigger the plan — the better the deal!</i>""",
        "PAYMENT_PLANS_LOAD_ERROR": "❌ Error loading subscription plans.",
        "PAYMENT_CONFIG_ERROR": "❌ Configuration error. Contact the administrator.",
        "PAYMENT_INVALID_PLAN": "❌ Invalid subscription plan. Try again.",
        "PAYMENT_INVOICE_ERROR": "❌ Error creating invoice. Try later.",
        "PAYMENT_SAVE_ERROR": "❌ Error saving payment. Try later.",
        "PAYMENT_USER_START": "❌ User not found. Start with /start",
        "CHANNEL_BONUS_GIVEN": "💰 You received {credits} downloads for subscribing!",
        "CHANNEL_BONUS_ALREADY": "✅ You already received the subscription bonus.",
        "CHANNEL_BONUS_ALREADY_ALT": "❌ You already received the subscription bonus.",
        "PERPETUAL_MAX_EXCEEDED": (
            "❌ <b>Maximum exceeded</b>\n\n"
            "Maximum quantity: <b>{max_quantity} downloads</b> per purchase.\n\n"
            "Please enter a number no greater than {max_quantity}."
        ),
        "LANG_CHOOSE": "🌐 <b>Выберите язык / Choose language:</b>",
        "LANG_SET": "✅ Language set: <b>English</b> 🇬🇧",
        "BTN_DOWNLOAD_ENVATO": "Download Envato",
        "BTN_DOWNLOAD_FREEPIK": "Download Freepik",
        "BTN_DOWNLOAD_MOTION": "Download Motion Array",
        "BTN_INFO": "Information",
        "BTN_SUBSCRIBE": "Subscribe 💳",
        "BTN_CANCEL": "❌ Cancel",
        "BTN_SUBSCRIBE_CHANNEL": "Subscribe ✅",
        "BTN_CHECK_SUBSCRIPTION": "Check subscription 🔍",
        "BTN_BUY_SUBSCRIPTION": "💳 Subscribe",
        "BTN_DOWNLOAD_FILE": "Download file 📁",
        "BTN_DOWNLOAD_MORE": "Download more",
        "BTN_BACK_TO_PLANS": "⬅️ Back to plans",
        # Кнопки навигации
        "BTN_BACK": "« Back",
        "BTN_DOWNLOAD": "⬇️ Download",
        "BTN_PAY": "💳 Pay",
        "BTN_BUY_PERPETUAL": "💎 Buy per download",
        "BTN_MY_REFERRALS": "👥 My referrals",
        "BTN_REFERRAL_HISTORY": "💎 Rewards history",
        "BTN_SEPARATOR_OR": "─────────── or ───────────",
        "BTN_LANG_RU": "🇷🇺 Русский",
        "BTN_LANG_EN": "🇬🇧 English",
        # Кнопки тарифов
        "BTN_PLAN_LITE": "Lite · 50 pcs · {price} ₽/mo",
        "BTN_PLAN_STANDARD": "Standard · 150 pcs · {price} ₽/mo ⭐️",
        "BTN_PLAN_PRO": "Pro · 400 pcs · {price} ₽/mo",
        "BTN_PLAN_OTHER": "{name} · {limit} pcs · {price} ₽/mo",
        # Статусы подписки
        "SUB_STATUS_ACTIVE": "✅ Active",
        "SUB_STATUS_INACTIVE": "❌ Inactive",
        "SUB_LIMITS_UNLIMITED": "♾️ Unlimited",
        "SUB_LIMITS_DAILY": "{used}/{limit} (today)",
        # Реферальная система
        "REFERRAL_RECENT_HEADER": "\n💎 <b>Recent rewards:</b>\n",
        "REFERRAL_REWARD_LINE": "{emoji} {trigger}: +{value} downloads\n",
        "REFERRAL_OTHER": "Other",
        "REFERRAL_LIST_TITLE": "<b>Referrals list:</b>\n",
        "REFERRAL_ITEM": "{idx}. ID: <b>{tid}</b>\n   Channel: {ch} | Purchase: {pay} | {date}\n",
        "REFERRAL_AND_MORE": "\n<i>... and {count} more</i>\n",
        "REFERRAL_TRIGGER_NAMES_EXT": {
            "REGISTRATION": "📝 Referral registrations",
            "FIRST_PAYMENT": "💳 First purchases",
            "SUBSCRIPTION": "🔔 Subscriptions",
            "MILESTONE": "🏆 Milestone rewards",
        },
        "REFERRAL_TRIGGER_STATS": "{name}\nCount: {count} | Total: {sum} downloads\n",
        # Описания инвойсов
        "INVOICE_SUBSCRIPTION": "Subscription purchase {name}",
        "INVOICE_PERPETUAL": "Purchase of {quantity} permanent downloads",
        # Ошибки download_service
        "ERR_INSUFFICIENT_CREDITS": "Insufficient credits. Remaining: {remaining}",
        "ERR_SUBSCRIPTION_REQUIRED": "An active subscription is required to download",
        "ERR_AUTH_FAILED": "{provider} authentication error. Contact administrator.",
        "ERR_DOWNLOAD_FAILED": "Failed to download the file",
        "ERR_DOWNLOAD_GENERIC": "Download error: {error}",
        # Ошибки subscription_repository
        "ERR_SUB_EXPIRED": "Subscription expired",
        "ERR_TOTAL_LIMIT": "Total download limit reached",
        "ERR_DAILY_LIMIT": "Daily download limit reached",
        # Команды бота
        "CMD_MENU": "Menu",
        "CMD_ENVATO": "Download Envato",
        "CMD_FREEPIK": "Download Freepik",
        "CMD_MOTION": "Download Motion Array",
        "CMD_INFO": "Information",
        "CMD_PAY": "Subscribe",
        "CMD_REFERRAL": "Referral program",
        "CMD_LANG": "Language",
    }
}
