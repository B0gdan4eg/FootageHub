"""
Bonus system management functionality for admin panel.
"""

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from media_bot.handlers.admin.core import is_admin
from media_bot.keyboards import get_cancel_kb
from media_bot.state import AdminStates
from shared.db.models import BonusType, UserBonus
from shared.db.session import get_session

router = Router()


async def manage_bonuses(callback: types.CallbackQuery):
    """Show bonus management menu"""
    if not await is_admin(callback.from_user.id):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список бонусов", callback_data="bonus_list")],
            [InlineKeyboardButton(text="🔄 Инициализировать бонусы", callback_data="bonus_init")],
            [InlineKeyboardButton(text="➕ Создать новый бонус", callback_data="bonus_create")],
            [InlineKeyboardButton(text="✏️ Редактировать бонус", callback_data="bonus_edit")],
            [
                InlineKeyboardButton(
                    text="🔄 Активировать/Деактивировать", callback_data="bonus_toggle"
                )
            ],
            [InlineKeyboardButton(text="📊 Статистика бонусов", callback_data="bonus_stats")],
        ]
    )

    await callback.message.answer(
        "🎉 <b>Управление бонусной системой</b>\n\n" "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "bonus_init")
async def bonus_init(callback: types.CallbackQuery):
    """Initialize default bonuses"""
    from shared.db.init_bonuses import initialize_bonuses

    try:
        await callback.message.edit_text("⏳ Инициализация бонусов...", parse_mode="HTML")

        stats = await initialize_bonuses()

        await callback.message.edit_text(
            f"✅ <b>Бонусы успешно инициализированы!</b>\n\n"
            f"✨ Создано новых: {stats['created']}\n"
            f"🔄 Обновлено: {stats['updated']}\n\n"
            f"Используйте <b>📋 Список бонусов</b> для просмотра.",
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка инициализации бонусов:</b>\n\n" f"<code>{str(e)}</code>",
            parse_mode="HTML",
        )

    await callback.answer()


@router.callback_query(F.data == "bonus_list")
async def bonus_list(callback: types.CallbackQuery):
    """Show list of all bonuses"""
    async for session in get_session():
        result = await session.execute(select(BonusType).order_by(BonusType.id))
        bonuses = result.scalars().all()

    if not bonuses:
        await callback.answer("Нет созданных бонусов", show_alert=True)
        return

    text = "📋 <b>Список всех бонусов</b>\n\n"

    for bonus in bonuses:
        status = "✅ Активен" if bonus.is_active else "❌ Неактивен"
        repeatable = "🔄 Повторяемый" if bonus.is_repeatable else "1️⃣ Одноразовый"

        rewards = []
        if bonus.credits_amount > 0:
            rewards.append(f"💰 {bonus.credits_amount} скачиваний")
        if bonus.ai_credits_amount > 0:
            rewards.append(f"💎 {bonus.ai_credits_amount} AI скачиваний")

        reward_text = ", ".join(rewards) if rewards else "Нет наград"

        text += (
            f"<b>{bonus.name}</b>\n"
            f"📝 Код: <code>{bonus.code}</code>\n"
            f"🎁 Награда: {reward_text}\n"
            f"📊 Статус: {status}\n"
            f"🔁 Тип: {repeatable}\n"
        )

        if bonus.cooldown_days:
            text += f"⏰ Кулдаун: {bonus.cooldown_days} дней\n"

        text += "\n"

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "bonus_stats")
async def bonus_stats(callback: types.CallbackQuery):
    """Show bonus statistics"""
    async for session in get_session():
        # Total bonuses granted
        result = await session.execute(select(UserBonus))
        all_bonuses = result.scalars().all()

        # Group by bonus type
        bonus_counts = {}
        total_credits = 0
        total_ai_credits = 0

        for user_bonus in all_bonuses:
            result = await session.execute(
                select(BonusType).where(BonusType.id == user_bonus.bonus_type_id)
            )
            bonus_type = result.scalar_one_or_none()

            if bonus_type:
                if bonus_type.code not in bonus_counts:
                    bonus_counts[bonus_type.code] = {
                        "name": bonus_type.name,
                        "count": 0,
                        "credits": 0,
                        "ai_credits": 0,
                    }

                bonus_counts[bonus_type.code]["count"] += 1
                bonus_counts[bonus_type.code]["credits"] += user_bonus.credits_granted
                bonus_counts[bonus_type.code]["ai_credits"] += user_bonus.ai_credits_granted

                total_credits += user_bonus.credits_granted
                total_ai_credits += user_bonus.ai_credits_granted

    text = "📊 <b>Статистика бонусной системы</b>\n\n"

    if bonus_counts:
        for code, data in bonus_counts.items():
            text += (
                f"<b>{data['name']}</b> (<code>{code}</code>)\n"
                f"👥 Выдано: {data['count']} раз\n"
                f"💰 Кредитов: {data['credits']:,}\n"
                f"💎 AI скачиваний: {data['ai_credits']:,}\n\n"
            )

        text += (
            f"<b>📈 Итого:</b>\n"
            f"🎁 Всего бонусов выдано: {len(all_bonuses)}\n"
            f"💰 Всего скачиваний: {total_credits:,}\n"
            f"💎 Всего AI скачиваний: {total_ai_credits:,}"
        )
    else:
        text += "Нет данных о выданных бонусах"

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "bonus_create")
async def bonus_create_start(callback: types.CallbackQuery, state: FSMContext):
    """Start bonus creation process"""
    await state.set_state(AdminStates.waiting_for_bonus_code)
    await callback.message.answer(
        "➕ <b>Создание нового бонуса</b>\n\n"
        "Шаг 1/5: Введите уникальный код бонуса (например: WELCOME_BONUS):",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_bonus_code)
