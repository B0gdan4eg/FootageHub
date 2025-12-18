from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from bot.webpay_utils import webpay_api
from bot.config import WEBPAY_SECRET_KEY, WEBPAY_RESOURCE_ID
from db.session import get_session
from db.models import User, Payment
from sqlalchemy import select
import logging
import hashlib
import time

router = APIRouter()
logger = logging.getLogger(__name__)


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

        logger.info(f"[WEBPAY] Получено уведомление: {params}")

        # Проверяем подпись
        if not webpay_api.verify_webhook_signature(params, WEBPAY_SECRET_KEY):
            logger.warning(f"[WEBPAY] Неверная подпись! Params: {params}")
            return Response(content='{"code": 400, "message": "Invalid signature"}', status_code=400)

        # Извлекаем данные
        payment_type = params.get('payment_type')
        order_id = params.get('site_order_id')  # Наш ID заказа
        transaction_id = params.get('transaction_id')
        amount = params.get('amount')
        currency = params.get('currency_id')

        # Проверяем, что платеж успешный (payment_type = 1 или 4)
        if payment_type not in ['1', '4']:
            logger.warning(f"[WEBPAY] Неуспешный платеж: type={payment_type}, order={order_id}")
            return Response(content='{"code": 200}', status_code=200)

        logger.info(f"[WEBPAY] Успешный платеж! Order: {order_id}, Amount: {amount} {currency}, TX: {transaction_id}")

        # Обрабатываем платеж в БД
        async for session in get_session():
            # Проверяем, не обработан ли уже этот платеж
            existing_payment = await session.scalar(
                select(Payment).where(Payment.payment_id == transaction_id)
            )

            if existing_payment:
                logger.info(f"[WEBPAY] Платеж {transaction_id} уже обработан")
                return Response(content='{"code": 200}', status_code=200)

            # Извлекаем user_id из order_id (формат: USER_{user_id}_{uuid})
            try:
                if order_id.startswith('USER_'):
                    parts = order_id.split('_')
                    user_id = int(parts[1])
                else:
                    logger.warning(f"[WEBPAY] Некорректный формат order_id: {order_id}")
                    return Response(content='{"code": 200}', status_code=200)
            except (IndexError, ValueError):
                logger.warning(f"[WEBPAY] Не удалось извлечь user_id из {order_id}")
                return Response(content='{"code": 200}', status_code=200)

            # Находим пользователя
            user = await session.scalar(select(User).where(User.id == user_id))
            if not user:
                logger.warning(f"[WEBPAY] Пользователь {user_id} не найден")
                return Response(content='{"code": 200}', status_code=200)

            # Создаем запись о платеже
            payment = Payment(
                user_id=user_id,
                payment_id=transaction_id,
                amount=float(amount),
                status="success",
                payment_method="webpay"
            )
            session.add(payment)

            # Начисляем кредиты в зависимости от суммы
            # TODO: Добавить логику начисления кредитов по тарифам

            await session.commit()
            logger.info(f"[WEBPAY] Платеж {transaction_id} успешно обработан для пользователя {user_id}")

        # Возвращаем успешный ответ
        return Response(content='{"code": 200}', status_code=200)

    except Exception as e:
        logger.error(f"[WEBPAY] Ошибка обработки webhook: {e}", exc_info=True)
        return Response(content='{"code": 500}', status_code=500)