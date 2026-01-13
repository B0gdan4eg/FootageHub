"""
Database export and restore functionality for admin panel.
"""

from enum import Enum
from pathlib import Path

import openpyxl
from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from media_bot.state import AdminStates
from shared.core.logger import get_logger
from shared.db.models import Download, Media, Payment, ReferralReward, Subscription, User
from shared.db.session import get_session

# Create a separate router for database functions
router = Router()

# Setup logger
logger = get_logger(__name__)
logger.info("DATABASE HANDLER MODULE LOADED - LOGGER ACTIVE")


async def export_full_db_and_send(session: AsyncSession, bot: Bot, chat_id: int):
    """
    Экспортирует все таблицы БД в XLSX и отправляет в Telegram.
    """
    logger.info(f"Starting database export for chat_id: {chat_id}")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Удаляем пустой первый лист

    # Список моделей и названия листов
    tables = [
        (User, "Users"),
        (Media, "Media"),
        (Download, "Downloads"),
        (Payment, "Payments"),
        (Subscription, "Subscriptions"),
        (ReferralReward, "ReferralRewards"),
    ]

    for model, sheet_name in tables:
        logger.info(f"Exporting table: {sheet_name}")
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
    logger.info(f"Database exported to file: {file_path}")

    try:
        await bot.send_document(
            chat_id=chat_id, document=FSInputFile(file_path), caption="📊 Полный экспорт базы данных"
        )
        logger.info(f"Database export sent to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send database export: {e}", exc_info=True)
        raise
    finally:
        # Удаляем файл после отправки
        import os

        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Temporary file removed: {file_path}")


async def export_db_callback(callback_query: types.CallbackQuery, bot: Bot):
    """Экспорт базы данных в XLSX"""
    logger.info(f"Export DB callback triggered by user: {callback_query.from_user.id}")
    try:
        async for session in get_session():
            await export_full_db_and_send(session, bot, callback_query.message.chat.id)
        await callback_query.answer("📁 База выгружена!")
        logger.info(
            f"Database export completed successfully for user: {callback_query.from_user.id}"
        )
    except Exception as e:
        logger.error(
            f"Database export failed for user {callback_query.from_user.id}: {e}", exc_info=True
        )
        await callback_query.answer("❌ Ошибка при экспорте базы данных", show_alert=True)
        raise


