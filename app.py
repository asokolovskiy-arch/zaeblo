import os
import datetime
import json
from collections import defaultdict
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask
import threading
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------- Токен бота ----------
TOKEN = os.environ.get("BOT_TOKEN", "8467867383:AAGrCYHbRJqxZwPm2rS8YCjb5Wf_ulLVG_o")

# ---------- PostgreSQL ----------
DATABASE_URL = os.environ.get('DATABASE_URL')

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

# ---------- Список админов ----------
ADMINS = {
    6702575755,
    7085347092,
}

# Хранилище пользователей и сессий
USER_ACTIVITY = defaultdict(list)
AUTHORIZED_USERS = set()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS or is_admin(user_id)

# ---------- PostgreSQL функции ----------
def init_db():
    """Инициализация таблиц в базе данных"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS cash_data (
                shop_name TEXT PRIMARY KEY,
                user_id BIGINT,
                cash INTEGER,
                timestamp TEXT
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("✅ База данных инициализирована")
        load_authorized_users()
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def load_authorized_users():
    """Загружает авторизованных пользователей из БД"""
    global AUTHORIZED_USERS
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('SELECT user_id FROM authorized_users')
        for row in cur.fetchall():
            AUTHORIZED_USERS.add(row[0])
        print(f"✅ Загружено {len(AUTHORIZED_USERS)} авторизованных пользователей")
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователей: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def add_authorized_user(user_id: int, username: str = "", full_name: str = ""):
    """Добавляет пользователя в авторизованные"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO authorized_users (user_id, username, full_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, username, full_name))
        conn.commit()
        AUTHORIZED_USERS.add(user_id)
        print(f"✅ Пользователь {user_id} авторизован")
    except Exception as e:
        print(f"❌ Ошибка добавления пользователя: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def remove_authorized_user(user_id: int):
    """Удаляет пользователя из авторизованных"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('DELETE FROM authorized_users WHERE user_id = %s', (user_id,))
        conn.commit()
        AUTHORIZED_USERS.discard(user_id)
        print(f"✅ Пользователь {user_id} удален")
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def save_cash_data():
    """Сохраняет все данные касс в PostgreSQL"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        for shop, data in CASH_DATA.items():
            if data:
                cur.execute('''
                    INSERT INTO cash_data (shop_name, user_id, cash, timestamp)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (shop_name) 
                    DO UPDATE SET user_id = %s, cash = %s, timestamp = %s
                ''', (shop, data.get('user_id'), data.get('cash'), data.get('timestamp'),
                      data.get('user_id'), data.get('cash'), data.get('timestamp')))
            else:
                cur.execute('DELETE FROM cash_data WHERE shop_name = %s', (shop,))
        
        conn.commit()
        print("✅ Данные сохранены в PostgreSQL")
    except Exception as e:
        print(f"❌ Ошибка сохранения в БД: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

def load_cash_data():
    """Загружает данные касс из PostgreSQL"""
    global CASH_DATA
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM cash_data')
        
        for row in cur.fetchall():
            shop = row['shop_name']
            if shop in CASH_DATA:
                CASH_DATA[shop] = {
                    'user_id': row['user_id'],
                    'cash': str(row['cash']),
                    'timestamp': row['timestamp']
                }
        
        print("✅ Данные загружены из PostgreSQL")
    except Exception as e:
        print(f"❌ Ошибка загрузки из БД: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

# ---------- Flask app ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Telegram Bot is running with Authorization!"

@app.route('/health')
def health():
    return "OK"

# ---------- Клавиатуры ----------
def get_reply_keyboard(state: str, user_id: int = None):
    if state == "start":
        return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)
    
    if state == "auth_required":
        return ReplyKeyboardMarkup([[KeyboardButton("Авторизоваться")]], resize_keyboard=True)
    
    if state == "menu":
        if user_id and is_admin(user_id):
            buttons = [
                ["Выбрать точку"],
                ["Статистика", "Управление"]
            ]
        elif user_id and is_authorized(user_id):
            buttons = [["Выбрать точку"]]
        else:
            buttons = [["Авторизоваться"]]
        
        buttons.append(["Назад"])
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    if state == "select_shop":
        shops = list(CASH_DATA.keys())
        keyboard = [[shop] for shop in shops] + [["Назад"]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if state == "admin_management":
        buttons = [
            ["Сбросить всё", "Управление пользователями"],
            ["Экспорт данных", "Список пользователей"],
            ["Рассылка", "Список админов"],
            ["Назад"]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    if state == "user_management":
        buttons = [
            ["Добавить пользователя", "Удалить пользователя"],
            ["Список пользователей"],
            ["Назад"]
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    
    return ReplyKeyboardMarkup([[KeyboardButton("Показать меню")]], resize_keyboard=True)

# ---------- Логирование ----------
def log_user_activity(user_id: int, action: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    USER_ACTIVITY[user_id].append(f"{timestamp} - {action}")
    if len(USER_ACTIVITY[user_id]) > 10:
        USER_ACTIVITY[user_id] = USER_ACTIVITY[user_id][-10:]

# ---------- Основные хэндлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    log_user_activity(user_id, "start")
    
    if not is_authorized(user_id) and not is_admin(user_id):
        context.user_data["state"] = "auth_required"
        keyboard = get_reply_keyboard("auth_required", user_id)
        await update.message.reply_text(
            "🔐 Для работы с ботом требуется авторизация.\n\nНажмите кнопку ниже для авторизации:",
            reply_markup=keyboard
        )
        return
    
    context.user_data["state"] = "start"
    keyboard = get_reply_keyboard("start", user_id)
    
    if is_admin(user_id):
        await update.message.reply_text("👑 Добро пожаловать, Админ!\nНажмите кнопку ниже:", reply_markup=keyboard)
    else:
        await update.message.reply_text("✅ Добро пожаловать!\nНажмите кнопку ниже:", reply_markup=keyboard)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    state = context.user_data.get("state", "start")
    
    log_user_activity(user_id, f"text: {text}")

    if text not in ["Авторизоваться", "Показать меню", "Назад"] and not is_authorized(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен. Требуется авторизация.")
        return

    if text == "Показать меню":
        context.user_data["state"] = "menu"
        keyboard = get_reply_keyboard("menu", user_id)
        await update.message.reply_text("Меню:", reply_markup=keyboard)
        return

    if text == "Авторизоваться":
        if is_authorized(user_id) or is_admin(user_id):
            await update.message.reply_text("✅ Вы уже авторизованы!")
            context.user_data["state"] = "menu"
            keyboard = get_reply_keyboard("menu", user_id)
            await update.message.reply_text("Меню:", reply_markup=keyboard)
        else:
            await update.message.reply_text(
                "🔐 Для авторизации обратитесь к администратору.\n\n"
                f"Ваш User ID: `{user_id}`",
                parse_mode='MarkdownV2'
            )
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
        if is_admin(user_id):
            await admin_stats(update, context)
        else:
            await update.message.reply_text("❌ Доступ запрещен")
        return

    if text == "Управление":
        if is_admin(user_id):
            context.user_data["state"] = "admin_management"
            keyboard = get_reply_keyboard("admin_management", user_id)
            await update.message.reply_text("👑 Панель управления:", reply_markup=keyboard)
        else:
            await update.message.reply_text("❌ Доступ запрещен")
        return

    if state == "admin_management":
        if text == "Сбросить всё":
            await admin_reset_all(update, context)
            return
        elif text == "Управление пользователями":
            context.user_data["state"] = "user_management"
            keyboard = get_reply_keyboard("user_management", user_id)
            await update.message.reply_text("👥 Управление пользователями:", reply_markup=keyboard)
            return
        elif text == "Экспорт данных":
            await admin_export(update, context)
            return
        elif text == "Список пользователей":
            await admin_users(update, context)
            return
        elif text == "Рассылка":
            await update.message.reply_text("Введите команду: /broadcast <сообщение>")
            return
        elif text == "Список админов":
            await admin_list(update, context)
            return

    if state == "user_management":
        if text == "Добавить пользователя":
            await update.message.reply_text("Используйте команду: /adduser <user_id>")
            return
        elif text == "Удалить пользователя":
            await update.message.reply_text("Используйте команду: /removeuser <user_id>")
            return
        elif text == "Список пользователей":
            await admin_authorized_users(update, context)
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
            
            save_cash_data()
            
            log_user_activity(user_id, f"updated_cash: {shop} = {text} руб.")
            await update.message.reply_text(f"Касса для {shop} обновлена: {text} руб.")
            context.user_data["state"] = "menu"
            keyboard = get_reply_keyboard("menu", user_id)
            await update.message.reply_text("Меню:", reply_markup=keyboard)
            return

    await update.message.reply_text("Не понял команду. Нажмите кнопку ниже.")

# ---------- Команды управления пользователями ----------
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в авторизованные"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /adduser <user_id>")
        return
    
    try:
        new_user_id = int(context.args[0])
        username = update.message.from_user.username or ""
        full_name = update.message.from_user.full_name or ""
        
        add_authorized_user(new_user_id, username, full_name)
        await update.message.reply_text(f"✅ Пользователь `{new_user_id}` добавлен", parse_mode='MarkdownV2')
        
    except ValueError:
        await update.message.reply_text("❌ User ID должен быть числом")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить пользователя из авторизованных"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /removeuser <user_id>")
        return
    
    try:
        user_id_to_remove = int(context.args[0])
        
        if user_id_to_remove in ADMINS:
            await update.message.reply_text("❌ Нельзя удалить администратора")
            return
        
        remove_authorized_user(user_id_to_remove)
        await update.message.reply_text(f"✅ Пользователь `{user_id_to_remove}` удален", parse_mode='MarkdownV2')
        
    except ValueError:
        await update.message.reply_text("❌ User ID должен быть числом")

async def admin_authorized_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список авторизованных пользователей"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not AUTHORIZED_USERS:
        await update.message.reply_text("📝 Авторизованных пользователей пока нет")
        return
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('SELECT user_id, username, full_name, authorized_at FROM authorized_users ORDER BY authorized_at DESC')
        
        text = "👥 **АВТОРИЗОВАННЫЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
        
        for user_id, username, full_name, authorized_at in cur.fetchall():
            text += f"🆔 `{user_id}`\n"
            text += f"👤 {full_name or 'Не указано'}\n"
            if username:
                text += f"📱 @{username}\n"
            text += f"⏰ Добавлен: {authorized_at.strftime('%Y-%m-%d %H:%M')}\n"
            text += "─" * 20 + "\n"
        
        text += f"\nВсего пользователей: {len(AUTHORIZED_USERS)}"
        await update.message.reply_text(text, parse_mode='MarkdownV2')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка получения списка: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

# ---------- Админские функции ----------
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
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
    
    average_cash = 0
    if cash_values:
        average_cash = sum(cash_values) / len(cash_values)
    
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
• Авторизованных: {len(AUTHORIZED_USERS)}
• Действий сегодня: {today_actions}

⏰ **Последние обновления:**
"""
    
    recent_updates = []
    for shop, data in CASH_DATA.items():
        if data and "timestamp" in data:
            recent_updates.append((shop, data["timestamp"], data.get("cash", "N/A")))
    
    recent_updates.sort(key=lambda x: x[1], reverse=True)
    
    for shop, timestamp, cash in recent_updates[:5]:
        text += f"• {shop}: {cash} руб. ({timestamp})\n"
    
    if cash_values:
        text += f"\n🏆 **Топ-3 по выручке:**\n"
        top_shops = [(shop, int(data["cash"])) for shop, data in CASH_DATA.items() if data and "cash" in data]
        top_shops.sort(key=lambda x: x[1], reverse=True)
        
        for i, (shop, cash) in enumerate(top_shops[:3], 1):
            text += f"{i}. {shop}: {cash:,} руб.\n"
    
    await update.message.reply_text(text)

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех пользователей с активностью"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not USER_ACTIVITY:
        await update.message.reply_text("📝 Пользователей пока нет")
        return
    
    text = "👥 **СПИСОК ВСЕХ ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
    
    for user_id, actions in USER_ACTIVITY.items():
        last_action = actions[-1] if actions else "нет действий"
        user_status = "👑 АДМИН" if is_admin(user_id) else ("✅ АВТОРИЗОВАН" if is_authorized(user_id) else "❌ НЕАВТОРИЗОВАН")
        text += f"🆔 {user_id} ({user_status})\n"
        text += f"📊 Действий: {len(actions)}\n"
        text += f"⏰ Последнее: {last_action}\n"
        text += "─" * 20 + "\n"
    
    await update.message.reply_text(text)

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных для админа"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    export_data = {
        "cash_data": CASH_DATA,
        "timestamp": datetime.datetime.now().isoformat(),
        "total_shops": len(CASH_DATA)
    }
    
    formatted_data = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    if len(formatted_data) < 4000:
        await update.message.reply_text(f"```json\n{formatted_data}\n```", parse_mode='MarkdownV2')
    else:
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
        
        if len(ADMINS) <= 1:
            await update.message.reply_text("❌ Нельзя удалить последнего админа")
            return
        
        ADMINS.remove(admin_id_to_remove)
        await update.message.reply_text(f"✅ Пользователь `{admin_id_to_remove}` удален из админов", parse_mode='MarkdownV2')
        
    except ValueError:
        await update.message.reply_text("❌ User ID должен быть числом")

async def admin_reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить все данные касс"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    for shop in CASH_DATA:
        CASH_DATA[shop] = {}
    
    save_cash_data()
    await update.message.reply_text("✅ Все данные касс сброшены!")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now().strftime("%H:%M")
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, f"⏰ Напоминание обновить кассы ({now})")
        except Exception as e:
            print(f"Ошибка отправки напоминания админу {admin_id}: {e}")

# ---------- Запуск Flask и бота ----------
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    print("🤖 Starting Telegram Bot...")
    
    init_db()
    load_cash_data()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Основные команды
    application.add_handler(CommandHandler("start", start))
    
    # Команды управления пользователями
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("removeuser", remove_user))
    
    # Админские команды
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("users", admin_users))
    application.add_handler(CommandHandler("export", admin_export))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("admins", admin_list))
    application.add_handler(CommandHandler("addadmin", admin_add))
    application.add_handler(CommandHandler("removeadmin", admin_remove))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    if application.job_queue:
        application.job_queue.run_daily(
            send_reminder, 
            time=datetime.time(hour=21, minute=0, second=0)
        )

    print("✅ Bot is running with authorization system...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    import time
    time.sleep(2)
    
    run_bot()