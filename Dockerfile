FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Telegram-боту НЕ нужен порт
CMD ["python", "app.py"]
