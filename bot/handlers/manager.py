import uuid

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select, update

from bot.handlers.admin import is_admin
from bot.services import BotServices
from bot.state import ManagerFlow
from bot.webpay_utils import get_webpay_api
from db.models import Payment, User, UserRole
from db.session import get_session

router = Router()


async def is_manager(user_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь роль MANAGER.
    """
    async for session in get_session():
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            return False
        return user.role == UserRole.MANAGER


@router.message(Command("manager"))
async def manager_command(message: types.Message, state: FSMContext):
    await state.clear()
    is_mgr = await is_manager(message.from_user.id)
    is_adm = await is_admin(message.from_user.id)
    access = is_mgr or is_adm
    print(access)
    if not access:
        await message.answer("🚫 У вас нет прав для этой команды.")
        return

    manager_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📁 Выгрузка базы", callback_data="export_db")],
            [
                InlineKeyboardButton(
                    text="➕ Создать реферальную ссылку", callback_data="manager_create_referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Просмотреть всех рефералов", callback_data="manager_view_referrals"
                )
            ],
            [InlineKeyboardButton(text="🔄 Рестарт Envato", callback_data="manager_restart_envato")],
            [
                InlineKeyboardButton(
                    text="🔄 Рестарт Freepik", callback_data="manager_restart_freepik"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Рестарт Motion Array", callback_data="manager_restart_motion"
                )
            ],
            [InlineKeyboardButton(text="💳 Тест WebPay", callback_data="manager_test_webpay")],
            [
                InlineKeyboardButton(
                    text="🍌 Тест NANO BANANA", callback_data="manager_test_nano_banana"
                )
            ],
            [InlineKeyboardButton(text="🎬 Тест Kling Video", callback_data="manager_test_kling")],
        ]
    )
    # Если роль менеджера подтверждена
    await message.answer("✅ Привет, менеджер! Что будем делать?", reply_markup=manager_kb)


@router.callback_query(lambda c: c.data == "manager_create_referral")
async def start_referral(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ManagerFlow.waiting_for_ref_code)
    await callback.message.answer("Введите аргумент для реферальной ссылки (например: promo123):")
    await callback.answer()


# Шаг 2: Получаем аргумент
@router.message(ManagerFlow.waiting_for_ref_code)
async def receive_ref_code(message: types.Message, state: FSMContext):
    ref_code = message.text.strip()
    if not ref_code:
        return await message.answer("❌ Аргумент не может быть пустым. Попробуйте снова.")
    await state.update_data(ref_code=ref_code)
    await state.set_state(ManagerFlow.waiting_for_description)
    await message.answer("Введите описание/комментарий для этой ссылки:")


# Шаг 3: Получаем описание и сохраняем
@router.message(ManagerFlow.waiting_for_description)
async def save_referral(message: types.Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()
    ref_code = data["ref_code"]

    user_id = message.from_user.id  # менеджер, создающий ссылку

    async for session in get_session():
        # Сохраняем код у менеджера (если один код на менеджера)
        await session.execute(
            update(User).where(User.tg_id == user_id).values(referral_code=ref_code)
        )
        await session.commit()

    referral_link = f"https://t.me/FootageHub_bot?start={ref_code}"
    await message.answer(
        f"✅ Реферальная ссылка создана!\n\nСсылка: {referral_link}\nОписание: {description}"
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "manager_view_referrals")
async def view_referrals(callback: types.CallbackQuery):
    manager_id = callback.from_user.id

    async for session in get_session():
        # Получаем всех рефералов
        result = await session.execute(select(User).where(User.referred_by_id == manager_id))
        referrals = result.scalars().all()

        if not referrals:
            await callback.message.answer("У вас ещё нет рефералов.")
            return

        total_referrals = len(referrals)
        total_purchases = 0
        total_earnings = 0.0

        # Собираем список с данными для сортировки
        referral_stats = []

        for ref in referrals:
            # Считаем успешные платежи
            payments_result = await session.execute(
                select(func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.user_id == ref.id, Payment.status == "success"
                )
            )
            count, amount = payments_result.one()
            earnings = float(amount) * 0.2  # 20% доход менеджера
            total_purchases += count
            total_earnings += earnings

            referral_stats.append({"ref": ref, "count": count, "earnings": earnings})

        # Сортируем по заработку (убывание)
        referral_stats.sort(key=lambda x: x["earnings"], reverse=True)

        # Формируем текст
        details = ""
        for stat in referral_stats:
            ref = stat["ref"]
            username = f"@{ref.username}" if ref.username else "нет username"
            details += f"ID: {ref.tg_id}, {username}, Покупок: {stat['count']}, Заработок: {stat['earnings']:.2f}\n"

        summary = (
            f"📊 Статистика ваших рефералов:\n\n"
            f"Всего рефералов: {total_referrals}\n"
            f"Всего покупок: {total_purchases}\n"
            f"Ваш заработок (20%): {total_earnings:.2f}\n\n"
            f"Детали (сортировка по заработку):\n{details}"
        )

        await callback.message.answer(summary)


@router.callback_query(lambda c: c.data == "manager_restart_envato")
async def restart_envato_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Envato через LinkProcessor"""
    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.envato_downloader:
            await callback.answer("⚠️ Браузер Envato не запущен", show_alert=True)
            return

        await callback.message.answer("🔄 Начинаю рестарт браузера Envato...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._envato_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.envato_request_count

            # Закрываем старый браузер
            if link_processor.envato_downloader:
                await link_processor.envato_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from envato_utils.envato_playwright import EnvatoDownloader

            link_processor.envato_downloader = await EnvatoDownloader().__aenter__()
            link_processor.envato_request_count = 0

        await callback.message.answer(
            f"✅ Браузер Envato перезапущен!\n\n"
            f"📊 Обработано запросов до рестарта: {current_requests}\n"
            f"🔄 Счетчик сброшен: 0/{link_processor.restart_after}"
        )
        await callback.answer("✅ Рестарт завершен!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Envato:\n{e}")
        await callback.answer("❌ Ошибка!", show_alert=True)
        print(f"[MANAGER] Ошибка рестарта браузера Envato: {e}")


@router.callback_query(lambda c: c.data == "manager_restart_freepik")
async def restart_freepik_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Freepik через LinkProcessor"""
    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.freepik_downloader:
            await callback.answer("⚠️ Браузер Freepik не запущен", show_alert=True)
            return

        await callback.message.answer("🔄 Начинаю рестарт браузера Freepik...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._freepik_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.freepik_request_count

            # Закрываем старый браузер
            if link_processor.freepik_downloader:
                await link_processor.freepik_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from freepik_utils.freepik import FreepikDownloader

            link_processor.freepik_downloader = await FreepikDownloader().__aenter__()
            link_processor.freepik_request_count = 0

        await callback.message.answer(
            f"✅ Браузер Freepik перезапущен!\n\n"
            f"📊 Обработано запросов до рестарта: {current_requests}\n"
            f"🔄 Счетчик сброшен: 0/{link_processor.restart_after}"
        )
        await callback.answer("✅ Рестарт завершен!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Freepik:\n{e}")
        await callback.answer("❌ Ошибка!", show_alert=True)
        print(f"[MANAGER] Ошибка рестарта браузера Freepik: {e}")


@router.callback_query(lambda c: c.data == "manager_restart_motion")
async def restart_motion_browser(callback: types.CallbackQuery):
    """Принудительный рестарт браузера Motion Array через LinkProcessor"""
    try:
        # Получаем LinkProcessor из BotServices
        link_processor = BotServices.link_processor

        if not link_processor or not link_processor.motion_downloader:
            await callback.answer("⚠️ Браузер Motion Array не запущен", show_alert=True)
            return

        await callback.message.answer("🔄 Начинаю рестарт браузера Motion Array...")

        # Принудительно запускаем рестарт браузера
        async with link_processor._motion_restart_lock:
            # Текущее количество запросов
            current_requests = link_processor.motion_request_count

            # Закрываем старый браузер
            if link_processor.motion_downloader:
                await link_processor.motion_downloader.__aexit__(None, None, None)

            # Создаем новый браузер
            from motion_utils.motion import MotionDownloader

            link_processor.motion_downloader = await MotionDownloader().__aenter__()
            link_processor.motion_request_count = 0

        await callback.message.answer(
            f"✅ Браузер Motion Array перезапущен!\n\n"
            f"📊 Обработано запросов до рестарта: {current_requests}\n"
            f"🔄 Счетчик сброшен: 0/{link_processor.restart_after}"
        )
        await callback.answer("✅ Рестарт завершен!")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при рестарте браузера Motion Array:\n{e}")
        await callback.answer("❌ Ошибка!", show_alert=True)
        print(f"[MANAGER] Ошибка рестарта браузера Motion Array: {e}")


@router.callback_query(lambda c: c.data == "manager_test_webpay")
async def test_webpay_payment(callback: types.CallbackQuery):
    """Тестовый платеж через WebPay"""
    try:
        await callback.answer()

        # Берем ID того, кто нажал кнопку
        user_id = callback.from_user.id

        # Генерируем уникальный ID заказа с user_id
        order_id = f"USER_{user_id}_test_{uuid.uuid4().hex[:8]}"

        # Параметры тестового платежа
        amount = 10.00  # 10 BYN
        description = f"Тестовый платеж FootageHub (User: {user_id})"

        # URL для вебхуков
        base_url = "https://footage.com.by"
        return_url = f"{base_url}/payment/success"
        cancel_url = f"{base_url}/payment/cancel"
        notify_url = f"{base_url}/api/webpay/webhook"

        await callback.message.answer("⏳ Создаю тестовый счет WebPay...")

        # Создаем счет
        webpay_api = get_webpay_api()
        result = await webpay_api.create_invoice(
            order_id=order_id,
            amount=amount,
            description=description,
            return_url=return_url,
            cancel_url=cancel_url,
            notify_url=notify_url,
        )

        invoice_url = result.get("invoiceUrl")
        invoice_number = result.get("webpayInvoiceNumber")

        if invoice_url:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=invoice_url)]]
            )

            await callback.message.answer(
                f"✅ Тестовый счет создан!\n\n"
                f"👤 User ID: {user_id}\n"
                f"📋 Order ID: {order_id}\n"
                f"📄 Invoice: {invoice_number}\n"
                f"💰 Сумма: {amount} BYN\n\n"
                f"Нажмите кнопку для оплаты:",
                reply_markup=keyboard,
            )
        else:
            await callback.message.answer("❌ Не удалось получить ссылку на оплату")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при создании счета:\n{e}")
        print(f"[MANAGER] Ошибка WebPay: {e}")


# ============ NANO BANANA Integration ============


@router.callback_query(lambda c: c.data == "manager_test_nano_banana")
async def start_nano_banana_test(callback: types.CallbackQuery, state: FSMContext):
    """Начало тестирования NANO BANANA"""
    await callback.answer()

    # Initialize config with defaults
    await state.update_data(aspect_ratio="1:1", resolution="2K", output_format="png")

    await state.set_state(ManagerFlow.waiting_for_prompt)
    await callback.message.answer(
        "🍌 <b>NANO BANANA Test - Генерация изображения</b>\n\n"
        "Введите текстовое описание для генерации изображения (prompt):\n\n"
        "<i>Например: A surreal painting of a giant banana floating in space</i>",
        parse_mode="HTML",
    )


@router.message(ManagerFlow.waiting_for_prompt)
async def receive_nano_prompt(message: types.Message, state: FSMContext):
    """Получение prompt и предложение настроек"""
    prompt = message.text.strip()

    if not prompt:
        return await message.answer("❌ Prompt не может быть пустым. Попробуйте снова.")

    await state.update_data(prompt=prompt)

    # Show configuration menu
    config_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📐 Соотношение сторон (1:1)", callback_data="nano_config_aspect_ratio"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎨 Разрешение (2K)", callback_data="nano_config_resolution"
                )
            ],
            [InlineKeyboardButton(text="📄 Формат (PNG)", callback_data="nano_config_format")],
            [InlineKeyboardButton(text="✅ Генерировать", callback_data="nano_generate")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nano_cancel")],
        ]
    )

    await message.answer(
        f"✅ Prompt сохранен:\n\n<b>{prompt}</b>\n\n"
        "Настройте параметры генерации или нажмите 'Генерировать':",
        reply_markup=config_kb,
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "nano_config_aspect_ratio")
async def config_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Настройка соотношения сторон"""
    await callback.answer()

    aspect_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1:1 (Квадрат)", callback_data="nano_ar_1:1"),
                InlineKeyboardButton(text="2:3 (Портрет)", callback_data="nano_ar_2:3"),
            ],
            [
                InlineKeyboardButton(text="3:2 (Альбом)", callback_data="nano_ar_3:2"),
                InlineKeyboardButton(text="4:3", callback_data="nano_ar_4:3"),
            ],
            [
                InlineKeyboardButton(text="16:9 (Широкий)", callback_data="nano_ar_16:9"),
                InlineKeyboardButton(text="9:16 (Вертикальный)", callback_data="nano_ar_9:16"),
            ],
            [
                InlineKeyboardButton(text="21:9 (Ультраширокий)", callback_data="nano_ar_21:9"),
                InlineKeyboardButton(text="Auto", callback_data="nano_ar_auto"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="nano_back_to_config")],
        ]
    )

    await callback.message.edit_text(
        "📐 <b>Выберите соотношение сторон:</b>", reply_markup=aspect_kb, parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("nano_ar_"))
