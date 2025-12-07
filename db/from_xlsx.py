"""
Скрипт для восстановления базы данных из Excel файла
Использование: python -m db.from_xlsx <file.xlsx>
Правила:
- tg_id из Excel — единственный источник истины для пользователей
- id из Excel не используется для назначения user.id (БД сама назначает)
- все внешние связи (user_id, media_id, payment_id, subscription_id и т.д.)
  сопоставляются через внутренний маппинг old_id -> new_id
"""
import asyncio
import openpyxl
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from db.session import get_session
from db.models import (
    User, UserRole, Media, Download, Payment,
    Subscription, SubscriptionType, ServiceType,
    ReferralReward, ReferralRewardStatus
)

# Маппинги: excel_id -> db_id
USER_ID_MAP: dict = {}
MEDIA_ID_MAP: dict = {}
PAYMENT_ID_MAP: dict = {}
SUBSCRIPTION_ID_MAP: dict = {}
# (не обязательно маппить downloads/rewards по id, если не нужно)


async def safe_commit(session):
    try:
        await session.commit()
        return True
    except IntegrityError as e:
        await session.rollback()
        print(f"   [WARN] IntegrityError при commit: {getattr(e, 'orig', e)}")
        return False
    except Exception as e:
        await session.rollback()
        print(f"   [ERROR] Ошибка при commit: {e}")
        return False


async def import_users(sheet, session):
    """Импорт пользователей: ключ — tg_id. id из Excel игнорируем для назначения PK."""
    print("\n[IMPORT] Импорт пользователей...")
    headers = [cell.value for cell in sheet[1]]

    added = 0
    updated = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))

        tg_id = data.get("tg_id")
        old_id = data.get("id")

        if not tg_id:
            skipped += 1
            continue

        # Ищем пользователя только по tg_id
        user = await session.scalar(select(User).where(User.tg_id == tg_id))

        if user:
            # Можно обновить поля, если нужно (не перезаписываем пустыми значениями)
            if data.get("username"):
                user.username = data.get("username")
            if data.get("role"):
                user.role = UserRole(data["role"])
            if data.get("credits") is not None:
                user.credits = data.get("credits")
            if data.get("referral_code"):
                user.referral_code = data.get("referral_code")
            updated += 1
        else:
            # Создаём нового пользователя — НЕ указываем id, БД назначит его сама
            user = User(
                tg_id=tg_id,
                username=data.get("username"),
                role=UserRole(data["role"]) if data.get("role") else UserRole.USER,
                credits=(data.get("credits", 0) or 0),
                referral_code=data.get("referral_code"),
                created_at=(data.get("created_at") or datetime.utcnow())
            )
            session.add(user)
            # flush чтобы получить user.id до коммита
            await session.flush()
            added += 1

        # сохраняем маппинг old_id -> новый id (если в Excel указан old_id)
        if old_id is not None:
            USER_ID_MAP[old_id] = user.id

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Обновлено: {updated}, Пропущено: {skipped}")


async def import_media(sheet, session):
    """Импорт медиа. Ключ — url. id из Excel не используется при конфликте."""
    print("\n[IMPORT] Импорт медиа...")
    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))
        url = data.get("url")
        old_id = data.get("id")

        if not url:
            skipped += 1
            continue

        media = await session.scalar(select(Media).where(Media.url == url))
        if media:
            # уже есть — используем существующий
            if old_id is not None:
                MEDIA_ID_MAP[old_id] = media.id
            skipped += 1
            continue

        # создаём новый медиа (не указываем id; БД назначит)
        media = Media(
            url=url,
            file_type=data.get("file_type"),
            created_at=(data.get("created_at") or datetime.utcnow())
        )
        session.add(media)
        await session.flush()
        added += 1

        if old_id is not None:
            MEDIA_ID_MAP[old_id] = media.id

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Пропущено: {skipped}")


async def import_payments(sheet, session):
    """Импорт платежей. Связь по user через USER_ID_MAP. invoice_id уникален."""
    print("\n[IMPORT] Импорт платежей...")
    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))
        old_id = data.get("id")
        excel_user_id = data.get("user_id")

        new_user_id = USER_ID_MAP.get(excel_user_id)
        if not new_user_id:
            # если не нашли user по маппингу — пропускаем
            print(f"   [WARN] Payment пропущен: user_id {excel_user_id} не найден в маппинге")
            skipped += 1
            continue

        invoice = data.get("invoice_id")
        if invoice:
            exists = await session.scalar(select(Payment).where(Payment.invoice_id == invoice))
            if exists:
                skipped += 1
                # если exists — можно маппить old_id -> exists.id
                if old_id is not None:
                    PAYMENT_ID_MAP[old_id] = exists.id
                continue

        payment = Payment(
            user_id=new_user_id,
            amount=data.get("amount"),
            currency=data.get("currency", "USDT"),
            status=data.get("status", "pending"),
            invoice_id=invoice,
            plan_key=data.get("plan_key"),
            created_at=(data.get("created_at") or datetime.utcnow())
        )
        session.add(payment)
        await session.flush()
        added += 1

        if old_id is not None:
            PAYMENT_ID_MAP[old_id] = payment.id

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Пропущено: {skipped}")


