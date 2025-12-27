"""
Start command handler for AI Bot
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ai_bot.keyboards import main_menu_kb, tools_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command"""
    from db.session import AsyncSessionLocal
    from ai_bot.services import CreditManager

    user_id = message.from_user.id
    username = message.from_user.username or "User"

    # Get user's AI credits balance
    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        ai_credits = await credit_manager.get_user_credits(user_id) or 0

    welcome_text = (
        f"🤖 <b>Добро пожаловать в AI Bot!</b>\n\n"
        f"👋 Привет, {username}!\n\n"
        f"Я помогу вам создавать контент с помощью нейросетей:\n"
        f"🎨 <b>Генерация изображений</b> - Nano Banana\n"
        f"🎬 <b>Генерация видео</b> - Kling 2.6, VEO 3.1\n\n"
        f"💎 У вас <b>{ai_credits} AI кредитов</b>\n\n"
        f"Используйте кнопки ниже для начала работы:"
    )

    await message.answer(welcome_text, reply_markup=main_menu_kb, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "📖 <b>Справка по AI Bot</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/balance или /credits - Проверить баланс AI кредитов\n"
        "/pricing - Показать цены на генерацию\n"
        "/image - Создать изображение\n"
        "/video - Создать видео\n\n"
        "<b>Для подробной информации о ценах используйте /pricing</b>\n\n"
        "<b>Поддержка:</b> @support"
    )

    await message.answer(help_text, parse_mode="HTML")




# Handle text button commands
@router.message(F.text == "🎨 Изображение")
async def text_generate_image(message: Message, state):
    """Handle image generation button"""
    from ai_bot.handlers.image_generation import cmd_generate_image
    await cmd_generate_image(message, state)


@router.message(F.text == "🎬 Видео")
async def text_generate_video(message: Message, state):
    """Handle video generation button"""
    from ai_bot.handlers.video_generation import cmd_generate_video
    await cmd_generate_video(message, state)


@router.message(F.text == "🛠 Прочие инструменты")
async def text_other_tools(message: Message):
    """Handle other tools button"""
    tools_text = (
        "🛠 <b>Прочие инструменты</b>\n\n"
        "Выберите нужный инструмент:"
    )
    await message.answer(tools_text, reply_markup=tools_menu_kb, parse_mode="HTML")


@router.message(F.text == "💎 Баланс кредитов")
async def text_balance(message: Message):
    """Handle balance button from tools menu"""
    from db.session import AsyncSessionLocal
    from ai_bot.services import CreditManager, PricingService

    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        pricing_service = PricingService()

        stats = await credit_manager.get_user_stats(user_id)

        if not stats:
            balance_text = "💎 <b>Ваш баланс</b>\n\nАI кредиты: <b>0</b>"
        else:
            balance_text = (
                "💎 <b>Ваш баланс AI кредитов</b>\n\n"
                f"💰 Доступно: <b>{stats['ai_credits']:,} кредитов</b>\n"
                f"📊 Использовано: {stats['ai_credits_used']:,} кредитов\n"
                f"📈 Всего получено: {stats['total_received']:,} кредитов"
            )

            # Try to get Kie.ai balance
            try:
                kie_credits = await pricing_service.get_kie_credits()
                if kie_credits is not None:
                    balance_text += f"\n\n🌐 Kie.ai баланс: <b>{kie_credits:,} кредитов</b>"
            except:
                pass

    await message.answer(balance_text, parse_mode="HTML")


@router.message(F.text == "💰 Цены")
async def text_pricing(message: Message):
    """Handle pricing button from tools menu"""
    from ai_bot.services import PricingService

    pricing_service = PricingService()

    pricing_text = (
        "💰 <b>Цены на генерацию</b>\n\n"
        "1 кредит = $0.005 (0.5¢)\n\n"
    )

    models = pricing_service.get_all_models()

    # Image models
    image_models = {k: v for k, v in models.items() if v["type"] == "image"}
    if image_models:
        pricing_text += "<b>🎨 Изображения:</b>\n"
        for model_id, info in image_models.items():
            usd = pricing_service.credits_to_usd(info["credits"])
            pricing_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.3f})\n"
        pricing_text += "\n"

    # Video models
    video_models = {k: v for k, v in models.items() if v["type"] == "video"}
    if video_models:
        pricing_text += "<b>🎬 Видео:</b>\n"
        for model_id, info in video_models.items():
            usd = pricing_service.credits_to_usd(info["credits"])
            pricing_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.2f})\n"

    await message.answer(pricing_text, parse_mode="HTML")


