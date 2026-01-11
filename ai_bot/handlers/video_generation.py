"""
Video Generation Handlers

Handlers for AI video generation using Kling 2.6 and VEO 3.1
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ai_bot.config import config
from ai_bot.services import AIService, CreditManager, PricingService
from ai_bot.state import VideoGenerationStates
from shared.db.session import AsyncSessionLocal

router = Router()


@router.message(Command("video"))
@router.callback_query(F.data == "generate_video")
async def cmd_generate_video(event, state: FSMContext):
    """Start video generation flow"""
    # Handle both Message and CallbackQuery
    if isinstance(event, CallbackQuery):
        message = event.message
        await event.answer()
    else:
        message = event

    # Get dynamic pricing
    pricing_service = PricingService()
    try:
        kling_cost = pricing_service.get_model_price("kling-2.6/text-to-video")
        veo_cost = pricing_service.get_model_price("veo-3.1/text-to-video")
        kling_usd = pricing_service.credits_to_usd(kling_cost)
        veo_usd = pricing_service.credits_to_usd(veo_cost)
    except:
        kling_cost = config.VIDEO_GENERATION_COST
        veo_cost = config.VIDEO_GENERATION_COST
        kling_usd = kling_cost * 0.005
        veo_usd = veo_cost * 0.005

    # Provider selection
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Kling 2.6 (Рекомендуется)", callback_data="provider_kling")
    builder.button(text="🎥 VEO 3.1 (Google)", callback_data="provider_veo")
    builder.adjust(1)

    text = (
        "🎬 <b>Генерация видео</b>\n\n"
        "Выберите AI провайдер для генерации:\n\n"
        f"<b>Kling 2.6</b> - Быстрая генерация, поддержка звука\n"
        f"💎 {kling_cost} кредитов (${kling_usd:.2f})\n\n"
        f"<b>VEO 3.1</b> - Google, высокое качество\n"
        f"💎 {veo_cost} кредитов (${veo_usd:.2f})"
    )

    await state.set_state(VideoGenerationStates.waiting_for_provider_choice)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(
    VideoGenerationStates.waiting_for_provider_choice, F.data.startswith("provider_")
)
async def handle_provider_choice(callback: CallbackQuery, state: FSMContext):
    """Handle provider selection"""
    provider = callback.data.replace("provider_", "")
    await state.update_data(provider=provider)

    provider_name = "Kling 2.6" if provider == "kling" else "VEO 3.1"

    text = (
        f"✅ Выбран: <b>{provider_name}</b>\n\n"
        "📝 Опишите, какое видео вы хотите создать.\n"
        "Используйте детальное описание на английском языке.\n\n"
        "<i>Пример: A cat playing piano in a cozy room with warm lighting</i>"
    )

    await state.set_state(VideoGenerationStates.waiting_for_prompt)
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(VideoGenerationStates.waiting_for_prompt)
async def handle_video_prompt(message: Message, state: FSMContext):
    """Handle video generation prompt"""
    prompt = message.text.strip()

    if len(prompt) < 3:
        await message.answer("❌ Описание слишком короткое. Попробуйте ещё раз.")
        return

    # Save prompt to state
    await state.update_data(prompt=prompt)

    # Ask for aspect ratio
    builder = InlineKeyboardBuilder()
    builder.button(text="16:9 (Широкий)", callback_data="var_16:9")
    builder.button(text="9:16 (Вертикальный)", callback_data="var_9:16")
    builder.button(text="1:1 (Квадрат)", callback_data="var_1:1")
    builder.adjust(1)

    await state.set_state(VideoGenerationStates.waiting_for_aspect_ratio)
    await message.answer("📐 Выберите соотношение сторон:", reply_markup=builder.as_markup())


@router.callback_query(VideoGenerationStates.waiting_for_aspect_ratio, F.data.startswith("var_"))
async def handle_video_aspect_ratio(callback: CallbackQuery, state: FSMContext):
    """Handle aspect ratio selection for video"""
    aspect_ratio = callback.data.replace("var_", "")
    await state.update_data(aspect_ratio=aspect_ratio)

    # Ask for duration
    builder = InlineKeyboardBuilder()
    builder.button(text="5 секунд (Быстро)", callback_data="dur_5")
    builder.button(text="10 секунд (Макс.)", callback_data="dur_10")
    builder.adjust(1)

    await state.set_state(VideoGenerationStates.waiting_for_duration)
    await callback.message.edit_text(
        f"✅ Соотношение: {aspect_ratio}\n\n" "⏱ Выберите длительность:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(VideoGenerationStates.waiting_for_duration, F.data.startswith("dur_"))
async def handle_video_duration(callback: CallbackQuery, state: FSMContext):
    """Handle duration selection"""
    duration = callback.data.replace("dur_", "")
    await state.update_data(duration=duration)

    data = await state.get_data()
    provider = data.get("provider")

    # For Kling, ask about sound
    if provider == "kling":
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Со звуком", callback_data="sound_yes")
        builder.button(text="❌ Без звука", callback_data="sound_no")
        builder.adjust(1)

        await state.set_state(VideoGenerationStates.waiting_for_sound_option)
        await callback.message.edit_text(
            f"✅ Длительность: {duration}с\n\n" "🔊 Генерировать со звуком?",
            reply_markup=builder.as_markup(),
        )
    else:
        # VEO doesn't have sound option, start generation
        await start_video_generation(callback, state, sound=False)

    await callback.answer()


@router.callback_query(VideoGenerationStates.waiting_for_sound_option, F.data.startswith("sound_"))
async def handle_sound_option(callback: CallbackQuery, state: FSMContext):
    """Handle sound option for Kling"""
    sound = callback.data == "sound_yes"
    await start_video_generation(callback, state, sound)


async def start_video_generation(callback: CallbackQuery, state: FSMContext, sound: bool):
    """Start video generation process"""
    user_id = callback.from_user.id

    # Get data from state
    data = await state.get_data()
    provider = data.get("provider")
    prompt = data.get("prompt")
    aspect_ratio = data.get("aspect_ratio")
    duration = data.get("duration")

    provider_name = "Kling 2.6" if provider == "kling" else "VEO 3.1"

    await callback.message.edit_text(
        f"✅ Провайдер: {provider_name}\n"
        f"✅ Соотношение: {aspect_ratio}\n"
        f"✅ Длительность: {duration}с\n"
        f"✅ Звук: {'Да' if sound else 'Нет'}\n\n"
        "⏳ Генерирую видео... Это может занять до 10 минут.\n"
        "Пожалуйста, подождите..."
    )
    await callback.answer()

    # Start generation
    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)

        # Check credits
        has_credits = await credit_manager.has_enough_credits(user_id, config.VIDEO_GENERATION_COST)

        if not has_credits:
            await callback.message.answer(
                "❌ <b>Недостаточно AI кредитов</b>\n\n"
                f"Требуется: {config.VIDEO_GENERATION_COST} AI кредитов\n\n"
                "Пополните баланс: /buy"
            )
            await state.clear()
            return

        # Deduct credits
        await credit_manager.deduct_credits(user_id, config.VIDEO_GENERATION_COST)

        # Generate video
        ai_service = AIService()

        try:
            result = await ai_service.generate_video(
                prompt=prompt,
                provider_name=provider,
                sound=sound,
                aspect_ratio=aspect_ratio,
                duration=duration,
                timeout=600,
            )

            if result["success"]:
                # Send result
                caption = (
                    f"✅ <b>Видео готово!</b>\n\n"
                    f"🤖 Провайдер: {provider_name}\n"
                    f"📝 Prompt: {prompt[:100]}...\n"
                    f"📐 Соотношение: {aspect_ratio}\n"
                    f"⏱ Длительность: {duration}с\n"
                    f"🔊 Звук: {'Да' if sound else 'Нет'}\n"
                    f"⏱ Время генерации: {result['processing_time']}с\n\n"
                    f"💎 Потрачено: {result['credits_spent']} AI кредитов"
                )

                await callback.message.answer_video(video=result["result_url"], caption=caption)

                # Log generation (TODO: add to AIGenerationLog)

            else:
                # Refund credits on failure
                await credit_manager.refund_credits(
                    user_id, config.VIDEO_GENERATION_COST, reason="Generation failed"
                )

                await callback.message.answer(
                    f"❌ <b>Ошибка генерации</b>\n\n"
                    f"{result.get('error', 'Unknown error')}\n\n"
                    f"💎 Кредиты возвращены на ваш счёт"
                )

        except Exception as e:
            # Refund credits on exception
            await credit_manager.refund_credits(
                user_id, config.VIDEO_GENERATION_COST, reason=f"Exception: {str(e)}"
            )

            await callback.message.answer(
                f"❌ <b>Произошла ошибка</b>\n\n" f"{str(e)}\n\n" f"💎 Кредиты возвращены на ваш счёт"
            )

    await state.clear()
