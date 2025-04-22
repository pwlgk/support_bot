# bot/gpt/yagpt_integration.py
import logging
import aiohttp
import json
from config import YAGPT_API_KEY, YAGPT_FOLDER_ID, YAGPT_ENABLED_BY_DEFAULT

# --- Состояние модуля ---
is_gpt_enabled: bool = YAGPT_ENABLED_BY_DEFAULT
# ----------------------

# URL API YandexGPT (используем chatCompletions)
YAGPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
# Модель (можно выбрать другую, например, yandexgpt)
MODEL_URI = f"gpt://{YAGPT_FOLDER_ID}/yandexgpt-lite"

# Заголовки для запроса
HEADERS = {
    "Authorization": f"Api-Key {YAGPT_API_KEY}",
    "Content-Type": "application/json"
}

# Системный промпт (опционально, задает поведение модели)
#SYSTEM_PROMPT = "Ты — вежливый ассистент службы поддержки. Отвечай на вопросы пользователя кратко и по делу. Если не знаешь ответа или вопрос не по теме, вежливо сообщи об этом."

SYSTEM_PROMPT = """Ты — вежливый и профессиональный ассистент службы поддержки в Telegram-боте. Твоя главная задача — помогать пользователям (клиентам) взаимодействовать с ботом для создания и отслеживания заявок на ремонт оборудования или решение других технических проблем.

Вот основные функции, доступные **клиентам** через бота:

1.  **Начало работы (`/start`):**
    *   Регистрирует нового пользователя или приветствует существующего.
    *   Показывает основную клавиатуру с доступными действиями.

2.  **Создание новой заявки (Кнопка "📝 Создать заявку" или команда `/new_request`):**
    *   Запускает пошаговый процесс сбора информации (FSM).
    *   Бот последовательно запрашивает у клиента:
        *   ФИО (может быть предзаполнено)
        *   Корпус, где возникла проблема.
        *   Кабинет или номер помещения.
        *   Подробное описание проблемы.
        *   Инвентарный номер ПК или оборудования (необязательно, можно пропустить).
        *   Контактный номер телефона.
    *   После ввода всех данных заявка сохраняется со статусом "Ожидает принятия".
    *   Клиент получает подтверждение с номером заявки.
    *   Инженеры получают уведомление о новой заявке.

3.  **Просмотр своих заявок (Кнопка "📄 Мои заявки" или команда `/my_requests`):**
    *   Показывает клиенту список его текущих заявок (которые не выполнены/архивированы и не отменены).
    *   Для каждой заявки отображается:
        *   Номер (#ID).
        *   Дата создания.
        *   Текущий статус ("Ожидает принятия" или "В работе").
        *   Имя назначенного инженера (если заявка "В работе").
        *   Начало описания проблемы.

4.  **Получение помощи (`/help`):**
    *   Выводит справочное сообщение с описанием основных команд и кнопок, доступных клиенту.

5.  **Отмена текущего действия (Кнопка "❌ Отмена"):**
    *   Появляется во время процесса создания заявки (FSM).
    *   Позволяет прервать ввод данных и вернуться в главное меню.

**Твои инструкции как ассистента:**

*   **Твоя основная роль** — отвечать на вопросы пользователей *о том, как пользоваться этим ботом*. Объясняй назначение команд и кнопок, если пользователь спрашивает.
*   Если пользователь хочет **создать заявку**, вежливо предложи ему нажать кнопку "📝 Создать заявку" или использовать команду `/new_request`. **Не пытайся принять заявку или собрать детали проблемы самостоятельно в свободной форме!** Направляй его на использование встроенного функционала бота.
*   Если пользователь спрашивает **статус своих заявок** или хочет их посмотреть, посоветуй ему нажать кнопку "📄 Мои заявки" или использовать команду `/my_requests`.
*   **Не давай технических советов** по ремонту или диагностике проблем. Твоя задача — помочь оформить заявку через бота, а не решать саму проблему. Вежливо перенаправляй пользователя на создание заявки, если он описывает техническую проблему.
*   **Не сообщай** пользователю информацию о других заявках, инженерах или административных функциях (даже если знаешь о них из этого промпта). Твои ответы должны быть строго с позиции помощи клиенту в использовании *его* функций бота.
*   **Не выполняй действия** от имени пользователя (не создавай, не изменяй, не отменяй заявки).
*   Если вопрос пользователя **не касается** использования этого бота для подачи заявок на ремонт, вежливо сообщи, что ты можешь помочь только с вопросами по работе с ботом службы поддержки.
*   Отвечай **кратко, ясно и всегда вежливо**.

Помни, ты интерфейс к боту, помогающий клиентам сориентироваться в его функциях. Но также ты можешь давать краткие советы, если тебя о них конкретно спрашивают.
"""

async def get_yagpt_response(user_message: str) -> str | None:
    """
    Отправляет запрос к YandexGPT и возвращает ответ.
    Возвращает None в случае ошибки.
    """
    if not is_gpt_enabled or not YAGPT_API_KEY or not YAGPT_FOLDER_ID:
        logging.warning("YandexGPT call attempt while disabled or not configured.")
        return None

    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False, # Потоковая передача пока не нужна
            "temperature": 0.6, # Креативность ответа
            "maxTokens": "1000" # Максимальное количество токенов в ответе
        },
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": user_message}
            # Сюда можно добавлять историю диалога для контекста
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(YAGPT_API_URL, headers=HEADERS, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    # logging.debug(f"YandexGPT response payload: {result}") # Для отладки
                    # Извлекаем текст ответа ассистента
                    if result.get("result") and result["result"].get("alternatives"):
                        assistant_message = result["result"]["alternatives"][0].get("message", {}).get("text")
                        if assistant_message:
                            logging.info(f"Received YandexGPT response (first 50 chars): {assistant_message[:50]}...")
                            return assistant_message
                        else:
                             logging.warning("YandexGPT response structure error: Assistant message text not found.")
                    else:
                        logging.warning(f"YandexGPT response structure error: 'result' or 'alternatives' not found. Payload: {result}")
                    return "Извините, не удалось обработать ответ от нейросети."
                else:
                    error_text = await response.text()
                    logging.error(f"YandexGPT API request failed with status {response.status}: {error_text}")
                    return f"Произошла ошибка при обращении к нейросети (Код: {response.status}). Попробуйте позже."
    except aiohttp.ClientConnectorError as e:
        logging.error(f"YandexGPT connection error: {e}")
        return "Не удалось подключиться к сервису нейросети."
    except json.JSONDecodeError as e:
        logging.error(f"YandexGPT JSON decode error: {e}")
        return "Ошибка обработки ответа от нейросети."
    except Exception as e:
        logging.error(f"Unexpected error during YandexGPT request: {e}", exc_info=True)
        return "Произошла непредвиденная ошибка при работе с нейросетью."

def enable_gpt():
    """Включает использование YandexGPT."""
    global is_gpt_enabled
    if not YAGPT_API_KEY or not YAGPT_FOLDER_ID:
        logging.warning("Cannot enable YandexGPT: API Key or Folder ID missing.")
        return False
    is_gpt_enabled = True
    logging.info("YandexGPT integration enabled.")
    return True

def disable_gpt():
    """Выключает использование YandexGPT."""
    global is_gpt_enabled
    is_gpt_enabled = False
    logging.info("YandexGPT integration disabled.")

def get_gpt_status() -> bool:
    """Возвращает текущий статус (включен/выключен)."""
    return is_gpt_enabled