from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram import Bot

from db.models import User, Download, Media, Payment, UserRole, SubscriptionType, ServiceType, Subscription, ReferralReward
from db.session import get_session
from db.user_crud import get_all_users, count_active_subs, get_user_by_telegram_id
from db.downloaded_file_crud import count_total_downloads
from db.subscription_crud import create_subscription, delete_all_subscriptions
from sqlalchemy import select, update
from bot.state import AdminStates
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession
import openpyxl
import json
from pathlib import Path
from aiogram.filters import Command
from enum import Enum
from datetime import datetime, timezone
from bot.config import PRICE_LIST_PATH as PRICE_LIST

router = Router()


# Метод проверки роли админа
# ------------------------------------------------------------
async def is_admin(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль ADMIN.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.ADMIN
# ------------------------------------------------------------

# Роутер на коллбэк статистику по всем пользователям
# ------------------------------------------------------------
@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    from sqlalchemy import func

    async for session in get_session():
        total_users = len(await get_all_users(session))
        active_subs = await count_active_subs(session)
        total_downloads = await count_total_downloads(session)

        # Граница времени (начало сегодняшнего дня в UTC)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Новые пользователи с начала дня
        result = await session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
        new_users_today = result.scalar()

        # Загрузки с начала дня
        result = await session.execute(
            select(func.count(Download.id)).where(Download.downloaded_at >= today_start)
        )
        downloads_today = result.scalar()

        # Загрузки с Envato за сегодня
        result = await session.execute(
            select(func.count(Download.id)).where(
                Download.downloaded_at >= today_start,
                Download.service_type == ServiceType.ENVATO
            )
        )
        envato_downloads_today = result.scalar()

        # Загрузки с Freepik за сегодня
        result = await session.execute(
            select(func.count(Download.id)).where(
                Download.downloaded_at >= today_start,
                Download.service_type == ServiceType.FREEPIK
            )
        )
        freepik_downloads_today = result.scalar()

        # Общая сумма всех успешных платежей по валютам
        result = await session.execute(
            select(
                Payment.currency,
                func.coalesce(func.sum(Payment.amount), 0)
            ).where(Payment.status == "success").group_by(Payment.currency)
        )
        total_payments_by_currency = result.all()

        # Сумма платежей за сегодня по валютам
        result = await session.execute(
            select(
                Payment.currency,
                func.coalesce(func.sum(Payment.amount), 0)
            ).where(
                Payment.status == "success",
                Payment.created_at >= today_start
            ).group_by(Payment.currency)
        )
        payments_today_by_currency = result.all()

    # Форматируем суммы по валютам
    total_payments_text = "\n".join([f"   • {currency}: {amount:.2f}" for currency, amount in total_payments_by_currency]) if total_payments_by_currency else "   • Нет платежей"
    today_payments_text = "\n".join([f"   • {currency}: {amount:.2f}" for currency, amount in payments_today_by_currency]) if payments_today_by_currency else "   • Нет платежей"

    text = (
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🆕 Новых сегодня: {new_users_today}\n\n"
        f"🔐 Активных подписок: {active_subs}\n\n"
        f"⬇️ Всего скачиваний: {total_downloads}\n"
        f"📥 Сегодня: {downloads_today}\n"
        f"   • Envato: {envato_downloads_today}\n"
        f"   • Freepik: {freepik_downloads_today}\n\n"
        f"💰 Всего платежей:\n{total_payments_text}\n\n"
        f"💵 Сегодня:\n{today_payments_text}"
    )
    await callback.message.edit_text(text)
# ------------------------------------------------------------


# Роутер на коллбэк выдачи подписки - шаг 1: запрос ID пользователя
# ------------------------------------------------------------
@router.callback_query(F.data == "admin_give_subscription")
async def give_subscription_start(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_subscription_user_id)
    await callback.message.answer(
        "🆔 <b>Выдача подписки</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите выдать подписку:\n\n"
        "Отправьте 'q' для отмены",
        parse_mode="HTML"
    )
    await callback.answer()
# ------------------------------------------------------------

# Роутер на получение ID пользователя - шаг 2: выбор плана
# ------------------------------------------------------------
@router.message(AdminStates.waiting_for_subscription_user_id)
async def receive_subscription_user_id(message: types.Message, state: FSMContext):
    user_id_text = message.text.strip()

    if user_id_text.lower() == "q":
        await state.clear()
        return await message.answer("❌ Выдача подписки отменена.")

    if not user_id_text.isdigit():
        return await message.answer("❌ ID должен быть числом. Попробуйте снова или отправьте 'q' для отмены.")

    user_id = int(user_id_text)

    # Проверяем существование пользователя
    async for session in get_session():
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            return await message.answer(f"❌ Пользователь с ID {user_id} не найден в базе данных.")

    # Сохраняем ID в state
    await state.update_data(subscription_user_id=user_id)

    # Показываем выбор плана подписки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Monthly 150 (30 дней)", callback_data="sub_plan_monthly_150")],
        [InlineKeyboardButton(text="⚡ Daily 30 (30 дней)", callback_data="sub_plan_daily_30")],
        [InlineKeyboardButton(text="♾️ Unlimited (30 дней)", callback_data="sub_plan_unlimited")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="sub_plan_cancel")],
    ])

    await message.answer(
        f"✅ Пользователь найден: <b>{user_id}</b>\n\n"
        f"Выберите план подписки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_subscription_plan)
# ------------------------------------------------------------

# Роутер на выбор плана подписки - шаг 3: создание подписки
# ------------------------------------------------------------
@router.callback_query(AdminStates.waiting_for_subscription_plan, F.data.startswith("sub_plan_"))
async def create_subscription_for_user(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "sub_plan_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Выдача подписки отменена.")
        await callback.answer()
        return

    # Получаем сохраненный ID пользователя
    data = await state.get_data()
    user_id = data.get("subscription_user_id")

    if not user_id:
        await callback.message.edit_text("❌ Ошибка: ID пользователя не найден. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    # Определяем параметры подписки по выбранному плану
    plan_key = callback.data.replace("sub_plan_", "")

    if plan_key == "monthly_150":
        subscription_type = SubscriptionType.MONTHLY_150
        total_limit = 150
        daily_limit = None
        plan_name = "Monthly 150"
    elif plan_key == "daily_30":
        subscription_type = SubscriptionType.DAILY_30
        total_limit = None
        daily_limit = 30
        plan_name = "Daily 30"
    elif plan_key == "unlimited":
        subscription_type = SubscriptionType.UNLIMITED
        total_limit = None
        daily_limit = None
        plan_name = "Unlimited ♾️"
    else:
        await callback.message.edit_text("❌ Неизвестный план подписки.")
        await state.clear()
        await callback.answer()
        return

    # Создаем подписку
    async for session in get_session():
        user = await get_user_by_telegram_id(session, user_id)
        if not user:
            await callback.message.edit_text(f"❌ Пользователь с ID {user_id} не найден.")
            await state.clear()
            await callback.answer()
            return

        try:
            subscription = await create_subscription(
                session=session,
                user_id=user.id,
                subscription_type=subscription_type,
                service_type=ServiceType.ALL,
                total_limit=total_limit,
                daily_limit=daily_limit,
                days=30,
                payment_id=None  # Подписка выдана администратором
            )

            limit_text = "♾️ Безлимит" if plan_key == "unlimited" else (f"{total_limit} скачиваний" if total_limit else f"{daily_limit}/день")

            await callback.message.edit_text(
                f"✅ <b>Подписка успешно выдана!</b>\n\n"
                f"👤 Пользователь: <code>{user_id}</code>\n"
                f"📦 План: <b>{plan_name}</b>\n"
                f"📊 Лимит: {limit_text}\n"
                f"📅 Срок: 30 дней\n"
                f"🆔 ID подписки: <code>{subscription.id}</code>",
                parse_mode="HTML"
            )

            # Опционально: уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"🎁 <b>Вам выдана подписка!</b>\n\n"
                    f"📦 План: <b>{plan_name}</b>\n"
                    f"📊 Лимит: {limit_text}\n"
                    f"📅 Срок действия: 30 дней\n\n"
                    f"Приятного использования! 🚀",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[ADMIN] Не удалось отправить уведомление пользователю {user_id}: {e}")

        except Exception as e:
            await callback.message.edit_text(f"❌ Ошибка при создании подписки: {e}")
            print(f"[ADMIN] Ошибка создания подписки: {e}")
            import traceback
            traceback.print_exc()

    await state.clear()
    await callback.answer()
# ------------------------------------------------------------

# Временная команда для получения chat_id группы
# ------------------------------------------------------------
@router.message(Command("get_chat_id"))
async def get_chat_id_command(message: types.Message):
    """Показывает ID текущего чата (работает в группах и личных сообщениях)"""
    chat_type = message.chat.type
    chat_id = message.chat.id

    if chat_type in ["group", "supergroup"]:
        await message.answer(
            f"📋 <b>Информация о группе:</b>\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📛 Название: {message.chat.title}\n"
            f"📊 Тип: {chat_type}\n\n"
            f"Используйте этот Chat ID для ADMIN_CHAT_ID в .env",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"📋 <b>Информация о чате:</b>\n\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📊 Тип: {chat_type}",
            parse_mode="HTML"
        )
# ------------------------------------------------------------

# Роутер на текст вызов панели админа
# ------------------------------------------------------------
@router.message(Command("admin"))
async def admin_panel(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return await message.answer("⛔ У тебя нет доступа")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="admin_give_subscription")],
        [InlineKeyboardButton(text="👤 Назначить роль", callback_data="admin_assign_role")],
        [InlineKeyboardButton(text="💳 Загрузить цены", callback_data="admin_upload_prices")],
        [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="export_db")],
        [InlineKeyboardButton(text="🔄 Восстановить базу", callback_data="admin_restore_db")],
        [InlineKeyboardButton(text="🍪 Загрузить cookies", callback_data="admin_upload_cookies")],
        [InlineKeyboardButton(text="📦 Установить лимит всем", callback_data="admin_set_download_limit")],
        [InlineKeyboardButton(text="🗑️ Удалить все подписки", callback_data="admin_delete_all_subscriptions")],
        [InlineKeyboardButton(text="📢 Оповещение", callback_data="admin_broadcast")],
    ])
    await message.answer("📂 Панель администратора", reply_markup=keyboard)
    await state.clear()
