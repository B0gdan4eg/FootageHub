"""
Модуль для работы с Freepik API
Документация: https://docs.freepik.com
"""
import aiohttp
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class ContentType(Enum):
    """Типы контента в Freepik"""
    PHOTO = "photo"
    VECTOR = "vector"
    PSD = "psd"
    VIDEO = "video"
    ICON = "icon"


class Orientation(Enum):
    """Ориентация изображения"""
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"
    PANORAMIC = "panoramic"


@dataclass
class FreepikResource:
    """Ресурс из Freepik"""
    id: str
    title: str
    url: str
    thumbnail: str
    preview: str
    download_url: Optional[str]
    content_type: str
    width: int
    height: int
    author: str
    license: str


class FreepikAPI:
    """Клиент для работы с Freepik API"""
    
    BASE_URL = "https://api.freepik.com/v1"
    
    def __init__(self, api_key: str):
        """
        Инициализация клиента
        
        Args:
            api_key: API ключ от Freepik (получить на https://www.freepik.com/api)
        """
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Создание сессии"""
        self.session = aiohttp.ClientSession(
            headers={"x-freepik-api-key": self.api_key}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
    
    async def search_resources(
        self,
        query: str,
        content_type: Optional[List[ContentType]] = None,
        orientation: Optional[Orientation] = None,
        limit: int = 20,
        page: int = 1,
        order: str = "relevance"  # relevance или recent
    ) -> Dict[str, Any]:
        """
        Поиск ресурсов в Freepik
        
        Args:
            query: Поисковый запрос
            content_type: Типы контента (photo, vector, video и т.д.)
            orientation: Ориентация (landscape, portrait и т.д.)
            limit: Количество результатов (1-200)
            page: Номер страницы
            order: Сортировка (relevance или recent)
        
        Returns:
            Словарь с результатами поиска
        """
        params = {
            "term": query,
            "limit": limit,
            "page": page,
            "order": order
        }

        # Добавляем фильтры в правильном формате для Freepik API
        # Freepik API принимает фильтры как отдельные параметры
        if content_type:
            # Преобразуем список типов в строку через запятую
            params["content_type"] = ",".join([ct.value for ct in content_type])

        if orientation:
            params["orientation"] = orientation.value

        url = f"{self.BASE_URL}/resources"

        async with self.session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_resource_details(self, resource_id: str) -> Dict[str, Any]:
        """
        Получить детальную информацию о ресурсе
        
        Args:
            resource_id: ID ресурса
        
        Returns:
            Словарь с информацией о ресурсе
        """
        url = f"{self.BASE_URL}/resources/{resource_id}"
        
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_download_url(
        self,
        resource_id: str,
        format_id: Optional[str] = None
    ) -> str:
        """
        Получить URL для скачивания ресурса

        Args:
            resource_id: ID ресурса
            format_id: ID формата (опционально, для выбора качества)

        Returns:
            URL для скачивания

        Raises:
            ClientResponseError: 403 если API ключ не имеет прав на скачивание
        """
        url = f"{self.BASE_URL}/resources/{resource_id}/download"

        params = {}
        if format_id:
            params["format"] = format_id

        async with self.session.get(url, params=params) as response:
            if response.status == 403:
                error_data = await response.json()
                error_msg = error_data.get("message", "Forbidden")
                raise PermissionError(
                    f"API ключ не имеет прав на скачивание. "
                    f"Ошибка: {error_msg}. "
                    f"Для скачивания нужен Premium API ключ."
                )
            response.raise_for_status()
            data = await response.json()
            return data.get("url", "")
    
    async def download_resource(
        self,
        resource_id: str,
        save_path: str,
        format_id: Optional[str] = None
    ) -> str:
        """
        Скачать ресурс
        
        Args:
            resource_id: ID ресурса
            save_path: Путь для сохранения
            format_id: ID формата (опционально)
        
        Returns:
            Путь к сохраненному файлу
        """
        download_url = await self.get_download_url(resource_id, format_id)
        
        async with self.session.get(download_url) as response:
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
        
        return save_path
    
    async def generate_ai_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        num_images: int = 1,
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Генерация изображения через AI (Mystic API)
        
        Args:
            prompt: Описание изображения
            negative_prompt: Что НЕ должно быть на изображении
            num_images: Количество вариантов (1-4)
            style: Стиль изображения
        
        Returns:
            Словарь с результатами генерации
        """
        url = f"{self.BASE_URL}/ai/text-to-image"
        
        payload = {
            "prompt": prompt,
            "num_images": num_images
        }
        
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        
        if style:
            payload["styling"] = {"style": style}
        
        async with self.session.post(url, json=payload) as response:
            response.raise_for_status()
            return await response.json()
    
    def parse_resources(self, response_data: Dict[str, Any]) -> List[FreepikResource]:
        """
        Парсинг результатов поиска в удобный формат
        
        Args:
            response_data: Ответ от API
        
        Returns:
            Список объектов FreepikResource
        """
        resources = []
        
        for item in response_data.get("data", []):
            resource = FreepikResource(
                id=item.get("id", ""),
                title=item.get("title", ""),
                url=item.get("url", ""),
                thumbnail=item.get("thumbnail", {}).get("url", ""),
                preview=item.get("preview", {}).get("url", ""),
                download_url=None,  # Получается отдельным запросом
                content_type=item.get("content_type", ""),
                width=item.get("image", {}).get("width", 0),
                height=item.get("image", {}).get("height", 0),
                author=item.get("author", {}).get("name", "Unknown"),
                license=item.get("license", "")
            )
            resources.append(resource)
        
        return resources


# Пример использования
async def main():
    """Пример работы с Freepik API"""
    
    # Получи API ключ на https://www.freepik.com/api
    API_KEY = "FPSX425319711947d200fc90811a3632d011"
    
    async with FreepikAPI(API_KEY) as api:
        # Поиск фотографий природы
        print("🔍 Ищу фотографии природы...")
        results = await api.search_resources(
            query="nature landscape",
            content_type=[ContentType.PHOTO],
            orientation=Orientation.LANDSCAPE,
            limit=10
        )
        
        resources = api.parse_resources(results)
        
        print(f"\n✅ Найдено {len(resources)} ресурсов:\n")
        
        for i, resource in enumerate(resources, 1):
            print(f"{i}. {resource.title}")
            print(f"   ID: {resource.id}")
            print(f"   Размер: {resource.width}x{resource.height}")
            print(f"   Автор: {resource.author}")
            print(f"   Preview: {resource.preview}")
            print()
        
        # Попытка скачать первый результат
        if resources:
            first = resources[0]
            print(f"\n📥 Попытка получить ссылку на скачивание: {first.title}...")

            try:
                download_url = await api.get_download_url(first.id)
                print(f"   ✅ URL: {download_url}")

                # Можно скачать файл
                # await api.download_resource(first.id, f"downloads/{first.id}.jpg")
            except PermissionError as e:
                print(f"   ⚠️ {e}")
                print(f"   💡 Используй Premium API ключ для скачивания или используй Playwright метод")
        
        # AI генерация изображения
        print("\n🎨 Генерирую AI изображение...")
        ai_result = await api.generate_ai_image(
            prompt="Beautiful sunset over mountains, photorealistic",
            negative_prompt="blurry, low quality",
            num_images=1
        )
        
        print(f"   Результат: {ai_result}")


if __name__ == "__main__":
    asyncio.run(main())