async def set_aspect_ratio(callback: types.CallbackQuery, state: FSMContext):
    """Установка выбранного соотношения сторон"""
    aspect_ratio = callback.data.replace("nano_ar_", "")
    await state.update_data(aspect_ratio=aspect_ratio)
    await callback.answer(f"✅ Соотношение: {aspect_ratio}")

    # Return to config menu
    await show_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "nano_config_resolution")
async def config_resolution(callback: types.CallbackQuery, state: FSMContext):
    """Настройка разрешения"""
    await callback.answer()

    resolution_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1K (Низкое)", callback_data="nano_res_1K"),
                InlineKeyboardButton(text="2K (Среднее)", callback_data="nano_res_2K"),
                InlineKeyboardButton(text="4K (Высокое)", callback_data="nano_res_4K"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="nano_back_to_config")],
        ]
    )

    await callback.message.edit_text(
        "🎨 <b>Выберите разрешение:</b>", reply_markup=resolution_kb, parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("nano_res_"))
async def set_resolution(callback: types.CallbackQuery, state: FSMContext):
    """Установка выбранного разрешения"""
    resolution = callback.data.replace("nano_res_", "")
    await state.update_data(resolution=resolution)
    await callback.answer(f"✅ Разрешение: {resolution}")

    # Return to config menu
    await show_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "nano_config_format")