async def bonus_create_code(message: types.Message, state: FSMContext):
    """Receive bonus code"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание бонуса отменено")
        return

    code = message.text.strip().upper()

    # Check if code already exists
    async for session in get_session():
        result = await session.execute(select(BonusType).where(BonusType.code == code))
        existing = result.scalar_one_or_none()

        if existing:
            await message.answer(
                f"❌ Бонус с кодом <code>{code}</code> уже существует. Введите другой код:",
                parse_mode="HTML",
            )
            return

    await state.update_data(bonus_code=code)
    await state.set_state(AdminStates.waiting_for_bonus_name)
    await message.answer(
        f"✅ Код: <code>{code}</code>\n\n"
        f"Шаг 2/5: Введите название бонуса (например: Приветственный бонус):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_bonus_name)
async def bonus_create_name(message: types.Message, state: FSMContext):
    """Receive bonus name"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание бонуса отменено")
        return

    name = message.text.strip()
    await state.update_data(bonus_name=name)
    await state.set_state(AdminStates.waiting_for_bonus_description)
    await message.answer(
        f"✅ Название: {name}\n\n" f"Шаг 3/5: Введите описание бонуса (или - для пропуска):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_bonus_description)
async def bonus_create_description(message: types.Message, state: FSMContext):
    """Receive bonus description"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание бонуса отменено")
        return

    description = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(bonus_description=description)
    await state.set_state(AdminStates.waiting_for_bonus_credits)
    await message.answer(
        "✅ Описание сохранено\n\n" "Шаг 4/5: Введите количество обычных скачиваний (или 0):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_bonus_credits)
async def bonus_create_credits(message: types.Message, state: FSMContext):
    """Receive bonus credits amount"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание бонуса отменено")
        return

    try:
        credits = int(message.text.strip())
        if credits < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число или 0:")
        return

    await state.update_data(bonus_credits=credits)
    await state.set_state(AdminStates.waiting_for_bonus_repeatable)
    await message.answer(
        f"✅ Кредитов: {credits}\n\n" f"Шаг 5/5: Бонус повторяемый? (да/нет):",
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_bonus_repeatable)
async def bonus_create_repeatable(message: types.Message, state: FSMContext):
    """Receive bonus repeatable setting and create bonus"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Создание бонуса отменено")
        return

    is_repeatable = message.text.strip().lower() in ["да", "yes", "y", "1", "true"]

    data = await state.get_data()

    # Determine reward type
    from shared.db.models import BonusRewardType

    if data["bonus_credits"] > 0:
        reward_type = BonusRewardType.CREDITS
    else:
        reward_type = BonusRewardType.CREDITS  # Default

    async for session in get_session():
        new_bonus = BonusType(
            code=data["bonus_code"],
            name=data["bonus_name"],
            description=data.get("bonus_description"),
            reward_type=reward_type,
            credits_amount=data["bonus_credits"],
            ai_credits_amount=0,
            is_active=True,
            is_repeatable=is_repeatable,
        )

        session.add(new_bonus)
        await session.commit()

    repeatable_text = "🔄 Повторяемый" if is_repeatable else "1️⃣ Одноразовый"

    await message.answer(
        "✅ <b>Бонус успешно создан!</b>\n\n"
        f"📝 Код: <code>{data['bonus_code']}</code>\n"
        f"💡 Название: {data['bonus_name']}\n"
        f"💰 Кредитов: {data['bonus_credits']}\n"
        f"🔁 Тип: {repeatable_text}\n"
        f"📊 Статус: ✅ Активен",
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data == "bonus_toggle")
async def bonus_toggle_start(callback: types.CallbackQuery, state: FSMContext):
    """Start bonus toggle process"""
    await state.set_state(AdminStates.waiting_for_bonus_code_toggle)
    await callback.message.answer(
        "🔄 <b>Активировать/Деактивировать бонус</b>\n\n" "Введите код бонуса:",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_bonus_code_toggle)
async def bonus_toggle_execute(message: types.Message, state: FSMContext):
    """Toggle bonus active status"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Операция отменена")
        return

    code = message.text.strip().upper()

    async for session in get_session():
        result = await session.execute(select(BonusType).where(BonusType.code == code))
        bonus = result.scalar_one_or_none()

        if not bonus:
            await message.answer(
                f"❌ Бонус с кодом <code>{code}</code> не найден",
                parse_mode="HTML",
            )
            await state.clear()
            return

        # Toggle active status
        bonus.is_active = not bonus.is_active
        await session.commit()

        status = "✅ активирован" if bonus.is_active else "❌ деактивирован"

    await message.answer(
        f"✅ Бонус <b>{bonus.name}</b> (<code>{code}</code>) {status}",
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(F.data == "bonus_edit")
async def bonus_edit_not_implemented(callback: types.CallbackQuery):
    """Bonus edit not implemented yet"""
    await callback.answer(
        "Редактирование бонусов будет доступно в следующей версии", show_alert=True
    )
