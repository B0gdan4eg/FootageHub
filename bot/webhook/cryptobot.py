from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json

router = APIRouter()

@router.post("/webhook/cryptobot")
async def webhook(request: Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    print("Получен webhook:", data)

    # Проверка типа обновления
    if data.get("update_type") == "invoice_paid":
        payload = data.get("payload", {})
        invoice_id = payload.get("invoice_id")
        amount = payload.get("amount")
        currency = payload.get("asset")
        user_payload = payload.get("payload")  # Например: "559268908:credits"
        description = payload.get("description")
        paid_at = payload.get("paid_at")

        # 💡 Твои действия: логирование, запись в БД, выдача доступа и т.п.
        print(f"✅ Оплата получена: Invoice #{invoice_id}")
        print(f"💰 Сумма: {amount} {currency}")
        print(f"📦 Payload: {user_payload}")
        print(f"🕒 Оплачено: {paid_at}")
        print(f"📄 Описание: {description}")

        # Здесь можно вызвать свою функцию, например:
        # process_payment(user_payload, amount)

        return JSONResponse(content={"status": "processed"}, status_code=200)

    # Если это не тот тип события
    return JSONResponse(content={"status": "ignored"}, status_code=200)