# ------------------------------------------------------------

# Роутер на коллбэк выдача роли манагера
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "admin_assign_role")
async def assign_manager_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.answer("Введите Telegram ID пользователя, которому хотите назначить роль менеджера:")
    await callback.answer()
# ------------------------------------------------------------

# Роутер на коллбэк ввод ид для выдачи роли
# ------------------------------------------------------------
@router.message(AdminStates.waiting_for_user_id)
async def assign_manager(message: types.Message, state: FSMContext):
    user_id_text = message.text.strip()
    if user_id_text == "q":
        return await state.clear()
    if not user_id_text.isdigit():
        return await message.answer("❌ ID должен быть числом. Попробуйте снова.")

    user_id = int(user_id_text)

    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return await message.answer(f"❌ Пользователь с ID {user_id} не найден.")

        # Назначаем роль MANAGER
        await session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(role=UserRole.MANAGER)
        )
        await session.commit()

    await message.answer(f"✅ Пользователю с ID {user_id} назначена роль MANAGER.")
    await state.clear()
# ------------------------------------------------------------

# Роутер на коллбэк смена цен
# ------------------------------------------------------------
@router.callback_query(lambda c: c.data == "admin_upload_prices")
async def upload_prices(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_price_json)
    await callback.message.answer("Отправьте JSON с ценами (например, кредиты и подписки):")
    await callback.answer()
