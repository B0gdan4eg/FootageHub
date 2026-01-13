from datetime import datetime

from aiogram import Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext

from media_bot.config import ADMIN
from media_bot.handlers.messages import MAINTENANCE_MESSAGE, WELCOME
from media_bot.keyboards import main_menu_kb
from shared.core.logger import get_logger
from shared.db.models import UserRole
from shared.db.repositories.bonus_repository import BonusRepository
from shared.db.repositories.user_repository import UserRepository
from shared.db.session import get_session
from shared.services.bonus_service import BonusService
from shared.services.referral_service import ReferralService

logger = get_logger(__name__)

router = Router()

# Пользователи, для которых показываем сообщение о технических работах
BLOCKED_USERS = {472785197, 289997391, 6269570979}


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    await state.clear()
    telegram_id = message.from_user.id

    # Проверка на заблокированных пользователей
    if telegram_id in BLOCKED_USERS:
        await message.answer(
            MAINTENANCE_MESSAGE, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    args = command.args  # Аргументы после /start (в 3.x так правильно)

    is_new_user = False
    async for session in get_session():
        user_repo = UserRepository(session)
        bonus_repo = BonusRepository(session)

        user = await user_repo.get_by_telegram_id(telegram_id)
        if not user:
            is_new_user = True
            # Check if this user should be admin
            user_role = UserRole.USER
            if ADMIN and str(telegram_id) == str(ADMIN):
                user_role = UserRole.ADMIN
                logger.info(f"Creating user {telegram_id} with ADMIN role")

            # Создаем пользователя с 0 кредитов (бонусная система добавит)
            user = await user_repo.create(tg_id=telegram_id, role=user_role, credits=0)
            await session.flush()
            await session.refresh(user)

            # Применяем бонус за регистрацию
            try:
                bonus_service = BonusService(bonus_repo, user_repo)
                registration_bonus = await bonus_service.claim_bonus(
                    user_id=user.id,
                    bonus_code="REGISTRATION",
                    metadata={"registered_at": datetime.utcnow().isoformat()},
                )
                logger.info(
                    f"REGISTRATION bonus: {registration_bonus.credits_granted} кредитов для {telegram_id}"
                )
            except Exception as e:
                logger.error(f"Ошибка начисления REGISTRATION бонуса: {e}")
                # Fallback: добавляем кредиты вручную
                user.credits = 3
                await session.commit()

            # Если есть реферальный код — создаем реферальную связь
            if args:
                await user_repo.set_user_referrer(telegram_id, args)

                # Начисляем бонус рефереру через ReferralService
                try:
                    referral_service = ReferralService(
                        session, user_repo, bonus_repo, bonus_service
                    )

                    # Получаем нового пользователя
                    new_user = await user_repo.get_by_telegram_id(telegram_id)
                    if new_user:
                        await referral_service.create_referral_registration(
                            referred_user_id=new_user.id, referral_code=args
                        )
                        logger.info(f"Referral registration created for user {telegram_id}")
                except Exception as e:
                    logger.error(f"Failed to create referral registration: {e}")
        else:
            # For existing users, check if they should be admin
            if ADMIN and str(telegram_id) == str(ADMIN) and user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                await session.commit()
                logger.info(f"Updated user {telegram_id} to ADMIN role")

        # Начисляем FIRST_LOGIN бонус для новых пользователей
        if is_new_user:
            try:
                bonus_service = BonusService(bonus_repo, user_repo)

                user = await user_repo.get_by_telegram_id(telegram_id)
                if user:
                    # Проверяем, можно ли начислить бонус
                    can_claim = await bonus_service.can_claim_bonus(
                        user_id=user.id, bonus_code="FIRST_LOGIN"
                    )

                    if can_claim:
                        bonus = await bonus_service.claim_bonus(
                            user_id=user.id, bonus_code="FIRST_LOGIN"
                        )

                        # Отправляем уведомление о бонусе
                        bonus_message = (
                            f"🎁 <b>Приветственный бонус!</b>\n\n"
                            f"Вы получили {bonus.credits_granted} кредитов для загрузок!\n\n"
                            f"Используйте их для загрузки медиа контента."
                        )
                        await message.answer(bonus_message, parse_mode=ParseMode.HTML)
                        logger.info(f"FIRST_LOGIN bonus claimed by user {telegram_id}")
            except Exception as e:
                logger.error(f"Failed to claim FIRST_LOGIN bonus: {e}")

    await message.answer(
        WELCOME.format(name=message.from_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
        disable_web_page_preview=True,
    )
