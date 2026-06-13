# -*- coding: utf-8 -*-
import os
import logging
import random
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
REVIEWS_CHANNEL = "https://t.me/kamaz_repp"
SUPPORT_CONTACT = "@w1zzxrd"
ADMIN_CHANNEL = "@w1zzxrd"

# ID адміністратора (ТВІЙ ID)
ADMIN_IDS = [8381902355]

# Реквізити карти Монобанк
MONOBANK_CARD = "4441 1110 1486 5079"
MONOBANK_CARD_NO_SPACES = "4441111014865079"

# Тарифи Premium
PREMIUM_PACKAGES = {
    "3_months": {"price": 600, "currency": "гривень", "name": "3 місяці"},
    "6_months": {"price": 800, "currency": "гривень", "name": "6 місяців"},
    "12_months": {"price": 1400, "currency": "гривень", "name": "12 місяців"}
}

STAR_PRICE = 0.85
user_states = {}

# ============= БАЗА ДАНИХ =============
def init_db():
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  joined_date TEXT,
                  total_spent REAL DEFAULT 0,
                  orders_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  product_name TEXT,
                  base_amount REAL,
                  paid_amount REAL,
                  status TEXT DEFAULT 'pending',
                  created_date TEXT)''')
    conn.commit()
    conn.close()

init_db()

def save_user(user_id, username, first_name):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
                 VALUES (?, ?, ?, ?)''', (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def save_order(user_id, product_name, base_amount, paid_amount):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''INSERT INTO orders (user_id, product_name, base_amount, paid_amount, created_date)
                 VALUES (?, ?, ?, ?, ?)''', 
              (user_id, product_name, base_amount, paid_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def confirm_order(order_id):
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('UPDATE orders SET status = "confirmed" WHERE order_id = ?', (order_id,))
    c.execute('SELECT user_id, paid_amount FROM orders WHERE order_id = ?', (order_id,))
    order = c.fetchone()
    if order:
        c.execute('UPDATE users SET total_spent = total_spent + ?, orders_count = orders_count + 1 WHERE user_id = ?', (order[1], order[0]))
    conn.commit()
    conn.close()

def generate_unique_amount(base_amount: float) -> tuple:
    random_cents = random.randint(1, 99)
    return round(base_amount + (random_cents / 100), 2), random_cents

# ============= АДМІН ПАНЕЛЬ =============
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("❌ Немає доступу!", show_alert=True)
        return
    
    text = "🔐 **АДМІН ПАНЕЛЬ**\n\nОберіть дію:"
    keyboard = [
        [InlineKeyboardButton("📊 СТАТИСТИКА", callback_data="admin_stats")],
        [InlineKeyboardButton("📦 ЗАМОВЛЕННЯ", callback_data="admin_orders")],
        [InlineKeyboardButton("📢 РОЗСИЛКА", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👤 ПОШУК", callback_data="admin_search")],
        [InlineKeyboardButton("✅ ПІДТВЕРДИТИ", callback_data="admin_confirm")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    c.execute("SELECT SUM(paid_amount) FROM orders WHERE status = 'confirmed'")
    total_revenue = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*), SUM(paid_amount) FROM orders WHERE status = 'pending'")
    pending = c.fetchone()
    conn.close()
    
    text = f"📊 **СТАТИСТИКА**\n\n👥 Користувачів: {total_users}\n📦 Замовлень: {total_orders}\n💰 Дохід: {total_revenue:.2f} грн\n⏳ Очікує: {pending[0] or 0} на {pending[1] or 0:.2f} грн"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 НАЗАД", callback_data="admin_panel")]]), parse_mode='Markdown')

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT order_id, user_id, product_name, paid_amount, status, created_date FROM orders ORDER BY order_id DESC LIMIT 20''')
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        text = "📦 Немає замовлень"
    else:
        text = "📦 **ОСТАННІ 20 ЗАМОВЛЕНЬ:**\n\n"
        for order in orders:
            text += f"{'✅' if order[4]=='confirmed' else '⏳'} #{order[0]} | {order[2]}\n   👤 {order[1]} | 💰 {order[3]:.2f} грн\n\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 НАЗАД", callback_data="admin_panel")]]), parse_mode='Markdown')

