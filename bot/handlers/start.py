from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode

from db.session import get_session
from db.user_crud import get_user_by_telegram_id, create_user
from bot.keyboards import main_menu_kb

router = Router()

WELCOME_MESSAGE = """
<b>👋 Привет, {name}!</b>
Добро пожаловать в наш бот 🎬 Здесь ты найдёшь:

• 🖼️ Картинки высокого качества  
• 📂 Готовые шаблоны для проектов  
• 🎞️ Футажи для монтажа и оформления видео  

📢 Не пропусти обновления и бонусы — <a href="https://t.me/+HVUoctN58uc3ZDYy">подпишись на канал</a>  
💬 Пообщаться с другими — <a href="https://t.me/+Km5vuADpc1FmMTMy">вступи в чат</a>

💳 Быстрая и безопасная оплата  
⬇️ Скачивание файлов сразу после покупки

Если возникли вопросы — используй команду <b>/support</b>

🎉 Приятных покупок и вдохновения для новых проектов!
"""

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id

    # Получаем сессию и регистрируем пользователя при необходимости
    async for session in get_session():
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await create_user(session, telegram_id)

    # Отправляем приветствие
    await message.answer(
        WELCOME_MESSAGE.format(name=message.from_user.first_name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb,
        disable_web_page_preview=True
    )
