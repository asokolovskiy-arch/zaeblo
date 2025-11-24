# Используем Python 3.11
FROM python:3.11

# Создаём рабочую директорию
WORKDIR /app

# Копируем и устанавливаем зависимости
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . /app/

# Запуск бота
CMD ["python", "app.py"]