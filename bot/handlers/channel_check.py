# channel_check.py
from aiogram import Bot
from aiogram.types import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError

# ID или @username канала
CHANNEL_ID = "@footageChanel"  # например, "@mycoolchannel"

async def is_subscribed(bot: Bot, tg_user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    
    :param bot: Экземпляр бота (aiogram.Bot)
    :param user_id: ID пользователя
    :return: True если подписан, иначе False
    """
    try:
        member = await bot.get_chat_member(CHANNEL_ID, tg_user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        )
    except TelegramForbiddenError:
        # Бот не имеет доступа к информации о канале
        return False
    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
        return False
