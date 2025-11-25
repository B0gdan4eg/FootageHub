from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from db.session import get_session
from db.user_crud import get_user_by_telegram_id
from db.payment_crud import get_payment_by_invoice_id, mark_payment_success
from db.subscription_crud import create_subscription
from db.models import SubscriptionType, ServiceType
from pathlib import Path
import json
import os

router = APIRouter()
PRICE_LIST = Path(__file__).resolve().parent.parent / "handlers" / "prices_list.json"


@router.post("/webhook/cryptobot")
async def webhook(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        print("❌ Invalid JSON in webhook")
        return JSONResponse(content={"status": "ok"}, status_code=200)  # Возвращаем 200 чтобы не повторяли

    update_type = data.get("update_type")

    # Игнорируем все события кроме invoice_paid
    if update_type != "invoice_paid":
        return JSONResponse(content={"status": "ok"}, status_code=200)

    payload = data.get("payload", {})
    invoice_id = payload.get("invoice_id")
    amount = payload.get("amount")
    currency = payload.get("asset")
    user_payload = payload.get("payload")  # Например: "559268908:monthly_150"

    print(f"💰 Invoice #{invoice_id}: {amount} {currency}, Payload: {user_payload}")

    if not os.path.exists(PRICE_LIST):
        print(f"❌ Файл {PRICE_LIST} не найден.")
        return JSONResponse(content={"error": "Price list not found"}, status_code=500)

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        plans = json.load(f)

    try:
        user_id, plan_key = parse_payload(user_payload)
    except ValueError as e:
        print(f"⚠️ Некорректный payload '{user_payload}': {e}, игнорируем")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    try:
        async for session in get_session():
            # Проверяем пользователя
            user = await get_user_by_telegram_id(session, user_id)
            if not user:
                print(f"⚠️ Пользователь с id {user_id} не найден в БД, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Проверяем платеж в БД
            payment = await get_payment_by_invoice_id(session, str(invoice_id))
            if not payment:
                print(f"⚠️ Платеж с invoice_id {invoice_id} не найден в БД, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Проверяем, что платеж еще не обработан
            if payment.status == "success":
                print(f"✅ Платеж {invoice_id} уже обработан ранее, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Получаем план из JSON
            plan_data = plans["subscription_plans"].get(plan_key)
            if not plan_data:
                print(f"⚠️ План {plan_key} не найден в конфигурации, игнорируем")
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Создаем подписку
            subscription_type = SubscriptionType[plan_data["subscription_type"]]
            period_days = plan_data["period_days"]
            total_limit = plan_data.get("total_limit")
            daily_limit = plan_data.get("daily_limit")

            await create_subscription(
                session=session,
                user_id=user.id,
                subscription_type=subscription_type,
                service_type=ServiceType.ALL,
                total_limit=total_limit,
                daily_limit=daily_limit,
                days=period_days,
                payment_id=payment.id
            )

            # Помечаем платеж как успешный
            await mark_payment_success(session, str(invoice_id))

            print(f"✅ Подписка {plan_key} создана: user={user_id}, period={period_days}д, limits=(total={total_limit}, daily={daily_limit})")

    except Exception as e:
        print(f"❌ Ошибка при обработке платежа {invoice_id}: {e}")
        import traceback
        traceback.print_exc()
        # Возвращаем 200 чтобы CryptoBot не повторял запрос, но логируем ошибку
        return JSONResponse(content={"status": "ok"}, status_code=200)

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
        raise ValueError(f"Некорректный payload: {payload}. Ожидается формат 'user_id:plan_key'. Ошибка: {e}")