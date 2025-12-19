from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from bot.webpay_utils import get_webpay_api
from bot.config import WEBPAY_SECRET_KEY
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.payment_crud import get_payment_by_invoice_id, mark_payment_success
from db.subscription_crud import create_subscription
from db.models import SubscriptionType, ServiceType
from bot.handlers.messages import SUBSCRIPTION_ACTIVATED
from bot.services import BotServices
from aiogram.enums.parse_mode import ParseMode
from pathlib import Path
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
PRICE_LIST = Path(__file__).resolve().parent.parent / "handlers" / "prices_list.json"


@router.post("/api/webpay/webhook")
async def webpay_webhook(request: Request):
    """
    Webhook для получения уведомлений о платежах от WebPay
    
    Документация: https://docs.webpay.by/en/paymentIntegration/cardIntegration/paymentNotification/
    """
    try:
        # Получаем параметры из POST запроса
        form_data = await request.form()
        params = dict(form_data)
        
        print(f"💳 [WEBPAY] Получено уведомление: {params}")
        
        # Проверяем подпись
        webpay_api = get_webpay_api()
        if not webpay_api.verify_webhook_signature(params, WEBPAY_SECRET_KEY):
            logger.warning(f"❌ [WEBPAY] Неверная подпись! Params: {params}")
            return JSONResponse(content={"code": 400, "message": "Invalid signature"}, status_code=200)
        
        # Извлекаем данные
        payment_type = params.get('payment_type')
        order_id = params.get('site_order_id')  # Формат: "USER_{user_id}_{plan_key}"
        transaction_id = params.get('transaction_id')
        amount = params.get('amount')
        currency = params.get('currency_id')
        
        # Проверяем, что платеж успешный (payment_type = 1 или 4)
        if payment_type not in ['1', '4']:
            logger.warning(f"⚠️ [WEBPAY] Неуспешный платеж: type={payment_type}, order={order_id}")
            return JSONResponse(content={"code": 200}, status_code=200)
        
        print(f"💰 [WEBPAY] Успешный платеж! Order: {order_id}, Amount: {amount} {currency}, TX: {transaction_id}")
        
        # Парсим order_id
        try:
            user_id, plan_key = parse_order_id(order_id)
        except ValueError as e:
            logger.warning(f"⚠️ [WEBPAY] Некорректный order_id '{order_id}': {e}")
            return JSONResponse(content={"code": 200}, status_code=200)
        
        # Загружаем тарифы
        if not PRICE_LIST.exists():
            logger.error(f"❌ [WEBPAY] Файл {PRICE_LIST} не найден")
            return JSONResponse(content={"code": 500, "message": "Price list not found"}, status_code=200)
        
        with open(PRICE_LIST, "r", encoding="utf-8") as f:
            plans = json.load(f)
        
        # Обрабатываем платеж в БД
        async for session in get_session():
            # Проверяем пользователя
            user = await get_user_by_telegram_id(session, user_id)
            if not user:
                logger.warning(f"⚠️ [WEBPAY] Пользователь {user_id} не найден в БД")
                return JSONResponse(content={"code": 200}, status_code=200)
            
            # ТЕСТОВАЯ ЗАГЛУШКА: проверяем платеж (в тестовом режиме просто логируем)
            # payment = await get_payment_by_invoice_id(session, transaction_id)
            # if payment and payment.status == "success":
            #     print(f"✅ [WEBPAY] Платеж {transaction_id} уже обработан")
            #     return JSONResponse(content={"code": 200}, status_code=200)
            
            # Получаем план из JSON
            plan_data = plans["subscription_plans"].get(plan_key)
            if not plan_data:
                logger.warning(f"⚠️ [WEBPAY] План {plan_key} не найден в конфигурации")
                return JSONResponse(content={"code": 200}, status_code=200)
            
            # ТЕСТОВАЯ ЗАГЛУШКА: создаем подписку (временно отключено)
            subscription_type = SubscriptionType[plan_data["subscription_type"]]
            period_days = plan_data["period_days"]
            total_limit = plan_data.get("total_limit")
            daily_limit = plan_data.get("daily_limit")
            
            # subscription = await create_subscription(
            #     session=session,
            #     user_id=user.id,
            #     subscription_type=subscription_type,
            #     service_type=ServiceType.ALL,
            #     total_limit=total_limit,
            #     daily_limit=daily_limit,
            #     days=period_days,
            #     payment_id=None  # В тестовом режиме
            # )
            
            # ТЕСТОВАЯ ЗАГЛУШКА: помечаем платеж успешным (временно отключено)
            # await mark_payment_success(session, transaction_id)
            
            print(f"✅ [WEBPAY] ТЕСТ: Платеж обработан для user={user_id}, plan={plan_key}")
            
            # Отправляем уведомление пользователю
            if BotServices.bot:
                try:
                    # Формируем тестовое сообщение
                    message = f"""
🎉 <b>Тестовая оплата WebPay успешна!</b>

📦 Тариф: {plan_data["name"]}
💰 Сумма: {amount} {currency}
🔑 Transaction ID: {transaction_id}

⚠️ <i>Это тестовый платеж, подписка не активирована</i>
"""
                    
                    await BotServices.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    print(f"✅ [WEBPAY] Тестовое уведомление отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ [WEBPAY] Не удалось отправить уведомление пользователю {user_id}: {e}")
            else:
                logger.warning(f"⚠️ [WEBPAY] BotServices.bot не инициализирован")
        
        return JSONResponse(content={"code": 200}, status_code=200)
        
    except Exception as e:
        logger.error(f"❌ [WEBPAY] Ошибка обработки webhook: {e}", exc_info=True)
        return JSONResponse(content={"code": 500}, status_code=200)


def parse_order_id(order_id: str):
    """
    Парсит order_id формата "USER_{user_id}_{plan_key}"
    
    Args:
        order_id: Строка формата "USER_559268908_monthly_150"
    
    Returns:
        tuple: (user_id: int, plan_key: str)
    """
    try:
        if not order_id.startswith('USER_'):
            raise ValueError("Order ID должен начинаться с 'USER_'")
        
        parts = order_id.split('_', 2)  # Разделяем только на 3 части
        if len(parts) < 3:
            raise ValueError("Недостаточно частей в order_id")
        
        user_id = int(parts[1])
        plan_key = parts[2]
        return user_id, plan_key
    except (IndexError, ValueError) as e:
        raise ValueError(f"Некорректный order_id: {order_id}. Ожидается формат 'USER_{{user_id}}_{{plan_key}}'. Ошибка: {e}")