import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from media_bot.handlers.messages import (
    ALREADY_HAS_SUBSCRIPTION,
    SUB_PAYMENT_DAILY,
    SUB_PAYMENT_MONTHLY_50,
    SUB_PAYMENT_MONTHLY_150,
    SUB_PAYMENT_MONTHLY_400,
)
from media_bot.utils.price_loader import load_subscription_plans
from media_bot.webpay_utils import get_webpay_api
from shared.db.repositories import PaymentRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session
from shared.utils import dict_to_namespace

logger = logging.getLogger(__name__)
router = Router()


async def send_price_menu(message_or_callback):
    """Отправляет меню с подписками."""
    try:
        plans = load_subscription_plans()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load subscription plans: {e}")
        await message_or_callback.answer("❌ Ошибка загрузки списка подписок.")
        return

    data = dict_to_namespace({"subscription_plans": plans})
    keyboard_buttons = []

    # Добавляем подписки
    if hasattr(data, "subscription_plans"):
        for key, item in data.subscription_plans.__dict__.items():
            # Формируем описание лимитов
            limits_text = ""
            if item.total_limit:
                limits_text = f"{item.total_limit} на месяц"
            if item.daily_limit:
                limits_text = f"{item.daily_limit}/день"

            callback_data = f"select_plan_{key}"
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{item.name} ({limits_text}) — {item.price} RUB",
                        callback_data=callback_data,
                    )
                ]
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Для CallbackQuery редактируем сообщение, для Message создаем новое
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text("💳 Выберите подписку:", reply_markup=keyboard)
        await message_or_callback.answer()
    else:
        await message_or_callback.answer("💳 Выберите подписку:", reply_markup=keyboard)


# Хендлер для callback "buy_subscription"
@router.message(Command("pay"))
@router.message(F.text == "Оформить подписку 💳")
async def choose_plan_message(message: types.Message, state):
    await state.clear()
    await send_price_menu(message)


@router.callback_query(F.data == "buy_subscription")
async def choose_plan_callback(callback_query: types.CallbackQuery, state):
    await state.clear()
    await send_price_menu(callback_query)


@router.callback_query(F.data.startswith("select_plan_"))
async def show_plan_details(callback_query: types.CallbackQuery):
    """Показывает детали выбранной подписки с описанием всех тарифов."""
    plan_key = callback_query.data.replace("select_plan_", "")

    # Загружаем данные плана
    try:
        plans = load_subscription_plans()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load subscription plans: {e}")
        await callback_query.message.answer("❌ Ошибка конфигурации. Обратитесь к администратору.")
        await callback_query.answer()
        return

    data = dict_to_namespace({"subscription_plans": plans})
    plan = getattr(data.subscription_plans, plan_key, None)

    if not plan:
        logger.error(f"Plan not found for key: {plan_key}")
        await callback_query.message.answer("❌ Неверный тариф подписки. Попробуйте снова.")
        await callback_query.answer()
        return

    # Выбираем правильное сообщение в зависимости от плана
    if plan_key == "monthly_50":
        message_template = SUB_PAYMENT_MONTHLY_50
    elif plan_key == "monthly_150":
        message_template = SUB_PAYMENT_MONTHLY_150
    elif plan_key == "monthly_400":
        message_template = SUB_PAYMENT_MONTHLY_400
    elif plan_key == "daily_30":
        message_template = SUB_PAYMENT_DAILY
    else:
        message_template = SUB_PAYMENT_MONTHLY_150  # По умолчанию

    # Проверяем наличие активной подписки
    user_id = callback_query.from_user.id
    async for session in get_session():
        # Получаем пользователя из БД
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        if not user:
            logger.error(f"User not found in DB: {user_id}")
            await callback_query.message.answer("❌ Пользователь не найден. Начните с /start")
            await callback_query.answer()
            return

        # Проверяем активную подписку
        subscription_repo = SubscriptionRepository(session)
        active_subscription = await subscription_repo.get_active_by_user_id(user.id)
        if active_subscription:
            # У пользователя уже есть активная подписка
            subscription_type_name = active_subscription.subscription_type.value
            end_date = active_subscription.end_date.strftime("%d.%m.%Y %H:%M")

            message = ALREADY_HAS_SUBSCRIPTION.format(
                subscription_type=subscription_type_name, end_date=end_date, credits=user.credits
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_subscription")]
                ]
            )

            logger.warning(
                f"User {user_id} already has active subscription: {subscription_type_name}"
            )
            await callback_query.message.edit_text(
                message, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
            )
            await callback_query.answer()
            return

    # Показываем детали подписки
    description = message_template.format(_price=plan.price)

    # Создаем инвойс сразу
    logger.info(
        f"Creating invoice for user_id: {user_id}, amount: {plan.price}, plan_key: {plan_key}"
    )

    try:
        # Генерируем уникальный ID заказа формата: USER_{user_id}_{plan_key}_{uuid}
        order_id = f"USER_{user_id}_{plan_key}_{uuid.uuid4().hex[:8]}"

        # URL для вебхуков
        base_url = "https://footage.com.by"
        return_url = f"{base_url}/payment/success"
        cancel_url = f"{base_url}/payment/cancel"
        notify_url = f"{base_url}/api/webpay/webhook"

        # Создаем счет через WebPay
        webpay_api = get_webpay_api()
        result = await webpay_api.create_invoice(
            order_id=order_id,
            amount=plan.price,
            description=f"Покупка подписки {plan.name}",
            return_url=return_url,
            cancel_url=cancel_url,
            notify_url=notify_url,
        )

        pay_url = result.get("invoiceUrl")
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
        await callback_query.answer()
        return

    if not pay_url or not order_id:
        logger.error("Invoice creation returned empty values")
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
        await callback_query.answer()
        return

    logger.info("Saving payment to DB")
    # Сохраняем платеж в БД
    async for session in get_session():
        # Получаем пользователя из БД
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)
        if not user:
            logger.error(f"User not found in DB: {user_id}")
            await callback_query.message.answer("❌ Пользователь не найден. Начните с /start")
            await callback_query.answer()
            return

        logger.debug(f"User found: {user.id}, creating payment")
        try:
            payment_repo = PaymentRepository(session)
            await payment_repo.create_payment(
                user_id=user.id,
                amount=plan.price,
                currency="RUB",
                plan_key=plan_key,
                invoice_id=order_id,
            )
            logger.info("Payment created successfully")
        except Exception as e:
            logger.error(f"Error creating payment in DB: {e}", exc_info=True)
            import traceback

            traceback.print_exc()
            await callback_query.message.answer(
                "❌ Ошибка при сохранении платежа. Попробуйте позже."
            )
            await callback_query.answer()
            return

    # Кнопка для оплаты
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="buy_subscription")],
        ]
    )

    logger.debug("Editing message with payment details")
    try:
        await callback_query.message.edit_text(
            description, reply_markup=keyboard, parse_mode="HTML"
        )
        await callback_query.answer()
        logger.info("Message edited successfully")
    except Exception as e:
        logger.error(f"Error editing message: {e}")
