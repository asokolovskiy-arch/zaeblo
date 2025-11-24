import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ---------- Токен бота ----------

TOKEN = "8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o"

# ---------- Данные касс ----------

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

# ---------- Reply Клавиатура ----------

def get_reply_keyboard(state: str):
if state == "start":
return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)
if state == "menu":
buttons = [["Выбрать точку"], ["Показать все кассы"], ["Назад"]]
return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
if state == "select_shop":
shops = list(CASH_DATA.keys())
keyboard = [[shop] for shop in shops] + [["Назад"]]
return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)

# ---------- Хэндлеры ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
context.user_data["state"] = "start"
keyboard = get_reply_keyboard("start")
await update.message.reply_text("Нажмите кнопку ниже:", reply_markup=keyboard)

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

```
if text == "Показать меню":
    context.user_data["state"] = "menu"
    keyboard = get_reply_keyboard("menu")
    await update.message.reply_text("Меню:", reply_markup=keyboard)
    return

if text == "Назад":
    context.user_data["state"] = "menu"
    keyboard = get_reply_keyboard("menu")
    await update.message.reply_text("Меню:", reply_markup=keyboard)
    return

if text == "Выбрать точку":
    context.user_data["state"] = "select_shop"
    keyboard = get_reply_keyboard("select_shop")
    await update.message.reply_text("Выберите точку:", reply_markup=keyboard)
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
        keyboard = get_reply_keyboard("menu")
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

await update.message.reply_text("Не понял команду. Нажмите кнопку ниже.")
```

# ---------- Напоминание ----------

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
now = datetime.datetime.now().strftime("%H:%M")
await context.bot.send_message(ADMIN_ID, f"⏰ Напоминание обновить кассы ({now})")

# ---------- MAIN ----------

def main():
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

```
# ---------- JobQueue ----------
if app.job_queue is not None:
    app.job_queue.run_daily(send_reminder, time=datetime.time(hour=21, minute=0, second=0))

app.run_polling()
```

if **name** == "**main**":
main()
