"""
Cookie upload functionality for admin panel.
"""

import json
from io import BytesIO
from pathlib import Path

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext

from media_bot.state import AdminStates

# Create a separate router for cookie functions
router = Router()


@router.callback_query(lambda c: c.data == "admin_upload_cookies")
async def upload_cookies(callback: types.CallbackQuery, state: FSMContext):
    """Запрос загрузки JSON с cookies"""
    await state.set_state(AdminStates.waiting_for_cookies_json)
    await callback.message.answer("Отправьте JSON с cookies (envato_cookies.json):")
    await callback.answer()


@router.message(AdminStates.waiting_for_cookies_json, F.content_type == "document")
async def receive_cookies_json(message: types.Message, state: FSMContext, bot: Bot):
    """Получение и сохранение JSON с cookies"""
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
