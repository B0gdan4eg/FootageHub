import hashlib
import logging
import time

import httpx

from media_bot.config import (
    WEBPAY_API_KEY,
    WEBPAY_AUTH_TOKEN,
    WEBPAY_RESOURCE_ID,
    WEBPAY_SANDBOX,
    WEBPAY_SECRET_KEY,
    WEBPAY_SIGNING_KEY,
)

logger = logging.getLogger(__name__)


class WebPayAPI:
    """WebPay JSON API integration for payment processing"""

    def __init__(self):
        self.merchant_id = WEBPAY_RESOURCE_ID
        self.auth_token = WEBPAY_AUTH_TOKEN  # Токен из .env
        self.secret_key = WEBPAY_SECRET_KEY  # Password для логина (для авторизации)
        self.signing_key = WEBPAY_SIGNING_KEY  # Secret key для подписи платежей
        self.api_key = WEBPAY_API_KEY  # Username для автоматического обновления токена
        self.sandbox = WEBPAY_SANDBOX
        self._token_refresh_time = time.time()  # Время последнего обновления токена

        if self.sandbox:
            self.base_url = "https://sandbox.webpay.by"
        else:
            self.base_url = "https://billing.webpay.by"

    async def _refresh_token(self):
        """Обновляет auth_token через API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://billing.webpay.by/api/login",
                    json={
                        "merchantId": self.merchant_id,
                        "username": self.api_key,
                        "password": self.secret_key,
                    },
                    timeout=30.0,
                )

                # API может вернуть 200 или 201
                if response.status_code in (200, 201):
                    data = response.json()
                    new_token = data.get("data", {}).get("auth_token")
                    if new_token:
                        self.auth_token = new_token
                        self._token_refresh_time = time.time()
                        logger.info("[WEBPAY] Токен успешно обновлен")
                        return True

            logger.warning("[WEBPAY] Не удалось обновить токен")
            return False
        except Exception as e:
            logger.error(f"[WEBPAY] Ошибка обновления токена: {e}")
            return False

    async def create_invoice(
        self,
        order_id: str,
        amount: float,
        description: str,
        return_url: str,
        cancel_url: str,
        notify_url: str,
    ) -> dict:
        """
        Создает счет для оплаты через JSON API

        Args:
            order_id: Уникальный номер заказа
            amount: Сумма платежа в RUB (будет автоматически конвертирована в BYN)
            description: Описание платежа
            return_url: URL для возврата после успешной оплаты
            cancel_url: URL для возврата при отмене
            notify_url: URL для webhook уведомлений

        Returns:
            dict с redirectUrl для перенаправления пользователя на оплату
        """
        # Обновляем токен перед каждым платежом
        await self._refresh_token()

        # Генерируем seed (текущее время)
        seed = str(int(time.time()))

        # Конвертируем RUB в BYN (курс примерно 1 RUB = 0.033 BYN)
        amount_byn = round(amount * 0.037, 2)

        # Форматируем amount для подписи по документации WebPay:
        # если поле содержит дробную часть (например, 1.00), используйте значение с нулями
        # если поле не содержит дробную часть (например, 1), используйте значение без нулей
        amount_byn_for_signature = f"{amount_byn:.2f}"

        # Вычисляем подпись
        # Формат: seed + storeid + order_num + test + currency_id + total + signing_key
        test_mode = 1 if self.sandbox else 0
        signature_string = f"{seed}{self.merchant_id}{order_id}{test_mode}BYN{amount_byn_for_signature}{self.signing_key}"
        signature = hashlib.sha1(
            signature_string.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        logger.info(
            f"💳 [WEBPAY] Creating invoice: order_id={order_id}, amount_rub={amount}, amount_byn={amount_byn}"
        )
        logger.debug(
            f"💳 [WEBPAY] Signature string (without secret): {seed}{self.merchant_id}{order_id}{test_mode}BYN{amount_byn_for_signature}***"
        )

        # Формируем payload
        payload = {
            "wsb_storeid": int(self.merchant_id),
            "wsb_order_num": order_id,
            "wsb_currency_id": "BYN",
            "wsb_version": 2,
            "wsb_seed": seed,
            "wsb_test": test_mode,
            "wsb_invoice_item_name": [description],
            "wsb_invoice_item_quantity": [1],
            "wsb_invoice_item_price": [amount_byn],
            "wsb_total": amount_byn,
            "wsb_signature": signature,
            "wsb_return_url": return_url,
            "wsb_cancel_return_url": cancel_url,
            "wsb_notify_url": notify_url,
            "wsb_redirect": 1,
            "wsb_return_format": "json",
        }

        # API URL
        api_url = "https://payment.webpay.by/api/v1/payment"

        # Выполняем запрос на создание платежа
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )

            # Если ошибка, показываем тело ответа
            if response.status_code >= 400:
                error_body = response.text
                logger.error(f"[WEBPAY] ❌ Status: {response.status_code}")
                logger.error(f"[WEBPAY] ❌ Response body: {error_body}")
                logger.error(f"[WEBPAY] ❌ Request payload: {payload}")

            response.raise_for_status()
            data = response.json()
            logger.info(f"💳 [WEBPAY] Invoice created successfully: {data}")

            # Возвращаем URL для оплаты
            return {
                "invoiceUrl": data.get("data", {}).get("redirectUrl"),
                "wt": data.get("data", {}).get("wt"),
            }

    @staticmethod
    def verify_webhook_signature(params: dict, secret_key: str = None) -> bool:
        """
        Проверяет подпись webhook уведомления

        Args:
            params: Параметры из POST запроса
            secret_key: Secret key от WebPay (signing_key)

        Returns:
            True если подпись верна
        """
        received_signature = params.get("wsb_signature", "")

        # Формируем строку для проверки подписи
        # Для NOTIFICATION: batch_timestamp + currency_id + amount + payment_method +
        # order_id + site_order_id + transaction_id + payment_type + rrn + SECRET_KEY
        # ВАЖНО: В webhook используется signing_key в конце!
        fields = [
            params.get("batch_timestamp", ""),
            params.get("currency_id", ""),
            params.get("amount", ""),
            params.get("payment_method", ""),
            params.get("order_id", ""),
            params.get("site_order_id", ""),
            params.get("transaction_id", ""),
            params.get("payment_type", ""),
            params.get("rrn", ""),
        ]

        # Добавляем secret_key в конец
        string_to_sign = "".join(str(f) for f in fields) + (secret_key or "")

        # Для notification всегда используется MD5 (независимо от версии)
        expected_signature = hashlib.md5(
            string_to_sign.encode("utf-8"), usedforsecurity=False
        ).hexdigest()

        match = expected_signature == received_signature

        # Логируем только ошибки
        if not match:
            logger.error(f"[WEBPAY] ❌ Signature mismatch!")
            logger.error(f"  Expected: {expected_signature}")
            logger.error(f"  Received: {received_signature}")
            logger.error(f"  String to sign (without secret): {''.join(str(f) for f in fields)}***")

        return match


# Lazy initialization - создаем только при первом использовании
_webpay_instance = None


def get_webpay_api() -> WebPayAPI:
    """Возвращает экземпляр WebPayAPI (создает при первом вызове)"""
    global _webpay_instance
    if _webpay_instance is None:
        _webpay_instance = WebPayAPI()
    return _webpay_instance
