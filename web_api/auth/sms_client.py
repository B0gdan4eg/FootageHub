"""SMSC.ru SMS client for Russian phone verification."""

import logging
import random
from datetime import datetime, timedelta

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import SmsVerification
from web_api.config import config


def _generate_code() -> str:
    """Generate 6-digit verification code."""
    return f"{random.randint(100000, 999999)}"


async def _count_today_sms(db: AsyncSession, phone: str) -> int:
    """Count SMS sent to phone today."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(SmsVerification).where(
            and_(
                SmsVerification.phone == phone,
                SmsVerification.created_at >= today_start,
            )
        )
    )
    return len(result.scalars().all())


async def send_verification_sms(db: AsyncSession, phone: str) -> dict:
    """
    Generate a code, save it to DB and send SMS via SMSC.ru.

    Returns:
        {"status": "sent", "expires_in": 300} or raises ValueError
    """
    # Rate limit: макс 5 SMS в день
    count = await _count_today_sms(db, phone)
    if count >= config.SMS_MAX_PER_DAY:
        raise ValueError("Превышен дневной лимит SMS. Попробуйте завтра.")

    # Rate limit: 1 SMS в 60 сек (проверяем последний)
    result = await db.execute(
        select(SmsVerification)
        .where(SmsVerification.phone == phone)
        .order_by(SmsVerification.created_at.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last:
        cooldown_end = last.created_at + timedelta(seconds=config.SMS_COOLDOWN_SECONDS)
        if datetime.utcnow() < cooldown_end:
            remaining = int((cooldown_end - datetime.utcnow()).total_seconds())
            raise ValueError(f"Подождите {remaining} сек. перед повторной отправкой")

    code = _generate_code()
    expires_at = datetime.utcnow() + timedelta(seconds=300)

    # Сохраняем код в БД
    sms_record = SmsVerification(phone=phone, code=code, expires_at=expires_at)
    db.add(sms_record)
    await db.commit()

    # Отправляем SMS через SMSC.ru
    if config.SMSC_LOGIN and config.SMSC_PASSWORD:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://smsc.ru/sys/send.php",
                    params={
                        "login": config.SMSC_LOGIN,
                        "psw": config.SMSC_PASSWORD,
                        "phones": phone,
                        "mes": f"FootageHub: ваш код подтверждения {code}",
                        "fmt": "3",  # JSON response
                    },
                )
                data = resp.json()
                if "error" in data:
                    raise ValueError(f"SMSC error: {data['error']}")
        except httpx.HTTPError as e:
            raise ValueError(f"Не удалось отправить SMS: {e}") from e
    else:
        # В режиме разработки логируем код
        logging.getLogger(__name__).info(f"[DEV] SMS to {phone}: code={code}")

    return {"status": "sent", "expires_in": 300}


async def verify_sms_code(db: AsyncSession, phone: str, code: str) -> bool:
    """
    Verify SMS code. Marks it as used if valid.

    Returns:
        True if code is valid, False otherwise
    """
    now = datetime.utcnow()
    result = await db.execute(
        select(SmsVerification)
        .where(
            and_(
                SmsVerification.phone == phone,
                SmsVerification.code == code,
                SmsVerification.used == False,  # noqa: E712
                SmsVerification.expires_at > now,
            )
        )
        .order_by(SmsVerification.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if not record:
        return False

    record.used = True
    await db.commit()
    return True
