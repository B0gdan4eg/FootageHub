from aiosend import CryptoPay, TESTNET, MAINNET
from bot.config import CRYPTO_BOT_API_KEY

async def create_crypto_invoice(user_id: int, amount: float, plan_key: str):
    """
    Создает инвойс для оплаты подписки.

    Args:
        user_id: Telegram ID пользователя
        amount: Сумма платежа
        plan_key: Ключ плана (monthly_150, daily_30)

    Returns:
        tuple: (pay_url, invoice_id)
    """
    crypto = CryptoPay(token=CRYPTO_BOT_API_KEY, network=MAINNET)

    invoice = await crypto.create_invoice(
        currency_type="crypto",
        asset="USDT",
        amount=amount,
        description="Покупка подписки",
        hidden_message="Спасибо за оплату!",
        payload=f"{user_id}:{plan_key}",
        expires_in=3600
    )

    pay_url = invoice.pay_url if invoice else None
    invoice_id = str(invoice.invoice_id) if invoice else None

    return pay_url, invoice_id
