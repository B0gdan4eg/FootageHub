from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from db.session import get_session
from db.user_crud import grant_access, get_user_by_telegram_id
from db.payment_crud import create_payment
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
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    print("Получен webhook:", data)

    if data.get("update_type") != "invoice_paid":
        return JSONResponse(content={"status": "ignored"}, status_code=200)

    payload = data.get("payload", {})
    invoice_id = payload.get("invoice_id")
    amount = payload.get("amount")
    currency = payload.get("asset")
    user_payload = payload.get("payload")  # Например: "559268908:credits:five"
    description = payload.get("description")
    paid_at = payload.get("paid_at")

    print(f"✅ Оплата получена: Invoice #{invoice_id}")
    print(f"💰 Сумма: {amount} {currency}")
    print(f"📦 Payload: {user_payload}")
    print(f"🕒 Оплачено: {paid_at}")
    print(f"📄 Описание: {description}")

    if not os.path.exists(PRICE_LIST):
        print(f"❌ Файл {PRICE_LIST} не найден.")
        return JSONResponse(content={"error": "Price list not found"}, status_code=500)

    with open(PRICE_LIST, "r", encoding="utf-8") as f:
        plans = json.load(f)

    try:
        user_id, type_, value = parse_payload(user_payload, plans)

        async for session in get_session():
            
            user = await get_user_by_telegram_id(session, user_id)
            if not user:
                print(f"❌ Пользователь с id {user_id} не найден")
                return JSONResponse(content={"error": f"User {user_id} not found"}, status_code=404)
            
            # Выдача подписки или кредитов
            await grant_access(user_id=user_id, type_=type_, value=value, session=session)

            # Запись платежа
            await create_payment(
                session=session,
                user_id=user.id,
                amount=amount,
                currency=currency,
                payment_type=type_,
                invoice_id=str(invoice_id)
            )

    except Exception as e:
        print(f"❌ Ошибка при обработке платежа: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

    return JSONResponse(content={"status": "processed"}, status_code=200)


def parse_payload(payload: str, plans: dict):
    try:
        user_id_str, type_, plan_key = payload.split(":")
        user_id = int(user_id_str)

        if type_ == "subscription":
            plan_dict = plans["subscription_plans"].get(plan_key)
            if not plan_dict:
                raise ValueError(f"Неизвестный план подписки: {plan_key}")
            value = int(plan_dict["period"])

        elif type_ == "credits":
            plan_dict = plans["credits_limit"].get(plan_key)
            if not plan_dict:
                raise ValueError(f"Неизвестный кредитный план: {plan_key}")
            value = int(plan_dict["max_downloads"])

        else:
            raise ValueError("Тип должен быть 'subscription' или 'credits'")

        return user_id, type_, value

    except ValueError as e:
        raise ValueError(f"Некорректный payload: {payload}. Ошибка: {e}")

