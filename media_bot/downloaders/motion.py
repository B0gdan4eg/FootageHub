"""
Motion Array downloader wrapper

Wrapper around existing motion_utils.motion module.
Preserves all existing functionality without modification.
"""

from typing import Optional

# Import existing Motion Array utilities (не модифицируем их)
from motion_utils.motion import get_motion_direct_download_url

from .base import AbstractDownloader


class MotionDownloader(AbstractDownloader):
    """
    Загрузчик для Motion Array.

    Обертка над существующим motion_utils.motion.
    Сохраняет весь существующий функционал без изменений.
    """

    async def download(self, url: str) -> Optional[str]:
        """
        Получить прямую ссылку на загрузку с Motion Array.

        Args:
            url: Ссылка на ресурс Motion Array

        Returns:
            str: URL для загрузки файла или None при ошибке
        """
        # Используем существующую логику из motion_utils
        return await get_motion_direct_download_url(url)

    async def check_auth(self) -> bool:
        """
        Проверить авторизацию на Motion Array.

        Note: Motion Array не имеет отдельной функции проверки авторизации.
        Возвращаем True, т.к. авторизация проверяется во время загрузки.

        Returns:
            bool: True (проверка происходит при загрузке)
        """
        # TODO: Добавить отдельную функцию проверки в motion_utils если потребуется
        return True

    async def rotate_cookies(self) -> None:
        """
        Переключиться на следующий Motion Array аккаунт.

        Note: Ротация cookies происходит автоматически в get_next_cookie_file()
        при каждом вызове download(). Отдельный метод ротации не требуется.
        """
        # Ротация происходит автоматически в motion_utils.motion.get_next_cookie_file()
        pass

    def get_platform_name(self) -> str:
        """
        Получить название платформы.

        Returns:
            str: "Motion Array"
        """
        return "Motion Array"
