from aiosend import CryptoPay, TESTNET
from bot.config import CRYPTO_BOT_API_KEY

async def create_crypto_invoice(user_id: int, amount: float, type_: str):
    crypto = CryptoPay(token=CRYPTO_BOT_API_KEY, network=TESTNET)

    invoice = await crypto.create_invoice(
        currency_type="crypto",
        asset="USDT",
        amount=amount,
        description="Покупка доступа",
        hidden_message="Спасибо за оплату!",
        payload=f"{user_id}:{type_}",
        expires_in=3600
    )

    pay_url = invoice.pay_url if invoice else None
    invoice_id = invoice.invoice_id if invoice else None

    return pay_url, invoice_id
