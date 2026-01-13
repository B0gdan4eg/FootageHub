"""
Referral System Handler для MediaBot

Обработчики для реферальной системы:
- Показ реферальной ссылки
- Статистика рефералов
- История наград
"""


from aiogram import Bot, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shared.core.logger import get_logger
from shared.db.repositories import BonusRepository, UserRepository
from shared.db.session import get_session
from shared.services.bonus_service import BonusService
from shared.services.referral_service import ReferralService

logger = get_logger(__name__)
router = Router()


@router.message(Command("referral", "ref"))
async def cmd_referral(message: types.Message, bot: Bot):
    """
    Команда /referral - показывает реферальную ссылку и статистику

    Отображает:
    - Реферальную ссылку пользователя
    - Количество приглашенных рефералов
    - Общую сумму заработанных бонусов
    - Инструкции по использованию
    """
    telegram_id = message.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await message.answer(
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Генерируем реферальный код, если его нет
        if not user.referral_code:
            referral_code = await user_repo.generate_referral_code(user.id)
            logger.info(f"Generated referral code for user {telegram_id}: {referral_code}")
        else:
            referral_code = user.referral_code

        # Получаем информацию о боте для формирования ссылки
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        # Формируем реферальную ссылку
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"

        # Получаем статистику рефералов
        try:
            user_repo = UserRepository(session)
            bonus_repo = BonusRepository(session)
            bonus_service = BonusService(bonus_repo, user_repo)
            referral_service = ReferralService(session, user_repo, bonus_repo, bonus_service)

            stats = await referral_service.get_referral_stats(user_id=user.id)

            # Получаем историю наград
            rewards = await referral_service.get_user_referral_rewards(user_id=user.id, limit=5)

            # Формируем сообщение
            message_text = (
                "🎁 <b>Реферальная программа</b>\n\n"
                f"👥 Приглашено рефералов: <b>{stats['total_referrals']}</b>\n"
                f"💰 Заработано бонусов: <b>{stats['total_credits_earned']} скачиваний</b>\n"
                f"✅ Активных рефералов: <b>{stats['active_referrals']}</b>\n\n"
                "📋 <b>Ваша реферальная ссылка:</b>\n"
                f"<code>{referral_link}</code>\n\n"
                "🎯 <b>Как это работает:</b>\n"
                "1️⃣ Поделитесь ссылкой с друзьями\n"
                "2️⃣ Когда друг регистрируется — вы получаете <b>1 скачивание</b>\n"
                "3️⃣ Когда друг совершает первую покупку — вы получаете <b>5 скачиваний</b>\n\n"
                "🏆 <b>Milestone награды:</b>\n"
                "• 5 рефералов → +5 скачиваний\n"
                "• 10 рефералов → +10 скачиваний\n"
                "• 25 рефералов → +25 скачиваний\n"
                "• 50 рефералов → +50 скачиваний\n"
                "• 100 рефералов → +100 скачиваний\n"
            )

            # Добавляем последние награды, если есть
            if rewards:
                message_text += "\n💎 <b>Последние награды:</b>\n"
                for reward in rewards:
                    trigger_text = {
                        "REGISTRATION": "Регистрация реферала",
                        "FIRST_PAYMENT": "Первая покупка реферала",
                        "SUBSCRIPTION": "Подписка реферала",
                        "MILESTONE": "Milestone награда",
                    }.get(reward.trigger_type, "Другое")

                    status_emoji = "✅" if reward.status == "COMPLETED" else "⏳"
                    message_text += (
                        f"{status_emoji} {trigger_text}: " f"+{reward.credits_earned} скачиваний\n"
                    )

            # Создаем инлайн-клавиатуру
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="ref_my_referrals")],
                    [
                        InlineKeyboardButton(
                            text="💎 История наград", callback_data="ref_rewards_history"
                        )
                    ],
                ]
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            logger.info(f"Referral info sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral stats for user {telegram_id}: {e}", exc_info=True)
            await message.answer(
                "❌ Ошибка при получении статистики рефералов.", parse_mode=ParseMode.HTML
            )


