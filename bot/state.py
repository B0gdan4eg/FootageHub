# bot/states.py
from aiogram.fsm.state import StatesGroup, State

class DownloadFlow(StatesGroup):
    waiting_for_link = State()       # Ждём ссылку
    waiting_for_payment = State()    # Предложено оплатить
    waiting_for_confirmation = State()  # Ждём подтверждение оплаты (вебхук или вручную)

class ManagerFlow(StatesGroup):
    waiting_for_description = State()     # Выбор действия
    waiting_for_ref_code = State() # (если нужно по ID глянуть)

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_role = State()
    waiting_for_price_json = State()
    waiting_for_cookies_json = State()  # 👈 Добавь это
    waiting_for_limit_value = State()   # 👈 И это, если еще не добавил
