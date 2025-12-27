"""
Credits Handlers

Handlers for checking AI credits balance and usage
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from ai_bot.services import CreditManager, PricingService
from db.session import AsyncSessionLocal

router = Router()


@router.message(Command("balance"))
@router.message(Command("credits"))
async def cmd_check_balance(message: Message):
    """Check user's AI credits balance"""
    user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)
        pricing_service = PricingService()

        # Get user stats
        stats = await credit_manager.get_user_stats(user_id)

        if not stats:
            await message.answer(
                "❌ <b>Профиль не найден</b>\n\n"
                "Используйте /start для регистрации"
            )
            return

        # Get Kie.ai credits (optional, might fail)
        kie_credits = None
        try:
            kie_credits = await pricing_service.get_kie_credits()
        except Exception:
            pass  # Fail silently

        # Build response
        text = (
            "💎 <b>Ваш баланс AI кредитов</b>\n\n"
            f"💰 Доступно: <b>{stats['ai_credits']:,} кредитов</b>\n"
            f"📊 Использовано: {stats['ai_credits_used']:,} кредитов\n"
            f"📈 Всего получено: {stats['total_received']:,} кредитов\n"
        )

        if kie_credits is not None:
            text += f"\n🌐 Kie.ai баланс: <b>{kie_credits:,} кредитов</b>"

        text += "\n\n📋 <b>Стоимость генерации:</b>\n"

        # Get pricing for all models
        models = pricing_service.get_all_models()

        # Group by type
        image_models = {k: v for k, v in models.items() if v["type"] == "image"}
        video_models = {k: v for k, v in models.items() if v["type"] == "video"}

        # Show image models
        if image_models:
            text += "\n🎨 <b>Изображения:</b>\n"
            for model_id, info in image_models.items():
                usd = pricing_service.credits_to_usd(info["credits"])
                text += f"  • {info['name']}: {info['credits']} кредитов (${usd:.3f})\n"

        # Show video models
        if video_models:
            text += "\n🎬 <b>Видео:</b>\n"
            for model_id, info in video_models.items():
                usd = pricing_service.credits_to_usd(info["credits"])
                text += f"  • {info['name']}: {info['credits']} кредитов (${usd:.2f})\n"

        text += "\n💡 Используйте /buy для пополнения баланса"

        await message.answer(text)


@router.message(Command("pricing"))
async def cmd_pricing_info(message: Message):
    """Show detailed pricing information"""
    pricing_service = PricingService()

    text = (
        "💰 <b>Информация о ценах</b>\n\n"
        "Все цены указаны в AI кредитах Kie.ai\n"
        "1 кредит = $0.005 (0.5¢)\n\n"
    )

    models = pricing_service.get_all_models()

    # Group by type
    for gen_type in ["image", "video"]:
        type_name = "🎨 Генерация изображений" if gen_type == "image" else "🎬 Генерация видео"
        type_models = {k: v for k, v in models.items() if v["type"] == gen_type}

        if type_models:
            text += f"<b>{type_name}</b>\n"

            for model_id, info in type_models.items():
                usd = pricing_service.credits_to_usd(info["credits"])
                text += (
                    f"\n📌 <b>{info['name']}</b>\n"
                    f"   {info['description']}\n"
                    f"   💎 {info['credits']} кредитов (${usd:.3f})\n"
                )

            text += "\n"

    text += (
        "ℹ️ <b>Примечания:</b>\n"
        "• Цены актуальны на 2025 год\n"
        "• Цены могут меняться провайдером\n"
        "• При ошибке генерации кредиты возвращаются\n\n"
        "📊 Проверьте свой баланс: /balance"
    )

    await message.answer(text)
