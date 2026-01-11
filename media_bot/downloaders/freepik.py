"""
Freepik downloader wrapper

Wrapper around existing freepik_utils.freepik module.
Preserves all existing functionality without modification.
"""

from typing import Optional

# Import existing Freepik utilities (не модифицируем их)
from freepik_utils.freepik import check_freepik_auth
from freepik_utils.freepik import download_file as freepik_download_file
from freepik_utils.freepik import rotate_freepik_cookies

from .base import AbstractDownloader


class FreepikDownloader(AbstractDownloader):
    """
    Загрузчик для Freepik.

    Обертка над существующим freepik_utils.freepik.
    Сохраняет весь существующий функционал без изменений.
    """

    async def download(self, url: str) -> Optional[str]:
        """
        Загрузить файл с Freepik.

        Args:
            url: Ссылка на ресурс Freepik

        Returns:
            str: URL загруженного файла или None при ошибке
        """
        # Используем существующую логику из freepik_utils
        return await freepik_download_file(url)

    async def check_auth(self) -> bool:
        """
        Проверить авторизацию на Freepik.

        Returns:
            bool: True если cookies валидны
        """
        return await check_freepik_auth()

    async def rotate_cookies(self) -> None:
        """
        Переключиться на следующий Freepik аккаунт.
        """
        await rotate_freepik_cookies()

    def get_platform_name(self) -> str:
        """
        Получить название платформы.

        Returns:
            str: "Freepik"
        """
        return "Freepik"
