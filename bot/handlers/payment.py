import json
from aiogram import Router, types, F
import os
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.crypto import create_crypto_invoice
from services.json_reader import dict_to_namespace
from pathlib import Path
from bot.handlers.messages import CR_PAYMENT, SUB_PAYMENT

router = Router()


PRICE_LIST = Path(__file__).resolve().parent / "prices_list.json"
# Потом убрать

# Коллбек на скачивания   
async def send_price_menu(message_or_callback):
    """Отправляет меню с кредитами и подписками."""
    if not os.path.exists(PRICE_LIST):
        await message_or_callback.answer(f"❌ Файл {PRICE_LIST} не найден.")
        return

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        pr = json.load(f)

    data = dict_to_namespace(pr)
    keyboard_buttons = []

    # Добавляем кредиты
    if hasattr(data, "credits_limit"):
        for key, item in data.credits_limit.__dict__.items():
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{item.max_downloads} кредит(ов) — {item.price} USD",
                    callback_data=f"buy_credits_{key}"
                )
            ])

    # Добавляем подписки
    if hasattr(data, "subscription_plans"):
        for key, item in data.subscription_plans.__dict__.items():
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"Подписка на {item.period} дн. — {item.price} USD",
                    callback_data=f"buy_subscription_{key}"
                )
            ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Для CallbackQuery используем edit_text, для Message — answer
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer("💳 Выберите пакет:", reply_markup=keyboard)
        await message_or_callback.answer()
    else:
        await message_or_callback.answer("💳 Выберите пакет:", reply_markup=keyboard)


# Хендлер для callback
@router.callback_query(lambda c: c.data == "create_invoice")
async def choose_plan_callback(callback_query: types.CallbackQuery):
    await send_price_menu(callback_query)


# Хендлер для сообщения (например, текст "Купить")
@router.message((lambda message: message.text == "Оплата 💳"))
async def choose_plan_message(message: types.Message):
    await send_price_menu(message)
    
@router.callback_query(lambda c: c.data.startswith("buy_"))
async def process_purchase(callback_query: types.CallbackQuery):
    try:
        _, purchase_type, plan_key = callback_query.data.split("_", 2)
    except ValueError:
        await callback_query.message.answer("❌ Некорректные данные. Попробуйте снова.")
        await callback_query.answer()
        return

    # Загружаем цену из JSON
    if not os.path.exists(PRICE_LIST):
        print(f"❌ Файл {PRICE_LIST} не найден.")
        return None

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        pr = json.load(f)
        

    data = dict_to_namespace(pr)
    user_id = callback_query.from_user.id

    # Выбор данных по типу покупки
    if purchase_type == "credits":
        plan = getattr(data.credits_limit, plan_key, None)
        if not plan:
            await callback_query.message.answer("❌ Неверный пакет кредитов. Попробуйте снова.")
            await callback_query.answer()
            return

        price = plan.price
        description = CR_PAYMENT.format(downloads=plan.max_downloads, _price=price)

    elif purchase_type == "subscription":
        plan = getattr(data.subscription_plans, plan_key, None)
        if not plan:
            await callback_query.message.answer("❌ Неверный тариф подписки. Попробуйте снова.")
            await callback_query.answer()
            return

        price = plan.price
        description = SUB_PAYMENT.format(name=plan.name, period=plan.period, _price=price)

    else:
        await callback_query.message.answer("❌ Неизвестный тип покупки.")
        await callback_query.answer()
        return

    # Создание инвойса
    pay_url, invoice_id = await create_crypto_invoice(
        user_id=user_id,
        amount=price,
        type_=purchase_type,
        plan=plan_key
    )

    if pay_url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=pay_url)]]
        )
        await callback_query.message.answer(
            description,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")

    await callback_query.answer()
