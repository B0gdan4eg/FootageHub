import json
from aiogram import Router, types, F
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.downloaded_file_crud import get_media_by_url, create_media, create_download
import os
from uuid import uuid4
import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.crypto import create_crypto_invoice
from services.json_reader import dict_to_namespace
from envato_utils.test_env import test

router = Router()

PRICE_LIST = "prices_list.json"



@router.callback_query(lambda c: c.data == "buy_subscription")
async def choose_subscribe_plan(callback_query: types.CallbackQuery):
    # Загружаем куки из JSON
    if not os.path.exists(PRICE_LIST):
        print(f"❌ Файл {PRICE_LIST} не найден.")
        return None

    try:
        with open(PRICE_LIST, "r", encoding="utf-8") as f:
            data_dict = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка при загрузке PRICE_LIST: {e}")
        return None    
        
    data = dict_to_namespace(data_dict) 
       
    subscription = data.subscription_plans

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{plan.name} — {plan.price} USD на {plan.period} дн.",
                callback_data=f"buy_subscription_{key}"
            )]
            for key, plan in subscription.__dict__.items()
        ]
    )
    
    await callback_query.message.answer("💳 Выберите подписку:", reply_markup=keyboard)
    await callback_query.answer()
    
@router.callback_query(lambda c: c.data == "buy_credits")
async def choose_credit_plan(callback_query: types.CallbackQuery):
    with open("prices_list.json", "r", encoding="utf-8") as f:
        data_dict = json.load(f)
    data = dict_to_namespace(data_dict)

    credits = data.credits_limit

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{item.max_downloads} кредит(ов) — {item.price} USD",
            callback_data=f"buy_credits_{key}"
        )]
        for key, item in credits.__dict__.items()
    ])

    await callback_query.message.answer("💳 Выберите пакет кредитов:", reply_markup=keyboard)
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "create_invoice")
async def choose_product_type(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🔐 Подписка", callback_data="buy_subscription"),
            InlineKeyboardButton(text="💰 Кредиты", callback_data="buy_credits")
        ]]
    )
    await callback_query.message.answer(
        "Что вы хотите купить?",
        reply_markup=keyboard
    )
    await callback_query.answer()
    
@router.callback_query(lambda c: c.data.startswith("buy_"))
async def process_purchase(callback_query: types.CallbackQuery):
    try:
        _, purchase_type, plan_key = callback_query.data.split("_", 2)
    except ValueError:
        await callback_query.message.answer("❌ Некорректные данные. Попробуйте снова.")
        await callback_query.answer()
        return

    with open("prices_list.json", "r", encoding="utf-8") as f:
        data_dict = json.load(f)

    data = dict_to_namespace(data_dict)
    user_id = callback_query.from_user.id

    # Выбор данных по типу покупки
    if purchase_type == "credits":
        plan = getattr(data.credits_limit, plan_key, None)
        if not plan:
            await callback_query.message.answer("❌ Неверный пакет кредитов. Попробуйте снова.")
            await callback_query.answer()
            return

        price = plan.price
        description = f"{plan.max_downloads} кредит(ов) за {price} USD"

    elif purchase_type == "subscription":
        plan = getattr(data.subscription_plans, plan_key, None)
        if not plan:
            await callback_query.message.answer("❌ Неверный тариф подписки. Попробуйте снова.")
            await callback_query.answer()
            return

        price = plan.price
        description = f"Подписка «{plan.name}» на {plan.period} дней за {price} USD"

    else:
        await callback_query.message.answer("❌ Неизвестный тип покупки.")
        await callback_query.answer()
        return

    # Создание инвойса
    pay_url, invoice_id = await create_crypto_invoice(
        user_id=user_id,
        amount=price,
        type_=purchase_type
    )

    if pay_url:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=pay_url)]]
        )
        await callback_query.message.answer(
            f"🔹 Вы выбрали:\n<b>{description}</b>\n\nПерейдите по ссылке для оплаты:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await callback_query.message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")

    await callback_query.answer()

