from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, func
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db.session import get_session
from db.models import User, UserRole, Payment
from bot.state import ManagerFlow
from bot.handlers.admin import is_admin
from bot.services import BotServices

router = Router()

async def is_manager(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль MANAGER.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.MANAGER


@router.message(Command("manager"))
async def manager_command(message: types.Message, state: FSMContext):
    is_mgr = await is_manager(message.from_user.id)
    is_adm = await is_admin(message.from_user.id)
    access = is_mgr or is_adm
    print(access)
    if not access:
        await message.answer("🚫 У вас нет прав для этой команды.")
        return
        
    manager_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="export_db")],
        [InlineKeyboardButton(text="➕ Создать реферальную ссылку", callback_data="manager_create_referral")],
        [InlineKeyboardButton(text="👥 Просмотреть всех рефералов", callback_data="manager_view_referrals")],
        [InlineKeyboardButton(text="🔄 Рестарт Envato", callback_data="manager_restart_envato")],
        [InlineKeyboardButton(text="🔄 Рестарт Freepik", callback_data="manager_restart_freepik")]
    ])
    # Если роль менеджера подтверждена
    await message.answer(
        "✅ Привет, менеджер! Что будем делать?",
        reply_markup=manager_kb
    )
    

@router.callback_query(lambda c: c.data == "manager_create_referral")
async def start_referral(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerFlow.waiting_for_ref_code)
    await callback.message.answer("Введите аргумент для реферальной ссылки (например: promo123):")
    await callback.answer()

# Шаг 2: Получаем аргумент
@router.message(ManagerFlow.waiting_for_ref_code)
async def receive_ref_code(message: types.Message, state: FSMContext):
    ref_code = message.text.strip()
    if not ref_code:
        return await message.answer("❌ Аргумент не может быть пустым. Попробуйте снова.")
    await state.update_data(ref_code=ref_code)
    await state.set_state(ManagerFlow.waiting_for_description)
    await message.answer("Введите описание/комментарий для этой ссылки:")

# Шаг 3: Получаем описание и сохраняем
@router.message(ManagerFlow.waiting_for_description)
async def save_referral(message: types.Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    ref_code = data["ref_code"]

    user_id = message.from_user.id  # менеджер, создающий ссылку

    async for session in get_session():
        # Сохраняем код у менеджера (если один код на менеджера)
        await session.execute(
            update(User)
            .where(User.tg_id == user_id)
            .values(referral_code=ref_code)
        )
        await session.commit()

    referral_link = f"https://t.me/FootageHub_bot?start={ref_code}"
    await message.answer(f"✅ Реферальная ссылка создана!\n\nСсылка: {referral_link}\nОписание: {description}")
    await state.clear()


@router.callback_query(lambda c: c.data == "manager_view_referrals")
async def view_referrals(callback: types.CallbackQuery):
    manager_id = callback.from_user.id

    async for session in get_session():
        # Получаем всех рефералов
        result = await session.execute(select(User).where(User.referred_by_id == manager_id))
        referrals = result.scalars().all()

        if not referrals:
            await callback.message.answer("У вас ещё нет рефералов.")
            return

        total_referrals = len(referrals)
        total_purchases = 0
        total_earnings = 0.0

        # Собираем список с данными для сортировки
        referral_stats = []

        for ref in referrals:
            # Считаем успешные платежи
            payments_result = await session.execute(
                select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
                .where(Payment.user_id == ref.id, Payment.status == "success")
            )
            count, amount = payments_result.one()
            earnings = float(amount) * 0.2  # 20% доход менеджера
            total_purchases += count
            total_earnings += earnings

            referral_stats.append({
                "ref": ref,
                "count": count,
                "earnings": earnings
            })

        # Сортируем по заработку (убывание)
        referral_stats.sort(key=lambda x: x["earnings"], reverse=True)

        # Формируем текст
        details = ""
        for stat in referral_stats:
            ref = stat["ref"]
            username = f"@{ref.username}" if ref.username else "нет username"
            details += f"ID: {ref.tg_id}, {username}, Покупок: {stat['count']}, Заработок: {stat['earnings']:.2f}\n"

        summary = (
            f"📊 Статистика ваших рефералов:\n\n"
            f"Всего рефералов: {total_referrals}\n"
            f"Всего покупок: {total_purchases}\n"
            f"Ваш заработок (20%): {total_earnings:.2f}\n\n"
            f"Детали (сортировка по заработку):\n{details}"
        )

        await callback.message.answer(summary)


@router.callback_query(lambda c: c.data == "manager_restart_envato")
async def restart_envato_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Envato через LinkProcessor"""
    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.envato_downloader:
            await callback.answer("⚠️ Браузер Envato не запущен", show_alert=True)
            return

        await callback.message.answer("🔄 Начинаю рестарт браузера Envato...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._envato_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.envato_request_count

            # Закрываем старый браузер
            if link_processor.envato_downloader:
                await link_processor.envato_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from envato_utils.envato_playwright import EnvatoDownloader
            link_processor.envato_downloader = await EnvatoDownloader().__aenter__()
            link_processor.envato_request_count = 0

        await callback.message.answer(
            f"✅ Браузер Envato перезапущен!\n\n"
            f"📊 Обработано запросов до рестарта: {current_requests}\n"
            f"🔄 Счетчик сброшен: 0/{link_processor.restart_after}"
        )
        await callback.answer("✅ Рестарт завершен!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Envato:\n{e}")
        await callback.answer("❌ Ошибка!", show_alert=True)
        print(f"[MANAGER] Ошибка рестарта браузера Envato: {e}")


@router.callback_query(lambda c: c.data == "manager_restart_freepik")
async def restart_freepik_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Freepik через LinkProcessor"""
    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.freepik_downloader:
            await callback.answer("⚠️ Браузер Freepik не запущен", show_alert=True)
            return

        await callback.message.answer("🔄 Начинаю рестарт браузера Freepik...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._freepik_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.freepik_request_count

            # Закрываем старый браузер
            if link_processor.freepik_downloader:
                await link_processor.freepik_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from freepik_utils.freepik import FreepikDownloader
            link_processor.freepik_downloader = await FreepikDownloader().__aenter__()
            link_processor.freepik_request_count = 0

        await callback.message.answer(
            f"✅ Браузер Freepik перезапущен!\n\n"
            f"📊 Обработано запросов до рестарта: {current_requests}\n"
            f"🔄 Счетчик сброшен: 0/{link_processor.restart_after}"
        )
        await callback.answer("✅ Рестарт завершен!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Freepik:\n{e}")
        await callback.answer("❌ Ошибка!", show_alert=True)
        print(f"[MANAGER] Ошибка рестарта браузера Freepik: {e}")