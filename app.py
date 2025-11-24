import os
import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o")

# Данные касс
CASH_DATA = {
    "Точка 1": {},
    "Точка 2": {},
    "Точка 3": {},
}

# ID админа (замени на свой)
ADMIN_ID = 6702575755


# ---------- Reply Клавиатура ----------
def get_reply_keyboard(state: str, user_id=None):
    if state == "start":
        return ReplyKeyboardMarkup(
            [[KeyboardButton("Показать меню")]],
            resize_keyboard=True,
        )

    if state == "menu":
        buttons = [["Выбрать точку"], ["Показать все кассы"], ["Назад"]]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    if state == "select_shop":
        shops = list(CASH_DATA.keys())
        keyboard = [[shop] for shop in shops] + [["Назад"]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    return ReplyKeyboardMarkup(
        [[KeyboardButton("Показать меню")]],
        resize_keyboard=True
    )


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "start"
    keyboard = get_reply_keyboard("start")
    await update.message.reply_text("Нажмите кнопку ниже:", reply_markup=keyboard)


# ---------- Показ всех касс ----------
async def show_all_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📊 Все кассы:\n\n"
    for shop, data in CASH_DATA.items():
        if "cash" in data:
            text += f"🏪 {shop}: {data['cash']} руб. (в {data['timestamp']})\n"
        else:
            text += f"🏪 {shop}: нет данных\n"

    await update.message.reply_text(text)


# ---------- Напоминание ----------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now().strftime("%H:%M")
    await context.bot.send_message(ADMIN_ID, f"⏰ Напоминание обновить кассы ({now})")


def schedule_jobs(app):
    hours = [21]  # каждый день в 21:00
    for hour in hours:
        app.job_queue.run_daily(
            send_reminder,
            time=datetime.time(hour=hour, minute=0, second=0)
        )


# ---------- Основной обработчик текстов ----------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    state = context.user_data.get("state", "start")

    # === Кнопка Показать меню ===
    if text == "Показать меню":
        context.user_data["state"] = "menu"
        keyboard = get_reply_keyboard("menu", user_id)
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    # === Назад ===
    if text == "Назад":
        context.user_data["state"] = "menu"
        keyboard = get_reply_keyboard("menu", user_id)
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    # === Выбрать точку ===
    if text == "Выбрать точку":
        context.user_data["state"] = "select_shop"
        keyboard = get_reply_keyboard("select_shop", user_id)
        await update.message.reply_text("Выберите точку:", reply_markup=keyboard)
        return

    # === Показать все кассы ===
    if text == "Показать все кассы":
        await show_all_cash(update, context)
        return

    # === Пользователь выбирает точку ===
    if state == "select_shop" and text in CASH_DATA:
        context.user_data["shop"] = text
        context.user_data["state"] = "after_shop"
        await update.message.reply_text(f"Введите сумму кассы для {text}:")
        return

    # === Пользователь вводит кассу (должно быть число) ===
    if state == "after_shop":
        shop = context.user_data.get("shop")
        if shop:

            # Проверка на число
            if not text.isdigit():
                await update.message.reply_text("❗ Введите число")
                return

            # Сохраняем
            CASH_DATA[shop] = {
                "user_id": user_id,
                "cash": text,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            await update.message.reply_text(f"Касса для {shop} обновлена: {text} руб.")

            # Возврат в меню
            context.user_data["state"] = "menu"
            keyboard = get_reply_keyboard("menu", user_id)
            await update.message.reply_text("Меню:", reply_markup=keyboard)
            return

    await update.message.reply_text("Не понял команду. Нажмите кнопку ниже.")


# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    schedule_jobs(app)

    app.run_polling()


if __name__ == "__main__":
    main()
