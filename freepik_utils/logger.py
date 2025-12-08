"""
Универсальный логгер для отправки сообщений в Telegram админу
Используется для Freepik, Envato, Filesta и других сервисов
"""
import os
from typing import Optional
from datetime import datetime


class TelegramLogger:
    """
    Универсальный логгер с отправкой в Telegram

    Использование:
        from freepik_utils.logger import logger

        # В main.py
        logger.set_bot(bot, admin_chat_id=-1001234567890)

        # В любом месте кода
        await logger.error("❌ Произошла ошибка")
        await logger.warning("⚠️ Предупреждение")
        await logger.info("ℹ️ Информация")
    """

    def __init__(self):
        self.bot = None
        self.admin_chat_id = None
        self._enabled = True

    def set_bot(self, bot, admin_chat_id: Optional[int] = None):
        """
        Установить бот для отправки сообщений

        Args:
            bot: Экземпляр aiogram Bot
            admin_chat_id: ID чата/группы админа (если не указан, берется из env ADMIN_CHAT_ID)
        """
        self.bot = bot

        # Пытаемся получить из параметра, потом из env, потом из env как строку
        if admin_chat_id:
            self.admin_chat_id = admin_chat_id
        else:
            chat_id_str = os.getenv('ADMIN_CHAT_ID')
            if chat_id_str:
                try:
                    self.admin_chat_id = int(chat_id_str)
                except ValueError:
                    print(f"⚠️ ADMIN_CHAT_ID должен быть числом, получено: {chat_id_str}")
                    self.admin_chat_id = None

        if self.admin_chat_id:
            print(f"✅ Логгер настроен. Ошибки будут отправляться в чат: {self.admin_chat_id}")
        else:
            print("⚠️ ADMIN_CHAT_ID не установлен. Ошибки будут только в консоли.")

    def disable(self):
        """Отключить отправку в Telegram (только консоль)"""
        self._enabled = False

    def enable(self):
        """Включить отправку в Telegram"""
        self._enabled = True

    async def error(self, message: str, send_to_telegram: bool = True, screenshot_path: Optional[str] = None):
        """
        Логировать ошибку (в консоль + Telegram админу)

        Args:
            message: Текст сообщения об ошибке
            send_to_telegram: Отправлять ли в Telegram (по умолчанию True)
            screenshot_path: Путь к скриншоту для отправки (опционально)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console_message = f"[{timestamp}] {message}"

        # Всегда выводим в консоль
        print(console_message)

        # Отправляем в Telegram если настроено и разрешено
        if send_to_telegram and self._enabled and self.bot and self.admin_chat_id:
            try:
                # Если есть скриншот, отправляем его с подписью
                if screenshot_path and os.path.exists(screenshot_path):
                    from aiogram.types import FSInputFile
                    photo = FSInputFile(screenshot_path)
                    await self.bot.send_photo(
                        self.admin_chat_id,
                        photo=photo,
                        caption=message[:1024]  # Telegram limit for caption
                    )
                    # Удаляем скриншот после успешной отправки
                    try:
                        os.remove(screenshot_path)
                        print(f"🗑️ Скриншот удален: {os.path.basename(screenshot_path)}")
                    except Exception as rm_error:
                        print(f"⚠️ Не удалось удалить скриншот: {rm_error}")
                else:
                    # Просто текстовое сообщение
                    await self.bot.send_message(self.admin_chat_id, message, parse_mode=None)
            except Exception as e:
                print(f"⚠️ Не удалось отправить ошибку в Telegram: {e}")

    async def warning(self, message: str, send_to_telegram: bool = False):
        """
        Логировать предупреждение (в консоль, опционально в Telegram)

        Args:
            message: Текст предупреждения
            send_to_telegram: Отправлять ли в Telegram (по умолчанию False для warning)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console_message = f"[{timestamp}] {message}"
        print(console_message)

        if send_to_telegram and self._enabled and self.bot and self.admin_chat_id:
            try:
                await self.bot.send_message(self.admin_chat_id, message, parse_mode=None)
            except Exception as e:
                print(f"⚠️ Не удалось отправить предупреждение в Telegram: {e}")

    def info(self, message: str):
        """
        Просто вывод в консоль без отправки в Telegram

        Args:
            message: Информационное сообщение
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")


# Глобальный экземпляр логгера
logger = TelegramLogger()