@router.message(F.text == "ℹ️ Помощь")
async def text_help(message: Message):
    """Handle help button from tools menu"""
    await cmd_help(message)


@router.message(F.text == "ℹ️ Информация")
async def text_info(message: Message):
    """Handle info button"""
    from ai_bot.services import PricingService

    pricing_service = PricingService()

    info_text = (
        "ℹ️ <b>Информация об AI Bot</b>\n\n"
        "<b>📋 Доступные функции:</b>\n"
        "🎨 Генерация изображений (Nano Banana Pro)\n"
        "🎬 Генерация видео (Kling 2.6, VEO 3.1)\n\n"
        "<b>💰 Стоимость:</b>\n"
    )

    # Добавляем цены
    try:
        image_price = pricing_service.get_model_price("google/nano-banana")
        kling_price = pricing_service.get_model_price("kling-2.6/text-to-video")
        veo_price = pricing_service.get_model_price("veo-3.1/text-to-video")

        info_text += (
            f"• Изображение: {image_price} кредитов (${pricing_service.credits_to_usd(image_price):.3f})\n"
            f"• Видео Kling: {kling_price} кредитов (${pricing_service.credits_to_usd(kling_price):.2f})\n"
            f"• Видео VEO: {veo_price} кредитов (${pricing_service.credits_to_usd(veo_price):.2f})\n"
        )
    except:
        info_text += "Используйте /pricing для просмотра цен\n"

    info_text += (
        "\n<b>📖 Команды:</b>\n"
        "/balance - Проверить баланс\n"
        "/pricing - Все цены\n"
        "/image - Создать изображение\n"
        "/video - Создать видео\n"
        "/help - Помощь"
    )

    await message.answer(info_text, parse_mode="HTML")


@router.message(F.text == "💰 Купить кредиты")
async def text_buy_credits(message: Message):
    """Handle buy credits button"""
    await message.answer(
        "💰 <b>Покупка AI кредитов</b>\n\n"
        "Эта функция находится в разработке.\n"
        "Скоро вы сможете приобретать AI кредиты!",
        parse_mode="HTML"
    )


@router.message(F.text == "« Назад")
async def text_back(message: Message):
    """Handle back button"""
    await message.answer(
        "Вы вернулись в главное меню",
        reply_markup=main_menu_kb
    )


@router.callback_query(F.data == "buy_credits")
async def callback_buy_credits(callback):
    """Handle buy credits button"""
    await callback.message.answer(
        "💰 <b>Покупка AI кредитов</b>\n\n"
        "Эта функция находится в разработке.\n"
        "Скоро вы сможете приобретать AI кредиты!",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "info")
async def callback_info(callback):
    """Handle info button - show detailed information"""
    from ai_bot.services import PricingService

    pricing_service = PricingService()

    info_text = (
        "ℹ️ <b>Информация об AI Bot</b>\n\n"
        "<b>📋 Доступные функции:</b>\n"
        "🎨 Генерация изображений (Nano Banana Pro)\n"
        "🎬 Генерация видео (Kling 2.6, VEO 3.1)\n\n"
        "<b>💰 Стоимость:</b>\n"
    )

    # Добавляем цены
    try:
        image_price = pricing_service.get_model_price("google/nano-banana")
        kling_price = pricing_service.get_model_price("kling-2.6/text-to-video")
        veo_price = pricing_service.get_model_price("veo-3.1/text-to-video")

        info_text += (
            f"• Изображение: {image_price} кредитов (${pricing_service.credits_to_usd(image_price):.3f})\n"
            f"• Видео Kling: {kling_price} кредитов (${pricing_service.credits_to_usd(kling_price):.2f})\n"
            f"• Видео VEO: {veo_price} кредитов (${pricing_service.credits_to_usd(veo_price):.2f})\n"
        )
    except:
        info_text += "Используйте /pricing для просмотра цен\n"

    info_text += (
        "\n<b>📖 Команды:</b>\n"
        "/balance - Проверить баланс\n"
        "/pricing - Все цены\n"
        "/image - Создать изображение\n"
        "/video - Создать видео\n"
        "/help - Помощь"
    )

    await callback.message.answer(info_text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "other_tools")
