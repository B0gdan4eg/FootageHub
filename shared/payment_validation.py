"""Provider verification without logging payment payloads or credentials."""

import hashlib
import hmac
import re
from decimal import Decimal, InvalidOperation


def verify_crypto_signature(body: bytes, signature: str, token: str) -> bool:
    if not token or not re.fullmatch(r"[0-9a-fA-F]{64}", signature):
        return False
    key = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(key, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def verify_webpay_signature(params: dict[str, str], secret: str) -> bool:
    signature = params.get("wsb_signature", "")
    if not secret or not re.fullmatch(r"[0-9a-fA-F]{32}", signature):
        return False
    fields = (
        "batch_timestamp",
        "currency_id",
        "amount",
        "payment_method",
        "order_id",
        "site_order_id",
        "transaction_id",
        "payment_type",
        "rrn",
    )
    if any(not params.get(key) for key in fields[:-1]):
        return False
    # WebPay includes card in the signature when supplied for a card workflow.
    text = "".join(params.get(key, "") for key in fields) + params.get("card", "") + secret
    expected = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def positive_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid payment amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Invalid payment amount")
    return amount


def webpay_amount(rubles) -> Decimal:
    # Preserve the gateway's existing conversion and rounding, avoiding a pricing change.
    return positive_amount(f"{round(float(positive_amount(rubles)) * 0.037, 2):.2f}")
