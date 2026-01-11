"""
Admin Handlers

Admin panel for AI Bot management
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from ai_bot.config import config
from ai_bot.keyboards import admin_menu_kb, get_cancel_kb, main_menu_kb
from ai_bot.services import CreditManager, PricingService
from shared.db.models import User
from shared.db.session import AsyncSessionLocal

router = Router()


class AdminStates(StatesGroup):
    """Admin panel states"""

    waiting_for_user_id = State()
    waiting_for_credits_amount = State()
    waiting_for_broadcast_message = State()


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id == config.ADMIN


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Open admin panel"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return

    admin_text = (
        "🔐 <b>Админ-панель AI Bot</b>\n\n"
        "Добро пожаловать в панель управления!\n"
        "Выберите нужное действие:"
    )

    await message.answer(admin_text, reply_markup=admin_menu_kb, parse_mode="HTML")


@router.message(F.text == "📊 Статистика")
async def admin_statistics(message: Message):
    """Show bot statistics"""
    if not is_admin(message.from_user.id):
        return

    async with AsyncSessionLocal() as session:
        # Total users
        total_users_result = await session.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar()

        # Total credits distributed
        total_credits_result = await session.execute(
            select(func.sum(User.ai_credits + User.ai_credits_used))
        )
        total_credits = total_credits_result.scalar() or 0

        # Total credits used
        total_used_result = await session.execute(select(func.sum(User.ai_credits_used)))
        total_used = total_used_result.scalar() or 0

        # Total credits available
        total_available_result = await session.execute(select(func.sum(User.ai_credits)))
        total_available = total_available_result.scalar() or 0

    # Get Kie.ai balance via API
    pricing_service = PricingService(config.KIE_AI_API_KEY)
    try:
        kie_balance = await pricing_service.get_kie_credits(force_refresh=True)
        if kie_balance is not None:
            kie_balance_usd = pricing_service.credits_to_usd(kie_balance)
            kie_balance_text = (
                f"🌐 <b>Kie.ai API баланс:</b>\n"
                f"   💎 {kie_balance:,} кредитов\n"
                f"   💵 ${kie_balance_usd:.2f}\n"
            )
        else:
            kie_balance_text = f"🌐 Kie.ai баланс: <i>недоступен (API ключ не настроен)</i>\n"
    except Exception as e:
        kie_balance_text = f"🌐 Kie.ai баланс: <i>недоступен ({str(e)[:50]})</i>\n"

    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n\n"
        f"<b>Внутренние кредиты (база данных):</b>\n"
        f"💎 Всего выдано: <b>{total_credits:,}</b>\n"
        f"📊 Использовано: <b>{total_used:,}</b>\n"
        f"💰 Доступно: <b>{total_available:,}</b>\n\n"
        f"{kie_balance_text}"
    )

    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.text == "👥 Пользователи")
async def admin_users(message: Message):
    """Show recent users"""
    if not is_admin(message.from_user.id):
        return

    async with AsyncSessionLocal() as session:
        # Get last 10 users
        result = await session.execute(select(User).order_by(User.created_at.desc()).limit(10))
        users = result.scalars().all()

    if not users:
        await message.answer("Нет пользователей")
        return

    users_text = "👥 <b>Последние пользователи</b>\n\n"

    for user in users:
        username = user.username or "Без username"
        users_text += (
            f"ID: <code>{user.tg_id}</code>\n"
            f"Username: @{username}\n"
            f"💎 Кредитов: {user.ai_credits}\n"
            f"📊 Использовано: {user.ai_credits_used}\n"
            f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        )

    await message.answer(users_text, parse_mode="HTML")


@router.message(F.text == "💎 Управление кредитами")
async def admin_credits_menu(message: Message, state: FSMContext):
    """Credits management menu"""
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        "💎 <b>Управление кредитами</b>\n\n" "Отправьте Telegram ID пользователя:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_user_id)
async def admin_user_id_received(message: Message, state: FSMContext):
    """Process user ID for credits management"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Отменено", reply_markup=admin_menu_kb)
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Попробуйте снова.")
        return

    # Check if user exists
    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        stats = await credit_manager.get_user_stats(user_id)

        if not stats:
            await message.answer(
                f"❌ Пользователь с ID {user_id} не найден", reply_markup=admin_menu_kb
            )
            await state.clear()
            return

        user_info = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"💰 Доступно: <b>{stats['ai_credits']:,} кредитов</b>\n"
            f"📊 Использовано: {stats['ai_credits_used']:,} кредитов\n"
            f"📈 Всего получено: {stats['total_received']:,} кредитов\n\n"
            "Введите количество кредитов для добавления (или отрицательное число для вычитания):"
        )

        await state.update_data(user_id=user_id)
        await state.set_state(AdminStates.waiting_for_credits_amount)
        await message.answer(user_info, parse_mode="HTML")


