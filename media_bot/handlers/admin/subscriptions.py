"""
Subscription management functionality for admin panel.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from media_bot.handlers.admin.core import is_admin
from media_bot.keyboards import admin_menu_kb, get_cancel_kb
from media_bot.state import AdminStates
from shared.db.models import ServiceType, Subscription, SubscriptionType, User
from shared.db.repositories import SubscriptionRepository, UserRepository
from shared.db.session import get_session

# Create a separate router for subscription functions
router = Router()


@router.message(F.text == "🎁 Выдать подписку")
async def give_subscription_start(message: types.Message, state: FSMContext):
    """Запрос ID пользователя для выдачи подписки"""
    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_subscription_user_id)
    await message.answer(
        "🆔 <b>Выдача подписки</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите выдать подписку:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_subscription_user_id)
async def receive_subscription_user_id(message: types.Message, state: FSMContext):
    """Получение ID пользователя и показ выбора плана"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Выдача подписки отменена", reply_markup=admin_menu_kb)
        return

    user_id_text = message.text.strip()

    if not user_id_text.isdigit():
        return await message.answer("❌ ID должен быть числом. Попробуйте снова.")

    user_id = int(user_id_text)

    # Проверяем существование пользователя
    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        if not user:
            return await message.answer(f"❌ Пользователь с ID {user_id} не найден в базе данных.")

    # Сохраняем ID в state
    await state.update_data(subscription_user_id=user_id)

    # Показываем выбор плана подписки
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Monthly 50 (30 дней)", callback_data="sub_plan_monthly_50"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Monthly 150 (30 дней)", callback_data="sub_plan_monthly_150"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Monthly 400 (30 дней)", callback_data="sub_plan_monthly_400"
                )
            ],
            [InlineKeyboardButton(text="⚡ Daily 30 (30 дней)", callback_data="sub_plan_daily_30")],
            [
                InlineKeyboardButton(
                    text="♾️ Unlimited (30 дней)", callback_data="sub_plan_unlimited"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="sub_plan_cancel")],
        ]
    )

    await message.answer(
        f"✅ Пользователь найден: <b>{user_id}</b>\n\n" f"Выберите план подписки:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await state.set_state(AdminStates.waiting_for_subscription_plan)


@router.callback_query(AdminStates.waiting_for_subscription_plan, F.data.startswith("sub_plan_"))
async def create_subscription_for_user(callback: types.CallbackQuery, state: FSMContext):
    """Создание подписки для пользователя"""
    if callback.data == "sub_plan_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Выдача подписки отменена.")
        await callback.answer()
        return

    # Получаем сохраненный ID пользователя
    data = await state.get_data()
    user_id = data.get("subscription_user_id")

    if not user_id:
        await callback.message.edit_text("❌ Ошибка: ID пользователя не найден. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    # Определяем параметры подписки по выбранному плану
    plan_key = callback.data.replace("sub_plan_", "")

    if plan_key == "monthly_50":
        subscription_type = SubscriptionType.MONTHLY_50
        total_limit = 50
        daily_limit = None
        plan_name = "Lite"
    elif plan_key == "monthly_150":
        subscription_type = SubscriptionType.MONTHLY_150
        total_limit = 150
        daily_limit = None
        plan_name = "Standard"
    elif plan_key == "monthly_400":
        subscription_type = SubscriptionType.MONTHLY_400
        total_limit = 400
        daily_limit = None
        plan_name = "Pro"
    elif plan_key == "daily_30":
        subscription_type = SubscriptionType.DAILY_30
        total_limit = None
        daily_limit = 30
        plan_name = "Daily 30"
    elif plan_key == "unlimited":
        subscription_type = SubscriptionType.UNLIMITED
        total_limit = None
        daily_limit = None
        plan_name = "Unlimited ♾️"
    else:
        await callback.message.edit_text("❌ Неизвестный план подписки.")
        await state.clear()
        await callback.answer()
        return

    # Создаем подписку
    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        if not user:
            await callback.message.edit_text(f"❌ Пользователь с ID {user_id} не найден.")
            await state.clear()
            await callback.answer()
            return

        try:
            subscription_repo = SubscriptionRepository(session)
            subscription = await subscription_repo.create_subscription_with_credits(
                user_id=user.id,
                subscription_type=subscription_type,
                service_type=ServiceType.ALL,
                total_limit=total_limit,
                daily_limit=daily_limit,
                days=30,
                payment_id=None,  # Подписка выдана администратором
            )

            limit_text = (
                "♾️ Безлимит"
                if plan_key == "unlimited"
                else (f"{total_limit} скачиваний" if total_limit else f"{daily_limit}/день")
            )

            await callback.message.edit_text(
                f"✅ <b>Подписка успешно выдана!</b>\n\n"
                f"👤 Пользователь: <code>{user_id}</code>\n"
                f"📦 План: <b>{plan_name}</b>\n"
                f"📊 Лимит: {limit_text}\n"
                f"📅 Срок: 30 дней\n"
                f"🆔 ID подписки: <code>{subscription.id}</code>",
                parse_mode="HTML",
            )

            # Опционально: уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"🎁 <b>Вам выдана подписка!</b>\n\n"
                    f"📦 План: <b>{plan_name}</b>\n"
                    f"📊 Лимит: {limit_text}\n"
                    f"📅 Срок действия: 30 дней\n\n"
                    f"Приятного использования! 🚀",
                    parse_mode="HTML",
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send notification to user {user_id}: {e}")

        except Exception as e:
            await callback.message.edit_text(f"❌ Ошибка при создании подписки: {e}")
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"Error creating subscription: {e}", exc_info=True)
            traceback.print_exc()

    await state.clear()
    await callback.answer()


