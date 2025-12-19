import hashlib
import httpx
import time
from bot.config import (
    WEBPAY_RESOURCE_ID,
    WEBPAY_API_KEY,
    WEBPAY_AUTH_TOKEN,
    WEBPAY_SECRET_KEY,
    WEBPAY_SANDBOX
)


class WebPayAPI:
    """WebPay JSON API integration for payment processing"""

    def __init__(self):
        self.merchant_id = WEBPAY_RESOURCE_ID
        self.auth_token = WEBPAY_AUTH_TOKEN  # Токен из .env
        self.secret_key = WEBPAY_SECRET_KEY  # Для проверки webhook подписей
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
                    "https://sandbox.webpay.by/api/login",
                    json={
                        "merchantId": self.merchant_id,
                        "username": self.api_key,
                        "password": self.secret_key
                    },
                    timeout=30.0
                )

                # API может вернуть 200 или 201
                if response.status_code in (200, 201):
                    data = response.json()
                    new_token = data.get("data", {}).get("auth_token")
                    if new_token:
                        self.auth_token = new_token
                        self._token_refresh_time = time.time()
                        print(f"[WEBPAY] Токен успешно обновлен")
                        return True

            print(f"[WEBPAY] Не удалось обновить токен")
            return False
        except Exception as e:
            print(f"[WEBPAY] Ошибка обновления токена: {e}")
            return False

    async def create_invoice(
        self,
        order_id: str,
        amount: float,
        description: str,
        return_url: str,
        cancel_url: str,
        notify_url: str
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
        amount_byn = round(amount * 0.033, 2)

        # Форматируем amount для подписи: если .00, то без дробной части
        amount_byn_for_signature = str(int(amount_byn)) if amount_byn == int(amount_byn) else str(amount_byn)

        # Вычисляем подпись
        # Формат: seed + storeid + order_num + test + currency_id + total + secret_key
        test_mode = 1 if self.sandbox else 0
        signature_string = f"{seed}{self.merchant_id}{order_id}{test_mode}BYN{amount_byn_for_signature}{self.secret_key}"
        signature = hashlib.sha1(signature_string.encode('utf-8')).hexdigest()

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
            "wsb_return_format": "json"
        }

        # API URL
        api_url = "https://securesandbox.webpay.by/api/v1/payment"

        # Выполняем запрос на создание платежа
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # Возвращаем URL для оплаты
            return {
                "invoiceUrl": data.get("data", {}).get("redirectUrl"),
                "wt": data.get("data", {}).get("wt")
            }

    @staticmethod
    def verify_webhook_signature(params: dict, secret_key: str) -> bool:
        """
        Проверяет подпись webhook уведомления

        Args:
            params: Параметры из POST запроса
            secret_key: Secret key от WebPay

        Returns:
            True если подпись верна
        """
        received_signature = params.get('wsb_signature', '')

        # Формируем строку для проверки подписи
        # Порядок полей важен!
        fields = [
            params.get('batch_timestamp', ''),
            params.get('currency_id', ''),
            params.get('amount', ''),
            params.get('payment_method', ''),
            params.get('order_id', ''),
            params.get('site_order_id', ''),
            params.get('transaction_id', ''),
            params.get('payment_type', ''),
            params.get('rrn', ''),
            secret_key
        ]

        string_to_sign = ''.join(str(f) for f in fields)

        # Вычисляем MD5
        expected_signature = hashlib.md5(string_to_sign.encode('utf-8')).hexdigest()

        return expected_signature == received_signature


# Lazy initialization - создаем только при первом использовании
_webpay_instance = None


def get_webpay_api() -> WebPayAPI:
    """Возвращает экземпляр WebPayAPI (создает при первом вызове)"""
    global _webpay_instance
    if _webpay_instance is None:
        _webpay_instance = WebPayAPI()
    return _webpay_instance