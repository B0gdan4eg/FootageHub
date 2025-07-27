# bot/states.py
from aiogram.fsm.state import StatesGroup, State

class DownloadFlow(StatesGroup):
    waiting_for_link = State()       # Ждём ссылку
    waiting_for_payment = State()    # Предложено оплатить
    waiting_for_confirmation = State()  # Ждём подтверждение оплаты (вебхук или вручную)

class ManagerFlow(StatesGroup):
    choosing_action = State()     # Выбор действия
    waiting_for_user_id = State() # (если нужно по ID глянуть)

class AdminFlow(StatesGroup):
    choosing_action = State()
    waiting_for_user_id = State()
    waiting_for_role = State()
    waiting_for_credits = State()
    waiting_for_subscription_days = State()
