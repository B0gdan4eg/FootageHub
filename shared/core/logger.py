"""
Централизованное логирование для FootageHub.

Предоставляет унифицированную систему логирования для всех микросервисов.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли"""

    # ANSI цветовые коды
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{self.BOLD}{record.levelname}{self.RESET}"
        record.name = f"{self.BOLD}{record.name}{self.RESET}"
        return super().format(record)


class FootageHubLogger:
    """
    Централизованный логгер для FootageHub.

    Поддерживает:
    - Логирование в консоль с цветным выводом
    - Логирование в файлы с ротацией
    - Различные уровни логирования для разных компонентов
    - Структурированное логирование
    """

    _instance: Optional["FootageHubLogger"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not FootageHubLogger._initialized:
            self._loggers = {}
            self._log_dir = Path("logs")
            self._log_dir.mkdir(exist_ok=True)
            FootageHubLogger._initialized = True

    def get_logger(
        self,
        name: str,
        level: int = logging.INFO,
        log_to_file: bool = True,
        log_to_console: bool = True,
        file_max_bytes: int = 10 * 1024 * 1024,  # 10MB
        file_backup_count: int = 5,
    ) -> logging.Logger:
        """
        Получить или создать логгер.

        Args:
            name: Имя логгера (например, "media_bot", "ai_bot")
            level: Уровень логирования
            log_to_file: Логировать в файл
            log_to_console: Логировать в консоль
            file_max_bytes: Максимальный размер лог файла
            file_backup_count: Количество backup файлов

        Returns:
            Настроенный логгер
        """
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        # Очистка существующих handlers
        logger.handlers.clear()

        # Console handler с цветным выводом
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)

            console_formatter = ColoredFormatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # File handler с ротацией
        if log_to_file:
            log_file = self._log_dir / f"{name}.log"

            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=file_max_bytes,
                backupCount=file_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)

            file_formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        # Сохранение логгера
        self._loggers[name] = logger
        return logger

    def get_error_logger(self, name: str, log_dir: Optional[Path] = None) -> logging.Logger:
        """
        Получить специальный логгер только для ошибок.

        Args:
            name: Имя логгера
            log_dir: Директория для логов (по умолчанию logs/)

        Returns:
            Логгер только для ERROR и CRITICAL уровней
        """
        error_logger_name = f"{name}_errors"

        if error_logger_name in self._loggers:
            return self._loggers[error_logger_name]

        logger = logging.getLogger(error_logger_name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False

        # Определение директории для error логов
        if log_dir is None:
            log_dir = self._log_dir / "errors"
        log_dir.mkdir(exist_ok=True, parents=True)

        # File handler для ошибок с ежедневной ротацией
        error_file = log_dir / f"{name}_errors.log"
        error_handler = TimedRotatingFileHandler(
            filename=error_file,
            when="midnight",
            interval=1,
            backupCount=30,  # Храним 30 дней
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)

        error_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(pathname)s:%(lineno)d | %(message)s\n"
            "Exception: %(exc_info)s\n",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        error_handler.setFormatter(error_formatter)
        logger.addHandler(error_handler)

        self._loggers[error_logger_name] = logger
        return logger

    @staticmethod
    def setup_media_bot_logger(level: int = logging.INFO) -> logging.Logger:
        """
        Быстрая настройка логгера для MediaBot.

        Args:
            level: Уровень логирования

        Returns:
            Настроенный логгер
        """
        fh_logger = FootageHubLogger()
        return fh_logger.get_logger("media_bot", level=level)

    @staticmethod
    def setup_ai_bot_logger(level: int = logging.INFO) -> logging.Logger:
        """
        Быстрая настройка логгера для AIBot.

        Args:
            level: Уровень логирования

        Returns:
            Настроенный логгер
        """
        fh_logger = FootageHubLogger()
        return fh_logger.get_logger("ai_bot", level=level)

    @staticmethod
    def setup_shared_logger(level: int = logging.INFO) -> logging.Logger:
        """
        Быстрая настройка логгера для shared модулей.

        Args:
            level: Уровень логирования

        Returns:
            Настроенный логгер
        """
        fh_logger = FootageHubLogger()
        return fh_logger.get_logger("shared", level=level)


# Удобные функции для быстрого доступа


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Получить логгер по имени.

    Args:
        name: Имя логгера
        level: Уровень логирования

    Returns:
        Настроенный логгер
    """
    fh_logger = FootageHubLogger()
    return fh_logger.get_logger(name, level=level)


def get_media_bot_logger() -> logging.Logger:
    """Получить логгер для MediaBot"""
    return FootageHubLogger.setup_media_bot_logger()


def get_ai_bot_logger() -> logging.Logger:
    """Получить логгер для AIBot"""
    return FootageHubLogger.setup_ai_bot_logger()


def get_shared_logger() -> logging.Logger:
    """Получить логгер для shared модулей"""
    return FootageHubLogger.setup_shared_logger()


# Структурированное логирование


class StructuredLogger:
    """
    Структурированное логирование с дополнительными полями.

    Позволяет добавлять контекстную информацию к логам.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context = {}

    def add_context(self, **kwargs):
        """Добавить контекст к логам"""
        self.context.update(kwargs)

    def clear_context(self):
        """Очистить контекст"""
        self.context = {}

    def _format_message(self, message: str) -> str:
        """Форматировать сообщение с контекстом"""
        if self.context:
            context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{message} | {context_str}"
        return message

    def debug(self, message: str, **extra):
        """Лог DEBUG уровня"""
        self.logger.debug(self._format_message(message), extra=extra)

    def info(self, message: str, **extra):
        """Лог INFO уровня"""
        self.logger.info(self._format_message(message), extra=extra)

    def warning(self, message: str, **extra):
        """Лог WARNING уровня"""
        self.logger.warning(self._format_message(message), extra=extra)

    def error(self, message: str, exc_info=None, **extra):
        """Лог ERROR уровня"""
        self.logger.error(self._format_message(message), exc_info=exc_info, extra=extra)

    def critical(self, message: str, exc_info=None, **extra):
        """Лог CRITICAL уровня"""
        self.logger.critical(self._format_message(message), exc_info=exc_info, extra=extra)


# Пример использования:
#
# from shared.core.logger import get_logger, StructuredLogger
#
# # Обычный логгер
# logger = get_logger("my_service")
# logger.info("Service started")
#
# # Структурированный логгер
# struct_logger = StructuredLogger(logger)
# struct_logger.add_context(user_id=123, request_id="abc-def")
# struct_logger.info("User action") # Вывод: User action | user_id=123 | request_id=abc-def
#
# # Специализированные логгеры
# media_bot_logger = get_media_bot_logger()
# ai_bot_logger = get_ai_bot_logger()
