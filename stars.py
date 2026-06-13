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

# ID адміністратора
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

# База даних
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

# АДМІН ПАНЕЛЬ
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
            await context.bot.send_message(order[0], f"✅ **ЗАМОВЛЕННЯ ПІДТВЕРДЖЕНО!**\n\n🎯 {order[1]}\n💰 {order[2]:.2f} грн", parse_mode='Markdown')
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
    await query.edit_message_text("📢 **РОЗСИЛКА**\n\nНадішліть текст повідомлення:", parse_mode='Markdown')

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[query.from_user.id] = "waiting_search"
    await query.edit_message_text("👤 **ПОШУК**\n\nВведіть ID або @username:", parse_mode='Markdown')

# ОСНОВНІ ФУНКЦІЇ БОТА
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name)
    
    text = f"""✨ ЛАСКАВО ПРОСИМО В CRYPTO STARS STORE! ✨

🆔 Ваш ID: {user.id}

👇 ОБЕРІТЬ ТОВАР:"""
    
    keyboard = [
        [InlineKeyboardButton("⭐ КУПИТИ STARS", callback_data="buy_stars")],
        [InlineKeyboardButton("👑 КУПИТИ PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("💬 ВІДГУКИ", callback_data="reviews")],
        [InlineKeyboardButton("👤 ПРОФІЛЬ", callback_data="profile")],
        [InlineKeyboardButton("🛟 ПІДТРИМКА", callback_data="support")]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🔐 АДМІН ПАНЕЛЬ", callback_data="admin_panel")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_stars_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = f"⭐ **КУПИТИ STARS**\n\n💰 1 зірка = {STAR_PRICE} грн\n\n100⭐ = {100*STAR_PRICE} грн\n500⭐ = {500*STAR_PRICE} грн\n1000⭐ = {1000*STAR_PRICE} грн\n5000⭐ = {5000*STAR_PRICE} грн"
    keyboard = [
        [InlineKeyboardButton("100⭐", callback_data="stars_100"), InlineKeyboardButton("500⭐", callback_data="stars_500")],
        [InlineKeyboardButton("1000⭐", callback_data="stars_1000"), InlineKeyboardButton("5000⭐", callback_data="stars_5000")],
        [InlineKeyboardButton("🔢 СВОЯ КІЛЬКІСТЬ", callback_data="custom_stars")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_premium_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "👑 **КУПИТИ PREMIUM**\n\n3 місяці - 600 грн\n6 місяців - 800 грн\n12 місяців - 1400 грн"
    keyboard = [
        [InlineKeyboardButton("3 МІС - 600₴", callback_data="premium_3")],
        [InlineKeyboardButton("6 МІС - 800₴", callback_data="premium_6")],
        [InlineKeyboardButton("12 МІС - 1400₴", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def request_custom_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_states[query.from_user.id] = "waiting_stars_quantity"
    await query.edit_message_text(f"🔢 Введіть кількість зірок (100-10000):\n\n💰 1 зірка = {STAR_PRICE} грн")

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    if data == "copy_card":
        await query.answer(f"Номер картки: {MONOBANK_CARD_NO_SPACES}", show_alert=True)
        return
    
    if data.startswith('stars_'):
        qty = int(data.split('_')[1])
        price = qty * STAR_PRICE
        name = f"{qty} Telegram Stars"
    elif data.startswith('premium_'):
        months = {"3": "3 місяці", "6": "6 місяців", "12": "12 місяців"}
        price = {"3": 600, "6": 800, "12": 1400}[data.split('_')[1]]
        name = f"Telegram Premium ({months[data.split('_')[1]]})"
    else:
        return
    
    unique_amount, _ = generate_unique_amount(price)
    save_order(user.id, name, price, unique_amount)
    
    text = f"💳 **ДО ОПЛАТИ:** {unique_amount} грн\n\n🏦 Картка: `{MONOBANK_CARD}`\n\n⚠️ Перекажіть ТОЧНО цю суму!\n\n💬 Після оплати: @w1zzxrd"
    keyboard = [[InlineKeyboardButton("✅ Я ОПЛАТИВ", url="https://t.me/w1zzxrd")], [InlineKeyboardButton("🛒 В МАГАЗИН", callback_data="back_to_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_stars_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_states.get(user_id) != "waiting_stars_quantity":
        return
    try:
        qty = int(update.message.text)
        if qty < 100 or qty > 10000:
            await update.message.reply_text("❌ Від 100 до 10000!")
            return
        price = qty * STAR_PRICE
        unique, _ = generate_unique_amount(price)
        save_order(user_id, f"{qty} Telegram Stars", price, unique)
        text = f"💳 **ДО ОПЛАТИ:** {unique} грн\n\n🏦 Картка: `{MONOBANK_CARD}`\n\n⚠️ Перекажіть ТОЧНО цю суму!"
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Я ОПЛАТИВ", url="https://t.me/w1zzxrd")]]), parse_mode='Markdown')
        user_states[user_id] = None
    except:
        await update.message.reply_text("❌ Введіть число!")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute("SELECT total_spent, orders_count FROM users WHERE user_id = ?", (user.id,))
    data = c.fetchone()
    conn.close()
    spent = data[0] if data else 0
    count = data[1] if data else 0
    text = f"👤 **ПРОФІЛЬ**\n\n🆔 ID: {user.id}\n👤 Ім'я: {user.first_name}\n💰 Витрачено: {spent:.2f} грн\n📦 Покупок: {count}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]]), parse_mode='Markdown')

async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"💬 **ВІДГУКИ**\n\n{REVIEWS_CHANNEL}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 ПЕРЕЙТИ", url=REVIEWS_CHANNEL), InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]]))

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🛟 **ПІДТРИМКА**\n\n👤 @w1zzxrd\n\n24/7", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👤 НАПИСАТИ", url="https://t.me/w1zzxrd"), InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_main")]]))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    text = f"✨ ЛАСКАВО ПРОСИМО! ✨\n\n🆔 Ваш ID: {user.id}"
    keyboard = [
        [InlineKeyboardButton("⭐ STARS", callback_data="buy_stars")],
        [InlineKeyboardButton("👑 PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("💬 ВІДГУКИ", callback_data="reviews")],
        [InlineKeyboardButton("👤 ПРОФІЛЬ", callback_data="profile")],
        [InlineKeyboardButton("🛟 ПІДТРИМКА", callback_data="support")]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🔐 АДМІН", callback_data="admin_panel")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ОБРОБНИК ТЕКСТУ
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
    status = await update.message.reply_text("📢 Починаю розсилку...")
    for u in users:
        try:
            await context.bot.send_message(u[0], msg)
            success += 1
        except:
            pass
    await status.edit_text(f"✅ Розсилку завершено!\nВідправлено: {success}")
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
            await update.message.reply_text("❌ Не знайдено")
            user_states[user_id] = None
            return
    user = c.fetchone()
    if user:
        await update.message.reply_text(f"👤 **КОРИСТУВАЧ**\n\n🆔 ID: {user[0]}\n👤 Ім'я: {user[2]}\n💰 Витрачено: {user[4]:.2f} грн", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Не знайдено")
    user_states[user_id] = None

# ОБРОБНИК КНОПОК
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "buy_stars":
        await show_stars_packages(update, context)
    elif data == "buy_premium":
        await show_premium_packages(update, context)
    elif data == "reviews":
        await show_reviews(update, context)
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Помилка: {context.error}")

# ЗАПУСК
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
