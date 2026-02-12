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

from media_bot.handlers.messages import msg
from shared.core.logger import get_logger
from shared.db.repositories import BonusRepository, UserRepository
from shared.db.session import get_session
from shared.services.bonus_service import BonusService
from shared.services.referral_service import ReferralService

logger = get_logger(__name__)
router = Router()


@router.message(Command("referral", "ref"))
async def cmd_referral(message: types.Message, bot: Bot, lang: str = "ru"):
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
                msg("REFERRAL_USER_NOT_FOUND", lang),
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
            message_text = msg("REFERRAL_MAIN", lang).format(
                total_referrals=stats['total_referrals'],
                total_credits_earned=stats['total_credits_earned'],
                active_referrals=stats['active_referrals'],
                referral_link=referral_link,
            ) + msg("REFERRAL_MILESTONES", lang)

            # Добавляем последние награды, если есть
            if rewards:
                trigger_names = msg("REFERRAL_TRIGGER_NAMES", lang)
                message_text += msg("REFERRAL_RECENT_HEADER", lang)
                for reward in rewards:
                    trigger_text = trigger_names.get(reward.trigger_type, msg("REFERRAL_OTHER", lang))

                    status_emoji = "✅" if reward.status == "COMPLETED" else "⏳"
                    message_text += msg("REFERRAL_REWARD_LINE", lang).format(
                        emoji=status_emoji, trigger=trigger_text, value=reward.reward_value
                    )

            # Создаем инлайн-клавиатуру
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=msg("BTN_MY_REFERRALS", lang), callback_data="ref_my_referrals")],
                    [
                        InlineKeyboardButton(
                            text=msg("BTN_REFERRAL_HISTORY", lang), callback_data="ref_rewards_history"
                        )
                    ],
                ]
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            logger.info(f"Referral info sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral stats for user {telegram_id}: {e}", exc_info=True)
            await message.answer(
                msg("REFERRAL_ERROR_STATS", lang), parse_mode=ParseMode.HTML
            )


@router.callback_query(lambda c: c.data == "ref_my_referrals")
async def callback_my_referrals(callback: CallbackQuery, lang: str = "ru"):
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
                msg("REFERRAL_USER_NOT_FOUND", lang),
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
                message_text = msg("REFERRAL_NO_REFERRALS", lang)
            else:
                # Получаем детальную информацию о рефералах
                referrals_detailed = await referral_service.get_user_referrals_detailed(
                    user_id=user.id, limit=20
                )

                # Формируем сообщение
                message_text = msg("REFERRAL_LIST_HEADER", lang).format(
                    count=stats['total_referrals'],
                    active_referrals=stats['active_referrals'],
                    total_credits_earned=stats['total_credits_earned'],
                )

                if referrals_detailed:
                    message_text += msg("REFERRAL_LIST_TITLE", lang)
                    for idx, ref in enumerate(referrals_detailed[:10], 1):
                        # Эмодзи для статусов
                        channel_emoji = "✅" if ref["has_channel_subscription"] else "❌"
                        payment_emoji = "✅" if ref["has_first_payment"] else "❌"

                        # Формат даты
                        reg_date = ref["registered_at"].strftime("%d.%m.%Y")

                        message_text += msg("REFERRAL_ITEM", lang).format(
                            idx=idx, tid=ref['telegram_id'],
                            ch=channel_emoji, pay=payment_emoji, date=reg_date
                        )

                    if len(referrals_detailed) > 10:
                        message_text += msg("REFERRAL_AND_MORE", lang).format(
                            count=len(referrals_detailed) - 10
                        )

            # Кнопка "Назад"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=msg("BTN_BACK", lang), callback_data="ref_back")]]
            )

            await callback.message.edit_text(
                message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            logger.info(f"Referrals list sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referrals list for user {telegram_id}: {e}", exc_info=True)
            await callback.answer(msg("REFERRAL_ERROR_LIST", lang), show_alert=True)

    await callback.answer()


@router.callback_query(lambda c: c.data == "ref_rewards_history")
async def callback_referral_rewards(callback: CallbackQuery, lang: str = "ru"):
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
                msg("REFERRAL_USER_NOT_FOUND", lang),
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
                message_text = msg("REFERRAL_NO_REWARDS", lang)
            else:
                # Группируем по типам триггеров
                rewards_by_type = {}
                total_earned = 0

                for reward in rewards:
                    trigger = reward.trigger_type or "OTHER"
                    if trigger not in rewards_by_type:
                        rewards_by_type[trigger] = []
                    rewards_by_type[trigger].append(reward)
                    total_earned += reward.reward_value

                # Формируем сообщение
                message_text = msg("REFERRAL_REWARDS_HEADER", lang).format(
                    total_earned=total_earned,
                    total_rewards=len(rewards),
                )

                # Отображаем по типам
                trigger_names = msg("REFERRAL_TRIGGER_NAMES_EXT", lang)

                for trigger, trigger_rewards in rewards_by_type.items():
                    trigger_name = trigger_names.get(trigger, "❓ " + msg("REFERRAL_OTHER", lang))
                    trigger_sum = sum(r.reward_value for r in trigger_rewards)

                    message_text += "\n" + msg("REFERRAL_TRIGGER_STATS", lang).format(
                        name=trigger_name, count=len(trigger_rewards), sum=trigger_sum
                    )

                message_text += msg("REFERRAL_REWARDS_FOOTER", lang)

            # Кнопка "Назад"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=msg("BTN_BACK", lang), callback_data="ref_back")]]
            )

            await callback.message.edit_text(
                message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            logger.info(f"Referral rewards history sent to user {telegram_id}")

        except Exception as e:
            logger.error(f"Failed to get referral rewards for user {telegram_id}: {e}")
            await callback.answer(msg("REFERRAL_ERROR_REWARDS", lang), show_alert=True)

    await callback.answer()


@router.callback_query(lambda c: c.data == "ref_back")
async def callback_ref_back(callback: CallbackQuery, bot: Bot, lang: str = "ru"):
    """
    Callback - возвращает к главному меню реферальной программы
    """
    telegram_id = callback.from_user.id

    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(telegram_id)

        if not user:
            await callback.answer(
                msg("REFERRAL_USER_NOT_FOUND", lang),
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
            message_text = msg("REFERRAL_MAIN", lang).format(
                total_referrals=stats['total_referrals'],
                total_credits_earned=stats['total_credits_earned'],
                active_referrals=stats['active_referrals'],
                referral_link=referral_link,
            ) + msg("REFERRAL_MILESTONES", lang)

            # Добавляем последние награды, если есть
            if rewards:
                trigger_names = msg("REFERRAL_TRIGGER_NAMES", lang)
                message_text += msg("REFERRAL_RECENT_HEADER", lang)
                for reward in rewards:
                    trigger_text = trigger_names.get(reward.trigger_type, msg("REFERRAL_OTHER", lang))

                    status_emoji = "✅" if reward.status == "COMPLETED" else "⏳"
                    message_text += msg("REFERRAL_REWARD_LINE", lang).format(
                        emoji=status_emoji, trigger=trigger_text, value=reward.reward_value
                    )

            # Создаем инлайн-клавиатуру
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=msg("BTN_MY_REFERRALS", lang), callback_data="ref_my_referrals")],
                    [
                        InlineKeyboardButton(
                            text=msg("BTN_REFERRAL_HISTORY", lang), callback_data="ref_rewards_history"
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
            await callback.answer(msg("REFERRAL_ERROR_MENU", lang), show_alert=True)

    await callback.answer()