async def config_format(callback: types.CallbackQuery, state: FSMContext):
    """Настройка формата"""
    await callback.answer()

    format_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="PNG (Без потерь)", callback_data="nano_fmt_png"),
                InlineKeyboardButton(text="JPG (Сжатый)", callback_data="nano_fmt_jpg"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="nano_back_to_config")],
        ]
    )

    await callback.message.edit_text(
        "📄 <b>Выберите формат вывода:</b>", reply_markup=format_kb, parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("nano_fmt_"))
async def set_format(callback: types.CallbackQuery, state: FSMContext):
    """Установка выбранного формата"""
    output_format = callback.data.replace("nano_fmt_", "")
    await state.update_data(output_format=output_format)
    await callback.answer(f"✅ Формат: {output_format.upper()}")

    # Return to config menu
    await show_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "nano_back_to_config")
async def back_to_config(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к меню настроек"""
    await callback.answer()
    await show_config_menu(callback, state)


async def show_config_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню настроек с текущими значениями"""
    data = await state.get_data()
    prompt = data.get("prompt", "")
    aspect_ratio = data.get("aspect_ratio", "1:1")
    resolution = data.get("resolution", "2K")
    output_format = data.get("output_format", "png")

    config_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📐 Соотношение сторон ({aspect_ratio})",
                    callback_data="nano_config_aspect_ratio",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🎨 Разрешение ({resolution})", callback_data="nano_config_resolution"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📄 Формат ({output_format.upper()})", callback_data="nano_config_format"
                )
            ],
            [InlineKeyboardButton(text="✅ Генерировать", callback_data="nano_generate")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nano_cancel")],
        ]
    )

    await callback.message.edit_text(
        f"✅ Prompt:\n\n<b>{prompt}</b>\n\n"
        f"📐 Соотношение: <code>{aspect_ratio}</code>\n"
        f"🎨 Разрешение: <code>{resolution}</code>\n"
        f"📄 Формат: <code>{output_format.upper()}</code>\n\n"
        "Настройте параметры или нажмите 'Генерировать':",
        reply_markup=config_kb,
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "nano_generate")
async def generate_nano_banana(callback: types.CallbackQuery, state: FSMContext):
    """Генерация изображения через NANO BANANA"""
    await callback.answer()

    data = await state.get_data()
    prompt = data.get("prompt")
    aspect_ratio = data.get("aspect_ratio", "1:1")
    resolution = data.get("resolution", "2K")
    output_format = data.get("output_format", "png")

    await callback.message.edit_text(
        f"🍌 <b>Генерация изображения...</b>\n\n"
        f"Prompt: {prompt}\n"
        f"Соотношение: {aspect_ratio}\n"
        f"Разрешение: {resolution}\n"
        f"Формат: {output_format.upper()}\n\n"
        f"⏳ Пожалуйста, подождите...",
        parse_mode="HTML",
    )

    try:
        from bot.kie_utils import get_kie_client

        kie_client = get_kie_client()

        # Generate image
        image_url = await kie_client.generate_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            output_format=output_format,
            timeout=300,
        )

        if image_url:
            # Send image to user
            await callback.message.answer_photo(
                photo=image_url,
                caption=f"✅ <b>Изображение сгенерировано!</b>\n\n"
                f"Prompt: {prompt}\n"
                f"Параметры: {aspect_ratio}, {resolution}, {output_format.upper()}",
                parse_mode="HTML",
            )

            await callback.message.answer(
                "✅ Генерация завершена успешно!\n\n" f"🔗 URL: {image_url}"
            )
        else:
            await callback.message.answer("❌ Не удалось получить URL изображения")

    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Ошибка при генерации:</b>\n\n" f"<code>{str(e)}</code>", parse_mode="HTML"
        )
        print(f"[MANAGER] Ошибка NANO BANANA: {e}")

    finally:
        await state.clear()


