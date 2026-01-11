"""
Скрипт для восстановления базы данных из Excel файла
Использование: python -m shared.db.from_xlsx
"""
import asyncio
from datetime import datetime
from pathlib import Path

import openpyxl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shared.core.logger import get_logger
from shared.db.models import (
    Download,
    Media,
    Payment,
    ReferralReward,
    ReferralRewardStatus,
    ServiceType,
    Subscription,
    SubscriptionType,
    User,
    UserRole,
)
from shared.db.session import get_session

# Setup logger
logger = get_logger(__name__)


async def import_users(sheet, session):
    """Импорт пользователей из листа Users (tg_id — источник истины)"""
    logger.info("Импорт пользователей...")

    headers = [cell.value for cell in sheet[1]]

    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue

        data = dict(zip(headers, row))

        tg_id = data.get("tg_id")
        if not tg_id:
            continue

        # Проверяем существование пользователя ТОЛЬКО по tg_id
        existing = await session.scalar(select(User).where(User.tg_id == tg_id))

        if existing:
            skipped += 1
            continue

        # ❗ НЕ передаём id — база сама назначит корректный
        user = User(
            tg_id=tg_id,
            username=data.get("username"),
            role=UserRole(data["role"]) if data.get("role") else UserRole.USER,
            credits=data.get("credits", 0) or 0,
            referral_code=data.get("referral_code"),
            created_at=data.get("created_at") or datetime.utcnow(),
        )

        session.add(user)
        added += 1

    await session.commit()
    logger.info(f"Users: Добавлено: {added}, Пропущено: {skipped}")


async def import_media(sheet, session):
    """Импорт медиа из листа Media"""
    logger.info("Импорт медиа...")

    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue

        data = dict(zip(headers, row))

        # Проверяем существование по URL
        existing = await session.scalar(select(Media).where(Media.url == data["url"]))

        if existing:
            skipped += 1
            continue

        media = Media(
            id=data["id"],
            url=data["url"],
            file_type=data.get("file_type"),
            created_at=data.get("created_at") or datetime.utcnow(),
        )

        session.add(media)
        added += 1

    await session.commit()
    logger.info(f"Media: Добавлено: {added}, Пропущено: {skipped}")


async def import_downloads(sheet, session):
    """Импорт скачиваний из листа Downloads"""
    logger.info("Импорт скачиваний...")

    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue

        data = dict(zip(headers, row))

        # Проверяем существование
        existing = await session.scalar(select(Download).where(Download.id == data["id"]))

        if existing:
            skipped += 1
            continue

        download = Download(
            id=data["id"],
            user_id=data["user_id"],
            media_id=data["media_id"],
            subscription_id=data.get("subscription_id"),
            downloaded_at=data.get("downloaded_at") or datetime.utcnow(),
            paid=bool(data.get("paid", False)),
            service_type=ServiceType(data["service_type"]) if data.get("service_type") else None,
        )

        session.add(download)
        added += 1

    await session.commit()
    logger.info(f"Downloads: Добавлено: {added}, Пропущено: {skipped}")


async def import_payments(sheet, session):
    """Импорт платежей из листа Payments"""
    logger.info("Импорт платежей...")

    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue

        data = dict(zip(headers, row))

        # Проверяем по invoice_id
        if data.get("invoice_id"):
            existing = await session.scalar(
                select(Payment).where(Payment.invoice_id == data["invoice_id"])
            )
            if existing:
                skipped += 1
                continue

        payment = Payment(
            id=data["id"],
            user_id=data["user_id"],
            amount=data["amount"],
            currency=data.get("currency", "USDT"),
            status=data.get("status", "pending"),
            invoice_id=data.get("invoice_id"),
            plan_key=data["plan_key"],
            created_at=data.get("created_at") or datetime.utcnow(),
        )

        session.add(payment)
        added += 1

    await session.commit()
    logger.info(f"Payments: Добавлено: {added}, Пропущено: {skipped}")