async def callback_other_tools(callback):
    """Handle other tools button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Баланс кредитов", callback_data="show_balance")
    builder.button(text="💰 Цены на генерацию", callback_data="show_pricing")
    builder.button(text="ℹ️ Помощь", callback_data="help")
    builder.button(text="« Назад", callback_data="back_to_start")
    builder.adjust(1)

    await callback.message.edit_text(
        "🛠 <b>Прочие инструменты</b>\n\n"
        "Выберите нужный инструмент:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "show_balance")
async def callback_show_balance(callback):
    """Show balance from other tools menu"""
    from db.session import AsyncSessionLocal
    from ai_bot.services import CreditManager, PricingService

    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        pricing_service = PricingService()

        stats = await credit_manager.get_user_stats(user_id)

        if not stats:
            balance_text = "💎 <b>Ваш баланс</b>\n\nАI кредиты: <b>0</b>"
        else:
            balance_text = (
                "💎 <b>Ваш баланс AI кредитов</b>\n\n"
                f"💰 Доступно: <b>{stats['ai_credits']:,} кредитов</b>\n"
                f"📊 Использовано: {stats['ai_credits_used']:,} кредитов\n"
                f"📈 Всего получено: {stats['total_received']:,} кредитов"
            )

            # Try to get Kie.ai balance
            try:
                kie_credits = await pricing_service.get_kie_credits()
                if kie_credits is not None:
                    balance_text += f"\n\n🌐 Kie.ai баланс: <b>{kie_credits:,} кредитов</b>"
            except:
                pass

    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад к инструментам", callback_data="other_tools")
    builder.adjust(1)

    await callback.message.edit_text(
        balance_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "show_pricing")
async def callback_show_pricing(callback):
    """Show pricing from other tools menu"""
    from ai_bot.services import PricingService

    pricing_service = PricingService()

    pricing_text = (
        "💰 <b>Цены на генерацию</b>\n\n"
        "1 кредит = $0.005 (0.5¢)\n\n"
    )

    models = pricing_service.get_all_models()

    # Image models
    image_models = {k: v for k, v in models.items() if v["type"] == "image"}
    if image_models:
        pricing_text += "<b>🎨 Изображения:</b>\n"
        for model_id, info in image_models.items():
            usd = pricing_service.credits_to_usd(info["credits"])
            pricing_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.3f})\n"
        pricing_text += "\n"

    # Video models
    video_models = {k: v for k, v in models.items() if v["type"] == "video"}
    if video_models:
        pricing_text += "<b>🎬 Видео:</b>\n"
        for model_id, info in video_models.items():
            usd = pricing_service.credits_to_usd(info["credits"])
            pricing_text += f"• {info['name']}: {info['credits']} кредитов (${usd:.2f})\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад к инструментам", callback_data="other_tools")
    builder.adjust(1)

    await callback.message.edit_text(
        pricing_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def callback_help(callback):
    """Handle help button"""
    help_text = (
        "📖 <b>Справка по AI Bot</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/balance - Проверить баланс AI кредитов\n"
        "/pricing - Показать актуальные цены\n"
        "/image - Создать изображение\n"
        "/video - Создать видео\n\n"
        "Для подробной информации о ценах используйте /pricing"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="« Назад к инструментам", callback_data="other_tools")
    builder.adjust(1)

    await callback.message.edit_text(help_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_to_start")
async def callback_back_to_start(callback):
    """Go back to start menu"""
    from db.session import AsyncSessionLocal
    from ai_bot.services import CreditManager

    user_id = callback.from_user.id
    username = callback.from_user.username or "User"

    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        ai_credits = await credit_manager.get_user_credits(user_id) or 0

    welcome_text = (
        f"🤖 <b>Добро пожаловать в AI Bot!</b>\n\n"
        f"👋 Привет, {username}!\n\n"
        f"Я помогу вам создавать контент с помощью нейросетей:\n"
        f"🎨 <b>Генерация изображений</b> - Nano Banana\n"
        f"🎬 <b>Генерация видео</b> - Kling 2.6, VEO 3.1\n\n"
        f"💎 У вас <b>{ai_credits} AI кредитов</b>\n\n"
        f"Используйте команды ниже для начала работы:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 Изображение", callback_data="generate_image")
    builder.button(text="🎬 Видео", callback_data="generate_video")
    builder.button(text="🛠 Прочие инструменты", callback_data="other_tools")
    builder.button(text="ℹ️ Информация", callback_data="info")
    builder.button(text="💰 Купить кредиты", callback_data="buy_credits")
    builder.adjust(2, 1, 2)

    await callback.message.edit_text(
        welcome_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()