@router.message(AdminStates.waiting_for_credits_amount)
async def admin_credits_amount_received(message: Message, state: FSMContext):
    """Process credits amount"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Отменено", reply_markup=admin_menu_kb)
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число.")
        return

    data = await state.get_data()
    user_id = data.get("user_id")

    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)

        if amount > 0:
            await credit_manager.add_credits(user_id, amount)
            result_text = f"✅ Добавлено {amount} кредитов пользователю {user_id}"
        else:
            success = await credit_manager.deduct_credits(user_id, abs(amount))
            if success:
                result_text = f"✅ Снято {abs(amount)} кредитов у пользователя {user_id}"
            else:
                result_text = f"❌ Недостаточно кредитов у пользователя {user_id}"

        # Show updated stats
        stats = await credit_manager.get_user_stats(user_id)
        result_text += f"\n\n💰 Новый баланс: <b>{stats['ai_credits']:,} кредитов</b>"

    await message.answer(result_text, reply_markup=admin_menu_kb, parse_mode="HTML")
    await state.clear()


@router.message(F.text == "📢 Рассылка")
async def admin_broadcast_menu(message: Message, state: FSMContext):
    """Broadcast menu"""
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям:\n\n"
        "⚠️ Сообщение будет отправлено всем пользователям бота!",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_broadcast_message)
async def admin_broadcast_message_received(message: Message, state: FSMContext):
    """Process broadcast message"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Рассылка отменена", reply_markup=admin_menu_kb)
        return

    broadcast_text = message.text

    # Get all users
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.tg_id))
        user_ids = [row[0] for row in result.all()]

    # Send broadcast
    success_count = 0
    fail_count = 0

    status_message = await message.answer(
        f"📤 Рассылка началась...\n" f"Всего пользователей: {len(user_ids)}",
        reply_markup=admin_menu_kb,
    )

    from aiogram import Bot

    bot = message.bot

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, broadcast_text, parse_mode="HTML")
            success_count += 1
        except Exception:
            fail_count += 1

    await status_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: {success_count}\n"
        f"❌ Не отправлено: {fail_count}",
        parse_mode="HTML",
    )

    await state.clear()


@router.message(F.text == "⚙️ Настройки цен")
async def admin_pricing_settings(message: Message):
    """Show pricing settings"""
    if not is_admin(message.from_user.id):
        return

    from ai_bot.services import PricingService

    pricing_service = PricingService(config.KIE_AI_API_KEY)
    models = pricing_service.get_all_models()

    settings_text = "⚙️ <b>Настройки цен</b>\n\n"

    for model_id, info in models.items():
        usd = pricing_service.credits_to_usd(info["credits"])
        settings_text += (
            f"<b>{info['name']}</b>\n"
            f"Модель: <code>{model_id}</code>\n"
            f"Цена: {info['credits']} кредитов (${usd:.3f})\n"
            f"Тип: {info['type']}\n\n"
        )

    settings_text += "\n<i>Для изменения цен отредактируйте ai_bot/services/pricing_service.py</i>"

    await message.answer(settings_text, parse_mode="HTML")


@router.message(F.text == "🌐 Kie.ai баланс")
async def admin_kie_balance(message: Message):
    """Show Kie.ai API balance"""
    if not is_admin(message.from_user.id):
        return

    status_msg = await message.answer("⏳ Получаю баланс Kie.ai API...")

    pricing_service = PricingService(config.KIE_AI_API_KEY)

    try:
        # Force refresh to get latest balance
        kie_balance = await pricing_service.get_kie_credits(force_refresh=True)

        if kie_balance is None:
            raise ValueError("API ключ не настроен или клиент недоступен")

        kie_balance_usd = pricing_service.credits_to_usd(kie_balance)

        balance_text = (
            "🌐 <b>Баланс Kie.ai API</b>\n\n"
            f"💎 Кредитов: <b>{kie_balance:,}</b>\n"
            f"💵 В USD: <b>${kie_balance_usd:.2f}</b>\n\n"
            f"<i>1 кредит = $0.005</i>\n\n"
            "📋 <b>Расход на генерацию:</b>\n"
        )

        # Show pricing info
        models = pricing_service.get_all_models()

        # Image models
        balance_text += "\n🎨 <b>Изображения:</b>\n"
        for model_id, info in models.items():
            if info["type"] == "image":
                usd = pricing_service.credits_to_usd(info["credits"])
                generations = int(kie_balance / info["credits"])
                balance_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.3f}) - можно создать <b>{generations:,}</b> шт.\n"

        # Video models
        balance_text += "\n🎬 <b>Видео:</b>\n"
        for model_id, info in models.items():
            if info["type"] == "video":
                usd = pricing_service.credits_to_usd(info["credits"])
                generations = int(kie_balance / info["credits"])
                balance_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.2f}) - можно создать <b>{generations:,}</b> шт.\n"

        await status_msg.edit_text(balance_text, parse_mode="HTML")

    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Ошибка получения баланса</b>\n\n"
            f"Не удалось получить баланс Kie.ai API\n"
            f"Ошибка: <code>{str(e)}</code>\n\n"
            f"Проверьте:\n"
            f"• API ключ в конфигурации\n"
            f"• Соединение с интернетом\n"
            f"• Статус API Kie.ai",
            parse_mode="HTML",
        )


@router.message(F.text == "📝 Логи")
async def admin_logs(message: Message):
    """Show recent logs"""
    if not is_admin(message.from_user.id):
        return

    # TODO: Implement logging system
    await message.answer(
        "📝 <b>Логи</b>\n\n" "Система логирования находится в разработке", parse_mode="HTML"
    )


@router.message(F.text == "« Назад в главное меню")
async def admin_back_to_main(message: Message, state: FSMContext):
    """Return to main menu from admin panel"""
    await state.clear()
    await message.answer("Вы вернулись в главное меню", reply_markup=main_menu_kb)
