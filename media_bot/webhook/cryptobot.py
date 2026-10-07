import json
import logging
from datetime import datetime, timedelta, timezone

from aiogram.enums.parse_mode import ParseMode
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from media_bot.config import CRYPTO_BOT_API_KEY
from media_bot.handlers.messages import SUBSCRIPTION_ACTIVATED
from media_bot.services import BotServices
from media_bot.utils.price_loader import load_subscription_plans
from shared.db.models import ServiceType, SubscriptionType
from shared.db.repositories import PaymentRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session
from shared.error_tracking import report_exception
from shared.payment_validation import positive_amount, verify_crypto_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/cryptobot")
async def webhook(request: Request):
    body = await request.body()
    if not verify_crypto_signature(
        body, request.headers.get("crypto-pay-api-signature", ""), CRYPTO_BOT_API_KEY
    ):
        raise HTTPException(status_code=403, detail="Invalid payment signature")
    try:
        data = json.loads(body)
        sent = datetime.fromisoformat(data["request_date"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if sent.tzinfo is None or not now - timedelta(days=3, minutes=5) <= sent <= now + timedelta(
            minutes=5
        ):
            raise ValueError("Invalid callback date")
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid payment notification")

    update_type = data.get("update_type")

    # Игнорируем все события кроме invoice_paid
    if update_type != "invoice_paid":
        return JSONResponse(content={"status": "ok"}, status_code=200)

    payload = data.get("payload", {})
    if not isinstance(payload, dict) or payload.get("status") != "paid":
        raise HTTPException(status_code=400, detail="Invalid paid invoice")
    invoice_id = payload.get("invoice_id")
    amount = payload.get("amount")
    currency = payload.get("asset")
    user_payload = payload.get("payload")  # Например: "559268908:monthly_150"

    print(f"💰 Invoice #{invoice_id}: {amount} {currency}, Payload: {user_payload}")

    try:
        plans = load_subscription_plans()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load subscription plans: {e}")
        return JSONResponse(content={"error": "Price list not found"}, status_code=500)

    try:
        user_id, plan_key = parse_payload(user_payload)
    except ValueError as e:
        print(f"⚠️ Некорректный payload '{user_payload}': {e}, игнорируем")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    try:
        async for session in get_session():
            # Проверяем пользователя
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_id, lock=True)
            if not user:
                print(f"⚠️ Пользователь с id {user_id} не найден в БД, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Проверяем платеж в БД
            payment_repo = PaymentRepository(session)
            payment = await payment_repo.get_by_invoice_id(str(invoice_id), lock=True)
            if not payment:
                print(f"⚠️ Платеж с invoice_id {invoice_id} не найден в БД, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            if (
                payment.user_id != user.id
                or payment.plan_key != plan_key
                or currency != payment.currency
                or positive_amount(amount) != positive_amount(payment.amount)
            ):
                raise HTTPException(status_code=400, detail="Payment does not match invoice")
            # Проверяем, что платеж еще не обработан
            if payment.status == "success":
                print(f"✅ Платеж {invoice_id} уже обработан ранее, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)
            if payment.status != "pending":
                raise HTTPException(status_code=409, detail="Payment is not pending")

            # Получаем план из JSON
            plan_data = plans.get(plan_key)
            if not plan_data:
                print(f"⚠️ План {plan_key} не найден в конфигурации, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Создаем подписку
            subscription_type = SubscriptionType[plan_data["subscription_type"]]
            period_days = plan_data["period_days"]
            total_limit = plan_data.get("total_limit")
            daily_limit = plan_data.get("daily_limit")

            subscription_repo = SubscriptionRepository(session)
            subscription = await subscription_repo.create_subscription_with_credits(
                user_id=user.id,
                subscription_type=subscription_type,
                service_type=ServiceType.ALL,
                total_limit=total_limit,
                daily_limit=daily_limit,
                days=period_days,
                payment_id=payment.id,
                commit=False,
            )

            # Помечаем платеж как успешный
            payment.status = "success"
            await session.commit()

            print(
                f"✅ Подписка {plan_key} создана: user={user_id}, period={period_days}д, limits=(total={total_limit}, daily={daily_limit})"
            )

            # Отправляем уведомление пользователю
            if BotServices.bot:
                try:
                    # Обновляем данные пользователя из сессии
                    await session.refresh(user)

                    # Форматируем дату окончания подписки
                    end_date = subscription.end_date.strftime("%d.%m.%Y %H:%M")

                    # Формируем сообщение
                    message = SUBSCRIPTION_ACTIVATED.format(
                        subscription_type=plan_data["name"],
                        period_days=period_days,
                        credits=user.credits,
                        end_date=end_date,
                    )

                    # Отправляем сообщение пользователю
                    await BotServices.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                    print(f"✅ Уведомление отправлено пользователю {user_id}")
                except Exception as e:
                    print(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
            else:
                print("⚠️ BotServices.bot не инициализирован, уведомление не отправлено")

    except HTTPException:
        raise
    except Exception as e:
        report_exception(e)
        print(f"❌ Ошибка при обработке платежа {invoice_id}: {e}")
        import traceback

        traceback.print_exc()
        # Возвращаем 200 чтобы CryptoBot не повторял запрос, но логируем ошибку
        return JSONResponse(content={"status": "error"}, status_code=500)

    return JSONResponse(content={"status": "ok"}, status_code=200)


def parse_payload(payload: str):
    """
    Парсит payload формата "user_id:plan_key"

    Args:
        payload: Строка формата "559268908:monthly_150"

    Returns:
        tuple: (user_id: int, plan_key: str)
    """
    try:
        user_id_str, plan_key = payload.split(":")
        user_id = int(user_id_str)
        return user_id, plan_key
    except ValueError as e:
        raise ValueError(
            f"Некорректный payload: {payload}. Ожидается формат 'user_id:plan_key'. Ошибка: {e}"
        )