async def restore_db_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало восстановления базы данных - выбор режима"""
    from media_bot.handlers.admin.core import is_admin

    print(f"[DEBUG] Restore DB callback triggered by user: {callback.from_user.id}")
    logger.info(f"Restore DB callback triggered by user: {callback.from_user.id}")

    if not await is_admin(callback.from_user.id):
        print(f"[DEBUG] Unauthorized restore DB attempt by user: {callback.from_user.id}")
        logger.warning(f"Unauthorized restore DB attempt by user: {callback.from_user.id}")
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    # Показываем выбор режима
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Полная перезапись (очистить БД)",
                    callback_data="rst_9x4q2w",  # restore_mode_full obfuscated
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Обновление (добавить новые)",
                    callback_data="rst_3v7h8k",  # restore_mode_update obfuscated
                )
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="rst_5z1n6c")
            ],  # restore_mode_cancel obfuscated
        ]
    )

    await callback.message.answer(
        "🔄 <b>Восстановление базы данных</b>\n\n"
        "Выберите режим восстановления:\n\n"
        "<b>🔄 Полная перезапись:</b>\n"
        "• Удалит ВСЕ данные из БД\n"
        "• Загрузит данные из Excel с сохранением всех ID\n"
        "• Подходит для полного восстановления\n\n"
        "<b>➕ Обновление:</b>\n"
        "• Добавит только новые записи\n"
        "• Обновит существующие данные\n"
        "• Пропустит дубликаты\n"
        "• Безопасный режим",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()
    print("[DEBUG] Restore mode selection shown")
    logger.info(f"Restore mode selection shown for user: {callback.from_user.id}")


@router.callback_query(lambda c: c.data == "rst_9x4q2w")
async def restore_mode_full_callback(callback: types.CallbackQuery, state: FSMContext):
    """Режим полной перезаписи БД"""
    from media_bot.handlers.admin.core import is_admin

    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    await state.update_data(restore_mode="full", clear_before=True)
    await state.set_state(AdminStates.waiting_for_restore_xlsx)

    await callback.message.answer(
        "🔄 <b>Режим: Полная перезапись</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n"
        "Все данные в БД будут УДАЛЕНЫ!\n\n"
        "Отправьте XLSX файл с экспортом базы данных.\n\n"
        "📋 <b>Требования к файлу:</b>\n"
        "• Листы: Users, Media, Downloads, Payments, Subscriptions, ReferralRewards\n"
        "• Все ID из Excel будут сохранены\n"
        "• Все связи между таблицами будут восстановлены\n\n"
        "Отправьте 'отмена' для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()
    logger.info(f"Full restore mode selected by user: {callback.from_user.id}")


@router.callback_query(lambda c: c.data == "rst_3v7h8k")
async def restore_mode_update_callback(callback: types.CallbackQuery, state: FSMContext):
    """Режим обновления БД"""
    from media_bot.handlers.admin.core import is_admin

    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return

    await state.update_data(restore_mode="update", clear_before=False)
    await state.set_state(AdminStates.waiting_for_restore_xlsx)

    await callback.message.answer(
        "➕ <b>Режим: Обновление</b>\n\n"
        "✅ Безопасный режим\n\n"
        "Отправьте XLSX файл с экспортом базы данных.\n\n"
        "📋 <b>Что произойдёт:</b>\n"
        "• Новые записи будут добавлены\n"
        "• Существующие записи будут обновлены\n"
        "• Дубликаты будут пропущены\n"
        "• Данные не удаляются\n\n"
        "Отправьте 'отмена' для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()
    logger.info(f"Update restore mode selected by user: {callback.from_user.id}")


@router.callback_query(lambda c: c.data == "rst_5z1n6c")
async def restore_mode_cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    """Отмена восстановления БД"""
    await state.clear()
    await callback.message.answer("❌ Восстановление базы отменено.")
    await callback.answer()
    logger.info(f"Restore cancelled by user: {callback.from_user.id}")


@router.message(AdminStates.waiting_for_restore_xlsx, F.content_type == "document")
async def receive_restore_xlsx(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка загруженного XLSX файла для восстановления базы"""
    print("[DEBUG] ========== RESTORE DB FILE RECEIVED ==========")
    print(f"[DEBUG] User: {message.from_user.id}, File: {message.document.file_name}")
    logger.info(
        f"Restore DB file received from user: {message.from_user.id}, file: {message.document.file_name}"
    )
    try:
        # Скачиваем файл
        print("[DEBUG] Getting file from Telegram...")
        file = await bot.get_file(message.document.file_id)
        file_path = file.file_path
        print(f"[DEBUG] File path from Telegram: {file_path}")

        # Сохраняем во временную директорию
        import tempfile

        temp_dir = tempfile.gettempdir()
        local_file_path = (
            Path(temp_dir) / f"restore_{message.from_user.id}_{message.document.file_name}"
        )
        print(f"[DEBUG] Local file path: {local_file_path}")

        print("[DEBUG] Downloading file...")
        await bot.download_file(file_path, local_file_path)
        print("[DEBUG] File downloaded successfully!")
        logger.info(f"File downloaded to: {local_file_path}")

        # Проверяем, что это XLSX файл
        if not str(local_file_path).endswith((".xlsx", ".xls")):
            print(f"[DEBUG] Invalid file format: {local_file_path}")
            logger.warning(f"Invalid file format: {local_file_path}")
            local_file_path.unlink(missing_ok=True)
            return await message.answer("❌ Файл должен быть в формате XLSX")

        print("[DEBUG] File format is valid")
        # Отправляем сообщение о начале восстановления
        status_msg = await message.answer(
            "⏳ <b>Восстановление базы данных...</b>\n\n" "Это может занять некоторое время.",
            parse_mode="HTML",
        )
        print("[DEBUG] Status message sent")

        # Импортируем функцию восстановления
        print("[DEBUG] Importing restore_database function...")
        from shared.db.from_xlsx import restore_database

        # Получаем выбранный режим из state
        data = await state.get_data()
        restore_mode = data.get("restore_mode", "update")
        clear_before = data.get("clear_before", False)

        print(f"[DEBUG] Restore mode: {restore_mode}, Clear before: {clear_before}")
        logger.info(f"Restore mode: {restore_mode}, Clear before: {clear_before}")

        # Запускаем восстановление
        print("[DEBUG] Starting database restore...")
        logger.info(f"Starting database restore from file: {local_file_path}")
        try:
            await restore_database(
                str(local_file_path), mode=restore_mode, clear_before=clear_before
            )
            print("[DEBUG] Database restore completed successfully!")

            if restore_mode == "full":
                result_text = (
                    "✅ <b>База данных полностью восстановлена!</b>\n\n"
                    "• Все старые данные были удалены\n"
                    "• Данные из файла загружены с сохранением ID\n"
                    "• Все связи восстановлены"
                )
            else:
                result_text = (
                    "✅ <b>База данных обновлена!</b>\n\n"
                    "• Новые записи добавлены\n"
                    "• Существующие записи обновлены\n"
                    "• Дубликаты пропущены"
                )

            await status_msg.edit_text(result_text, parse_mode="HTML")
            print("[DEBUG] Success message sent to user")
            logger.info(f"Database restore completed successfully for user: {message.from_user.id}")
        except Exception as e:
            print(f"[DEBUG] ERROR during database restore: {e}")
            import html
            import traceback

            print("[DEBUG] Traceback:")
            traceback.print_exc()

            # Экранируем HTML теги в сообщении об ошибке
            error_msg = html.escape(str(e)[:500])

            await status_msg.edit_text(
                f"❌ <b>Ошибка при восстановлении базы:</b>\n\n" f"<code>{error_msg}</code>",
                parse_mode="HTML",
            )
            logger.error(f"Database restore error: {e}", exc_info=True)
        finally:
            # Удаляем временный файл
            print(f"[DEBUG] Removing temporary file: {local_file_path}")
            local_file_path.unlink(missing_ok=True)
            print("[DEBUG] Temporary file removed")
            logger.info(f"Temporary file removed: {local_file_path}")

    except Exception as e:
        print(f"[DEBUG] CRITICAL ERROR processing restore file: {e}")
        import html
        import traceback

        print("[DEBUG] Traceback:")
        traceback.print_exc()
        logger.error(f"Error processing restore file: {e}", exc_info=True)

        # Экранируем HTML теги в сообщении об ошибке
        error_msg = html.escape(str(e)[:500])

        return await message.answer(
            f"❌ Ошибка при обработке файла:\n\n" f"<code>{error_msg}</code>", parse_mode="HTML"
        )

    print("[DEBUG] Clearing state...")
    await state.clear()
    print("[DEBUG] State cleared successfully")
    print("[DEBUG] ========== RESTORE DB FINISHED ==========")
    logger.info(f"Restore DB state cleared for user: {message.from_user.id}")


@router.message(AdminStates.waiting_for_restore_xlsx, F.text)
async def cancel_restore_db(message: types.Message, state: FSMContext):
    """Отмена восстановления базы"""
    if message.text.lower() in ["отмена", "cancel", "q"]:
        await state.clear()
        await message.answer("❌ Восстановление базы отменено.")
    else:
        await message.answer("❌ Пожалуйста, отправьте XLSX файл или напишите 'отмена' для отмены.")
