"""
Abstract base class for all downloaders

This provides a common interface for Envato, Freepik, and Motion Array downloaders.
Following the Liskov Substitution Principle - all downloaders can be used interchangeably.
"""

from abc import ABC, abstractmethod
from typing import Optional


class AbstractDownloader(ABC):
    """
    Базовый класс для всех загрузчиков медиа контента.

    Определяет общий интерфейс для загрузки файлов с различных платформ.
    Конкретные реализации должны наследоваться от этого класса и
    реализовать все абстрактные методы.
    """

    @abstractmethod
    async def download(self, url: str) -> Optional[str]:
        """
        Загрузить медиа файл по URL.

        Args:
            url: Ссылка на файл для загрузки

        Returns:
            str: Путь к загруженному файлу или URL для загрузки
            None: Если загрузка не удалась

        Raises:
            InvalidUrlError: Если URL некорректен
            DownloadError: Если произошла ошибка при загрузке
        """

    @abstractmethod
    async def check_auth(self) -> bool:
        """
        Проверить авторизацию на платформе.

        Returns:
            bool: True если авторизация действительна, False иначе
        """

    @abstractmethod
    async def rotate_cookies(self) -> None:
        """
        Выполнить ротацию cookies (переключение на следующий аккаунт).

        Используется когда текущие cookies перестали работать
        или для распределения нагрузки между аккаунтами.
        """

    @abstractmethod
    def get_platform_name(self) -> str:
        """
        Получить название платформы.

        Returns:
            str: Название платформы (например, "Envato", "Freepik")
        """
