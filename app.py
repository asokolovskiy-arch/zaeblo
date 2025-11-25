import os
import datetime
import json
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ---------- Токен бота ----------
TOKEN = os.environ.get("BOT_TOKEN", "8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o")

# ---------- Данные касс ----------
CASH_DATA = {
    "Апельсин N1": {},
    "Мацеста1 N2": {},
    "Мацеста2 N4": {},
    "Водоканал N5": {},
    "Ц рынок N6": {},
    "Дагомыс N7": {},
    "Ареда N8": {},
}

# ---------- Список админов ----------
ADMINS = {
    6702575755,  # Основной админ
    # Добавьте сюда ID других админов:
    # 1234567890,
    # 9876543210,
}

# Хранилище пользователей
USER_ACTIVITY = defaultdict(list)

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь админом"""
    return user_id in ADMINS

# ---------- Reply Клавиатура ----------
def get_reply_keyboard(state: str, user_id: int = None):
    if state == "start":
        return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)
    
    if state == "menu":
        if user_id and is_admin(user_id):
            # Меню для админа
            buttons = [["Выбрать точку", "Статистика"]]
        else:
            # Меню для обычных пользователей - только выбор точки
            buttons = [["Выбрать точку"]]
        
        buttons.append(["Назад"])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    if state == "select_shop":
        shops = list(CASH_DATA.keys())
        keyboard = [[shop] for shop in shops] + [["Назад"]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)

# ---------- Логирование активности ----------
def log_user_activity(user_id: int, action: str):
    """Логируем действия пользователя"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    USER_ACTIVITY[user_id].append(f"{timestamp} - {action}")
    # Храним только последние 10 действий на пользователя
    if len(USER_ACTIVITY[user_id]) > 10:
        USER_ACTIVITY[user_id] = USER_ACTIVITY[user_id][-10:]

# ---------- Основные хэндлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    log_user_activity(user_id, "start")
    
    context.user_data["state"] = "start"
    keyboard = get_reply_keyboard("start", user_id)
    
    if is_admin(user_id):
        await update.message.reply_text("👑 Добро пожаловать, Админ!\nНажмите кнопку ниже:", reply_markup=keyboard)
    else:
        await update.message.reply_text("Нажмите кнопку ниже:", reply_markup=keyboard)

async def show_all_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    log_user_activity(user_id, "show_all_cash")
    
    text = "📊 Все кассы:\n\n"
    for shop, data in CASH_DATA.items():
        if data and "cash" in data:
            text += f"🏪 {shop}: {data['cash']} руб. (в {data['timestamp']})\n"
        else:
            text += f"🏪 {shop}: нет данных\n"
    await update.message.reply_text(text)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    state = context.user_data.get("state", "start")
    
    log_user_activity(user_id, f"text: {text}")

    if text == "Показать меню":
        context.user_data["state"] = "menu"
        keyboard = get_reply_keyboard("menu", user_id)
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    if text == "Назад":
        context.user_data["state"] = "menu"
        keyboard = get_reply_keyboard("menu", user_id)
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    if text == "Выбрать точку":
        context.user_data["state"] = "select_shop"
        keyboard = get_reply_keyboard("select_shop", user_id)
        await update.message.reply_text("Выберите точку:", reply_markup=keyboard)
        return

    if text == "Статистика":
        # Только админ имеет доступ к статистике
        if is_admin(user_id):
            await admin_stats(update, context)
        else:
            await update.message.reply_text("❌ Доступ запрещен")
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
            log_user_activity(user_id, f"updated_cash: {shop} = {text} руб.")
            
            await update.message.reply_text(f"Касса для {shop} обновлена: {text} руб.")
            context.user_data["state"] = "menu"
            keyboard = get_reply_keyboard("menu", user_id)
            await update.message.reply_text("Меню:", reply_markup=keyboard)
            return

    await update.message.reply_text("Не понял команду. Нажмите кнопку ниже.")