@router.callback_query(lambda c: c.data == "nano_cancel")
async def cancel_nano_banana(callback: types.CallbackQuery, state: FSMContext):
    """Отмена генерации"""
    await callback.answer("❌ Отменено")
    await callback.message.edit_text("❌ Генерация NANO BANANA отменена")
    await state.clear()


# ============ Kling Video Generation ============


@router.callback_query(lambda c: c.data == "manager_test_kling")
async def start_kling_test(callback: types.CallbackQuery, state: FSMContext):
    """Начало тестирования Kling Video"""
    await callback.answer()

    # Initialize config with defaults
    await state.update_data(video_aspect_ratio="16:9", video_duration="5", video_sound=False)

    await state.set_state(ManagerFlow.waiting_for_video_prompt)
    await callback.message.answer(
        "🎬 <b>Kling Video Test - Генерация видео</b>\n\n"
        "Введите текстовое описание для генерации видео (макс. 1000 символов):\n\n"
        "<i>Например: In a bright rehearsal room, sunlight streams through the window, "
        "a band performs an emotional song with the lead singer at the center microphone</i>",
        parse_mode="HTML",
    )


@router.message(ManagerFlow.waiting_for_video_prompt)
async def receive_video_prompt(message: types.Message, state: FSMContext):
    """Получение prompt для видео"""
    prompt = message.text.strip()

    if not prompt:
        return await message.answer("❌ Prompt не может быть пустым. Попробуйте снова.")

    if len(prompt) > 1000:
        return await message.answer(
            f"❌ Prompt слишком длинный ({len(prompt)} символов). Максимум 1000 символов."
        )

    await state.update_data(video_prompt=prompt)

    # Show configuration menu
    config_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📐 Соотношение сторон (16:9)", callback_data="kling_config_aspect"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏱️ Длительность (5 сек)", callback_data="kling_config_duration"
                )
            ],
            [InlineKeyboardButton(text="🔊 Звук (Выкл)", callback_data="kling_config_sound")],
            [InlineKeyboardButton(text="✅ Генерировать", callback_data="kling_generate")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="kling_cancel")],
        ]
    )

    await message.answer(
        f"✅ Prompt сохранен ({len(prompt)} символов):\n\n<b>{prompt[:200]}{'...' if len(prompt) > 200 else ''}</b>\n\n"
        "Настройте параметры генерации или нажмите 'Генерировать':",
        reply_markup=config_kb,
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "kling_config_aspect")
async def config_video_aspect(callback: types.CallbackQuery, state: FSMContext):
    """Настройка соотношения сторон для видео"""
    await callback.answer()

    aspect_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1:1 (Квадрат)", callback_data="kling_ar_1:1"),
                InlineKeyboardButton(text="16:9 (Широкий)", callback_data="kling_ar_16:9"),
            ],
            [InlineKeyboardButton(text="9:16 (Вертикальный)", callback_data="kling_ar_9:16")],
            [InlineKeyboardButton(text="« Назад", callback_data="kling_back")],
        ]
    )

    await callback.message.edit_text(
        "📐 <b>Выберите соотношение сторон для видео:</b>", reply_markup=aspect_kb, parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("kling_ar_"))
