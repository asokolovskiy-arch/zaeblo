from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, JobQueue
)
import datetime

TOKEN = "8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o"

# Список магазинов
SHOPS = ["Ц. Рынок", "ТЦ Апельсин", "Базар"]

# Словарь для хранения касс
# {shop_name: {"user_id": int, "cash": str, "timestamp": str}}
CASH_DATA = {}

ADMIN_ID = 7085347092  # Твой Telegram ID

# Список сотрудников, которые получают уведомления
EMPLOYEES = []  # user_id добавляем при первом /start

# Время уведомлений (часы)
NOTIFY_HOURS = [11, 13, 15, 18]

# ----- Основные команды -----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in EMPLOYEES and user_id != ADMIN_ID:
        EMPLOYEES.append(user_id)
    keyboard = [[InlineKeyboardButton(shop, callback_data=shop)] for shop in SHOPS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите свою точку:", reply_markup=reply_markup)

async def shop_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop = query.data
    context.user_data["shop"] = shop
    await query.message.reply_text(f"Введите актуальную кассу для {shop}:")

async def handle_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    cash = update.message.text
    shop = context.user_data.get("shop")
    if not shop:
        await update.message.reply_text("Сначала выберите точку через /start")
        return
    CASH_DATA[shop] = {"user_id": user_id, "cash": cash, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    await update.message.reply_text(f"Касса для {shop} обновлена: {cash}")

async def view_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("У вас нет прав для просмотра всех касс.")
        return
    msg = "Текущие кассы:\n"
    for shop, data in CASH_DATA.items():
        msg += f"{shop}: {data['cash']} (обновлено {data['timestamp']})\n"
    await update.message.reply_text(msg)

# ----- Авто-напоминания -----

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
    app.add_handler(CommandHandler("view_all", view_all))
    app.add_handler(CallbackQueryHandler(shop_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cash))

    schedule_jobs(app)

    app.run_polling()

if __name__ == "__main__":
    main()