async def import_subscriptions(sheet, session):
    """Импорт подписок. user_id и payment_id переводим через маппинг."""
    print("\n[IMPORT] Импорт подписок...")
    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))
        old_id = data.get("id")
        excel_user_id = data.get("user_id")
        excel_payment_id = data.get("payment_id")

        new_user_id = USER_ID_MAP.get(excel_user_id)
        if not new_user_id:
            print(f"   [WARN] Subscription пропущена: user_id {excel_user_id} не найден")
            skipped += 1
            continue

        new_payment_id = None
        if excel_payment_id is not None:
            new_payment_id = PAYMENT_ID_MAP.get(excel_payment_id)
            if new_payment_id is None:
                # возможно в Excel payment ещё не импортирован — пропускаем связь
                print(f"   [WARN] Subscription: payment_id {excel_payment_id} не найден, поле оставлено пустым")

        subscription = Subscription(
            user_id=new_user_id,
            subscription_type=SubscriptionType(data["subscription_type"]) if data.get("subscription_type") else None,
            service_type=ServiceType(data["service_type"]) if data.get("service_type") else ServiceType.ALL,
            total_limit=data.get("total_limit"),
            daily_limit=data.get("daily_limit"),
            used_total=(data.get("used_total", 0) or 0),
            used_today=(data.get("used_today", 0) or 0),
            last_reset_date=data.get("last_reset_date"),
            start_date=(data.get("start_date") or datetime.utcnow()),
            end_date=data.get("end_date"),
            is_active=bool(data.get("is_active", True)),
            payment_id=new_payment_id,
            created_at=(data.get("created_at") or datetime.utcnow()),
            updated_at=(data.get("updated_at") or datetime.utcnow())
        )
        session.add(subscription)
        await session.flush()
        added += 1

        if old_id is not None:
            SUBSCRIPTION_ID_MAP[old_id] = subscription.id

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Пропущено: {skipped}")


async def import_downloads(sheet, session):
    """Импорт скачиваний. user_id и media_id и subscription_id переводим через маппинг."""
    print("\n[IMPORT] Импорт скачиваний...")
    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))

        excel_user_id = data.get("user_id")
        excel_media_id = data.get("media_id")
        excel_subscription_id = data.get("subscription_id")

        new_user_id = USER_ID_MAP.get(excel_user_id)
        if not new_user_id:
            print(f"   [WARN] Download пропущен: user_id {excel_user_id} не найден")
            skipped += 1
            continue

        new_media_id = MEDIA_ID_MAP.get(excel_media_id) if excel_media_id is not None else None
        if excel_media_id is not None and new_media_id is None:
            print(f"   [WARN] Download: media_id {excel_media_id} не найден, пропускаем")
            skipped += 1
            continue

        new_subscription_id = None
        if excel_subscription_id is not None:
            new_subscription_id = SUBSCRIPTION_ID_MAP.get(excel_subscription_id)
            if new_subscription_id is None:
                print(f"   [WARN] Download: subscription_id {excel_subscription_id} не найден, оставляем пустым")

        download = Download(
            user_id=new_user_id,
            media_id=new_media_id,
            subscription_id=new_subscription_id,
            downloaded_at=(data.get("downloaded_at") or datetime.utcnow()),
            paid=bool(data.get("paid", False)),
            service_type=ServiceType(data["service_type"]) if data.get("service_type") else None
        )
        session.add(download)
        added += 1

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Пропущено: {skipped}")