async def set_video_aspect(callback: types.CallbackQuery, state: FSMContext):
    """Установка соотношения сторон"""
    aspect_ratio = callback.data.replace("kling_ar_", "")
    await state.update_data(video_aspect_ratio=aspect_ratio)
    await callback.answer(f"✅ Соотношение: {aspect_ratio}")
    await show_kling_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "kling_config_duration")
async def config_video_duration(callback: types.CallbackQuery, state: FSMContext):
    """Настройка длительности видео"""
    await callback.answer()

    duration_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5 секунд", callback_data="kling_dur_5"),
                InlineKeyboardButton(text="10 секунд", callback_data="kling_dur_10"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="kling_back")],
        ]
    )

    await callback.message.edit_text(
        "⏱️ <b>Выберите длительность видео:</b>", reply_markup=duration_kb, parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data.startswith("kling_dur_"))
async def set_video_duration(callback: types.CallbackQuery, state: FSMContext):
    """Установка длительности"""
    duration = callback.data.replace("kling_dur_", "")
    await state.update_data(video_duration=duration)
    await callback.answer(f"✅ Длительность: {duration} сек")
    await show_kling_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "kling_config_sound")
async def toggle_video_sound(callback: types.CallbackQuery, state: FSMContext):
    """Переключение звука"""
    data = await state.get_data()
    current_sound = data.get("video_sound", False)
    new_sound = not current_sound
    await state.update_data(video_sound=new_sound)
    await callback.answer(f"✅ Звук: {'Вкл' if new_sound else 'Выкл'}")
    await show_kling_config_menu(callback, state)