async def import_subscriptions(sheet, session):
    """Импорт подписок из листа Subscriptions"""
    logger.info("Импорт подписок...")

    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue

        data = dict(zip(headers, row))

        # Проверяем существование
        existing = await session.scalar(select(Subscription).where(Subscription.id == data["id"]))

        if existing:
            skipped += 1
            continue

        subscription = Subscription(
            id=data["id"],
            user_id=data["user_id"],
            subscription_type=SubscriptionType(data["subscription_type"]),
            service_type=ServiceType(data["service_type"])
            if data.get("service_type")
            else ServiceType.ALL,
            total_limit=data.get("total_limit"),
            daily_limit=data.get("daily_limit"),
            used_total=data.get("used_total", 0) or 0,
            used_today=data.get("used_today", 0) or 0,
            last_reset_date=data.get("last_reset_date"),
            start_date=data.get("start_date") or datetime.utcnow(),
            end_date=data["end_date"],
            is_active=bool(data.get("is_active", True)),
            payment_id=data.get("payment_id"),
            created_at=data.get("created_at") or datetime.utcnow(),
            updated_at=data.get("updated_at") or datetime.utcnow(),
        )

        session.add(subscription)
        added += 1

    await session.commit()
    logger.info(f"Subscriptions: Добавлено: {added}, Пропущено: {skipped}")


async def import_referral_rewards(sheet, session):
    """Импорт реферальных вознаграждений из листа ReferralRewards"""
    logger.info("Импорт реферальных вознаграждений...")

    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue

        data = dict(zip(headers, row))

        # Проверяем существование
        existing = await session.scalar(
            select(ReferralReward).where(ReferralReward.id == data["id"])
        )

        if existing:
            skipped += 1
            continue

        reward = ReferralReward(
            id=data["id"],
            referrer_id=data["referrer_id"],
            referred_id=data["referred_id"],
            reward_type=data["reward_type"],
            reward_value=data.get("reward_value"),
            status=ReferralRewardStatus(data["status"])
            if data.get("status")
            else ReferralRewardStatus.PENDING,
            condition_met=bool(data.get("condition_met", False)),
            condition_date=data.get("condition_date"),
            created_at=data.get("created_at") or datetime.utcnow(),
            rewarded_at=data.get("rewarded_at"),
        )

        session.add(reward)
        added += 1

    await session.commit()
    logger.info(f"ReferralRewards: Добавлено: {added}, Пропущено: {skipped}")


async def restore_database(xlsx_path: str):
    """Основная функция восстановления базы данных"""

    logger.info("=" * 60)
    logger.info("ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ИЗ EXCEL")
    logger.info("=" * 60)

    # Проверяем существование файла
    file_path = Path(xlsx_path)
    if not file_path.exists():
        logger.error(f"Файл не найден: {xlsx_path}")
        raise FileNotFoundError(f"Файл не найден: {xlsx_path}")

    logger.info(f"Файл: {xlsx_path}")

    # Открываем Excel файл
    try:
        wb = openpyxl.load_workbook(xlsx_path)
        logger.info(f"Excel файл загружен")
        logger.info(f"Листов в файле: {len(wb.sheetnames)}")
    except Exception as e:
        logger.error(f"Ошибка при открытии файла: {e}", exc_info=True)
        raise

    # Импортируем данные в правильном порядке (из-за внешних ключей)
    async for session in get_session():
        try:
            # 1. Users (независимая таблица)
            if "Users" in wb.sheetnames:
                await import_users(wb["Users"], session)

            # 2. Media (независимая таблица)
            if "Media" in wb.sheetnames:
                await import_media(wb["Media"], session)

            # 3. Payments (зависит от Users)
            if "Payments" in wb.sheetnames:
                await import_payments(wb["Payments"], session)

            # 4. Subscriptions (зависит от Users и Payments)
            if "Subscriptions" in wb.sheetnames:
                await import_subscriptions(wb["Subscriptions"], session)

            # 5. Downloads (зависит от Users, Media, Subscriptions)
            if "Downloads" in wb.sheetnames:
                await import_downloads(wb["Downloads"], session)

            # 6. ReferralRewards (зависит от Users)
            if "ReferralRewards" in wb.sheetnames:
                await import_referral_rewards(wb["ReferralRewards"], session)

            logger.info("=" * 60)
            logger.info("ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Ошибка при импорте: {e}", exc_info=True)
            await session.rollback()
            raise