async def import_referral_rewards(sheet, session):
    """Импорт реферальных вознаграждений: переводим referrer_id/referred_id через USER_ID_MAP."""
    print("\n[IMPORT] Импорт реферальных вознаграждений...")
    headers = [cell.value for cell in sheet[1]]
    added = 0
    skipped = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        data = dict(zip(headers, row))

        excel_referrer = data.get("referrer_id")
        excel_referred = data.get("referred_id")

        new_referrer = USER_ID_MAP.get(excel_referrer)
        new_referred = USER_ID_MAP.get(excel_referred)

        if not new_referrer or not new_referred:
            print(f"   [WARN] ReferralReward пропущен: referrer {excel_referrer} or referred {excel_referred} not found")
            skipped += 1
            continue

        reward = ReferralReward(
            referrer_id=new_referrer,
            referred_id=new_referred,
            reward_type=data.get("reward_type"),
            reward_value=data.get("reward_value"),
            status=ReferralRewardStatus(data["status"]) if data.get("status") else ReferralRewardStatus.PENDING,
            condition_met=bool(data.get("condition_met", False)),
            condition_date=data.get("condition_date"),
            created_at=(data.get("created_at") or datetime.utcnow()),
            rewarded_at=data.get("rewarded_at")
        )
        session.add(reward)
        added += 1

    await safe_commit(session)
    print(f"   OK: Добавлено: {added}, Пропущено: {skipped}")


async def refresh_sequence(session, table_name: str, pk: str = 'id'):
    """
    Устанавливает sequence (если есть) в значение >= max(id) в таблице,
    чтобы следующий INSERT без id не конфликтовал.
    """
    try:
        result = await session.execute(text(f"SELECT COALESCE(MAX({pk}), 0) FROM {table_name}"))
        max_id = result.scalar_one()
        if max_id is None:
            max_id = 0
        # pg_get_serial_sequence вернёт имя sequence или NULL
        seq_sql = text("SELECT pg_get_serial_sequence(:table, :pk) as seq")
        res = await session.execute(seq_sql.bindparams(table=table_name, pk=pk))
        seq_name = res.scalar_one()
        if seq_name:
            await session.execute(text(f"SELECT setval(:seq, :val, true)").bindparams(seq=seq_name, val=max_id))
            await session.commit()
            print(f"   SEQ: Обновлена последовательность для {table_name} -> {max_id}")
        else:
            # нет serial/identity — ничего не делаем
            print(f"   SEQ: sequence для {table_name}.{pk} не найдена, пропущено")
    except Exception as e:
        await session.rollback()
        print(f"   SEQ: Не удалось обновить sequence для {table_name}: {e}")


async def restore_database(xlsx_path: str):
    print("=" * 60)
    print("ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ИЗ EXCEL")
    print("=" * 60)

    file_path = Path(xlsx_path)
    if not file_path.exists():
        print(f"[ERROR] Файл не найден: {xlsx_path}")
        return

    print(f"\n[INFO] Файл: {xlsx_path}")

    try:
        wb = openpyxl.load_workbook(xlsx_path)
        print(f"[OK] Excel файл загружен")
        print(f"[INFO] Листов в файле: {len(wb.sheetnames)}")
    except Exception as e:
        print(f"[ERROR] Ошибка при открытии файла: {e}")
        return

    async for session in get_session():
        try:
            # 1. Users (независимая таблица)
            if "Users" in wb.sheetnames:
                await import_users(wb["Users"], session)
            else:
                print("   [INFO] Лист Users отсутствует")

            # 2. Media (независимая таблица)
            if "Media" in wb.sheetnames:
                await import_media(wb["Media"], session)
            else:
                print("   [INFO] Лист Media отсутствует")

            # 3. Payments (зависит от Users)
            if "Payments" in wb.sheetnames:
                await import_payments(wb["Payments"], session)
            else:
                print("   [INFO] Лист Payments отсутствует")

            # 4. Subscriptions (зависит от Users и Payments)
            if "Subscriptions" in wb.sheetnames:
                await import_subscriptions(wb["Subscriptions"], session)
            else:
                print("   [INFO] Лист Subscriptions отсутствует")

            # 5. Downloads (зависит от Users, Media, Subscriptions)
            if "Downloads" in wb.sheetnames:
                await import_downloads(wb["Downloads"], session)
            else:
                print("   [INFO] Лист Downloads отсутствует")

            # 6. ReferralRewards (зависит от Users)
            if "ReferralRewards" in wb.sheetnames:
                await import_referral_rewards(wb["ReferralRewards"], session)
            else:
                print("   [INFO] Лист ReferralRewards отсутствует")

            # Обновляем последовательности (если использовались serial/identity)
            seq_tables = ["users", "media", "payments", "subscriptions", "downloads", "referral_rewards"]
            for t in seq_tables:
                await refresh_sequence(session, t, 'id')

            print("\n" + "=" * 60)
            print("ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
            print("=" * 60)

        except Exception as e:
            print(f"\n[ERROR] Ошибка при импорте: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m db.from_xlsx <file.xlsx>")
        sys.exit(1)

    path = sys.argv[1]
    asyncio.run(restore_database(path))
