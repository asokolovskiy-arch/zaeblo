from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import datetime
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is not set!")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-render-url/webhook

CASH_DATA = {
    "Апельсин N1": {},
    "Мацеста1 N2": {},
    "Базар N3": {},
    "Мацеста2 N4": {},
    "Водоканал N5": {},
    "Ц рынок N6": {},
    "Дагомыс N7": {},
    "Ареда N8": {},
}

ADMIN_ID = 6702575755

# Flask web server
app = Flask(__name__)
tg_app = Application.builder().token(TOKEN).build()


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
    return ReplyKeyboardMarkup([["Показать меню"]], resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "start"
    await update.message.reply_text(
        "Нажмите кнопку ниже:",
        reply_markup=get_reply_keyboard("start")
    )


async def show_all_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📊 Все кассы:\n\n"
    for shop, data in CASH_DATA.items():
        if "cash" in data:
            text += f"🏪 {shop}: {data['cash']} руб. (в {data['timestamp']})\n"
        else:
            text += f"🏪 {shop}: нет данных\n"
    await update.message.reply_text(text)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id
    state = context.user_data.get("state", "start")

    if text == "Показать меню":
        context.user_data["state"] = "menu"
        await update.message.reply_text(
            "Меню:",
            reply_markup=get_reply_keyboard("menu")
        )
        return

    if text == "Назад":
        context.user_data["state"] = "menu"
        await update.message.reply_text(
            "Меню:",
            reply_markup=get_reply_keyboard("menu")
        )
        return

    if text == "Выбрать точку":
        context.user_data["state"] = "select_shop"
        await update.message.reply_text(
            "Выберите точку:",
            reply_markup=get_reply_keyboard("select_shop")
        )
        return

    if text == "Показать все кассы":
        await show_all_cash(update, context)
        return

    if state == "select_shop" and text in CASH_DATA:
        context.user_data["shop"] = text
        context.user_data["state"] = "after_shop"
        await update.message.reply_text(f"Введите сумму кассы для {text}:")
        return

    if state == "after_shop":
        shop = context.user_data.get("shop")
        if shop:
            if not text.isdigit():
                await update.message.reply_text("❗ Введите число")
                return

            CASH_DATA[shop] = {
                "user_id": user_id,
                "cash": text,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            await update.message.reply_text(f"Касса для {shop} обновлена: {text} руб.")
            context.user_data["state"] = "menu"
            await update.message.reply_text(
                "Меню:",
                reply_markup=get_reply_keyboard("menu")
            )
            return

    await update.message.reply_text("Не понял команду. Нажмите кнопку ниже.")


# --- ROUTES --- #

@app.post("/webhook")
def webhook():
    update = Update.de_json(request.json, tg_app.bot)
    tg_app.update_queue.put_nowait(update)
    return "OK", 200


@app.get("/")
def home():
    return "Bot is running!", 200


async def set_webhook():
    await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    import asyncio

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Устанавливаем webhook
    asyncio.run(set_webhook())

    # запускаем Flask
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