@router.message(F.text == "🗑️ Удалить подписку")
async def delete_subscription_start(message: types.Message, state: FSMContext):
    """Начать процесс удаления подписки по ID"""
    if not await is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_subscription_delete_id)
    await message.answer(
        "🗑️ <b>Удаление подписки</b>\n\n"
        "Введите Telegram ID пользователя, у которого нужно удалить подписку:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_subscription_delete_id)
async def delete_subscription_execute(message: types.Message, state: FSMContext):
    """Удалить подписку пользователя"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Удаление подписки отменено", reply_markup=admin_menu_kb)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID должен быть числом. Попробуйте снова.")
        return

    async for session in get_session():
        # Find user
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь с ID {user_id} не найден", reply_markup=admin_menu_kb
            )
            await state.clear()
            return

        # Find and delete subscription
        result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
        subscription = result.scalar_one_or_none()

        if not subscription:
            await message.answer(
                f"❌ У пользователя {user_id} нет активной подписки", reply_markup=admin_menu_kb
            )
            await state.clear()
            return

        # Delete subscription
        await session.delete(subscription)
        await session.commit()

    await message.answer(
        f"✅ Подписка пользователя {user_id} (@{user.username or 'Нет username'}) успешно удалена",
        reply_markup=admin_menu_kb,
        parse_mode="HTML",
    )
    await state.clear()


# Keep old callback handlers for compatibility
@router.callback_query(lambda c: c.data == "admin_delete_all_subscriptions")
async def confirm_delete_all_subscriptions(callback: types.CallbackQuery):
    """Deprecated - kept for compatibility"""
    await callback.answer("Эта функция больше не используется", show_alert=True)


@router.callback_query(lambda c: c.data == "admin_confirm_delete_subscriptions")
async def delete_all_subs_confirmed(callback: types.CallbackQuery):
    """Подтверждение удаления всех подписок"""
    from media_bot.handlers.admin.core import is_admin

    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    try:
        async for session in get_session():
            subscription_repo = SubscriptionRepository(session)
            deleted_count = await subscription_repo.delete_all_subscriptions()

        await callback.message.edit_text(
            f"✅ <b>Все подписки удалены!</b>\n\n" f"🗑️ Удалено подписок: <b>{deleted_count}</b>",
            parse_mode="HTML",
        )
        await callback.answer("✅ Подписки удалены!")
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении подписок:</b>\n\n" f"<code>{e}</code>", parse_mode="HTML"
        )
        await callback.answer("❌ Ошибка!")
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting subscriptions: {e}", exc_info=True)
        traceback.print_exc()


@router.callback_query(lambda c: c.data == "admin_cancel_delete_subscriptions")
async def cancel_delete_subscriptions(callback: types.CallbackQuery, state):
    """Отмена удаления подписок"""
    await state.clear()
    await callback.message.edit_text("❌ Удаление подписок отменено.")
    await callback.answer()
