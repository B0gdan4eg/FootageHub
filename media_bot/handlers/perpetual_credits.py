"""Модуль для покупки несгораемых (perpetual) кредитов"""

import json
import logging
import uuid
from typing import Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from media_bot.handlers.messages import (
    PERPETUAL_CREDITS_CONFIRMATION,
    PERPETUAL_CREDITS_INVALID_INPUT,
    PERPETUAL_CREDITS_INVALID_QUANTITY,
    PERPETUAL_CREDITS_PROMPT,
)
from media_bot.state import PerpetualCreditsFlow
from media_bot.webpay_utils import get_webpay_api
from shared.db.repositories import PaymentRepository, UserRepository
from shared.db.session import get_session

logger = logging.getLogger(__name__)
router = Router()

# Загрузка конфигурации из prices_list.json
PRICE_PER_CREDIT = 30
MIN_QUANTITY = 3
MAX_QUANTITY = 90


def load_perpetual_credits_config():
    """Загружает конфигурацию несгораемых кредитов из prices_list.json"""
    try:
        from media_bot.config import PRICE_LIST_PATH

        with open(PRICE_LIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            config = data.get("perpetual_credits", {})
            return {
                "price_per_credit": config.get("price_per_credit", 30),
                "minimum_quantity": config.get("minimum_quantity", 3),
                "maximum_quantity": config.get("maximum_quantity", 90),
            }
    except Exception as e:
        logger.error(f"Failed to load perpetual credits config: {e}")
        return {
            "price_per_credit": 30,
            "minimum_quantity": 3,
            "maximum_quantity": 90,
        }


def validate_quantity_input(text: str) -> Tuple[bool, int, str]:
    """
    Валидация пользовательского ввода количества кредитов.

    Args:
        text: Текст от пользователя

    Returns:
        (is_valid, quantity, error_message)
    """
    config = load_perpetual_credits_config()

    # Проверка на целое число
    try:
        quantity = int(text.strip())
    except ValueError:
        return False, 0, PERPETUAL_CREDITS_INVALID_INPUT

    # Минимум
    if quantity < config["minimum_quantity"]:
        return False, quantity, PERPETUAL_CREDITS_INVALID_QUANTITY

    # Максимум
    if quantity > config["maximum_quantity"]:
        return (
            False,
            quantity,
            f"❌ <b>Превышен максимум</b>\n\nМаксимальное количество: <b>{config['maximum_quantity']} загрузок</b> за один раз.\n\nПожалуйста, введите число не больше {config['maximum_quantity']}.",
        )

    return True, quantity, ""


@router.callback_query(F.data == "buy_perpetual_credits")
async def show_perpetual_credits_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Показывает меню покупки несгораемых кредитов"""
    await state.clear()

    # Обновляем сообщение с промптом
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="buy_subscription")]]
    )

    await callback_query.message.edit_text(
        PERPETUAL_CREDITS_PROMPT, reply_markup=keyboard, parse_mode="HTML"
    )

    # Устанавливаем состояние ожидания количества
    await state.set_state(PerpetualCreditsFlow.waiting_for_quantity)
    await callback_query.answer()


@router.message(PerpetualCreditsFlow.waiting_for_quantity)
async def process_quantity_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод количества кредитов от пользователя"""

    # Валидация ввода
    is_valid, quantity, error_message = validate_quantity_input(message.text)

    if not is_valid:
        # Отправляем сообщение об ошибке
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="buy_subscription")]
            ]
        )
        await message.answer(error_message, reply_markup=keyboard, parse_mode="HTML")
        return

    # Ввод валиден - создаём инвойс
    config = load_perpetual_credits_config()
    price_per_credit = config["price_per_credit"]
    total_price = quantity * price_per_credit

    user_id = message.from_user.id
    logger.info(
        f"User {user_id} requested to buy {quantity} perpetual credits for {total_price} RUB"
    )

    try:
        # Генерируем уникальный ID заказа
        order_id = f"USER_{user_id}_perpetual_credits_{quantity}_{uuid.uuid4().hex[:8]}"

        # URL для вебхуков
        base_url = "https://footage.com.by"
        return_url = f"{base_url}/payment/success"
        cancel_url = f"{base_url}/payment/cancel"
        notify_url = f"{base_url}/api/webpay/webhook"

        # Создаем счет через WebPay
        webpay_api = get_webpay_api()
        result = await webpay_api.create_invoice(
            order_id=order_id,
            amount=total_price,
            description=f"Покупка {quantity} несгораемых загрузок",
            return_url=return_url,
            cancel_url=cancel_url,
            notify_url=notify_url,
        )

        pay_url = result.get("invoiceUrl")
    except Exception as e:
        logger.error(f"Error creating perpetual credits invoice: {e}")
        await message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.", parse_mode="HTML")
        await state.clear()
        return

    if not pay_url or not order_id:
        logger.error("Perpetual credits invoice creation returned empty values")
        await message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.", parse_mode="HTML")
        await state.clear()
        return

    # Сохраняем платеж в БД
    async for session in get_session():
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(user_id)

        if not user:
            logger.error(f"User not found in DB: {user_id}")
            await message.answer("❌ Пользователь не найден. Начните с /start", parse_mode="HTML")
            await state.clear()
            return

        try:
            payment_repo = PaymentRepository(session)
            plan_key = f"perpetual_credits_{quantity}"
            await payment_repo.create_payment(
                user_id=user.id,
                amount=total_price,
                currency="RUB",
                plan_key=plan_key,
                invoice_id=order_id,
            )
            logger.info(
                f"Payment created for perpetual credits: user={user_id}, amount={total_price}, quantity={quantity}"
            )
        except Exception as e:
            logger.error(f"Error creating payment in DB: {e}", exc_info=True)
            await message.answer(
                "❌ Ошибка при сохранении платежа. Попробуйте позже.", parse_mode="HTML"
            )
            await state.clear()
            return

    # Показываем подтверждение с кнопкой оплаты
    confirmation_message = PERPETUAL_CREDITS_CONFIRMATION.format(
        quantity=quantity, price=total_price
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="buy_subscription")],
        ]
    )

    await message.answer(confirmation_message, reply_markup=keyboard, parse_mode="HTML")

    # Очищаем состояние
    await state.clear()
