import json
import logging
import uuid

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from media_bot.handlers.messages import msg
from media_bot.utils.price_loader import load_subscription_plans
from media_bot.webpay_utils import get_webpay_api
from shared.db.repositories import PaymentRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session
from shared.utils import dict_to_namespace

logger = logging.getLogger(__name__)
router = Router()


async def send_price_menu(message_or_callback, lang: str = "ru"):
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
                await message_or_callback.message.answer(msg("PAYMENT_USER_NOT_FOUND", lang))
                await message_or_callback.answer()
            else:
                await message_or_callback.answer(msg("PAYMENT_USER_NOT_FOUND", lang))
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

            message_text = msg("PAYMENT_HAS_SUBSCRIPTION", lang).format(
                subscription_type=subscription_type_name,
                end_date=end_date,
                credits=user.credits,
            )

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
            await message_or_callback.message.answer(msg("PAYMENT_PLANS_LOAD_ERROR", lang))
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(msg("PAYMENT_PLANS_LOAD_ERROR", lang))
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

    # Для CallbackQuery редактируем сообщение, для Message создаем новое
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            msg("PAYMENT_PLANS_MENU", lang), reply_markup=keyboard, parse_mode="HTML"
        )
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(msg("PAYMENT_PLANS_MENU", lang), reply_markup=keyboard, parse_mode="HTML")


# Хендлер для callback "buy_subscription"
@router.message(Command("pay"))
@router.message(F.text == "Оформить подписку 💳")
async def choose_plan_message(message: types.Message, state, lang: str = "ru"):
    await state.clear()
    await send_price_menu(message, lang)


@router.callback_query(F.data == "buy_subscription")
async def choose_plan_callback(callback_query: types.CallbackQuery, state, lang: str = "ru"):
    await state.clear()
    await send_price_menu(callback_query, lang)


@router.callback_query(F.data.startswith("select_plan_"))
async def show_plan_details(callback_query: types.CallbackQuery, lang: str = "ru"):
    """Показывает детали выбранной подписки с описанием всех тарифов."""
    plan_key = callback_query.data.replace("select_plan_", "")

    # Загружаем данные плана
    try:
        plans = load_subscription_plans()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load subscription plans: {e}")
        await callback_query.message.answer(msg("PAYMENT_CONFIG_ERROR", lang))
        await callback_query.answer()
        return

    data = dict_to_namespace({"subscription_plans": plans})
    plan = getattr(data.subscription_plans, plan_key, None)

    if not plan:
        logger.error(f"Plan not found for key: {plan_key}")
        await callback_query.message.answer(msg("PAYMENT_INVALID_PLAN", lang))
        await callback_query.answer()
        return

    # Выбираем правильное сообщение в зависимости от плана
    plan_msg_keys = {
        "monthly_50": "SUB_PAYMENT_MONTHLY_50",
        "monthly_150": "SUB_PAYMENT_MONTHLY_150",
        "monthly_400": "SUB_PAYMENT_MONTHLY_400",
        "daily_30": "SUB_PAYMENT_DAILY",
    }
    message_template = msg(plan_msg_keys.get(plan_key, "SUB_PAYMENT_MONTHLY_150"), lang)

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
        await callback_query.message.answer(msg("PAYMENT_INVOICE_ERROR", lang))
        await callback_query.answer()
        return

    if not pay_url or not order_id:
        logger.error("Invoice creation returned empty values")
        await callback_query.message.answer(msg("PAYMENT_INVOICE_ERROR", lang))
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
            await callback_query.message.answer(msg("PAYMENT_USER_START", lang))
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
            await callback_query.message.answer(msg("PAYMENT_SAVE_ERROR", lang))
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