@router.callback_query(lambda c: c.data == "kling_back")
async def back_to_kling_config(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к меню настроек Kling"""
    await callback.answer()
    await show_kling_config_menu(callback, state)


async def show_kling_config_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню настроек Kling с текущими значениями"""
    data = await state.get_data()
    prompt = data.get("video_prompt", "")
    aspect_ratio = data.get("video_aspect_ratio", "16:9")
    duration = data.get("video_duration", "5")
    sound = data.get("video_sound", False)

    config_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📐 Соотношение сторон ({aspect_ratio})",
                    callback_data="kling_config_aspect",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⏱️ Длительность ({duration} сек)", callback_data="kling_config_duration"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔊 Звук ({'Вкл' if sound else 'Выкл'})",
                    callback_data="kling_config_sound",
                )
            ],
            [InlineKeyboardButton(text="✅ Генерировать", callback_data="kling_generate")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="kling_cancel")],
        ]
    )

    prompt_preview = prompt[:200] + ("..." if len(prompt) > 200 else "")

    await callback.message.edit_text(
        f"✅ Prompt ({len(prompt)} символов):\n\n<b>{prompt_preview}</b>\n\n"
        f"📐 Соотношение: <code>{aspect_ratio}</code>\n"
        f"⏱️ Длительность: <code>{duration} сек</code>\n"
        f"🔊 Звук: <code>{'Включен' if sound else 'Выключен'}</code>\n\n"
        "Настройте параметры или нажмите 'Генерировать':",
        reply_markup=config_kb,
        parse_mode="HTML",
    )


