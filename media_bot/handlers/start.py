from datetime import datetime

from aiogram import Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext

from media_bot.config import ADMIN
from media_bot.handlers.messages import msg
from media_bot.handlers.qr_login import prompt_qr_login
from media_bot.keyboards import get_main_menu_kb
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
async def cmd_start(
    message: types.Message, state: FSMContext, command: CommandObject, lang: str = "ru"
):
    await state.clear()
    telegram_id = message.from_user.id

    # Проверка на заблокированных пользователей
    if telegram_id in BLOCKED_USERS:
        await message.answer(
            msg("MAINTENANCE_MESSAGE", lang),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    args = command.args  # Аргументы после /start (в 3.x так правильно)

    # QR-вход на сайт (deep-link login_<token>) — обрабатываем до реферальной логики
    if args and args.startswith("login_"):
        await prompt_qr_login(message, args.removeprefix("login_"), lang)
        return

    async for session in get_session():
        user_repo = UserRepository(session)
        bonus_repo = BonusRepository(session)

        user = await user_repo.get_by_telegram_id(telegram_id)
        if not user:
            pass
            # Check if this user should be admin
            user_role = UserRole.USER
            if ADMIN and str(telegram_id) == str(ADMIN):
                user_role = UserRole.ADMIN
                logger.info(f"Creating user {telegram_id} with ADMIN role")

            # Создаем пользователя с 0 кредитов (бонусная система добавит)
            user = await user_repo.create(
                tg_id=telegram_id, role=user_role, credits=0, username=lang
            )
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
                    f"REGISTRATION bonus: {registration_bonus.credits_granted} скачиваний для {telegram_id}"
                )
            except Exception as e:
                logger.error(f"Ошибка начисления REGISTRATION бонуса: {e}")
                # Fallback: добавляем скачивания вручную
                user.credits = 3
                await session.commit()

            # Если есть реферальный код — создаем реферальную связь
            if args:
                try:
                    # Находим реферера по коду
                    referrer = await user_repo.get_by_referral_code(args)

                    if referrer:
                        # Устанавливаем связь
                        await user_repo.set_user_referrer(telegram_id, args)

                        # Создаем реферальную награду
                        referral_service = ReferralService(
                            session, user_repo, bonus_repo, bonus_service
                        )

                        (
                            referral_reward,
                            user_bonus,
                        ) = await referral_service.create_referral_registration(
                            referrer_id=referrer.id, referred_id=user.id
                        )
                        logger.info(
                            f"Referral registration created: referrer={referrer.id}, referred={user.id}"
                        )

                        # Отправляем уведомление рефереру о новом реферале
                        if user_bonus:
                            try:
                                # Язык реферера берём из его username
                                ref_lang = (
                                    referrer.username if referrer.username in {"ru", "en"} else "ru"
                                )
                                await message.bot.send_message(
                                    chat_id=referrer.tg_id,
                                    text=msg("REFERRAL_NEW_NOTIFICATION", ref_lang).format(
                                        credits_granted=user_bonus.credits_granted
                                    ),
                                    parse_mode=ParseMode.HTML,
                                )
                                logger.info(
                                    f"Referral bonus notification sent to referrer {referrer.tg_id}: {user_bonus.credits_granted} credits"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to send referral notification to referrer: {e}"
                                )
                    else:
                        logger.warning(f"Referral code {args} not found")
                except Exception as e:
                    logger.error(f"Failed to create referral registration: {e}")
        else:
            # For existing users, check if they should be admin
            if ADMIN and str(telegram_id) == str(ADMIN) and user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                await session.commit()
                logger.info(f"Updated user {telegram_id} to ADMIN role")

    await message.answer(
        msg("WELCOME", lang),
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_kb(lang),
        disable_web_page_preview=True,
    )