# ------------------------------------------------------------

# Роутре на коллбэк ожидание json с ценами
# ------------------------------------------------------------
@router.message(AdminStates.waiting_for_price_json, F.content_type == "document")
async def receive_price_json(message: types.Message, state: FSMContext, bot: Bot):
    try:
        # Правильный способ скачивания файла в aiogram 3.x
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path

        # Скачиваем в BytesIO
        file_content = BytesIO()
        await bot.download_file(file_path, file_content)

        # Декодируем содержимое
        content = file_content.getvalue().decode("utf-8")
        data = json.loads(content)

    except json.JSONDecodeError as e:
        return await message.answer(f"❌ Ошибка при чтении JSON: {e}")
    except Exception as e:
        return await message.answer(f"❌ Ошибка при скачивании файла: {e}")

    try:
        with open(PRICE_LIST, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        await message.answer(f"✅ Цены успешно обновлены!\n📁 Путь: {PRICE_LIST}")
    except Exception as e:
        return await message.answer(f"❌ Ошибка при сохранении файла: {e}")

    await state.clear()
# ------------------------------------------------------------    


async def export_full_db_and_send(session: AsyncSession, bot: Bot, chat_id: int):
    """
    Экспортирует все таблицы БД в XLSX и отправляет в Telegram.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Удаляем пустой первый лист

    # Список моделей и названия листов
    tables = [
        (User, "Users"),
        (Media, "Media"),
        (Download, "Downloads"),
        (Payment, "Payments"),
        (Subscription, "Subscriptions"),
        (ReferralReward, "ReferralRewards")
    ]

    for model, sheet_name in tables:
        # Создаём лист
        ws = wb.create_sheet(title=sheet_name)

        # Получаем все записи из модели
        result = await session.execute(select(model))
        rows = result.scalars().all()

        if not rows:
            ws.append(["Нет данных"])
            continue

        # Заголовки — это имена всех колонок в модели
        columns = [col.name for col in model.__table__.columns]
        ws.append(columns)

        # Данные
        for row in rows:
            row_data = []
            for col in columns:
                value = getattr(row, col)
                if isinstance(value, Enum):
                    value = value.value  # Конвертируем enum в его значение
                elif value is None:
                    value = ""
                row_data.append(value)
            ws.append(row_data)

    # Сохраняем в память
    file_path = "/tmp/full_database_export.xlsx"
    wb.save(file_path)

    try:
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(file_path),
            caption="📊 Полный экспорт базы данных"
        )
    finally:
        # Удаляем файл после отправки
        import os
        if os.path.exists(file_path):
            os.remove(file_path)

@router.callback_query(lambda c: c.data == "export_db")
async def export_db_callback(callback_query: types.CallbackQuery, bot: Bot):
    async for session in get_session():
        await export_full_db_and_send(session, bot, callback_query.message.chat.id)
    await callback_query.answer("📁 База выгружена!")



# Загрузка envato_cookies.json
@router.callback_query(lambda c: c.data == "admin_upload_cookies")
async def upload_cookies(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_cookies_json)
    await callback.message.answer("Отправьте JSON с cookies (envato_cookies.json):")
    await callback.answer()


@router.message(AdminStates.waiting_for_cookies_json, F.content_type == "document")
async def receive_cookies_json(message: types.Message, state: FSMContext, bot: Bot):
    try:
        # Правильный способ скачивания файла в aiogram 3.x
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path

        # Скачиваем в BytesIO
        file_content = BytesIO()
        await bot.download_file(file_path, file_content)

        # Декодируем содержимое
        content = file_content.getvalue().decode("utf-8")
        cookies_data = json.loads(content)

    except json.JSONDecodeError as e:
        return await message.answer(f"❌ Ошибка при чтении JSON: {e}")
    except Exception as e:
        return await message.answer(f"❌ Ошибка при скачивании файла: {e}")

    # Сохраняем рядом с проектом
    cookies_path = Path(__file__).resolve().parents[2] / "envato_utils" / "envato_cookies.json"

    try:
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(cookies_data, f, indent=4, ensure_ascii=False)
        await message.answer(f"✅ Cookies успешно обновлены!\n📁 Путь: {cookies_path}")
    except Exception as e:
        return await message.answer(f"❌ Ошибка при сохранении файла: {e}")

    await state.clear()
    
    
    
# Начало установки лимита
@router.callback_query(lambda c: c.data == "admin_set_download_limit")
async def ask_download_limit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_limit_value)
    await callback.message.answer("Введите новое количество доступных скачиваний для всех пользователей:")
    await callback.answer()


# Принятие числа и обновление
@router.message(AdminStates.waiting_for_limit_value)
async def set_download_limit(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введите число.")

    limit = int(message.text)

    async for session in get_session():
        await session.execute(update(User).values(credits=limit))
        await session.commit()

    await message.answer(f"✅ Всем пользователям установлено {limit} скачиваний.")
    await state.clear()
    
@router.callback_query(lambda c: c.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.answer("📝 Введите текст оповещения, который нужно отправить всем пользователям:")
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_text)
async def send_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text.strip()

    if text.lower() in {"отмена", "cancel"}:
        await state.clear()
        return await message.answer("❌ Рассылка отменена.")

    sent = 0
    failed = 0

    async for session in get_session():
        users = await session.execute(select(User.tg_id))
        tg_ids = [u[0] for u in users.all()]

    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"✅ Рассылка завершена!\n📬 Отправлено: {sent}\n⚠️ Ошибок: {failed}")
    await state.clear()


# Удаление всех подписок - запрос подтверждения
@router.callback_query(lambda c: c.data == "admin_delete_all_subscriptions")
async def confirm_delete_all_subscriptions(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    # Подсчитываем количество подписок
    async for session in get_session():
        result = await session.execute(select(Subscription))
        subscriptions_count = len(result.scalars().all())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить все", callback_data="admin_confirm_delete_subscriptions")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_delete_subscriptions")]
    ])

    await callback.message.edit_text(
        f"⚠️ <b>Внимание!</b>\n\n"
        f"Вы уверены, что хотите удалить ВСЕ подписки?\n\n"
        f"📊 Подписок в базе: <b>{subscriptions_count}</b>\n\n"
        f"⚠️ Это действие необратимо!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# Подтверждение удаления всех подписок
@router.callback_query(lambda c: c.data == "admin_confirm_delete_subscriptions")
async def delete_all_subs_confirmed(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    try:
        async for session in get_session():
            deleted_count = await delete_all_subscriptions(session)

        await callback.message.edit_text(
            f"✅ <b>Все подписки удалены!</b>\n\n"
            f"🗑️ Удалено подписок: <b>{deleted_count}</b>",
            parse_mode="HTML"
        )
        await callback.answer("✅ Подписки удалены!")
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении подписок:</b>\n\n"
            f"<code>{e}</code>",
            parse_mode="HTML"
        )
        await callback.answer("❌ Ошибка!")
        print(f"[ADMIN] Ошибка удаления подписок: {e}")
        import traceback
        traceback.print_exc()


# Отмена удаления подписок
@router.callback_query(lambda c: c.data == "admin_cancel_delete_subscriptions")
async def cancel_delete_subscriptions(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Удаление подписок отменено.")
    await callback.answer()


# Восстановление базы данных из XLSX
@router.callback_query(lambda c: c.data == "admin_restore_db")
async def restore_db_start(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_restore_xlsx)
    await callback.message.answer(
        "🔄 <b>Восстановление базы данных</b>\n\n"
        "Отправьте XLSX файл с экспортом базы данных.\n\n"
        "⚠️ <b>Внимание:</b>\n"
        "• Файл должен содержать листы: Users, Media, Downloads, Payments, Subscriptions, ReferralRewards\n"
        "• Существующие записи будут пропущены (не перезаписаны)\n"
        "• Это безопасная операция - дубликаты не создаются\n\n"
        "Отправьте 'отмена' для отмены.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_restore_xlsx, F.content_type == "document")
async def receive_restore_xlsx(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка загруженного XLSX файла для восстановления базы"""
    try:
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path

        # Сохраняем во временную директорию
        import tempfile
        temp_dir = tempfile.gettempdir()
        local_file_path = Path(temp_dir) / f"restore_{message.from_user.id}_{message.document.file_name}"

        await bot.download_file(file_path, local_file_path)

        # Проверяем, что это XLSX файл
        if not str(local_file_path).endswith(('.xlsx', '.xls')):
            local_file_path.unlink(missing_ok=True)
            return await message.answer("❌ Файл должен быть в формате XLSX")

        # Отправляем сообщение о начале восстановления
        status_msg = await message.answer(
            "⏳ <b>Восстановление базы данных...</b>\n\n"
            "Это может занять некоторое время.",
            parse_mode="HTML"
        )

        # Импортируем функцию восстановления
        from db.from_xlsx import restore_database

        # Запускаем восстановление
        try:
            await restore_database(str(local_file_path))

            await status_msg.edit_text(
                "✅ <b>База данных успешно восстановлена!</b>\n\n"
                "Все данные из файла были импортированы.\n"
                "Существующие записи были пропущены.",
                parse_mode="HTML"
            )
        except Exception as e:
            await status_msg.edit_text(
                f"❌ <b>Ошибка при восстановлении базы:</b>\n\n"
                f"<code>{str(e)[:500]}</code>",
                parse_mode="HTML"
            )
            print(f"[ADMIN] Ошибка восстановления базы: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Удаляем временный файл
            local_file_path.unlink(missing_ok=True)

    except Exception as e:
        return await message.answer(
            f"❌ Ошибка при обработке файла:\n\n"
            f"<code>{str(e)[:500]}</code>",
            parse_mode="HTML"
        )

    await state.clear()


@router.message(AdminStates.waiting_for_restore_xlsx, F.text)
async def cancel_restore_db(message: types.Message, state: FSMContext):
    """Отмена восстановления базы"""
    if message.text.lower() in ["отмена", "cancel", "q"]:
        await state.clear()
        await message.answer("❌ Восстановление базы отменено.")
    else:
        await message.answer("❌ Пожалуйста, отправьте XLSX файл или напишите 'отмена' для отмены.")