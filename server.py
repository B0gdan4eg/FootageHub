# webhook_server.py
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/cryptobot/webhook")
async def cryptobot_webhook(request: Request):
    data = await request.json()
    print("Webhook data:", data)
    return {"status": "ok"}