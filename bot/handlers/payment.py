import json
import logging
from aiogram import Router, types, F
import os
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.crypto import create_crypto_invoice
from services.json_reader import dict_to_namespace
from pathlib import Path
from bot.handlers.messages import SUB_PAYMENT_MONTHLY, SUB_PAYMENT_DAILY, ALREADY_HAS_SUBSCRIPTION
from db.session import get_session
from db.payment_crud import create_payment
from db.user_crud import get_user_by_telegram_id
from db.subscription_crud import get_active_subscription
from aiogram.filters import Command
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()

PRICE_LIST = Path(__file__).resolve().parent / "prices_list.json"


async def send_price_menu(message_or_callback):
    """Отправляет меню с подписками."""
    if not os.path.exists(PRICE_LIST):
        await message_or_callback.answer(f"❌ Файл {PRICE_LIST} не найден.")
        return

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        pr = json.load(f)

    data = dict_to_namespace(pr)
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
            print(f"[PAYMENT] Creating button with callback_data: {callback_data}")
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{item.name} ({limits_text}) — {item.price} USDT",
                    callback_data=callback_data
                )
            ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Для CallbackQuery редактируем сообщение, для Message создаем новое
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text("💳 Выберите подписку:", reply_markup=keyboard)
        await message_or_callback.answer()
    else:
        await message_or_callback.answer("💳 Выберите подписку:", reply_markup=keyboard)


# Хендлер для callback "buy_subscription"
@router.message(Command("pay"))
@router.message(lambda message: message.text == "Увеличить лимиты 💳")
@router.callback_query(lambda c: c.data == "buy_subscription")
async def choose_plan_callback(callback_query: types.CallbackQuery):
    print(f"[PAYMENT] Received buy_subscription callback from user {callback_query.from_user.id}")
    await send_price_menu(callback_query)

@router.callback_query(F.data.startswith("select_plan_"))
async def show_plan_details(callback_query: types.CallbackQuery):
    """Показывает детали выбранной подписки с описанием всех тарифов."""
    print(f"[PAYMENT] Received select_plan callback: {callback_query.data} from user {callback_query.from_user.id}")
    plan_key = callback_query.data.replace("select_plan_", "")
    print(f"[PAYMENT] Extracted plan_key: {plan_key}")

    # Загружаем данные плана
    if not os.path.exists(PRICE_LIST):
        await callback_query.message.answer("❌ Ошибка конфигурации. Обратитесь к администратору.")
        await callback_query.answer()
        return

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        pr = json.load(f)

    data = dict_to_namespace(pr)
    plan = getattr(data.subscription_plans, plan_key, None)
    print(f"[PAYMENT] Plan found: {plan is not None}")

    if not plan:
        print(f"[PAYMENT] ❌ Plan not found for key: {plan_key}")
        await callback_query.message.answer("❌ Неверный тариф подписки. Попробуйте снова.")
        await callback_query.answer()
        return

    # Выбираем правильное сообщение в зависимости от плана
    if plan_key == "monthly_150":
        message_template = SUB_PAYMENT_MONTHLY
    elif plan_key == "daily_30":
        message_template = SUB_PAYMENT_DAILY
    else:
        message_template = SUB_PAYMENT_MONTHLY  # По умолчанию

    # Проверяем наличие активной подписки
    user_id = callback_query.from_user.id
    async for session in get_session():
        # Получаем пользователя из БД
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            print(f"[PAYMENT] ❌ User not found in DB: {user_id}")
            await callback_query.message.answer("❌ Пользователь не найден. Начните с /start")
            await callback_query.answer()
            return

        # Проверяем активную подписку
        active_subscription = await get_active_subscription(session, user.id)
        if active_subscription:
            # У пользователя уже есть активная подписка
            subscription_type_name = active_subscription.subscription_type.value
            end_date = active_subscription.end_date.strftime("%d.%m.%Y %H:%M")

            message = ALREADY_HAS_SUBSCRIPTION.format(
                subscription_type=subscription_type_name,
                end_date=end_date,
                credits=user.credits
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_subscription")]
                ]
            )

            print(f"[PAYMENT] ⚠️ User {user_id} already has active subscription: {subscription_type_name}")
            await callback_query.message.edit_text(
                message,
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await callback_query.answer()
            return

    # Показываем детали подписки
    description = message_template.format(_price=plan.price)
    print(f"[PAYMENT] Description created for plan: {plan_key}, length: {len(description)}")

    # Создаем инвойс сразу
    print(f"[PAYMENT] Creating invoice for user_id: {user_id}, amount: {plan.price}, plan_key: {plan_key}")

    try:
        pay_url, invoice_id = await create_crypto_invoice(
            user_id=user_id,
            amount=plan.price,
            plan_key=plan_key
        )
        print(f"[PAYMENT] Invoice created: invoice_id={invoice_id}, pay_url exists={pay_url is not None}")
    except Exception as e:
        print(f"[PAYMENT] ❌ Error creating invoice: {e}")
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
        await callback_query.answer()
        return

    if not pay_url or not invoice_id:
        print(f"[PAYMENT] ❌ Invoice creation returned empty values")
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
        await callback_query.answer()
        return

    print(f"[PAYMENT] Saving payment to DB...")
    # Сохраняем платеж в БД
    async for session in get_session():
        # Получаем пользователя из БД
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            print(f"[PAYMENT] ❌ User not found in DB: {user_id}")
            await callback_query.message.answer("❌ Пользователь не найден. Начните с /start")
            await callback_query.answer()
            return

        print(f"[PAYMENT] User found: {user.id}, creating payment...")
        try:
            await create_payment(
                session=session,
                user_id=user.id,
                amount=plan.price,
                currency="USDT",
                plan_key=plan_key,
                invoice_id=invoice_id
            )
            print(f"[PAYMENT] Payment created successfully")
        except Exception as e:
            print(f"[PAYMENT] ❌ Error creating payment in DB: {e}")
            import traceback
            traceback.print_exc()
            await callback_query.message.answer("❌ Ошибка при сохранении платежа. Попробуйте позже.")
            await callback_query.answer()
            return

    # Кнопка для оплаты
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="⬅️ Назад к выбору", callback_data="buy_subscription")]
        ]
    )

    print(f"[PAYMENT] Editing message with payment details...")
    try:
        await callback_query.message.edit_text(
            description,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback_query.answer()
        print(f"[PAYMENT] ✅ Message edited successfully")
    except Exception as e:
        print(f"[PAYMENT] ❌ Error editing message: {e}")


# Добавляем универсальный хендлер для отладки всех callback
@router.callback_query()
async def catch_all_callbacks(callback_query: types.CallbackQuery):
    """Ловит все необработанные callback для отладки."""
    print(f"[PAYMENT] ⚠️ Unhandled callback: {callback_query.data} from user {callback_query.from_user.id}")
    await callback_query.answer("⚠️ Неизвестная команда")