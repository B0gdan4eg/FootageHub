"""
Image Generation Handlers

Handlers for AI image generation using Nano Banana
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ai_bot.config import config
from ai_bot.services import AIService, CreditManager, PricingService
from ai_bot.state import ImageGenerationStates
from shared.db.session import AsyncSessionLocal

router = Router()


@router.message(Command("image"))
@router.callback_query(F.data == "generate_image")
async def cmd_generate_image(event, state: FSMContext):
    """Start image generation flow"""
    # Handle both Message and CallbackQuery
    if isinstance(event, CallbackQuery):
        message = event.message
        await event.answer()
    else:
        message = event

    # Get dynamic pricing
    pricing_service = PricingService()
    try:
        cost = pricing_service.get_model_price("google/nano-banana")
        cost_usd = pricing_service.credits_to_usd(cost)
    except BaseException:
        cost = config.IMAGE_GENERATION_COST
        cost_usd = cost * 0.005

    text = (
        "🎨 <b>Генерация изображения</b>\n\n"
        "Опишите, какое изображение вы хотите создать.\n"
        "Можно использовать детальное описание на английском или русском языке.\n\n"
        "<i>Пример: A futuristic city at sunset with flying cars</i>\n\n"
        f"💎 Стоимость: <b>{cost} AI кредитов</b> (${cost_usd:.3f})"
    )

    await state.set_state(ImageGenerationStates.waiting_for_prompt)
    await message.answer(text)


@router.message(ImageGenerationStates.waiting_for_prompt)
async def handle_image_prompt(message: Message, state: FSMContext):
    """Handle image generation prompt"""
    prompt = message.text.strip()

    if len(prompt) < 3:
        await message.answer("❌ Описание слишком короткое. Попробуйте ещё раз.")
        return

    # Save prompt to state
    await state.update_data(prompt=prompt)

    # Ask for aspect ratio
    builder = InlineKeyboardBuilder()
    builder.button(text="1:1 (Квадрат)", callback_data="ar_1:1")
    builder.button(text="16:9 (Широкий)", callback_data="ar_16:9")
    builder.button(text="9:16 (Портрет)", callback_data="ar_9:16")
    builder.button(text="4:3 (Стандарт)", callback_data="ar_4:3")
    builder.button(text="Авто", callback_data="ar_auto")
    builder.adjust(2)

    await state.set_state(ImageGenerationStates.waiting_for_aspect_ratio)
    await message.answer("📐 Выберите соотношение сторон:", reply_markup=builder.as_markup())


@router.callback_query(ImageGenerationStates.waiting_for_aspect_ratio, F.data.startswith("ar_"))
async def handle_aspect_ratio(callback: CallbackQuery, state: FSMContext):
    """Handle aspect ratio selection"""
    aspect_ratio = callback.data.replace("ar_", "")
    await state.update_data(aspect_ratio=aspect_ratio)

    # Ask for resolution
    builder = InlineKeyboardBuilder()
    builder.button(text="1K (Быстро)", callback_data="res_1K")
    builder.button(text="2K (Рекомендуется)", callback_data="res_2K")
    builder.button(text="4K (Макс. качество)", callback_data="res_4K")
    builder.adjust(1)

    await state.set_state(ImageGenerationStates.waiting_for_resolution)
    await callback.message.edit_text(
        f"✅ Соотношение: {aspect_ratio}\n\n" "📊 Выберите разрешение:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(ImageGenerationStates.waiting_for_resolution, F.data.startswith("res_"))
async def handle_resolution(callback: CallbackQuery, state: FSMContext):
    """Handle resolution selection and start generation"""
    resolution = callback.data.replace("res_", "")
    user_id = callback.from_user.id

    # Get data from state
    data = await state.get_data()
    prompt = data.get("prompt")
    aspect_ratio = data.get("aspect_ratio")

    await callback.message.edit_text(
        f"✅ Разрешение: {resolution}\n\n" "⏳ Генерирую изображение... Это может занять до 2 минут."
    )
    await callback.answer()

    # Start generation
    async with AsyncSessionLocal() as session:
        credit_manager = CreditManager(session)

        # Check credits
        has_credits = await credit_manager.has_enough_credits(user_id, config.IMAGE_GENERATION_COST)

        if not has_credits:
            await callback.message.answer(
                "❌ <b>Недостаточно AI кредитов</b>\n\n"
                f"Требуется: {config.IMAGE_GENERATION_COST} AI кредита\n\n"
                "Пополните баланс: /buy"
            )
            await state.clear()
            return

        # Deduct credits
        await credit_manager.deduct_credits(user_id, config.IMAGE_GENERATION_COST)

        # Generate image
        ai_service = AIService()

        try:
            result = await ai_service.generate_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_format="png",
                timeout=300,
            )

            if result["success"]:
                # Send result
                caption = (
                    f"✅ <b>Изображение готово!</b>\n\n"
                    f"📝 Prompt: {prompt[:100]}...\n"
                    f"📐 Соотношение: {aspect_ratio}\n"
                    f"📊 Разрешение: {resolution}\n"
                    f"⏱ Время: {result['processing_time']}с\n\n"
                    f"💎 Потрачено: {result['credits_spent']} AI кредита"
                )

                await callback.message.answer_photo(photo=result["result_url"], caption=caption)

                # Log generation (TODO: add to AIGenerationLog)

            else:
                # Refund credits on failure
                await credit_manager.refund_credits(
                    user_id, config.IMAGE_GENERATION_COST, reason="Generation failed"
                )

                await callback.message.answer(
                    f"❌ <b>Ошибка генерации</b>\n\n"
                    f"{result.get('error', 'Unknown error')}\n\n"
                    f"💎 Кредиты возвращены на ваш счёт"
                )

        except Exception as e:
            # Refund credits on exception
            await credit_manager.refund_credits(
                user_id, config.IMAGE_GENERATION_COST, reason=f"Exception: {str(e)}"
            )

            await callback.message.answer(
                f"❌ <b>Произошла ошибка</b>\n\n" f"{str(e)}\n\n" f"💎 Кредиты возвращены на ваш счёт"
            )

    await state.clear()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation"""
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("Нет активных операций")
        return

    await state.clear()
    await message.answer("✅ Операция отменена")