@router.callback_query(lambda c: c.data == "ref_my_referrals")
async def callback_my_referrals(callback: CallbackQuery):
    """
    Callback - показывает список рефералов пользователя

    Отображает:
    - Список всех рефералов с датой регистрации
    - Статус активности
    - Заработанные бонусы от каждого реферала
    """
    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await callback.answer(
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                show_alert=True,
            )
            return

        try:
            user_repo = UserRepository(session)
            bonus_repo = BonusRepository(session)
            bonus_service = BonusService(bonus_repo, user_repo)
            referral_service = ReferralService(session, user_repo, bonus_repo, bonus_service)

            # Получаем статистику
            stats = await referral_service.get_referral_stats(user_id=user.id)

            if stats["total_referrals"] == 0:
                message_text = (
                    "📭 <b>У вас пока нет рефералов</b>\n\n"
                    "Используйте команду /referral чтобы получить вашу реферальную ссылку!"
                )
            else:
                # Формируем сообщение
                message_text = (
                    f"👥 <b>Ваши рефералы ({stats['total_referrals']})</b>\n\n"
                    f"✅ Активных: {stats['active_referrals']}\n"
                    f"💰 Заработано: {stats['total_credits_earned']} скачиваний\n\n"
                )

                # Получаем детальную информацию (первые 10)
                # TODO: Добавить метод get_user_referrals в ReferralService
                message_text += (
                    "ℹ️ Используйте /referral для просмотра детальной статистики "
                    "и вашей реферальной ссылки."
                )

            # Кнопка "Назад"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="« Назад", callback_data="ref_back")]]
            )

            await callback.message.edit_text(
                message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            logger.info(f"Referrals list sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referrals list for user {telegram_id}: {e}")
            await callback.answer("❌ Ошибка при получении списка рефералов.", show_alert=True)

    await callback.answer()


@router.callback_query(lambda c: c.data == "ref_rewards_history")
async def callback_referral_rewards(callback: CallbackQuery):
    """
    Callback - показывает историю реферальных наград

    Отображает:
    - Полную историю всех начисленных реферальных бонусов
    - Типы триггеров (регистрация, покупка, milestone)
    - Даты начисления
    """
    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await callback.answer(
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                show_alert=True,
            )
            return

        try:
            user_repo = UserRepository(session)
            bonus_repo = BonusRepository(session)
            bonus_service = BonusService(bonus_repo, user_repo)
            referral_service = ReferralService(session, user_repo, bonus_repo, bonus_service)

            # Получаем историю наград (все)
            rewards = await referral_service.get_user_referral_rewards(
                user_id=user.id, limit=50  # Показываем последние 50
            )

            if not rewards:
                message_text = (
                    "📭 <b>История наград пуста</b>\n\n"
                    "Приглашайте друзей, чтобы получать бонусы!\n"
                    "Используйте команду /referral для получения реферальной ссылки."
                )
            else:
                # Группируем по типам триггеров
                rewards_by_type = {}
                total_earned = 0

                for reward in rewards:
                    trigger = reward.trigger_type or "OTHER"
                    if trigger not in rewards_by_type:
                        rewards_by_type[trigger] = []
                    rewards_by_type[trigger].append(reward)
                    total_earned += reward.credits_earned

                # Формируем сообщение
                message_text = (
                    f"💎 <b>История реферальных наград</b>\n\n"
                    f"Всего заработано: <b>{total_earned} скачиваний</b>\n"
                    f"Всего наград: <b>{len(rewards)}</b>\n\n"
                )

                # Отображаем по типам
                trigger_names = {
                    "REGISTRATION": "📝 Регистрации рефералов",
                    "FIRST_PAYMENT": "💳 Первые покупки",
                    "SUBSCRIPTION": "🔔 Подписки",
                    "MILESTONE": "🏆 Milestone награды",
                }

                for trigger, trigger_rewards in rewards_by_type.items():
                    trigger_name = trigger_names.get(trigger, "❓ Другое")
                    trigger_sum = sum(r.credits_earned for r in trigger_rewards)

                    message_text += (
                        f"\n{trigger_name}\n"
                        f"Количество: {len(trigger_rewards)} | "
                        f"Сумма: {trigger_sum} скачиваний\n"
                    )

                message_text += (
                    "\n\nℹ️ Используйте /referral для просмотра текущей статистики "
                    "и реферальной ссылки."
                )

            # Кнопка "Назад"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="« Назад", callback_data="ref_back")]]
            )

            await callback.message.edit_text(
                message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            logger.info(f"Referral rewards history sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral rewards for user {telegram_id}: {e}")
            await callback.answer("❌ Ошибка при получении истории наград.", show_alert=True)

    await callback.answer()


@router.callback_query(lambda c: c.data == "ref_back")
async def callback_ref_back(callback: CallbackQuery, bot: Bot):
    """
    Callback - возвращает к главному меню реферальной программы
    """
    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await callback.answer(
                "❌ Пользователь не найден. Используйте /start для регистрации.",
                show_alert=True,
            )
            return

        # Генерируем реферальный код, если его нет
        if not user.referral_code:
            referral_code = await user_repo.generate_referral_code(user.id)
            logger.info(f"Generated referral code for user {telegram_id}: {referral_code}")
        else:
            referral_code = user.referral_code

        # Получаем информацию о боте для формирования ссылки
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        # Формируем реферальную ссылку
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"

        # Получаем статистику рефералов
        try:
            user_repo = UserRepository(session)
            bonus_repo = BonusRepository(session)
            bonus_service = BonusService(bonus_repo, user_repo)
            referral_service = ReferralService(session, user_repo, bonus_repo, bonus_service)

            stats = await referral_service.get_referral_stats(user_id=user.id)

            # Получаем историю наград
            rewards = await referral_service.get_user_referral_rewards(user_id=user.id, limit=5)

            # Формируем сообщение
            message_text = (
                "🎁 <b>Реферальная программа</b>\n\n"
                f"👥 Приглашено рефералов: <b>{stats['total_referrals']}</b>\n"
                f"💰 Заработано бонусов: <b>{stats['total_credits_earned']} скачиваний</b>\n"
                f"✅ Активных рефералов: <b>{stats['active_referrals']}</b>\n\n"
                "📋 <b>Ваша реферальная ссылка:</b>\n"
                f"<code>{referral_link}</code>\n\n"
                "🎯 <b>Как это работает:</b>\n"
                "1️⃣ Поделитесь ссылкой с друзьями\n"
                "2️⃣ Когда друг регистрируется — вы получаете <b>1 скачивание</b>\n"
                "3️⃣ Когда друг совершает первую покупку — вы получаете <b>5 скачиваний</b>\n\n"
                "🏆 <b>Milestone награды:</b>\n"
                "• 5 рефералов → +5 скачиваний\n"
                "• 10 рефералов → +10 скачиваний\n"
                "• 25 рефералов → +25 скачиваний\n"
                "• 50 рефералов → +50 скачиваний\n"
                "• 100 рефералов → +100 скачиваний\n"
            )

            # Добавляем последние награды, если есть
            if rewards:
                message_text += "\n💎 <b>Последние награды:</b>\n"
                for reward in rewards:
                    trigger_text = {
                        "REGISTRATION": "Регистрация реферала",
                        "FIRST_PAYMENT": "Первая покупка реферала",
                        "SUBSCRIPTION": "Подписка реферала",
                        "MILESTONE": "Milestone награда",
                    }.get(reward.trigger_type, "Другое")

                    status_emoji = "✅" if reward.status == "COMPLETED" else "⏳"
                    message_text += (
                        f"{status_emoji} {trigger_text}: " f"+{reward.credits_earned} скачиваний\n"
                    )

            # Создаем инлайн-клавиатуру
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="ref_my_referrals")],
                    [
                        InlineKeyboardButton(
                            text="💎 История наград", callback_data="ref_rewards_history"
                        )
                    ],
                ]
            )

            await callback.message.edit_text(
                message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            logger.info(f"Returned to referral main menu for user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to return to referral menu for user {telegram_id}: {e}")
            await callback.answer("❌ Ошибка при возврате в меню.", show_alert=True)

    await callback.answer()
