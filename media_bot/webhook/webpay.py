import json
import logging
from urllib.parse import parse_qs

from aiogram.enums.parse_mode import ParseMode
from fastapi import APIRouter, Request, Response

from media_bot.config import WEBPAY_SIGNING_KEY
from media_bot.handlers.messages import PERPETUAL_CREDITS_PURCHASED, SUBSCRIPTION_ACTIVATED
from media_bot.services import BotServices
from media_bot.utils.price_loader import load_subscription_plans
from media_bot.webpay_utils import get_webpay_api
from shared.db.models import ServiceType, SubscriptionType
from shared.db.repositories import PaymentRepository, SubscriptionRepository, UserRepository
from shared.db.session import get_session

router = APIRouter()
logger = logging.getLogger(__name__)


async def handle_perpetual_credits_purchase(session, user_id: int, order_id: str, plan_key: str):
    """
    Обработка покупки несгораемых кредитов (без создания подписки).

    Args:
        session: Database session
        user_id: Telegram user ID
        order_id: WebPay order ID
        plan_key: Формат "perpetual_credits_{quantity}"
    """
    logger.info(
        f"💎 [WEBPAY-PERPETUAL] Processing perpetual credits purchase: user_id={user_id}, order_id={order_id}, plan_key={plan_key}"
    )

    # Извлечь количество из plan_key
    try:
        quantity = int(plan_key.split("_")[-1])
        logger.info(f"💎 [WEBPAY-PERPETUAL] Extracted quantity: {quantity}")
    except (ValueError, IndexError) as e:
        logger.error(
            f"⚠️ [WEBPAY-PERPETUAL] Invalid perpetual credits plan_key: {plan_key}, error: {e}"
        )
        return

    # Находим пользователя
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(user_id)
    if not user:
        logger.warning(f"⚠️ [WEBPAY] Пользователь {user_id} не найден")
        return

    # Проверяем платеж в БД
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_by_invoice_id(order_id)
    if not payment:
        logger.warning(f"⚠️ [WEBPAY] Платеж с order_id {order_id} не найден в БД")
        return

    # Проверяем, что платеж еще не обработан
    if payment.status == "success":
        logger.info(f"✅ [WEBPAY] Платеж {order_id} уже обработан ранее (perpetual credits)")
        return

    # Добавить кредиты пользователю
    old_credits = user.credits
    user.credits += quantity
    await session.commit()

    # Отметить платёж как успешный
    await payment_repo.mark_success(order_id)

    logger.info(
        f"✅ [WEBPAY] Perpetual credits: {quantity} credits added to user {user_id} "
        f"(was: {old_credits}, now: {user.credits})"
    )

    # Отправить уведомление
    if BotServices.bot:
        try:
            # Обновляем данные пользователя из сессии
            await session.refresh(user)

            message = PERPETUAL_CREDITS_PURCHASED.format(
                quantity=quantity, total_credits=user.credits
            )
            await BotServices.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logger.info(f"✅ [WEBPAY] Perpetual credits notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"⚠️ [WEBPAY] Failed to send perpetual credits notification: {e}")
    else:
        logger.warning(f"⚠️ [WEBPAY] BotServices.bot not initialized, notification not sent")


@router.post("/api/webpay/webhook")
async def webpay_webhook(request: Request):
    """
    Webhook для получения уведомлений о платежах от WebPay

    Документация: https://docs.webpay.by/en/paymentIntegration/cardIntegration/paymentNotification/
    """
    try:
        # Читаем body и парсим URL-encoded данные
        body = await request.body()
        body_str = body.decode("utf-8")

        # Парсим URL-encoded данные
        parsed = parse_qs(body_str)
        # parse_qs возвращает списки значений, берем первый элемент
        params = {k: v[0] if v else None for k, v in parsed.items()}

        print(f"💳 [WEBPAY] Получено уведомление: {params}")

        # Проверяем подпись
        webpay_api = get_webpay_api()
        if not webpay_api.verify_webhook_signature(params, WEBPAY_SIGNING_KEY):
            logger.warning(f"❌ [WEBPAY] Неверная подпись! Params: {params}")
            return Response(
                content='{"code": 400, "message": "Invalid signature"}', status_code=400
            )

        # Извлекаем данные
        payment_type = params.get("payment_type")
        order_id = params.get("site_order_id")
        transaction_id = params.get("transaction_id")
        amount = params.get("amount")
        currency = params.get("currency_id")

        # Проверяем, что платеж успешный (payment_type = 1 или 4)
        if payment_type not in ["1", "4"]:
            logger.warning(f"⚠️ [WEBPAY] Неуспешный платеж: type={payment_type}, order={order_id}")
            return Response(content='{"code": 200}', status_code=200)

        print(
            f"💰 [WEBPAY] Успешный платеж! Order: {order_id}, Amount: {amount} {currency}, TX: {transaction_id}"
        )

        # Загружаем конфигурацию планов
        try:
            plans = load_subscription_plans()
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"❌ [WEBPAY] Failed to load subscription plans: {e}")
            return Response(content='{"error": "Price list not found"}', status_code=500)

        # Обрабатываем платеж
        async for session in get_session():
            # Извлекаем user_id и plan_key из order_id (формат: USER_{user_id}_{plan_key}_{uuid})
            try:
                if order_id and order_id.startswith("USER_"):
                    parts = order_id.split("_")
                    logger.info(f"💎 [WEBPAY] Parsing order_id: {order_id} -> parts={parts}")
                    user_id = int(parts[1])
                    plan_key = "_".join(parts[2:-1]) if len(parts) > 3 else None
                    logger.info(f"💎 [WEBPAY] Parsed: user_id={user_id}, plan_key={plan_key}")
                else:
                    logger.warning(f"⚠️ [WEBPAY] Некорректный формат order_id: {order_id}")
                    return Response(content='{"code": 200}', status_code=200)
            except (IndexError, ValueError) as e:
                logger.warning(f"⚠️ [WEBPAY] Не удалось извлечь данные из {order_id}: {e}")
                return Response(content='{"code": 200}', status_code=200)

            # Проверяем, является ли это покупкой perpetual credits
            if plan_key and plan_key.startswith("perpetual_credits_"):
                logger.info(
                    f"💎 [WEBPAY] Detected perpetual credits purchase, delegating to handler"
                )
                # Обрабатываем покупку несгораемых кредитов
                await handle_perpetual_credits_purchase(session, user_id, order_id, plan_key)
                return Response(content='{"code": 200}', status_code=200)

            # Находим пользователя
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(user_id)
            if not user:
                logger.warning(f"⚠️ [WEBPAY] Пользователь {user_id} не найден")
                return Response(content='{"code": 200}', status_code=200)

            # Проверяем платеж в БД
            payment_repo = PaymentRepository(session)
            payment = await payment_repo.get_by_invoice_id(order_id)
            if not payment:
                logger.warning(f"⚠️ [WEBPAY] Платеж с order_id {order_id} не найден в БД")
                return Response(content='{"code": 200}', status_code=200)

            # Проверяем, что платеж еще не обработан
            if payment.status == "success":
                logger.info(f"✅ [WEBPAY] Платеж {order_id} уже обработан ранее")
                return Response(content='{"code": 200}', status_code=200)

            # Получаем план из JSON
            plan_data = plans.get(plan_key)
            if not plan_data:
                logger.warning(f"⚠️ [WEBPAY] План {plan_key} не найден в конфигурации")
                return Response(content='{"code": 200}', status_code=200)

            # Создаем подписку
            subscription_type = SubscriptionType[plan_data["subscription_type"]]
            period_days = plan_data["period_days"]
            total_limit = plan_data.get("total_limit")
            daily_limit = plan_data.get("daily_limit")

            subscription_repo = SubscriptionRepository(session)
            subscription = await subscription_repo.create_subscription_with_credits(
                user_id=user.id,
                subscription_type=subscription_type,
                service_type=ServiceType.ALL,
                total_limit=total_limit,
                daily_limit=daily_limit,
                days=period_days,
                payment_id=payment.id,
            )

            # Помечаем платеж как успешный
            await payment_repo.mark_success(order_id)

            logger.info(
                f"✅ [WEBPAY] Подписка {plan_key} создана: user={user_id}, period={period_days}д, limits=(total={total_limit}, daily={daily_limit})"
            )

            # Отправляем уведомление пользователю
            if BotServices.bot:
                try:
                    # Обновляем данные пользователя из сессии
                    await session.refresh(user)

                    # Форматируем дату окончания подписки
                    end_date = subscription.end_date.strftime("%d.%m.%Y %H:%M")

                    # Формируем сообщение
                    message = SUBSCRIPTION_ACTIVATED.format(
                        subscription_type=plan_data["name"],
                        period_days=period_days,
                        credits=user.credits,
                        end_date=end_date,
                    )

                    # Отправляем сообщение пользователю
                    await BotServices.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                    logger.info(f"✅ [WEBPAY] Уведомление отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(
                        f"⚠️ [WEBPAY] Не удалось отправить уведомление пользователю {user_id}: {e}"
                    )
            else:
                logger.warning(
                    f"⚠️ [WEBPAY] BotServices.bot не инициализирован, уведомление не отправлено"
                )

        # Возвращаем успешный ответ
        return Response(content='{"code": 200}', status_code=200)

    except Exception as e:
        logger.error(f"❌ [WEBPAY] Ошибка обработки webhook: {e}", exc_info=True)
        import traceback

        traceback.print_exc()
        return Response(content='{"code": 500}', status_code=200)
