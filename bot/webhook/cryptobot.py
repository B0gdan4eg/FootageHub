from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/webhook/cryptobot")
async def webhook(request: Request):
    data = await request.json()
    print("Получен webhook:", data)

    # Здесь можно добавить обработку данных, например:
    # if data.get("status") == "paid":
    #     process_payment(data)

    return JSONResponse(content={"status": "ok"}, status_code=200)