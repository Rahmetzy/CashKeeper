#!/usr/bin/env python3
"""
CashKeeper - Bot Telegram Pencatat Pengeluaran Harian
Dibuat oleh: Lord Putra a.k.a Rahmet @r4hmtdwi_
"""

import os
import sqlite3
from datetime import datetime, timedelta
import schedule
import threading
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============= CONFIGURATION =============
DB_FILE = 'cashkeeper.db'
OWNER_USERNAME = "lordputra"
OWNER_PASSWORD = "cashkeeper2026"
OWNER_TELEGRAM_USERNAME = "r4hmtdwi_"

# Conversation states
(AMOUNT, CATEGORY, DESCRIPTION, 
 ONBOARD_NAME, ONBOARD_DAILY, ONBOARD_MONTHLY,
 OWNER_LOGIN_USERNAME, OWNER_LOGIN_PASSWORD) = range(8)

# Default categories dengan emoji
DEFAULT_CATEGORIES = {
    'Makanan': '🍔', 'Transport': '🚗', 'Belanja': '🛒',
    'Tagihan': '💳', 'Kesehatan': '🏥', 'Hiburan': '🎮',
    'Pendidikan': '📚', 'Lainnya': '📦'
}

# Themes
THEMES = {
    'default': {'name': '🏠 Classic', 'emoji': '🏠', 'color': '💙'},
    'pink_cute': {'name': '💖 Pink Cute', 'emoji': '💖', 'color': '💕'},
    'dark_mode': {'name': '🌙 Dark Mode', 'emoji': '🌙', 'color': '🖤'},
    'neon_vibes': {'name': '✨ Neon Vibes', 'emoji': '✨', 'color': '💜'},
    'nature': {'name': '🌿 Nature', 'emoji': '🌿', 'color': '💚'}
}

# ============= DATABASE SETUP =============
def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            display_name TEXT,
            daily_limit REAL DEFAULT 0,
            monthly_limit REAL DEFAULT 0,
            current_theme TEXT DEFAULT 'default',
            notification_enabled INTEGER DEFAULT 1,
            is_owner INTEGER DEFAULT 0,
            onboarding_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active DATE
        )
    ''')
    
    # Expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '💰'
        )
    ''')
    
    # Achievements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            badge_emoji TEXT,
            requirement_type TEXT,
            requirement_value INTEGER,
            difficulty TEXT DEFAULT 'easy'
        )
    ''')
    
    # User achievements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            achievement_code TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert achievements
    achievements = [
        ('first_expense', 'Langkah Pertama', 'Catat pengeluaran pertama', '🌟', 'expense_count', 1, 'easy'),
        ('five_expenses', 'Pemula Rajin', 'Catat 5 pengeluaran', '⭐', 'expense_count', 5, 'easy'),
        ('ten_expenses', 'Pencatat Handal', 'Catat 10 pengeluaran', '⭐⭐', 'expense_count', 10, 'medium'),
        ('thirty_expenses', 'Dedikasi Luar Biasa', 'Catat 30 pengeluaran', '⭐⭐⭐', 'expense_count', 30, 'medium'),
        ('hundred_expenses', 'Legenda Pencatat', 'Catat 100 pengeluaran', '👑', 'expense_count', 100, 'hard'),
        ('first_week', 'Survivor Minggu', 'Aktif 7 hari', '📅', 'days_active', 7, 'easy'),
        ('thirty_days', 'Konsisten Sebulan', 'Aktif 30 hari', '📆', 'days_active', 30, 'medium'),
        ('ninety_days', 'Komitmen 3 Bulan', 'Aktif 90 hari', '🏆', 'days_active', 90, 'hard'),
        ('under_budget_day', 'Hemat Hari Ini', 'Pengeluaran di bawah budget harian', '💚', 'under_daily', 1, 'easy'),
        ('under_budget_week', 'Master Hemat', 'Budget aman 7 hari berturut', '💎', 'streak_daily', 7, 'medium'),
        ('under_budget_month', 'Budget Master', 'Budget bulanan aman', '💰', 'under_monthly', 1, 'hard'),
        ('zero_day', 'Hari Tanpa Belanja', 'Tidak belanja sehari penuh', '🎖️', 'zero_day', 1, 'medium'),
        ('early_bird', 'Early Bird', 'Input sebelum jam 8 pagi', '🌅', 'early_expense', 1, 'medium'),
        ('all_categories', 'Eksplorer Lengkap', 'Gunakan semua kategori', '🎯', 'all_categories', 8, 'medium'),
        ('perfect_month', 'Bulan Sempurna', 'Catat setiap hari selama 30 hari', '💫', 'perfect_month', 30, 'ultra_hard'),
        ('frugal_legend', 'Legenda Hemat', 'Budget aman 30 hari berturut', '🏅', 'streak_daily', 30, 'ultra_hard'),
    ]
    
    for ach in achievements:
        cursor.execute('''
            INSERT OR IGNORE INTO achievements 
            (code, name, description, badge_emoji, requirement_type, requirement_value, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ach)
    
    conn.commit()
    conn.close()

# ============= HELPER FUNCTIONS =============
def get_theme_header(theme_code):
    """Generate header based on theme"""
    theme = THEMES.get(theme_code, THEMES['default'])
    
    if theme_code == 'pink_cute':
        return "✨💖✨ CashKeeper ✨💖✨"
    elif theme_code == 'dark_mode':
        return "🌙 CashKeeper 🌙"
    elif theme_code == 'neon_vibes':
        return "✨🎆 CashKeeper 🎆✨"
    elif theme_code == 'nature':
        return "🌿🍃 CashKeeper 🍃🌿"
    else:
        return "💰 CashKeeper 💰"

def format_currency(amount):
    """Format number as currency"""
    return f"Rp {amount:,.0f}".replace(',', '.')

