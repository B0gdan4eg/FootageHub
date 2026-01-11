"""
Referral System Handler для MediaBot

Обработчики для реферальной системы:
- Показ реферальной ссылки
- Статистика рефералов
- История наград
"""

from typing import List

from aiogram import Bot, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import Command

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
                f"💰 Заработано бонусов: <b>{stats['total_credits_earned']} кредитов</b>\n"
                f"✅ Активных рефералов: <b>{stats['active_referrals']}</b>\n\n"
                "📋 <b>Ваша реферальная ссылка:</b>\n"
                f"<code>{referral_link}</code>\n\n"
                "🎯 <b>Как это работает:</b>\n"
                "1️⃣ Поделитесь ссылкой с друзьями\n"
                "2️⃣ Когда друг регистрируется — вы получаете <b>1 кредит</b>\n"
                "3️⃣ Когда друг совершает первую покупку — вы получаете <b>5 кредитов</b>\n\n"
                "🏆 <b>Milestone награды:</b>\n"
                "• 5 рефералов → +5 кредитов\n"
                "• 10 рефералов → +10 кредитов\n"
                "• 25 рефералов → +25 кредитов\n"
                "• 50 рефералов → +50 кредитов\n"
                "• 100 рефералов → +100 кредитов\n"
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
                        f"{status_emoji} {trigger_text}: " f"+{reward.credits_earned} кредитов\n"
                    )

            await message.answer(message_text, parse_mode=ParseMode.HTML)
            logger.info(f"Referral info sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral stats for user {telegram_id}: {e}", exc_info=True)
            await message.answer(
                "❌ Ошибка при получении статистики рефералов.", parse_mode=ParseMode.HTML
            )


@router.message(Command("my_referrals"))
async def cmd_my_referrals(message: types.Message):
    """
    Команда /my_referrals - показывает список рефералов пользователя

    Отображает:
    - Список всех рефералов с датой регистрации
    - Статус активности
    - Заработанные бонусы от каждого реферала
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

        try:
            user_repo = UserRepository(session)
            bonus_repo = BonusRepository(session)
            bonus_service = BonusService(bonus_repo, user_repo)
            referral_service = ReferralService(session, user_repo, bonus_repo, bonus_service)

            # Получаем статистику
            stats = await referral_service.get_referral_stats(user_id=user.id)

            if stats["total_referrals"] == 0:
                await message.answer(
                    "📭 <b>У вас пока нет рефералов</b>\n\n"
                    "Используйте команду /referral чтобы получить вашу реферальную ссылку!",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Формируем сообщение
            message_text = (
                f"👥 <b>Ваши рефералы ({stats['total_referrals']})</b>\n\n"
                f"✅ Активных: {stats['active_referrals']}\n"
                f"💰 Заработано: {stats['total_credits_earned']} кредитов\n\n"
            )

            # Получаем детальную информацию (первые 10)
            # TODO: Добавить метод get_user_referrals в ReferralService
            message_text += (
                "ℹ️ Используйте /referral для просмотра детальной статистики "
                "и вашей реферальной ссылки."
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML)
            logger.info(f"Referrals list sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referrals list for user {telegram_id}: {e}")
            await message.answer(
                "❌ Ошибка при получении списка рефералов.", parse_mode=ParseMode.HTML
            )


@router.message(Command("referral_rewards"))
async def cmd_referral_rewards(message: types.Message):
    """
    Команда /referral_rewards - показывает историю реферальных наград

    Отображает:
    - Полную историю всех начисленных реферальных бонусов
    - Типы триггеров (регистрация, покупка, milestone)
    - Даты начисления
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
                await message.answer(
                    "📭 <b>История наград пуста</b>\n\n"
                    "Приглашайте друзей, чтобы получать бонусы!\n"
                    "Используйте команду /referral для получения реферальной ссылки.",
                    parse_mode=ParseMode.HTML,
                )
                return

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
                f"Всего заработано: <b>{total_earned} кредитов</b>\n"
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
                    f"Сумма: {trigger_sum} кредитов\n"
                )

            message_text += (
                "\n\nℹ️ Используйте /referral для просмотра текущей статистики "
                "и реферальной ссылки."
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML)
            logger.info(f"Referral rewards history sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral rewards for user {telegram_id}: {e}")
            await message.answer(
                "❌ Ошибка при получении истории наград.", parse_mode=ParseMode.HTML
            )
