"""
Start command handler for AI Bot
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or "User"

    welcome_text = (
        f"🤖 <b>Добро пожаловать в AI Bot!</b>\n\n"
        f"👋 Привет, {username}!\n\n"
        f"Я помогу вам создавать контент с помощью нейросетей:\n"
        f"🎨 <b>Генерация изображений</b> - Nano Banana\n"
        f"🎬 <b>Генерация видео</b> - Kling 2.6, VEO 3.1\n\n"
        f"💎 У вас <b>0 AI кредитов</b>\n\n"
        f"Используйте команды ниже для начала работы:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 Создать изображение", callback_data="generate_image")
    builder.button(text="🎬 Создать видео", callback_data="generate_video")
    builder.button(text="💰 Купить AI кредиты", callback_data="buy_credits")
    builder.button(text="ℹ️ Помощь", callback_data="help")
    builder.adjust(1)

    await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        "📖 <b>Справка по AI Bot</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/balance - Проверить баланс AI кредитов\n"
        "/image - Создать изображение\n"
        "/video - Создать видео\n\n"
        "<b>Стоимость генерации:</b>\n"
        "🎨 Изображение - 1 AI кредит\n"
        "🎬 Видео - 5 AI кредитов\n\n"
        "<b>Поддержка:</b> @support"
    )

    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Handle /balance command"""
    # TODO: Get actual balance from database
    balance_text = (
        "💎 <b>Ваш баланс</b>\n\n"
        "AI кредиты: <b>0</b>\n\n"
        "Хотите пополнить? Нажмите /buy"
    )

    await message.answer(balance_text, parse_mode="HTML")


@router.callback_query(F.data == "generate_image")
async def callback_generate_image(callback):
    """Handle image generation button"""
    await callback.message.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Эта функция находится в разработке.\n"
        "Скоро вы сможете создавать изображения с помощью AI!",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "generate_video")
async def callback_generate_video(callback):
    """Handle video generation button"""
    await callback.message.answer(
        "🎬 <b>Генерация видео</b>\n\n"
        "Эта функция находится в разработке.\n"
        "Скоро вы сможете создавать видео с помощью AI!",
        parse_mode="HTML"
    )
    await callback.answer()


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


@router.callback_query(F.data == "help")
async def callback_help(callback):
    """Handle help button"""
    help_text = (
        "📖 <b>Справка по AI Bot</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/balance - Проверить баланс AI кредитов\n\n"
        "<b>Стоимость генерации:</b>\n"
        "🎨 Изображение - 1 AI кредит\n"
        "🎬 Видео - 5 AI кредитов"
    )

    await callback.message.answer(help_text, parse_mode="HTML")
    await callback.answer()
