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
    """Отправляет меню с подписками и несгораемыми кредитами."""

    # Получить user_id
    if isinstance(message_or_callback, types.CallbackQuery):
        user_id = message_or_callback.from_user.id
    else:
        user_id = message_or_callback.from_user.id

    # Проверить активную подписку
    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)

        if not user:
            if isinstance(message_or_callback, types.CallbackQuery):
                await message_or_callback.message.answer("❌ Пользователь не найден")
                await message_or_callback.answer()
            else:
                await message_or_callback.answer("❌ Пользователь не найден")
            return

        subscription_repo = SubscriptionRepository(session)
        active_subscription = await subscription_repo.get_active_by_user_id(user.id)

        # ВЕТКА 1: У пользователя есть активная подписка
        if active_subscription:
            keyboard_buttons = [
                [
                    InlineKeyboardButton(
                        text="💎 Купить поштучно", callback_data="buy_perpetual_credits"
                    )
                ]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

            subscription_type_name = active_subscription.subscription_type.value
            end_date = active_subscription.end_date.strftime("%d.%m.%Y %H:%M")

            message_text = f"""✅ <b>У вас активная подписка!</b>

📋 <b>Ваша подписка:</b>
- Тариф: {subscription_type_name}
- Действует до: {end_date}
- Доступно: {user.credits} загрузок

⚠️ <b>Новую подписку нельзя купить, пока действует текущая.</b>

💎 Но вы можете докупить загрузки поштучно — они не сгорают и всегда доступны!

❓ Есть вопросы? Напишите в <a href="https://t.me/FootageHub_support">поддержку</a>
"""

            if isinstance(message_or_callback, types.CallbackQuery):
                await message_or_callback.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                await message_or_callback.answer()
            else:
                await message_or_callback.answer(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            return

    # ВЕТКА 2: У пользователя НЕТ активной подписки - показываем всё
    try:
        plans = load_subscription_plans()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load subscription plans: {e}")
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.answer("❌ Ошибка загрузки списка подписок.")
            await message_or_callback.answer()
        else:
            await message_or_callback.answer("❌ Ошибка загрузки списка подписок.")
        return

    data = dict_to_namespace({"subscription_plans": plans})
    keyboard_buttons = []

    # Добавляем подписки с новым форматом
    if hasattr(data, "subscription_plans"):
        # Порядок отображения планов
        plan_order = ["monthly_50", "monthly_150", "monthly_400"]

        for key in plan_order:
            if not hasattr(data.subscription_plans, key):
                continue

            item = getattr(data.subscription_plans, key)

            # Формируем текст кнопки
            if key == "monthly_50":
                button_text = f"Lite · 50 шт · {item.price} ₽/мес"
            elif key == "monthly_150":
                button_text = f"Standard · 150 шт · {item.price} ₽/мес ⭐️"
            elif key == "monthly_400":
                button_text = f"Pro · 400 шт · {item.price} ₽/мес"
            else:
                # Для других планов (если будут)
                button_text = f"{item.name} · {item.total_limit} шт · {item.price} ₽/мес"

            callback_data = f"select_plan_{key}"
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=callback_data,
                    )
                ]
            )

    # Добавить разделитель
    keyboard_buttons.append(
        [InlineKeyboardButton(text="─────────── или ───────────", callback_data="separator_ignore")]
    )

    # Добавить кнопку несгораемых кредитов
    keyboard_buttons.append(
        [InlineKeyboardButton(text="💎 Купить поштучно", callback_data="buy_perpetual_credits")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Новое сообщение с описанием планов
    menu_message = """💎 <b>Выберите тарифный план</b>

<b>Lite</b> · 50 шт. · ~8₽/файл
Базовый

<b>Standard</b> · 150 шт. · ~6₽/файл ⭐️
Популярный

<b>Pro</b> · 400 шт. · ~4.5₽/файл
Для активной работы

<i>Чем больше план — тем выгоднее!</i>"""

    # Для CallbackQuery редактируем сообщение, для Message создаем новое
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            menu_message, reply_markup=keyboard, parse_mode="HTML"
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(menu_message, reply_markup=keyboard, parse_mode="HTML")


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

    # Показываем детали подписки
    user_id = callback_query.from_user.id
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
