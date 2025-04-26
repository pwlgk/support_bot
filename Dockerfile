# Dockerfile

# 1. Базовый образ Python 
FROM python:3.11-slim

# 2. Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE 1  
ENV PYTHONUNBUFFERED 1      

# 3. Установка рабочей директории внутри контейнера
WORKDIR /app

# 4. Копирование файла зависимостей и установка библиотек
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Копирование всего остального кода приложения в рабочую директорию
COPY . .

# 6. Команда для запуска бота при старте контейнера
CMD ["python", "main.py"]