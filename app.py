from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, JobQueue
)
import datetime

TOKEN = "8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o"

SHOPS = ["Ц. Рынок", "ТЦ Апельсин", "Базар"]
CASH_DATA = {}
ADMIN_ID = 7085347092
EMPLOYEES = []
NOTIFY_HOURS = [11, 13, 15, 18]

# ----- Reply Keyboards -----
def get_reply_keyboard(state, user_id):
    if state == "start":
        return ReplyKeyboardMarkup([["Показать меню"]], resize_keyboard=True)
    elif state == "main":
        buttons = [["Выбрать точку"]]
        if user_id == ADMIN_ID:
            buttons[0].append("Показать все кассы")
        buttons.append(["Назад"])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    elif state == "after_shop":
        return ReplyKeyboardMarkup([["Назад"]], resize_keyboard=True)
    return None

# ----- Start -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in EMPLOYEES and user_id != ADMIN_ID:
        EMPLOYEES.append(user_id)
    context.user_data["state"] = "start"
    keyboard = get_reply_keyboard("start", user_id)
    await update.message.reply_text("Добро пожаловать! Нажмите кнопку меню ниже:", reply_markup=keyboard)

# ----- Show Menu -----
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    state = context.user_data.get("state", "start")

    # Обработка кнопок Reply Keyboard
    if text == "Показать меню":
        context.user_data["state"] = "main"
        keyboard = get_reply_keyboard("main", user_id)
        await update.message.reply_text("Главное меню:", reply_markup=keyboard)
    elif text == "Назад":
        # Возврат в стартовое меню
        context.user_data["state"] = "start"
        keyboard = get_reply_keyboard("start", user_id)
        await update.message.reply_text("Возврат в главное меню:", reply_markup=keyboard)
    elif text == "Выбрать точку":
        keyboard = [[InlineKeyboardButton(shop, callback_data=shop)] for shop in SHOPS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите точку:", reply_markup=reply_markup)
        context.user_data["state"] = "after_shop"
    elif text == "Показать все кассы" and user_id == ADMIN_ID:
        msg = "Текущие кассы:\n"
        for shop, info in CASH_DATA.items():
            msg += f"{shop}: {info['cash']} (обновлено {info['timestamp']})\n"
        await update.message.reply_text(msg)

# ----- Shop Selection -----
async def shop_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop = query.data
    context.user_data["shop"] = shop
    context.user_data["state"] = "after_shop"
    await query.message.reply_text(f"Введите актуальную кассу для {shop}:")
    # удаляем inline кнопки
    await query.message.delete()

# ----- Universal Text Handler -----
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state", "start")
    if state == "after_shop":
        # Пользователь ввел кассу
        shop = context.user_data.get("shop")
        if shop:
            cash = update.message.text
            user_id = update.message.from_user.id
            CASH_DATA[shop] = {
                "user_id": user_id,
                "cash": cash,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            await update.message.reply_text(f"Касса для {shop} обновлена: {cash}")
            context.user_data.pop("shop", None)
            context.user_data["state"] = "start"
            keyboard = get_reply_keyboard("start", user_id)
            await update.message.reply_text("Нажмите кнопку меню ниже:", reply_markup=keyboard)
        return
    else:
        # Все остальное обрабатываем как выбор меню
        await show_menu(update, context)

# ----- Reminders -----
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now()
    for user_id in EMPLOYEES:
        msg = f"Напоминаем обновить кассу на сегодня ({now.strftime('%H:%M')})!"
        keyboard = [[InlineKeyboardButton(shop, callback_data=shop)] for shop in SHOPS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=reply_markup)
        except Exception as e:
            print(f"Ошибка при отправке напоминания {user_id}: {e}")

def schedule_jobs(app):
    job_queue: JobQueue = app.job_queue
    for hour in NOTIFY_HOURS:
        job_queue.run_daily(send_reminder, time=datetime.time(hour=hour, minute=0, second=0))

# ----- Main -----
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(shop_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    schedule_jobs(app)
    app.run_polling()

if __name__ == "__main__":
    main()

