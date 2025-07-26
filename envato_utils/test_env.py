import asyncio
from envato_utils.envato_playwright import get_envato_direct_download_url  # замените на актуальный импорт

async def test(url: str):
    #url = "https://elements.envato.com/ru/dog-excited-about-his-walk-in-the-park-C24L97T"
    download_url = await get_envato_direct_download_url(url)
    if download_url:
        print("Ссылка на скачивание:", download_url)
    else:
        print("Не удалось получить ссылку")
    return download_url
# asyncio.run(test())