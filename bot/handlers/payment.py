# # bot/handlers/payment.py
# import aiohttp
# from aiogram import Router, types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# from db.session import get_session
# from db.payment_crud import create_payment
# from db.user_crud import get_user_by_telegram_id
# from bot.config import CRYPTO_BOT_API_KEY, CRYPTO_BOT_WEBHOOK  # добавьте в .env

# router = Router()

# CRYPTO_BOT_URL = "https://pay.crypt.bot/create_invoice"


# @router.message(lambda m: m.text == "Купить доступ")
# async def start_payment(message: types.Message):
#     user_tg_id = message.from_user.id

#     # ➊ берём (или создаём) пользователя
#     async for session in get_session():
#         user = await get_user_by_telegram_id(session, user_tg_id)
#         if not user:
#             await message.answer("Сначала воспользуйтесь /start.")
#             return

#         # ➋ сохраняем платёж со status='pending'
#         amount_usd = 2.00
#         payment = await create_payment(
#             session=session,
#             user_id=user.id,
#             amount=amount_usd,
#             currency="USDT",
#             payment_type="subscription",
#             invoice_id=""        # пока пусто – заполним после ответа CryptoBot
#         )

#         # ➌ готовим запрос к CryptoBot
#         payload = {
#             "asset": "USDT",
#             "amount": str(amount_usd),
#             "description": "Подписка на 30 дней",
#             "payload": f"payment:{payment.id}",           # привязываем к записи в БД
#             "hidden_message": "Спасибо за оплату!",
#             "callback_url": CRYPTO_BOT_WEBHOOK,           # https://<domain>/cryptobot/webhook
#             "expires_in": 3600
#         }
#         headers = {
#             "Crypto-Pay-API-Token": CRYPTO_BOT_API_KEY,
#             "Content-Type": "application/json"
#         }

#         # ➍ отправляем запрос
#         async with aiohttp.ClientSession() as client:
#             async with client.post(CRYPTO_BOT_URL, json=payload, headers=headers) as resp:
#                 data = await resp.json()

#         if data.get("ok") and data.get("result"):
#             result = data["result"]
#             pay_url = result["pay_url"]
#             invoice_id = result["invoice_id"]

#             # ➎ сохраняем invoice_id в той же записи
#             payment.invoice_id = str(invoice_id)
#             session.add(payment)
#             await session.commit()

#             kb = InlineKeyboardMarkup(
#                 inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить USDT", url=pay_url)]]
#             )
#             await message.answer("Нажмите кнопку ниже для оплаты:", reply_markup=kb)
#         else:
#             await message.answer("❌ Не удалось создать счёт. Попробуйте позже.")
