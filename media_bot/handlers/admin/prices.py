"""
Price management functionality for admin panel.
"""

import json
from io import BytesIO

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext

from media_bot.config import PRICE_LIST_PATH as PRICE_LIST
from media_bot.state import AdminStates

# Create a separate router for price functions
router = Router()


@router.callback_query(lambda c: c.data == "admin_upload_prices")
async def upload_prices(callback: types.CallbackQuery, state: FSMContext):
    """Запрос загрузки JSON с ценами"""
    await state.set_state(AdminStates.waiting_for_price_json)
    await callback.message.answer("Отправьте JSON с ценами (например, кредиты и подписки):")
    await callback.answer()


@router.message(AdminStates.waiting_for_price_json, F.content_type == "document")
async def receive_price_json(message: types.Message, state: FSMContext, bot: Bot):
    """Получение и сохранение JSON с ценами"""
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