def check_achievements(user_id):
    """Check and unlock achievements"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get expense count
    cursor.execute('SELECT COUNT(*) FROM expenses WHERE user_id = ?', (user_id,))
    expense_count = cursor.fetchone()[0]
    
    # Get days active
    cursor.execute('''
        SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id = ?
    ''', (user_id,))
    days_active = cursor.fetchone()[0]
    
    # Get categories used
    cursor.execute('''
        SELECT COUNT(DISTINCT category) FROM expenses WHERE user_id = ?
    ''', (user_id,))
    categories_used = cursor.fetchone()[0]
    
    # Get user limits
    cursor.execute('SELECT daily_limit, monthly_limit FROM users WHERE user_id = ?', (user_id,))
    daily_limit, monthly_limit = cursor.fetchone()
    
    # Check today's expense
    today = datetime.now().date()
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) FROM expenses 
        WHERE user_id = ? AND date = ?
    ''', (user_id, today))
    today_total = cursor.fetchone()[0]
    
    # Get unlocked achievements
    cursor.execute('''
        SELECT achievement_code FROM user_achievements WHERE user_id = ?
    ''', (user_id,))
    unlocked = {row[0] for row in cursor.fetchall()}
    
    # Get all achievements
    cursor.execute('SELECT code, requirement_type, requirement_value FROM achievements')
    all_achievements = cursor.fetchall()
    
    newly_unlocked = []
    
    for code, req_type, req_value in all_achievements:
        if code in unlocked:
            continue
            
        should_unlock = False
        
        if req_type == 'expense_count' and expense_count >= req_value:
            should_unlock = True
        elif req_type == 'days_active' and days_active >= req_value:
            should_unlock = True
        elif req_type == 'all_categories' and categories_used >= req_value:
            should_unlock = True
        elif req_type == 'under_daily' and daily_limit > 0 and today_total < daily_limit:
            should_unlock = True
        elif req_type == 'zero_day' and today_total == 0 and expense_count > 0:
            # Check if there's a day with zero expenses
            cursor.execute('''
                SELECT date FROM (
                    SELECT date FROM expenses WHERE user_id = ?
                    UNION
                    SELECT date('now', '-1 day')
                ) 
                WHERE date NOT IN (SELECT date FROM expenses WHERE user_id = ?)
                LIMIT 1
            ''', (user_id, user_id))
            if cursor.fetchone():
                should_unlock = True
        
        if should_unlock:
            cursor.execute('''
                INSERT INTO user_achievements (user_id, achievement_code)
                VALUES (?, ?)
            ''', (user_id, code))
            newly_unlocked.append(code)
    
    conn.commit()
    conn.close()
    
    return newly_unlocked

def get_motivational_message(user_id, today_total, daily_limit):
    """Get motivational message based on spending"""
    if daily_limit == 0:
        return ""
    
    percentage = (today_total / daily_limit) * 100
    
    messages = {
        (0, 30): [
            "🌟 Luar biasa! Kamu super hemat hari ini!",
            "💚 Amazing! Budget masih aman banget!",
            "✨ Keren! Pengeluaran masih sangat rendah!",
        ],
        (30, 50): [
            "👍 Bagus! Kamu masih di jalur yang benar!",
            "💙 Good job! Budget masih terkendali!",
            "😊 Nice! Tetap pertahankan!",
        ],
        (50, 75): [
            "⚠️ Hati-hati, sudah lebih dari setengah budget!",
            "💛 Awas, jangan sampai over budget ya!",
            "🤔 Hmm, coba hemat sedikit lagi!",
        ],
        (75, 90): [
            "🚨 Warning! Budget hampir habis!",
            "⚡ Bahaya! Sudah 75% terpakai!",
            "💸 Waspada! Jangan kebablasan!",
        ],
        (90, 100): [
            "🔴 ALERT! Budget hampir mepet!",
            "⛔ STOP! Sudah 90% lebih!",
            "🆘 BAHAYA! Jaga pengeluaran!",
        ],
        (100, 999): [
            "💥 OVER BUDGET! Kamu sudah melebihi target!",
            "❌ OVERLIMIT! Besok harus lebih hemat!",
            "😱 MELEDAK! Budget sudah terlewati!",
        ]
    }
    
    for (min_pct, max_pct), msgs in messages.items():
        if min_pct <= percentage < max_pct:
            import random
            return "\n\n" + random.choice(msgs)
    
    return ""

# ============= BOT CLASS =============
class CashKeeperBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        init_database()
        self.setup_handlers()
        
    def setup_handlers(self):
        """Setup all handlers"""
        
        # Onboarding conversation
        onboard_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                ONBOARD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboard_get_name)],
                ONBOARD_DAILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboard_get_daily)],
                ONBOARD_MONTHLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.onboard_get_monthly)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        # Add expense conversation
        add_expense_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_add_expense, pattern='^add_expense$')],
            states={
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_amount)],
                CATEGORY: [CallbackQueryHandler(self.get_category, pattern='^cat_')],
                DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_description)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        # Owner login conversation
        owner_login_handler = ConversationHandler(
            entry_points=[CommandHandler('owner', self.owner_login_start)],
            states={
                OWNER_LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.owner_check_username)],
                OWNER_LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.owner_check_password)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        self.application.add_handler(onboard_handler)
        self.application.add_handler(add_expense_handler)
        self.application.add_handler(owner_login_handler)
        
        # Command handlers
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('menu', self.show_menu))
        self.application.add_handler(CommandHandler('cancel', self.cancel))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.show_today, pattern='^today$'))
        self.application.add_handler(CallbackQueryHandler(self.show_month, pattern='^month$'))
        self.application.add_handler(CallbackQueryHandler(self.show_stats, pattern='^stats$'))
        self.application.add_handler(CallbackQueryHandler(self.show_achievements, pattern='^achievements$'))
        self.application.add_handler(CallbackQueryHandler(self.settings, pattern='^settings$'))
        self.application.add_handler(CallbackQueryHandler(self.change_theme, pattern='^themes$'))
        self.application.add_handler(CallbackQueryHandler(self.apply_theme, pattern='^theme_'))
        self.application.add_handler(CallbackQueryHandler(self.toggle_notification, pattern='^toggle_notif$'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_menu, pattern='^back$'))
        
        # Owner panel callbacks
        self.application.add_handler(CallbackQueryHandler(self.owner_panel, pattern='^owner_panel$'))
        self.application.add_handler(CallbackQueryHandler(self.owner_users, pattern='^owner_users$'))
        self.application.add_handler(CallbackQueryHandler(self.owner_stats, pattern='^owner_stats$'))
        self.application.add_handler(CallbackQueryHandler(self.owner_view_user, pattern='^owner_view_'))
    
    def get_main_keyboard(self, user_id=None):
        """Main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Tambah Pengeluaran", callback_data='add_expense'),
                InlineKeyboardButton("📊 Hari Ini", callback_data='today')
            ],
            [
                InlineKeyboardButton("📅 Bulan Ini", callback_data='month'),
                InlineKeyboardButton("📈 Statistik", callback_data='stats')
            ],
            [
                InlineKeyboardButton("🏆 Achievement", callback_data='achievements'),
                InlineKeyboardButton("⚙️ Pengaturan", callback_data='settings')
            ]
        ]
        
        # Add owner panel for owner
        if user_id:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT is_owner FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] == 1:
                keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data='owner_panel')])
        
        return InlineKeyboardMarkup(keyboard)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - Check onboarding"""
        user = update.effective_user
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT onboarding_completed FROM users WHERE user_id = ?', (user.id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == 1:
            # Already onboarded, show menu
            await self.show_menu(update, context)
            return ConversationHandler.END
        
        # Start onboarding
        welcome = (
            f"👋 Halo <b>{user.first_name}</b>!\n\n"
            f"Selamat datang di <b>CashKeeper</b> 💰\n\n"
            f"Bot pencatat pengeluaran harian yang:\n"
            f"✨ Mudah & Interaktif\n"
            f"🎨 Tema Keren untuk Gen Z\n"
            f"🏆 Achievement Seru\n"
            f"📊 Laporan Detail\n\n"
            f"<b>Dibuat oleh:</b>\n"
            f"Lord Putra a.k.a Rahmet\n"
            f"@{OWNER_TELEGRAM_USERNAME}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Pertama, siapa nama kamu?</b>\n"
            f"(Nama ini yang akan muncul di bot)\n\n"
            f"Ketik /cancel untuk membatalkan"
        )
        
        await update.message.reply_text(welcome, parse_mode='HTML')
        return ONBOARD_NAME
    
    async def onboard_get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user's display name"""
        display_name = update.message.text.strip()
        context.user_data['display_name'] = display_name
        
        await update.message.reply_text(
            f"Nice to meet you, <b>{display_name}</b>! 😊\n\n"
            f"Sekarang, atur budget harian kamu!\n\n"
            f"<b>Berapa maksimal pengeluaran per hari?</b>\n"
            f"(Contoh: 100000 untuk Rp 100.000)\n\n"
            f"Ketik 0 jika tidak ingin set limit\n"
            f"Ketik /cancel untuk membatalkan",
            parse_mode='HTML'
        )
        return ONBOARD_DAILY
    
    async def onboard_get_daily(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get daily limit"""
        try:
            daily_limit = float(update.message.text.replace(',', '').replace('.', ''))
            if daily_limit < 0:
                raise ValueError
            
            context.user_data['daily_limit'] = daily_limit
            
            limit_text = format_currency(daily_limit) if daily_limit > 0 else "Tanpa limit"
            
            await update.message.reply_text(
                f"✅ Budget harian: <b>{limit_text}</b>\n\n"
                f"Terakhir, atur budget bulanan!\n\n"
                f"<b>Berapa maksimal pengeluaran per bulan?</b>\n"
                f"(Contoh: 3000000 untuk Rp 3.000.000)\n\n"
                f"Ketik 0 jika tidak ingin set limit\n"
                f"Ketik /cancel untuk membatalkan",
                parse_mode='HTML'
            )
            return ONBOARD_MONTHLY
            
        except ValueError:
            await update.message.reply_text(
                "❌ Nominal tidak valid!\n"
                "Masukkan angka saja (contoh: 100000)"
            )
            return ONBOARD_DAILY
    
    async def onboard_get_monthly(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete onboarding"""
        try:
            monthly_limit = float(update.message.text.replace(',', '').replace('.', ''))
            if monthly_limit < 0:
                raise ValueError
            
            user = update.effective_user
            display_name = context.user_data['display_name']
            daily_limit = context.user_data['daily_limit']
            
            # Save to database
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, display_name, daily_limit, monthly_limit, onboarding_completed)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (user.id, user.username, user.first_name, display_name, daily_limit, monthly_limit))
            
            # Add default categories
            for cat_name, emoji in DEFAULT_CATEGORIES.items():
                cursor.execute('''
                    INSERT OR IGNORE INTO categories (user_id, name, emoji)
                    VALUES (?, ?, ?)
                ''', (user.id, cat_name, emoji))
            
            conn.commit()
            conn.close()
            
            daily_text = format_currency(daily_limit) if daily_limit > 0 else "Tanpa limit"
            monthly_text = format_currency(monthly_limit) if monthly_limit > 0 else "Tanpa limit"
            
            complete_msg = (
                f"🎉 <b>Setup Selesai!</b>\n\n"
                f"👤 Nama: <b>{display_name}</b>\n"
                f"📅 Budget Harian: <b>{daily_text}</b>\n"
                f"📆 Budget Bulanan: <b>{monthly_text}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ <b>Selamat memulai perjalanan finansial kamu!</b>\n\n"
                f"Tips:\n"
                f"💡 Catat pengeluaran langsung setelah transaksi\n"
                f"🏆 Kumpulkan achievement untuk motivasi\n"
                f"🎨 Ganti tema sesuai mood kamu\n\n"
                f"Gunakan menu di bawah untuk mulai!"
            )
            
            await update.message.reply_text(
                complete_msg,
                parse_mode='HTML',
                reply_markup=self.get_main_keyboard(user.id)
            )
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "❌ Nominal tidak valid!\n"
                "Masukkan angka saja (contoh: 3000000)"
            )
            return ONBOARD_MONTHLY
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu"""
        # Handle both message and callback query
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            user = query.from_user
            send_func = query.edit_message_text
        else:
            user = update.effective_user
            send_func = update.message.reply_text
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT display_name, current_theme FROM users WHERE user_id = ?
        ''', (user.id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await self.start(update, context)
            return
        
        display_name, theme = result
        header = get_theme_header(theme)
        
        menu_text = (
            f"{header}\n\n"
            f"Halo, <b>{display_name}</b>! 👋\n\n"
            f"Apa yang ingin kamu lakukan hari ini?"
        )
        
        await send_func(
            menu_text,
            parse_mode='HTML',
            reply_markup=self.get_main_keyboard(user.id)
        )
    
    async def start_add_expense(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start add expense flow"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "💰 <b>Tambah Pengeluaran Baru</b>\n\n"
            "Masukkan nominal pengeluaran:\n"
            "(hanya angka, contoh: 50000)\n\n"
            "Ketik /cancel untuk batal",
            parse_mode='HTML'
        )
        return AMOUNT
    
    async def get_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get expense amount"""
        try:
            amount = float(update.message.text.replace(',', '').replace('.', ''))
            if amount <= 0:
                raise ValueError
            
            context.user_data['amount'] = amount
            
            # Get categories
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, emoji FROM categories 
                WHERE user_id = ? ORDER BY name
            ''', (update.effective_user.id,))
            categories = cursor.fetchall()
            conn.close()
            
            # Build keyboard
            keyboard = []
            row = []
            for cat_name, emoji in categories:
                row.append(InlineKeyboardButton(
                    f"{emoji} {cat_name}",
                    callback_data=f'cat_{cat_name}'
                ))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            await update.message.reply_text(
                f"✅ Nominal: <b>{format_currency(amount)}</b>\n\n"
                "Pilih kategori:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CATEGORY
            
        except ValueError:
            await update.message.reply_text(
                "❌ Nominal tidak valid!\n"
                "Contoh yang benar: 50000"
            )
            return AMOUNT
    
    async def get_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get expense category"""
        query = update.callback_query
        await query.answer()
        
        category = query.data.replace('cat_', '')
        context.user_data['category'] = category
        amount = context.user_data['amount']
        
        # Get emoji
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT emoji FROM categories 
            WHERE user_id = ? AND name = ?
        ''', (update.effective_user.id, category))
        result = cursor.fetchone()
        emoji = result[0] if result else '💰'
        conn.close()
        
        await query.edit_message_text(
            f"✅ Nominal: <b>{format_currency(amount)}</b>\n"
            f"✅ Kategori: {emoji} <b>{category}</b>\n\n"
            "Tambahkan deskripsi?\n"
            "(atau ketik <code>-</code> untuk skip)\n\n"
            "Ketik /cancel untuk batal",
            parse_mode='HTML'
        )
        return DESCRIPTION
    
    async def get_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete expense entry"""
        description = update.message.text if update.message.text != '-' else ''
        
        user_id = update.effective_user.id
        amount = context.user_data['amount']
        category = context.user_data['category']
        today = datetime.now().date()
        
        # Save expense
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO expenses (user_id, amount, category, description, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, category, description, today))
        
        # Update last active
        cursor.execute('''
            UPDATE users SET last_active = ? WHERE user_id = ?
        ''', (today, user_id))
        
        # Get totals
        cursor.execute('''
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        total_today = cursor.fetchone()[0] or 0
        
        # Get limits
        cursor.execute('''
            SELECT daily_limit, monthly_limit, current_theme 
            FROM users WHERE user_id = ?
        ''', (user_id,))
        daily_limit, monthly_limit, theme = cursor.fetchone()
        
        # Get emoji
        cursor.execute('''
            SELECT emoji FROM categories 
            WHERE user_id = ? AND name = ?
        ''', (user_id, category))
        result = cursor.fetchone()
        emoji = result[0] if result else '💰'
        
        conn.commit()
        conn.close()
        
        # Check achievements
        new_achievements = check_achievements(user_id)
        
        # Get motivational message
        motivation = get_motivational_message(user_id, total_today, daily_limit)
        
        success_text = f"✅ <b>Pengeluaran Berhasil Ditambahkan!</b>\n\n"
        success_text += f"💰 Nominal: <b>{format_currency(amount)}</b>\n"
        success_text += f"{emoji} Kategori: <b>{category}</b>\n"
        if description:
            success_text += f"📝 Deskripsi: {description}\n"
        success_text += f"📅 Tanggal: {today.strftime('%d %B %Y')}\n\n"
        success_text += f"━━━━━━━━━━━━━━━━━━━━\n"
        success_text += f"📊 <b>Total Hari Ini: {format_currency(total_today)}</b>"
        
        if daily_limit > 0:
            percentage = (total_today / daily_limit) * 100
            success_text += f"\n💳 Budget: {percentage:.1f}% dari {format_currency(daily_limit)}"
        
        success_text += motivation
        
        if new_achievements:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, badge_emoji FROM achievements 
                WHERE code IN ({})
            '''.format(','.join('?' * len(new_achievements))), new_achievements)
            badges = cursor.fetchall()
            conn.close()
            
            success_text += "\n\n🎉 <b>Achievement Unlocked!</b>\n"
            for name, badge in badges:
                success_text += f"{badge} {name}\n"
        
        await update.message.reply_text(
            success_text,
            parse_mode='HTML',
            reply_markup=self.get_main_keyboard(user_id)
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def show_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show today's expenses"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        today = datetime.now().date()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.amount, e.category, e.description, c.emoji, e.date
            FROM expenses e
            LEFT JOIN categories c ON e.category = c.name AND e.user_id = c.user_id
            WHERE e.user_id = ? AND e.date = ?
            ORDER BY e.created_at DESC
        ''', (user_id, today))
        
        expenses = cursor.fetchall()
        total = sum(exp[0] for exp in expenses)
        
        # Get limits
        cursor.execute('SELECT daily_limit, current_theme FROM users WHERE user_id = ?', (user_id,))
        daily_limit, theme = cursor.fetchone()
        
        conn.close()
        
        header = get_theme_header(theme)
        
        if not expenses:
            text = f"{header}\n\n📊 <b>Pengeluaran Hari Ini</b>\n"
            text += f"📅 {today.strftime('%d %B %Y')}\n\n"
            text += "Belum ada pengeluaran hari ini.\n"
            text += "Yuk mulai catat! 💪"
        else:
            text = f"{header}\n\n📊 <b>Pengeluaran Hari Ini</b>\n"
            text += f"📅 {today.strftime('%d %B %Y')}\n\n"
            
            for amount, category, desc, emoji, date in expenses:
                emoji = emoji or '💰'
                text += f"{emoji} <b>{format_currency(amount)}</b> - {category}\n"
                if desc:
                    text += f"   <i>{desc}</i>\n"
                text += "\n"
            
            text += f"━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💰 <b>Total: {format_currency(total)}</b>\n"
            
            if daily_limit > 0:
                percentage = (total / daily_limit) * 100
                text += f"💳 Budget: {percentage:.1f}% dari {format_currency(daily_limit)}"
                
                if total < daily_limit:
                    text += "\n✅ Masih aman!"
                else:
                    text += "\n⚠️ Over budget!"
        
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='back')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show monthly expenses"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        now = datetime.now()
        first_day = now.replace(day=1).date()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Total this month
        cursor.execute('''
            SELECT SUM(amount), COUNT(*) FROM expenses 
            WHERE user_id = ? AND date >= ?
        ''', (user_id, first_day))
        total, count = cursor.fetchone()
        total = total or 0
        count = count or 0
        
        # By category
        cursor.execute('''
            SELECT e.category, SUM(e.amount), c.emoji
            FROM expenses e
            LEFT JOIN categories c ON e.category = c.name AND e.user_id = c.user_id
            WHERE e.user_id = ? AND e.date >= ?
            GROUP BY e.category
            ORDER BY SUM(e.amount) DESC
        ''', (user_id, first_day))
        
        categories = cursor.fetchall()
        
        # Get limits
        cursor.execute('SELECT monthly_limit, current_theme FROM users WHERE user_id = ?', (user_id,))
        monthly_limit, theme = cursor.fetchone()
        
        conn.close()
        
        header = get_theme_header(theme)
        month_name = now.strftime('%B %Y')
        
        if not categories:
            text = f"{header}\n\n📅 <b>Bulan {month_name}</b>\n\n"
            text += "Belum ada pengeluaran bulan ini."
        else:
            text = f"{header}\n\n📅 <b>Bulan {month_name}</b>\n\n"
            text += "<b>Breakdown Kategori:</b>\n\n"
            
            for category, amount, emoji in categories:
                emoji = emoji or '💰'
                percentage = (amount / total * 100) if total > 0 else 0
                bar_length = int(percentage / 10)
                bar = '█' * bar_length + '░' * (10 - bar_length)
                text += f"{emoji} <b>{category}</b>\n"
                text += f"   {format_currency(amount)} ({percentage:.1f}%)\n"
                text += f"   {bar}\n\n"
            
            text += f"━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💰 <b>Total: {format_currency(total)}</b>\n"
            text += f"📝 Transaksi: {count}x\n"
            
            if count > 0:
                avg = total / count
                text += f"📊 Rata-rata: {format_currency(avg)}/transaksi"
            
            if monthly_limit > 0:
                percentage = (total / monthly_limit) * 100
                text += f"\n\n💳 Budget: {percentage:.1f}% dari {format_currency(monthly_limit)}"
                if total < monthly_limit:
                    text += "\n✅ Budget bulan ini aman!"
                else:
                    text += "\n⚠️ Over budget bulanan!"
        
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='back')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show statistics"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        now = datetime.now()
        today = now.date()
        first_day_month = now.replace(day=1).date()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Total all time
        cursor.execute('SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id = ?', (user_id,))
        total_all, count_all = cursor.fetchone()
        total_all = total_all or 0
        count_all = count_all or 0
        
        # This month
        cursor.execute('''
            SELECT SUM(amount), COUNT(*) FROM expenses 
            WHERE user_id = ? AND date >= ?
        ''', (user_id, first_day_month))
        total_month, count_month = cursor.fetchone()
        total_month = total_month or 0
        count_month = count_month or 0
        
        # Today
        cursor.execute('''
            SELECT SUM(amount), COUNT(*) FROM expenses 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        total_today, count_today = cursor.fetchone()
        total_today = total_today or 0
        count_today = count_today or 0
        
        # Top category
        cursor.execute('''
            SELECT e.category, SUM(e.amount), c.emoji
            FROM expenses e
            LEFT JOIN categories c ON e.category = c.name AND e.user_id = c.user_id
            WHERE e.user_id = ?
            GROUP BY e.category
            ORDER BY SUM(e.amount) DESC
            LIMIT 1
        ''', (user_id,))
        top_category = cursor.fetchone()
        
        # Days active
        cursor.execute('''
            SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id = ?
        ''', (user_id,))
        days_active = cursor.fetchone()[0]
        
        # Theme
        cursor.execute('SELECT current_theme FROM users WHERE user_id = ?', (user_id,))
        theme = cursor.fetchone()[0]
        
        conn.close()
        
        header = get_theme_header(theme)
        
        text = f"{header}\n\n📈 <b>Statistik CashKeeper</b>\n\n"
        text += f"<b>📊 Hari Ini:</b>\n"
        text += f"💰 {format_currency(total_today)} ({count_today} transaksi)\n\n"
        text += f"<b>📅 Bulan Ini:</b>\n"
        text += f"💰 {format_currency(total_month)} ({count_month} transaksi)\n"
        if count_month > 0:
            avg_day = total_month / now.day
            text += f"📊 Rata-rata: {format_currency(avg_day)}/hari\n"
        text += f"\n<b>🎯 Total Keseluruhan:</b>\n"
        text += f"💰 {format_currency(total_all)} ({count_all} transaksi)\n"
        text += f"📅 Aktif {days_active} hari\n"
        
        if top_category:
            cat_name, cat_amount, cat_emoji = top_category
            cat_emoji = cat_emoji or '💰'
            text += f"\n<b>🏆 Kategori Terbesar:</b>\n"
            text += f"{cat_emoji} {cat_name} - {format_currency(cat_amount)}"
        
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='back')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_achievements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show achievements"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get unlocked achievements
        cursor.execute('''
            SELECT a.name, a.badge_emoji, a.description, a.difficulty, ua.unlocked_at
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_code = a.code
            WHERE ua.user_id = ?
            ORDER BY ua.unlocked_at DESC
        ''', (user_id,))
        
        unlocked = cursor.fetchall()
        unlocked_count = len(unlocked)
        
        # Get total achievements
        cursor.execute('SELECT COUNT(*) FROM achievements')
        total_achievements = cursor.fetchone()[0]
        
        # Get theme
        cursor.execute('SELECT current_theme FROM users WHERE user_id = ?', (user_id,))
        theme = cursor.fetchone()[0]
        
        conn.close()
        
        header = get_theme_header(theme)
        percentage = (unlocked_count / total_achievements * 100) if total_achievements > 0 else 0
        
        text = f"{header}\n\n🏆 <b>Achievement & Badge</b>\n\n"
        text += f"📊 Progress: <b>{unlocked_count}/{total_achievements}</b> ({percentage:.1f}%)\n\n"
        
        if unlocked:
            text += "<b>🎉 Badge yang Diraih:</b>\n\n"
            
            for name, badge, desc, difficulty, unlocked_at in unlocked:
                unlock_date = datetime.fromisoformat(unlocked_at).strftime('%d/%m/%Y')
                diff_emoji = {'easy': '⭐', 'medium': '⭐⭐', 'hard': '⭐⭐⭐', 'ultra_hard': '👑'}.get(difficulty, '⭐')
                text += f"{badge} <b>{name}</b> {diff_emoji}\n"
                text += f"   <i>{desc}</i>\n"
                text += f"   📅 Diraih: {unlock_date}\n\n"
        else:
            text += "Belum ada badge yang diraih.\n"
            text += "Yuk mulai kumpulkan achievement! 🚀\n\n"
            text += "Tips:\n"
            text += "💡 Catat pengeluaran pertama → 🌟\n"
            text += "💡 Aktif 7 hari → 📅\n"
            text += "💡 Hemat budget → 💚"
        
        if unlocked_count < total_achievements:
            remaining = total_achievements - unlocked_count
            text += f"\n\n🎯 Masih ada <b>{remaining} badge</b> lagi!\n"
            text += "Terus semangat! 💪"
        else:
            text += "\n\n🎊 <b>SELAMAT!</b> Kamu sudah kumpulkan semua badge! 🏆"
        
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data='back')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT notification_enabled, display_name, daily_limit, monthly_limit, current_theme
            FROM users WHERE user_id = ?
        ''', (user_id,))
        notif, name, daily, monthly, theme = cursor.fetchone()
        conn.close()
        
        header = get_theme_header(theme)
        status = "🔔 Aktif" if notif else "🔕 Nonaktif"
        theme_name = THEMES.get(theme, THEMES['default'])['name']
        
        text = f"{header}\n\n⚙️ <b>Pengaturan</b>\n\n"
        text += f"👤 Nama: <b>{name}</b>\n"
        text += f"📅 Budget Harian: <b>{format_currency(daily) if daily > 0 else 'Tidak ada'}</b>\n"
        text += f"📆 Budget Bulanan: <b>{format_currency(monthly) if monthly > 0 else 'Tidak ada'}</b>\n\n"
        text += f"🎨 Tema: <b>{theme_name}</b>\n"
        text += f"🔔 Notifikasi: <b>{status}</b>\n\n"
        text += "Notifikasi pengingat setiap jam 20:00 WIB"
        
        keyboard = [
            [InlineKeyboardButton("🎨 Ganti Tema", callback_data='themes')],
            [InlineKeyboardButton("🔄 Toggle Notifikasi", callback_data='toggle_notif')],
            [InlineKeyboardButton("🔙 Menu", callback_data='back')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def change_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show theme selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT current_theme FROM users WHERE user_id = ?', (user_id,))
        current_theme = cursor.fetchone()[0]
        conn.close()
        
        text = "🎨 <b>Pilih Tema Favorit Kamu!</b>\n\n"
        
        keyboard = []
        for theme_code, theme_data in THEMES.items():
            is_current = " ✅" if theme_code == current_theme else ""
            button_text = f"{theme_data['emoji']} {theme_data['name']}{is_current}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f'theme_{theme_code}')])
        
        keyboard.append([InlineKeyboardButton("🔙 Pengaturan", callback_data='settings')])
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def apply_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Apply selected theme"""
        query = update.callback_query
        await query.answer()
        
        theme_code = query.data.replace('theme_', '')
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET current_theme = ? WHERE user_id = ?', (theme_code, user_id))
        conn.commit()
        conn.close()
        
        theme_name = THEMES.get(theme_code, THEMES['default'])['name']
        
        await query.answer(f"✨ Tema berhasil diubah ke {theme_name}!", show_alert=True)
        await self.settings(update, context)
    
    async def toggle_notification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle notification"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET notification_enabled = 1 - notification_enabled 
            WHERE user_id = ?
        ''', (user_id,))
        
        cursor.execute('SELECT notification_enabled FROM users WHERE user_id = ?', (user_id,))
        new_status = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        status_text = "diaktifkan 🔔" if new_status else "dinonaktifkan 🔕"
        await query.answer(f"Notifikasi berhasil {status_text}", show_alert=True)
        await self.settings(update, context)
    
    async def back_to_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Back to main menu"""
        await self.show_menu(update, context)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel operation"""
        await update.message.reply_text(
            "❌ Dibatalkan.\n\nKetik /menu untuk kembali.",
            reply_markup=self.get_main_keyboard(update.effective_user.id)
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        help_text = (
            "📖 <b>Panduan CashKeeper</b>\n\n"
            "<b>Fitur Utama:</b>\n"
            "➕ Tambah Pengeluaran - Catat pengeluaran baru\n"
            "📊 Hari Ini - Lihat pengeluaran hari ini\n"
            "📅 Bulan Ini - Laporan bulanan lengkap\n"
            "📈 Statistik - Analisis pengeluaran\n"
            "🏆 Achievement - Kumpulkan badge seru!\n"
            "⚙️ Pengaturan - Atur tema, notifikasi, dll\n\n"
            "<b>Commands:</b>\n"
            "/start - Mulai bot\n"
            "/menu - Tampilkan menu utama\n"
            "/owner - Login sebagai owner\n"
            "/help - Bantuan\n"
            "/cancel - Batalkan operasi\n\n"
            "<b>Tips:</b>\n"
            "💡 Catat langsung setelah transaksi\n"
            "💡 Kumpulkan achievement\n"
            "💡 Ganti tema sesuai mood\n"
            "💡 Cek statistik rutin\n\n"
            "<b>Dibuat oleh:</b>\n"
            "Lord Putra a.k.a Rahmet\n"
            f"@{OWNER_TELEGRAM_USERNAME}"
        )
        
        await update.message.reply_text(
            help_text,
            parse_mode='HTML',
            reply_markup=self.get_main_keyboard(update.effective_user.id)
        )
    
    # ============= OWNER PANEL =============
    async def owner_login_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start owner login"""
        await update.message.reply_text(
            "👑 <b>Owner Login</b>\n\n"
            "Masukkan username owner:\n"
            "(Ketik /cancel untuk batal)",
            parse_mode='HTML'
        )
        return OWNER_LOGIN_USERNAME
    
    async def owner_check_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check owner username"""
        username = update.message.text.strip()
        
        if username == OWNER_USERNAME:
            context.user_data['owner_username'] = username
            await update.message.reply_text(
                "✅ Username benar!\n\n"
                "Masukkan password owner:\n"
                "(Ketik /cancel untuk batal)",
                parse_mode='HTML'
            )
            return OWNER_LOGIN_PASSWORD
        else:
            await update.message.reply_text(
                "❌ Username salah!\n"
                "Akses ditolak."
            )
            context.user_data.clear()
            return ConversationHandler.END
    
    async def owner_check_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check owner password"""
        password = update.message.text.strip()
        
        if password == OWNER_PASSWORD:
            user_id = update.effective_user.id
            
            # Set as owner
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_owner = 1 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                "✅ <b>Login Berhasil!</b>\n\n"
                "Selamat datang, Owner! 👑\n\n"
                "Kamu sekarang memiliki akses owner panel.\n"
                "Gunakan menu untuk mengaksesnya.",
                parse_mode='HTML',
                reply_markup=self.get_main_keyboard(user_id)
            )
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Password salah!\n"
                "Akses ditolak."
            )
            context.user_data.clear()
            return ConversationHandler.END
    
    async def owner_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show owner panel"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Verify owner
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT is_owner FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result or result[0] != 1:
            await query.answer("❌ Akses ditolak! Hanya owner yang bisa mengakses.", show_alert=True)
            return
        
        # Get stats
        cursor.execute('SELECT COUNT(*) FROM users WHERE onboarding_completed = 1')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM expenses')
        total_expenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM expenses')
        total_amount = cursor.fetchone()[0] or 0
        
        conn.close()
        
        text = (
            "👑 <b>OWNER PANEL</b>\n\n"
            f"<b>Statistik Global:</b>\n"
            f"👥 Total User: <b>{total_users}</b>\n"
            f"📝 Total Transaksi: <b>{total_expenses}</b>\n"
            f"💰 Total Pengeluaran: <b>{format_currency(total_amount)}</b>\n\n"
            "Gunakan menu di bawah untuk melihat detail."
        )
        
        keyboard = [
            [InlineKeyboardButton("👥 Daftar User", callback_data='owner_users')],
            [InlineKeyboardButton("📊 Statistik Detail", callback_data='owner_stats')],
            [InlineKeyboardButton("🔙 Menu", callback_data='back')]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def owner_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user list"""
        query = update.callback_query
        await query.answer()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.user_id, u.display_name, u.username, COUNT(e.id), 
                   COALESCE(SUM(e.amount), 0), u.created_at
            FROM users u
            LEFT JOIN expenses e ON u.user_id = e.user_id
            WHERE u.onboarding_completed = 1
            GROUP BY u.user_id
            ORDER BY COUNT(e.id) DESC
            LIMIT 10
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        text = "👑 <b>OWNER PANEL - Daftar User</b>\n\n"
        text += "<b>Top 10 User Teraktif:</b>\n\n"
        
        for idx, (uid, name, username, exp_count, total, created) in enumerate(users, 1):
            username_text = f"@{username}" if username else "No username"
            created_date = datetime.fromisoformat(created).strftime('%d/%m/%Y')
            text += f"{idx}. <b>{name}</b> ({username_text})\n"
            text += f"   📝 {exp_count} transaksi | 💰 {format_currency(total)}\n"
            text += f"   📅 Bergabung: {created_date}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Owner Panel", callback_data='owner_panel')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def owner_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics"""
        query = update.callback_query
        await query.answer()
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Daily stats
        today = datetime.now().date()
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id), COUNT(*), COALESCE(SUM(amount), 0)
            FROM expenses WHERE date = ?
        ''', (today,))
        daily_users, daily_exp, daily_amount = cursor.fetchone()
        
        # Monthly stats
        first_day = today.replace(day=1)
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id), COUNT(*), COALESCE(SUM(amount), 0)
            FROM expenses WHERE date >= ?
        ''', (first_day,))
        monthly_users, monthly_exp, monthly_amount = cursor.fetchone()
        
        # Top category
        cursor.execute('''
            SELECT category, COUNT(*), SUM(amount)
            FROM expenses
            GROUP BY category
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''')
        top_cat = cursor.fetchone()
        
        # Achievement stats
        cursor.execute('SELECT COUNT(*) FROM user_achievements')
        total_badges = cursor.fetchone()[0]
        
        conn.close()
        
        text = "👑 <b>OWNER PANEL - Statistik Detail</b>\n\n"
        text += f"<b>📊 Hari Ini:</b>\n"
        text += f"👥 {daily_users} user aktif\n"
        text += f"📝 {daily_exp} transaksi\n"
        text += f"💰 {format_currency(daily_amount)}\n\n"
        
        text += f"<b>📅 Bulan Ini:</b>\n"
        text += f"👥 {monthly_users} user aktif\n"
        text += f"📝 {monthly_exp} transaksi\n"
        text += f"💰 {format_currency(monthly_amount)}\n\n"
        
        if top_cat:
            text += f"<b>🏆 Kategori Terpopuler:</b>\n"
            text += f"{top_cat[0]} - {top_cat[1]} transaksi ({format_currency(top_cat[2])})\n\n"
        
        text += f"<b>🎖️ Total Badge Diraih:</b>\n"
        text += f"{total_badges} badge unlocked"
        
        keyboard = [[InlineKeyboardButton("🔙 Owner Panel", callback_data='owner_panel')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def owner_view_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View specific user details"""
        query = update.callback_query
        await query.answer()
        
        target_user_id = int(query.data.replace('owner_view_', ''))
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # User info
        cursor.execute('''
            SELECT display_name, username, daily_limit, monthly_limit, created_at
            FROM users WHERE user_id = ?
        ''', (target_user_id,))
        user_info = cursor.fetchone()
        
        # Expense stats
        cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM expenses WHERE user_id = ?
        ''', (target_user_id,))
        exp_count, total_amount = cursor.fetchone()
        
        # Achievements
        cursor.execute('''
            SELECT COUNT(*) FROM user_achievements WHERE user_id = ?
        ''', (target_user_id,))
        badge_count = cursor.fetchone()[0]
        
        conn.close()
        
        if not user_info:
            await query.answer("User not found", show_alert=True)
            return
        
        name, username, daily, monthly, created = user_info
        username_text = f"@{username}" if username else "No username"
        created_date = datetime.fromisoformat(created).strftime('%d/%m/%Y')
        
        text = f"👑 <b>Detail User</b>\n\n"
        text += f"👤 <b>{name}</b> ({username_text})\n"
        text += f"📅 Bergabung: {created_date}\n\n"
        text += f"<b>Budget:</b>\n"
        text += f"📅 Harian: {format_currency(daily) if daily > 0 else 'Tidak ada'}\n"
        text += f"📆 Bulanan: {format_currency(monthly) if monthly > 0 else 'Tidak ada'}\n\n"
        text += f"<b>Statistik:</b>\n"
        text += f"📝 {exp_count} transaksi\n"
        text += f"💰 Total: {format_currency(total_amount)}\n"
        text += f"🏆 {badge_count} badge diraih"
        
        keyboard = [[InlineKeyboardButton("🔙 Daftar User", callback_data='owner_users')]]
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ============= NOTIFICATION SCHEDULER =============
    async def send_daily_reminder(self):
        """Send daily reminder"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Get users with notification enabled
        cursor.execute('''
            SELECT user_id, display_name, current_theme FROM users 
            WHERE notification_enabled = 1 AND onboarding_completed = 1
        ''')
        users = cursor.fetchall()
        
        for user_id, name, theme in users:
            # Check if user already logged expense today
            cursor.execute('''
                SELECT COUNT(*) FROM expenses 
                WHERE user_id = ? AND date = ?
            ''', (user_id, today))
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                header = get_theme_header(theme)
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"{header}\n\n"
                            f"🔔 <b>Pengingat Harian</b>\n\n"
                            f"Halo {name}! 👋\n\n"
                            f"Kamu belum mencatat pengeluaran hari ini.\n\n"
                            f"Jangan lupa catat pengeluaran agar budget tetap terkontrol! 💪\n\n"
                            f"Yuk catat sekarang!"
                        ),
                        parse_mode='HTML',
                        reply_markup=self.get_main_keyboard(user_id)
                    )
                except Exception as e:
                    print(f"Error sending reminder to {user_id}: {e}")
        
        conn.close()
    
    def run_scheduler(self):
        """Run scheduler"""
        schedule.every().day.at("20:00").do(
            lambda: self.application.create_task(self.send_daily_reminder())
        )
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    def run(self):
        """Run bot"""
        # Start scheduler
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()
        
        print("=" * 50)
        print("🚀 CashKeeper Bot Started!")
        print(f"👑 Created by: Lord Putra a.k.a Rahmet")
        print(f"📱 Telegram: @{OWNER_TELEGRAM_USERNAME}")
        print("=" * 50)
        print(f"\n🔐 Owner Credentials:")
        print(f"   Username: {OWNER_USERNAME}")
        print(f"   Password: {OWNER_PASSWORD}")
        print(f"   Command: /owner")
        print("=" * 50)
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # BOT TOKEN - Ganti dengan token dari @BotFather
    TOKEN = 'YOUR_BOT_TOKEN_HERE'
    
    if TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("\n" + "=" * 50)
        print("❌ ERROR: Token Bot Belum Dikonfigurasi!")
        print("=" * 50)
        print("\n📝 Langkah Setup:")
        print("1. Buka Telegram, cari @BotFather")
        print("2. Ketik /newbot dan ikuti instruksi")
        print("3. Copy token yang diberikan")
        print("4. Ganti 'YOUR_BOT_TOKEN_HERE' dengan token Anda")
        print("\n" + "=" * 50)
    else:
        bot = CashKeeperBot(TOKEN)
        bot.run()