async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT order_id, user_id, product_name, paid_amount FROM orders WHERE status = 'pending' ORDER BY order_id DESC''')
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await query.edit_message_text("✅ Немає замовлень", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 НАЗАД", callback_data="admin_panel")]]))
        return
    
    keyboard = []
    for order in orders:
        keyboard.append([InlineKeyboardButton(f"✅ #{order[0]} | {order[2]}", callback_data=f"confirm_{order[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 НАЗАД", callback_data="admin_panel")])
    await query.edit_message_text("✅ **ВИБЕРІТЬ ЗАМОВЛЕННЯ:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def confirm_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split('_')[1])
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('SELECT user_id, product_name, paid_amount FROM orders WHERE order_id = ?', (order_id,))
    order = c.fetchone()
    if order:
        confirm_order(order_id)
        try:
            await context.bot.send_message(order[0], f"✅ **ЗАМОВЛЕННЯ ПІДТВЕРДЖЕНО!**\n\n🎯 {order[1]}\n💰 {order[2]:.2f} грн\n\nДякуємо за покупку!", parse_mode='Markdown')
        except:
            pass
        await query.edit_message_text(f"✅ Замовлення #{order_id} підтверджено!")
    else:
        await query.edit_message_text("❌ Замовлення не знайдено")
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 НАЗАД", callback_data="admin_panel")]]))

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[query.from_user.id] = "waiting_broadcast"
    await query.edit_message_text("📢 **РОЗСИЛКА**\n\nНадішліть текст повідомлення для розсилки всім користувачам:", parse_mode='Markdown')

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[query.from_user.id] = "waiting_search"
    await query.edit_message_text("👤 **ПОШУК КОРИСТУВАЧА**\n\nВведіть ID або @username:", parse_mode='Markdown')

# ============= ОСНОВНІ ФУНКЦІЇ БОТА =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name)
    
    text = f"""✨ ЛАСКАВО ПРОСИМО В CRYPTO STARS STORE! ✨

🆔 Користувач: @{user.username if user.username else user.first_name}
📅 Ваш ID: {user.id}

🌟 Telegram Stars & Premium
💎 Офіційні поставки
🔐 Криптоплатежі

⚡ ПЕРЕВАГИ:
• ✅ Миттєва доставка
• 🔒 Анонімні платежі  
• 💰 Найкращі ціни на ринку
• 🛡 100% гарантія
• 🕒 Підтримка 24/7

📊 НАША СТАТИСТИКА:
👥 125+ задоволених клієнтів
⭐ 4.9/5 рейтинг довіри
🚀 98% замовлень за 5 хвилин

💬 ВІДГУКИ КЛІЄНТІВ: {REVIEWS_CHANNEL}

👇 ОБЕРІТЬ ТОВАР:"""
    
    keyboard = [
        [InlineKeyboardButton("⭐ КУПИТИ TELEGRAM STARS", callback_data="buy_stars")],
        [InlineKeyboardButton("👑 КУПИТИ TELEGRAM PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("💬 ВІДГУКИ КЛІЄНТІВ", callback_data="reviews")],
        [InlineKeyboardButton("👤 МІЙ ПРОФІЛЬ", callback_data="profile")],
        [InlineKeyboardButton("🛟 ПІДТРИМКА", callback_data="support")]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🔐 АДМІН ПАНЕЛЬ", callback_data="admin_panel")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = f"""💫 ВІДГУКИ НАШИХ КЛІЄНТІВ 💫

📈 МИ ПИШАЄМОСЯ НАШОЮ РЕПУТАЦІЄЮ:

⭐ 4.9/5 середній рейтинг
👥 125+ задоволених клієнтів  
🚀 98% замовлень за 5 хвилин
💎 100% гарантія якості

💬 Читайте реальні відгуки: {REVIEWS_CHANNEL}

🌟 Приєднуйтесь до нашої спільноти задоволених клієнтів!"""
    
    keyboard = [
        [InlineKeyboardButton("📢 ПЕРЕЙТИ ДО ВІДГУКІВ", url=REVIEWS_CHANNEL)],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stars_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = f"""⭐ TELEGRAM STARS - ВИБІР КІЛЬКОСТі ⭐

🎯 Stars - це внутрішньоігрова валюта Telegram для підтримки творців

💰 ЦІНА: 1 зірка = {STAR_PRICE} грн

🎁 ГОТОВІ ПАКЕТИ:
├ 100 Stars - {100 * STAR_PRICE} грн
├ 500 Stars - {500 * STAR_PRICE} грн  
├ 1000 Stars - {1000 * STAR_PRICE} грн
└ 5000 Stars - {5000 * STAR_PRICE} грн

🔢 АБО ОБЕРІТЬ СВОЮ КІЛЬКІСТЬ

👇 ОБЕРІТЬ ВАРІАНТ:"""
    
    keyboard = [
        [InlineKeyboardButton("100 ⭐", callback_data="stars_100"), InlineKeyboardButton("500 ⭐", callback_data="stars_500")],
        [InlineKeyboardButton("1000 ⭐", callback_data="stars_1000"), InlineKeyboardButton("5000 ⭐", callback_data="stars_5000")],
        [InlineKeyboardButton("🔢 ОБРАТИ СВОЮ КІЛЬКІСТЬ", callback_data="custom_stars")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_premium_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = """👑 TELEGRAM PREMIUM - ПАКЕТИ 👑

🎯 ПЕРЕВАГИ PREMIUM:
• 📢 Збільшені ліміти завантаження
• 🎨 Унікальні стікери та емодзі
• 🌟 Кольорове ім'я в чатах  
• 🚀 Швидкі завантаження
• 🎭 Анімовані аватари
• ❌ Без реклами

💰 ДОСТУПНІ ТАРИФИ:
├ 3 місяці - 600 грн
├ 6 місяців - 800 грн
└ 12 місяців - 1400 грн

👇 ОБЕРІТЬ ПАКЕТ:"""
    
    keyboard = [
        [InlineKeyboardButton("3 МІСЯЦІ - 600₴", callback_data="premium_3"), InlineKeyboardButton("6 МІСЯЦІВ - 800₴", callback_data="premium_6")],
        [InlineKeyboardButton("12 МІСЯЦІВ - 1400₴", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT total_spent, orders_count FROM users WHERE user_id = ?", (user.id,))
    data = c.fetchone()
    conn.close()
    
    total_spent = data[0] if data and data[0] else 0
    orders_count = data[1] if data and data[1] else 0
    
    text = f"""👤 ВАШ ПРОФІЛЬ

📊 ОСНОВНА ІНФОРМАЦІЯ:
├ 🆔 ID: {user.id}
├ 👤 Ім'я: {user.first_name}
├ 📧 Username: @{user.username if user.username else 'не встановлено'}

💰 СТАТИСТИКА ПОКУПОК:
├ 🛍 Всього покупок: {orders_count}
└ 💸 Витрачено: {total_spent:.2f} грн

🎁 РЕФЕРАЛЬНА ПРОГРАМА:
Запрошуйте друзів і отримуйте 10% від їхніх перших покупок!"""
    
    keyboard = [[InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = f"""🛟 ПІДТРИМКА ТА ДОПОМОГА

📞 КОНТАКТИ:
👤 Оператор: @w1zzxrd

❓ ЯК ЗРОБИТИ ЗАМОВЛЕННЯ?
1. Оберіть товар в меню
2. Переведіть ТОЧНО вказану суму на карту
3. Надішліть чек оператору

💳 МЕТОДИ ОПЛАТИ:
• 💳 Картка Монобанк: {MONOBANK_CARD_NO_SPACES}
• 💎 Криптовалюти (USDT/TON) - за запитом

🕒 Підтримка: 24/7

💬 @w1zzxrd"""
    
    keyboard = [
        [InlineKeyboardButton("👤 ЗВ'ЯЗАТИСЯ З ОПЕРАТОРОМ", url="https://t.me/w1zzxrd")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def request_custom_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[query.from_user.id] = "waiting_stars_quantity"
    await query.edit_message_text(f"🔢 ВВЕДІТЬ КІЛЬКІСТЬ ЗІРОК\n\n💰 1 зірка = {STAR_PRICE} грн\n\n⚡ Мінімум: 100\n📈 Максимум: 10000\n\nВведіть число:")

async def handle_stars_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_states.get(user_id) != "waiting_stars_quantity":
        return
    
    try:
        qty = int(update.message.text)
        if qty < 100 or qty > 10000:
            await update.message.reply_text("❌ Від 100 до 10000 зірок!")
            return
        
        base_price = qty * STAR_PRICE
        unique_amount, random_cents = generate_unique_amount(base_price)
        product_name = f"{qty} Telegram Stars"
        save_order(user_id, product_name, base_price, unique_amount)
        
        text = f"""💳 ОФОРМЛЕННЯ ЗАМОВЛЕННЯ

🎯 Товар: {qty} Telegram Stars
💫 СУМА ДО ОПЛАТИ: {unique_amount} грн

━━━━━━━━━━━━━━━━━━━━
💳 РЕКВІЗИТИ ДЛЯ ОПЛАТИ:

🏦 Картка: {MONOBANK_CARD}
💵 Валюта: ГРИВНЯ (UAH)

⚠️ ВАЖЛИВО! Перекажіть ТОЧНО суму: {unique_amount} грн
━━━━━━━━━━━━━━━━━━━━

💬 ПІСЛЯ ОПЛАТИ: @w1zzxrd"""
        
        keyboard = [[InlineKeyboardButton("✅ Я ОПЛАТИВ", url="https://t.me/w1zzxrd")], [InlineKeyboardButton("🛒 В МАГАЗИН", callback_data="back_to_main")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        user_states[user_id] = None
        
    except ValueError:
        await update.message.reply_text("❌ Введіть число!")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    if data == "copy_card":
        await query.answer(f"Картка: {MONOBANK_CARD_NO_SPACES}", show_alert=True)
        return
    
    if data.startswith('stars_'):
        qty = int(data.split('_')[1])
        base_price = qty * STAR_PRICE
        product_name = f"{qty} Telegram Stars"
    elif data.startswith('premium_'):
        months = {"3": "3 місяці", "6": "6 місяців", "12": "12 місяців"}
        base_price = {"3": 600, "6": 800, "12": 1400}[data.split('_')[1]]
        product_name = f"Telegram Premium ({months[data.split('_')[1]]})"
    else:
        return
    
    unique_amount, random_cents = generate_unique_amount(base_price)
    save_order(user.id, product_name, base_price, unique_amount)
    
    text = f"""💳 ОФОРМЛЕННЯ ЗАМОВЛЕННЯ

🎯 Товар: {product_name}
💫 СУМА ДО ОПЛАТИ: {unique_amount} грн

━━━━━━━━━━━━━━━━━━━━
💳 РЕКВІЗИТИ ДЛЯ ОПЛАТИ:

🏦 Картка: {MONOBANK_CARD}
💵 Валюта: ГРИВНЯ (UAH)

⚠️ ВАЖЛИВО! Перекажіть ТОЧНО суму: {unique_amount} грн
━━━━━━━━━━━━━━━━━━━━

💬 ПІСЛЯ ОПЛАТИ: @w1zzxrd"""
    
    keyboard = [[InlineKeyboardButton("✅ Я ОПЛАТИВ", url="https://t.me/w1zzxrd")], [InlineKeyboardButton("🛒 В МАГАЗИН", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    text = f"""✨ ЛАСКАВО ПРОСИМО В CRYPTO STARS STORE! ✨

🆔 Користувач: @{user.username if user.username else user.first_name}
📅 Ваш ID: {user.id}

🌟 Telegram Stars & Premium
💎 Офіційні поставки
🔐 Криптоплатежі

👇 ОБЕРІТЬ ТОВАР:"""
    
    keyboard = [
        [InlineKeyboardButton("⭐ КУПИТИ TELEGRAM STARS", callback_data="buy_stars")],
        [InlineKeyboardButton("👑 КУПИТИ TELEGRAM PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("💬 ВІДГУКИ КЛІЄНТІВ", callback_data="reviews")],
        [InlineKeyboardButton("👤 МІЙ ПРОФІЛЬ", callback_data="profile")],
        [InlineKeyboardButton("🛟 ПІДТРИМКА", callback_data="support")]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🔐 АДМІН ПАНЕЛЬ", callback_data="admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============= ОБРОБНИК ТЕКСТОВИХ ПОВІДОМЛЕНЬ =============
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)
    
    if state == "waiting_stars_quantity":
        await handle_stars_quantity(update, context)
    elif state == "waiting_broadcast":
        await handle_broadcast_message(update, context)
    elif state == "waiting_search":
        await search_user(update, context)

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS or user_states.get(user_id) != "waiting_broadcast":
        return
    
    msg = update.message.text
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    success = 0
    status = await update.message.reply_text(f"📢 Починаю розсилку для {len(users)} користувачів...")
    
    for u in users:
        try:
            await context.bot.send_message(u[0], msg, parse_mode='Markdown')
            success += 1
        except:
            pass
        
        if success % 10 == 0:
            await status.edit_text(f"📢 Розсилка... Відправлено: {success}")
    
    await status.edit_text(f"✅ РОЗСИЛКУ ЗАВЕРШЕНО!\n\n✅ Відправлено: {success}")
    user_states[user_id] = None

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS or user_states.get(user_id) != "waiting_search":
        return
    
    query = update.message.text.strip()
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    if query.startswith('@'):
        c.execute("SELECT * FROM users WHERE username = ?", (query[1:],))
    else:
        try:
            c.execute("SELECT * FROM users WHERE user_id = ?", (int(query),))
        except:
            await update.message.reply_text("❌ Користувача не знайдено")
            user_states[user_id] = None
            return
    
    user = c.fetchone()
    conn.close()
    
    if user:
        text = f"""👤 **КОРИСТУВАЧ**

🆔 ID: {user[0]}
👤 Ім'я: {user[2]}
📧 Username: @{user[1] if user[1] else 'немає'}
📅 Реєстрація: {user[3]}
💰 Витрачено: {user[4]:.2f} грн
📦 Покупок: {user[5]}"""
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Користувача не знайдено")
    
    user_states[user_id] = None

# ============= ОБРОБНИК КНОПОК =============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "reviews":
        await show_reviews(update, context)
    elif data == "buy_stars":
        await show_stars_packages(update, context)
    elif data == "buy_premium":
        await show_premium_packages(update, context)
    elif data == "profile":
        await show_profile(update, context)
    elif data == "support":
        await show_support(update, context)
    elif data == "back_to_main":
        await back_to_main(update, context)
    elif data == "custom_stars":
        await request_custom_stars(update, context)
    elif data == "copy_card":
        await query.answer(f"Картка: {MONOBANK_CARD_NO_SPACES}", show_alert=True)
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "admin_orders":
        await admin_orders(update, context)
    elif data == "admin_broadcast":
        await admin_broadcast(update, context)
    elif data == "admin_search":
        await admin_search(update, context)
    elif data == "admin_confirm":
        await admin_confirm(update, context)
    elif data.startswith("confirm_"):
        await confirm_order_handler(update, context)
    elif data.startswith(('stars_', 'premium_')):
        await process_payment(update, context)

# ============= ОБРОБНИК ПОМИЛОК =============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Помилка: {context.error}")

# ============= ЗАПУСК БОТА =============
def main() -> None:
    token = os.environ.get("BOT_TOKEN", "8461125070:AAEhzywv7k9a8U0r7HA4jzhNlX8umRZt0Tc")
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_error_handler(error_handler)
    
    print("🎉 Crypto Stars Bot запущено!")
    print(f"💳 Картка: {MONOBANK_CARD}")
    print(f"👑 Адмін ID: {ADMIN_IDS[0]}")
    print("💎 Готовий приймати замовлення")
    
    application.run_polling()

if __name__ == '__main__':
    main()
