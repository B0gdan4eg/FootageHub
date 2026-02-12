"""I18n middleware — определяет язык пользователя и инжектит в data['lang']."""

from aiogram import BaseMiddleware

from media_bot.handlers.messages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from shared.db.repositories.user_repository import UserRepository
from shared.db.session import get_session


class I18nMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        lang = DEFAULT_LANGUAGE
        from_user = data.get("event_from_user")
        if from_user:
            try:
                async for session in get_session():
                    user = await UserRepository(session).get_by_telegram_id(from_user.id)
                    if user and user.username in SUPPORTED_LANGUAGES:
                        lang = user.username
                    elif from_user.language_code and from_user.language_code[:2] in SUPPORTED_LANGUAGES:
                        lang = from_user.language_code[:2]
            except Exception:
                pass
        data["lang"] = lang
        return await handler(event, data)
