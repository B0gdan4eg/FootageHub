import hashlib
import httpx
from bot.config import (
    WEBPAY_RESOURCE_ID,
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
        self.sandbox = WEBPAY_SANDBOX

        if self.sandbox:
            self.base_url = "https://sandbox.webpay.by"
        else:
            self.base_url = "https://billing.webpay.by"

        if not self.auth_token:
            raise ValueError(
                "WEBPAY_AUTH_TOKEN не найден в .env! "
                "Запустите get_webpay_token.py для получения токена."
            )

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
        Создает счет для оплаты через Billing API

        Args:
            order_id: Уникальный номер заказа
            amount: Сумма платежа в BYN
            description: Описание платежа
            return_url: URL для возврата после успешной оплаты
            cancel_url: URL для возврата при отмене
            notify_url: URL для webhook уведомлений

        Returns:
            dict с URL для перенаправления пользователя на оплату
        """
        # Вычисляем подпись для запроса
        seed = f"{self.merchant_id}{order_id}{amount}BYN{self.secret_key}"
        signature = hashlib.md5(seed.encode('utf-8')).hexdigest()

        # Формируем payload для создания платежа (form-data)
        payload = {
            "wsb_storeid": self.merchant_id,
            "wsb_store": self.merchant_id,
            "wsb_order_num": order_id,
            "wsb_currency_id": "BYN",
            "wsb_total": str(amount),
            "wsb_return_url": return_url,
            "wsb_cancel_return_url": cancel_url,
            "wsb_notify_url": notify_url,
            "wsb_invoice_item_name[0]": description,
            "wsb_invoice_item_quantity[0]": "1",
            "wsb_invoice_item_price[0]": str(amount),
            "wsb_test": "1" if self.sandbox else "0",
            "wsb_signature": signature,
            "wsb_version": "2"
        }

        # Выполняем запрос на создание платежа (form POST)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.post(
                f"{self.base_url}/order/create",
                data=payload,  # form-data вместо JSON
                headers={
                    "Authorization": f"Bearer {self.auth_token}"
                },
                timeout=30.0
            )

            # Если редирект (302/303), то это успех - получаем URL оплаты
            if response.status_code in (302, 303):
                invoice_url = response.headers.get("Location")
                return {
                    "invoiceUrl": invoice_url,
                    "webpayInvoiceNumber": order_id,
                    "webpayInvoiceId": None
                }

            # Если 200, пробуем распарсить JSON ответ
            if response.status_code == 200:
                try:
                    data = response.json()
                    return {
                        "invoiceUrl": data.get("url") or data.get("payment_url") or data.get("invoiceUrl"),
                        "webpayInvoiceNumber": data.get("invoice_number") or order_id,
                        "webpayInvoiceId": data.get("invoice_id") or data.get("transaction_id")
                    }
                except Exception:
                    # Если не JSON, возможно это HTML с формой
                    pass

            # Если ничего не сработало, поднимаем ошибку
            response.raise_for_status()
            raise ValueError(f"Неожиданный ответ от API: {response.text[:200]}")

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


# Singleton instance
webpay_api = WebPayAPI()