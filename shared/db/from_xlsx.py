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
    print(f"[IMPORT_USERS] Начало импорта пользователей...")
    logger.info("Импорт пользователей...")

    headers = [cell.value for cell in sheet[1]]
    print(f"[IMPORT_USERS] Заголовки: {headers}")

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
        # Конвертируем role в uppercase если это строка
        role_value = data.get("role")
        if role_value:
            if isinstance(role_value, str):
                role_value = role_value.upper()
            user_role = UserRole(role_value)
        else:
            user_role = UserRole.USER

        user = User(
            tg_id=tg_id,
            username=data.get("username"),
            role=user_role,
            credits=data.get("credits", 0) or 0,
            referral_code=data.get("referral_code"),
            created_at=data.get("created_at") or datetime.utcnow(),
        )

        session.add(user)
        added += 1

    print(f"[IMPORT_USERS] Коммит изменений в БД...")
    await session.commit()
    print(f"[IMPORT_USERS] Результат: Добавлено: {added}, Пропущено: {skipped}")
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

        # Проверяем существование download
        existing = await session.scalar(select(Download).where(Download.id == data["id"]))

        if existing:
            skipped += 1
            continue

        # Проверяем существование user_id в таблице users
        user_exists = await session.scalar(select(User).where(User.id == data["user_id"]))
        if not user_exists:
            print(
                f"[IMPORT_DOWNLOADS] Пропуск download id={data['id']}: user_id={data['user_id']} не найден"
            )
            skipped += 1
            continue

        # Проверяем существование media_id в таблице media
        media_exists = await session.scalar(select(Media).where(Media.id == data["media_id"]))
        if not media_exists:
            print(
                f"[IMPORT_DOWNLOADS] Пропуск download id={data['id']}: media_id={data['media_id']} не найден"
            )
            skipped += 1
            continue

        # Конвертируем service_type в uppercase если это строка
        service_type = None
        if data.get("service_type"):
            st_value = data["service_type"]
            if isinstance(st_value, str):
                st_value = st_value.upper()
            service_type = ServiceType(st_value)

        download = Download(
            id=data["id"],
            user_id=data["user_id"],
            media_id=data["media_id"],
            subscription_id=data.get("subscription_id"),
            downloaded_at=data.get("downloaded_at") or datetime.utcnow(),
            paid=bool(data.get("paid", False)),
            service_type=service_type,
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

        # Проверяем существование user_id
        user_exists = await session.scalar(select(User).where(User.id == data["user_id"]))
        if not user_exists:
            print(
                f"[IMPORT_PAYMENTS] Пропуск payment id={data['id']}: user_id={data['user_id']} не найден"
            )
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

        # Проверяем существование user_id
        user_exists = await session.scalar(select(User).where(User.id == data["user_id"]))
        if not user_exists:
            print(
                f"[IMPORT_SUBSCRIPTIONS] Пропуск subscription id={data['id']}: user_id={data['user_id']} не найден"
            )
            skipped += 1
            continue

        # Конвертируем subscription_type в uppercase если это строка
        sub_type_value = data["subscription_type"]
        if isinstance(sub_type_value, str):
            sub_type_value = sub_type_value.upper()
        subscription_type = SubscriptionType(sub_type_value)

        # Конвертируем service_type в uppercase если это строка
        if data.get("service_type"):
            svc_type_value = data["service_type"]
            if isinstance(svc_type_value, str):
                svc_type_value = svc_type_value.upper()
            service_type = ServiceType(svc_type_value)
        else:
            service_type = ServiceType.ALL

        subscription = Subscription(
            id=data["id"],
            user_id=data["user_id"],
            subscription_type=subscription_type,
            service_type=service_type,
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

        # Проверяем существование referrer_id
        referrer_exists = await session.scalar(select(User).where(User.id == data["referrer_id"]))
        if not referrer_exists:
            print(
                f"[IMPORT_REFERRAL_REWARDS] Пропуск reward id={data['id']}: referrer_id={data['referrer_id']} не найден"
            )
            skipped += 1
            continue

        # Проверяем существование referred_id
        referred_exists = await session.scalar(select(User).where(User.id == data["referred_id"]))
        if not referred_exists:
            print(
                f"[IMPORT_REFERRAL_REWARDS] Пропуск reward id={data['id']}: referred_id={data['referred_id']} не найден"
            )
            skipped += 1
            continue

        # Конвертируем status в uppercase если это строка
        status_value = data.get("status")
        if status_value:
            if isinstance(status_value, str):
                status_value = status_value.upper()
            reward_status = ReferralRewardStatus(status_value)
        else:
            reward_status = ReferralRewardStatus.PENDING

        reward = ReferralReward(
            id=data["id"],
            referrer_id=data["referrer_id"],
            referred_id=data["referred_id"],
            reward_type=data["reward_type"],
            reward_value=data.get("reward_value"),
            status=reward_status,
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

    print(f"[RESTORE] ========== НАЧАЛО ВОССТАНОВЛЕНИЯ ==========")
    logger.info("=" * 60)
    logger.info("ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ИЗ EXCEL")
    logger.info("=" * 60)

    # Проверяем существование файла
    file_path = Path(xlsx_path)
    print(f"[RESTORE] Проверка файла: {xlsx_path}")
    if not file_path.exists():
        print(f"[RESTORE] ERROR: Файл не найден!")
        logger.error(f"Файл не найден: {xlsx_path}")
        raise FileNotFoundError(f"Файл не найден: {xlsx_path}")

    print(f"[RESTORE] Файл найден: {xlsx_path}")
    logger.info(f"Файл: {xlsx_path}")

    # Открываем Excel файл
    try:
        print(f"[RESTORE] Открытие Excel файла...")
        wb = openpyxl.load_workbook(xlsx_path)
        print(f"[RESTORE] Excel файл загружен успешно!")
        print(f"[RESTORE] Листов в файле: {len(wb.sheetnames)}")
        print(f"[RESTORE] Список листов: {wb.sheetnames}")
        logger.info(f"Excel файл загружен")
        logger.info(f"Листов в файле: {len(wb.sheetnames)}")
    except Exception as e:
        print(f"[RESTORE] ERROR при открытии файла: {e}")
        import traceback

        traceback.print_exc()
        logger.error(f"Ошибка при открытии файла: {e}", exc_info=True)
        raise

    # Импортируем данные в правильном порядке (из-за внешних ключей)
    print(f"[RESTORE] Получение сессии БД...")
    async for session in get_session():
        try:
            print(f"[RESTORE] Сессия БД получена, начало импорта...")

            # 1. Users (независимая таблица)
            if "Users" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы Users...")
                await import_users(wb["Users"], session)
            else:
                print(f"[RESTORE] WARNING: Лист Users не найден")

            # 2. Media (независимая таблица)
            if "Media" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы Media...")
                await import_media(wb["Media"], session)
            else:
                print(f"[RESTORE] WARNING: Лист Media не найден")

            # 3. Payments (зависит от Users)
            if "Payments" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы Payments...")
                await import_payments(wb["Payments"], session)
            else:
                print(f"[RESTORE] WARNING: Лист Payments не найден")

            # 4. Subscriptions (зависит от Users и Payments)
            if "Subscriptions" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы Subscriptions...")
                await import_subscriptions(wb["Subscriptions"], session)
            else:
                print(f"[RESTORE] WARNING: Лист Subscriptions не найден")

            # 5. Downloads (зависит от Users, Media, Subscriptions)
            if "Downloads" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы Downloads...")
                await import_downloads(wb["Downloads"], session)
            else:
                print(f"[RESTORE] WARNING: Лист Downloads не найден")

            # 6. ReferralRewards (зависит от Users)
            if "ReferralRewards" in wb.sheetnames:
                print(f"[RESTORE] Импорт таблицы ReferralRewards...")
                await import_referral_rewards(wb["ReferralRewards"], session)
            else:
                print(f"[RESTORE] WARNING: Лист ReferralRewards не найден")

            print(f"[RESTORE] ========== ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО ==========")
            logger.info("=" * 60)
            logger.info("ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
            logger.info("=" * 60)

        except Exception as e:
            print(f"[RESTORE] CRITICAL ERROR при импорте: {e}")
            import traceback

            traceback.print_exc()
            logger.error(f"Ошибка при импорте: {e}", exc_info=True)
            await session.rollback()
            raise
