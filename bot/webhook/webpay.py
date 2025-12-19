from fastapi import APIRouter, Request, Response
from bot.webpay_utils import get_webpay_api
from bot.config import WEBPAY_SECRET_KEY
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from bot.services import BotServices
from aiogram.enums.parse_mode import ParseMode
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/webpay/webhook")
async def webpay_webhook(request: Request):
    """
    Webhook для получения уведомлений о платежах от WebPay

    Документация: https://docs.webpay.by/en/paymentIntegration/cardIntegration/paymentNotification/
    """
    try:
        # Получаем JSON из запроса
        params = await request.json()
        print(f"💳 [WEBPAY] Получено уведомление: {params}")

        # Проверяем подпись
        webpay_api = get_webpay_api()
        if not webpay_api.verify_webhook_signature(params, WEBPAY_SECRET_KEY):
            logger.warning(f"❌ [WEBPAY] Неверная подпись! Params: {params}")
            return Response(content='{"code": 400, "message": "Invalid signature"}', status_code=400)

        # Извлекаем данные
        payment_type = params.get('payment_type')
        order_id = params.get('site_order_id')
        transaction_id = params.get('transaction_id')
        amount = params.get('amount')
        currency = params.get('currency_id')

        # Проверяем, что платеж успешный (payment_type = 1 или 4)
        if payment_type not in ['1', '4']:
            logger.warning(f"⚠️ [WEBPAY] Неуспешный платеж: type={payment_type}, order={order_id}")
            return Response(content='{"code": 200}', status_code=200)

        print(f"💰 [WEBPAY] Успешный платеж! Order: {order_id}, Amount: {amount} {currency}, TX: {transaction_id}")

        # Обрабатываем платеж
        async for session in get_session():
            # Извлекаем user_id из order_id (формат: USER_{user_id}_{plan_key})
            try:
                if order_id.startswith('USER_'):
                    parts = order_id.split('_', 2)
                    user_id = int(parts[1])
                    plan_key = parts[2] if len(parts) > 2 else None
                else:
                    logger.warning(f"⚠️ [WEBPAY] Некорректный формат order_id: {order_id}")
                    return Response(content='{"code": 200}', status_code=200)
            except (IndexError, ValueError) as e:
                logger.warning(f"⚠️ [WEBPAY] Не удалось извлечь user_id из {order_id}: {e}")
                return Response(content='{"code": 200}', status_code=200)

            # Находим пользователя
            user = await get_user_by_telegram_id(session, user_id)
            if not user:
                logger.warning(f"⚠️ [WEBPAY] Пользователь {user_id} не найден")
                return Response(content='{"code": 200}', status_code=200)

            print(f"✅ [WEBPAY] ТЕСТ: Платеж обработан для user={user_id}, plan={plan_key}")

            # Отправляем уведомление пользователю
            if BotServices.bot:
                try:
                    message = f"""
🎉 <b>Тестовая оплата WebPay успешна!</b>

💰 Сумма: {amount} {currency}
🔑 Transaction ID: {transaction_id}
📦 План: {plan_key or 'не указан'}

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
                    logger.error(f"❌ [WEBPAY] Не удалось отправить уведомление: {e}")
            else:
                logger.warning(f"⚠️ [WEBPAY] BotServices.bot не инициализирован")

        # Возвращаем успешный ответ
        return Response(content='{"code": 200}', status_code=200)

    except Exception as e:
        logger.error(f"❌ [WEBPAY] Ошибка обработки webhook: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return Response(content='{"code": 500}', status_code=200)