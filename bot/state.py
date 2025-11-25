# bot/states.py
from aiogram.fsm.state import StatesGroup, State

class DownloadFlow(StatesGroup):
    waiting_for_link = State()       # Ждём ссылку Envato
    waiting_for_freepik_link = State()  # Ждём ссылку Freepik
    waiting_for_payment = State()    # Предложено оплатить
    waiting_for_confirmation = State()  # Ждём подтверждение оплаты (вебхук или вручную)

class ManagerFlow(StatesGroup):
    waiting_for_description = State()     # Выбор действия
    waiting_for_ref_code = State() # (если нужно по ID глянуть)

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_role = State()
    waiting_for_price_json = State()
    waiting_for_cookies_json = State()
    waiting_for_limit_value = State()
    waiting_for_broadcast_text = State()
    # Новые состояния для выдачи подписки
    waiting_for_subscription_user_id = State()
    waiting_for_subscription_plan = State()