# ---------- Админские функции ----------
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика для админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    # Статистика по кассам
    total_cash = 0
    updated_count = 0
    empty_count = 0
    cash_values = []
    
    for shop, data in CASH_DATA.items():
        if data and "cash" in data:
            cash_value = int(data["cash"])
            total_cash += cash_value
            cash_values.append(cash_value)
            updated_count += 1
        else:
            empty_count += 1
    
    # Расчет средней выручки
    average_cash = 0
    if cash_values:
        average_cash = sum(cash_values) / len(cash_values)
    
    # Статистика по пользователям
    active_users = len(USER_ACTIVITY)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_actions = sum(1 for actions in USER_ACTIVITY.values() for action in actions if action.startswith(today))
    
    text = f"""
📊 **СТАТИСТИКА АДМИНА**

🏪 **Кассы:**
• Обновлено: {updated_count}/{len(CASH_DATA)}
• Пустых: {empty_count}
• Общая сумма: {total_cash:,} руб.
• Средняя выручка: {average_cash:,.0f} руб.

👥 **Пользователи:**
• Активных: {active_users}
• Действий сегодня: {today_actions}

⏰ **Последние обновления:**
"""
    
    # Добавляем последние 5 обновлений
    recent_updates = []
    for shop, data in CASH_DATA.items():
        if data and "timestamp" in data:
            recent_updates.append((shop, data["timestamp"], data.get("cash", "N/A")))
    
    recent_updates.sort(key=lambda x: x[1], reverse=True)
    
    for shop, timestamp, cash in recent_updates[:5]:
        text += f"• {shop}: {cash} руб. ({timestamp})\n"
    
    # Добавляем топ-3 точки по выручке
    if cash_values:
        text += f"\n🏆 **Топ-3 по выручке:**\n"
        top_shops = [(shop, int(data["cash"])) for shop, data in CASH_DATA.items() if data and "cash" in data]
        top_shops.sort(key=lambda x: x[1], reverse=True)
        
        for i, (shop, cash) in enumerate(top_shops[:3], 1):
            text += f"{i}. {shop}: {cash:,} руб.\n"
    
    await update.message.reply_text(text)

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список пользователей для админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not USER_ACTIVITY:
        await update.message.reply_text("📝 Пользователей пока нет")
        return
    
    text = "👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
    
    for user_id, actions in USER_ACTIVITY.items():
        last_action = actions[-1] if actions else "нет действий"
        admin_status = "👑 АДМИН" if is_admin(user_id) else "👤 ПОЛЬЗОВАТЕЛЬ"
        text += f"🆔 {user_id} ({admin_status})\n"
        text += f"📊 Действий: {len(actions)}\n"
        text += f"⏰ Последнее: {last_action}\n"
        text += "─" * 20 + "\n"
    
    await update.message.reply_text(text)

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных для админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    # Создаем данные для экспорта
    export_data = {
        "cash_data": CASH_DATA,
        "timestamp": datetime.datetime.now().isoformat(),
        "total_shops": len(CASH_DATA)
    }
    
    # Форматируем для читаемости
    formatted_data = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    # Отправляем как файл или текст (если небольшой)
    if len(formatted_data) < 4000:  # Лимит Telegram для сообщения
        await update.message.reply_text(f"```json\n{formatted_data}\n```", parse_mode='MarkdownV2')
    else:
        # Если данных много - отправляем как файл
        await update.message.reply_document(
            document=json.dumps(export_data).encode(),
            filename=f"cash_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка сообщений всем пользователям"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /broadcast <сообщение>")
        return
    
    message = " ".join(context.args)
    broadcast_count = 0
    
    for user_id in USER_ACTIVITY.keys():
        try:
            await context.bot.send_message(user_id, f"📢 **РАССЫЛКА:**\n\n{message}")
            broadcast_count += 1
        except Exception as e:
            print(f"Не удалось отправить пользователю {user_id}: {e}")
    
    await update.message.reply_text(f"✅ Сообщение отправлено {broadcast_count} пользователям")

# ---------- Управление админами ----------
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список админов"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not ADMINS:
        await update.message.reply_text("📝 Список админов пуст")
        return
    
    text = "👑 **СПИСОК АДМИНОВ:**\n\n"
    for i, admin_id in enumerate(sorted(ADMINS), 1):
        text += f"{i}. `{admin_id}`\n"
    
    text += f"\nВсего админов: {len(ADMINS)}"
    await update.message.reply_text(text, parse_mode='MarkdownV2')

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить нового админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /addadmin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        
        if new_admin_id in ADMINS:
            await update.message.reply_text("⚠️ Этот пользователь уже является админом")
            return
        
        ADMINS.add(new_admin_id)
        await update.message.reply_text(f"✅ Пользователь `{new_admin_id}` добавлен в админы", parse_mode='MarkdownV2')
        
        # Уведомляем нового админа
        try:
            await context.bot.send_message(new_admin_id, "🎉 Вас добавили в админы бота!")
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ User ID должен быть числом")

async def admin_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /removeadmin <user_id>")
        return
    
    try:
        admin_id_to_remove = int(context.args[0])
        
        if admin_id_to_remove not in ADMINS:
            await update.message.reply_text("❌ Этот пользователь не является админом")
            return
        
        # Не позволяем удалить последнего админа
        if len(ADMINS) <= 1:
            await update.message.reply_text("❌ Нельзя удалить последнего админа")
            return
        
        ADMINS.remove(admin_id_to_remove)
        await update.message.reply_text(f"✅ Пользователь `{admin_id_to_remove}` удален из админов", parse_mode='MarkdownV2')
        
    except ValueError:
        await update.message.reply_text("❌ User ID должен быть числом")

# ---------- Напоминание ----------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Напоминание обновить кассы"""
    now = datetime.datetime.now().strftime("%H:%M")
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, f"⏰ Напоминание обновить кассы ({now})")
        except Exception as e:
            print(f"Ошибка отправки напоминания админу {admin_id}: {e}")

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Основные команды
    app.add_handler(CommandHandler("start", start))
    
    # Админские команды
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("export", admin_export))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    
    # Команды управления админами
    app.add_handler(CommandHandler("admins", admin_list))
    app.add_handler(CommandHandler("addadmin", admin_add))
    app.add_handler(CommandHandler("removeadmin", admin_remove))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # JobQueue для напоминаний
    if app.job_queue:
        app.job_queue.run_daily(
            send_reminder, 
            time=datetime.time(hour=21, minute=0, second=0)
        )

    app.run_polling()

if __name__ == "__main__":
    main()