@router.callback_query(lambda c: c.data == "kling_generate")
async def generate_kling_video(callback: types.CallbackQuery, state: FSMContext):
    """Генерация видео через Kling"""
    await callback.answer()

    data = await state.get_data()
    prompt = data.get("video_prompt")
    aspect_ratio = data.get("video_aspect_ratio", "16:9")
    duration = data.get("video_duration", "5")
    sound = data.get("video_sound", False)

    await callback.message.edit_text(
        f"🎬 <b>Генерация видео...</b>\n\n"
        f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n"
        f"Соотношение: {aspect_ratio}\n"
        f"Длительность: {duration} сек\n"
        f"Звук: {'Да' if sound else 'Нет'}\n\n"
        f"⏳ Пожалуйста, подождите (может занять 3-10 минут)...",
        parse_mode="HTML",
    )

    try:
        from bot.kie_utils import get_kling_client

        kling_client = get_kling_client()

        # Generate video
        video_url = await kling_client.generate_video(
            prompt=prompt,
            sound=sound,
            aspect_ratio=aspect_ratio,
            duration=duration,
            timeout=600,  # 10 minutes
        )

        if video_url:
            # Send video to user
            await callback.message.answer_video(
                video=video_url,
                caption=f"✅ <b>Видео сгенерировано!</b>\n\n"
                f"Параметры: {aspect_ratio}, {duration}с, звук: {'да' if sound else 'нет'}",
                parse_mode="HTML",
            )

            await callback.message.answer(
                "✅ Генерация завершена успешно!\n\n" f"🔗 URL: {video_url}"
            )
        else:
            await callback.message.answer("❌ Не удалось получить URL видео")

    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Ошибка при генерации:</b>\n\n" f"<code>{str(e)}</code>", parse_mode="HTML"
        )
        print(f"[MANAGER] Ошибка Kling: {e}")

    finally:
        await state.clear()


@router.callback_query(lambda c: c.data == "kling_cancel")
async def cancel_kling_video(callback: types.CallbackQuery, state: FSMContext):
    """Отмена генерации видео"""
    await callback.answer("❌ Отменено")
    await callback.message.edit_text("❌ Генерация Kling видео отменена")
    await state.clear()
