"""
Envato Elements downloader wrapper

Wrapper around existing envato_utils.envato_playwright module.
Preserves all existing functionality without modification.
"""

from typing import Optional

# Import existing Envato utilities (не модифицируем их)
from envato_utils.envato_playwright import check_envato_auth
from envato_utils.envato_playwright import download_file as envato_download_file
from envato_utils.envato_playwright import rotate_envato_cookies

from .base import AbstractDownloader


class EnvatoDownloader(AbstractDownloader):
    """
    Загрузчик для Envato Elements.

    Обертка над существующим envato_utils.envato_playwright.
    Сохраняет весь существующий функционал без изменений.
    """

    async def download(self, url: str) -> Optional[str]:
        """
        Загрузить файл с Envato Elements.

        Args:
            url: Ссылка на элемент Envato Elements

        Returns:
            str: URL загруженного файла или None при ошибке
        """
        # Используем существующую логику из envato_utils
        return await envato_download_file(url)

    async def check_auth(self) -> bool:
        """
        Проверить авторизацию на Envato Elements.

        Returns:
            bool: True если cookies валидны
        """
        return await check_envato_auth()

    async def rotate_cookies(self) -> None:
        """
        Переключиться на следующий Envato аккаунт.
        """
        await rotate_envato_cookies()

    def get_platform_name(self) -> str:
        """
        Получить название платформы.

        Returns:
            str: "Envato Elements"
        """
        return "Envato Elements"
