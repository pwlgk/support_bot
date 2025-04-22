# bot/states/request_states.py
from aiogram.fsm.state import State, StatesGroup

class CreateRequest(StatesGroup):
    """
    Состояния для процесса создания новой заявки с детальной информацией.
    """
    waiting_for_full_name = State()     # Ожидание ФИО
    waiting_for_building = State()      # Ожидание корпуса
    waiting_for_room = State()          # Ожидание кабинета
    waiting_for_description = State()   # Ожидание описания проблемы
    waiting_for_pc_number = State()     # Ожидание ПК/инв. номера (необязательно)
    waiting_for_phone = State()         # Ожидание номера телефона
    # confirming_request = State()      # Шаг подтверждения пока уберем для простоты