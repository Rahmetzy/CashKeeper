import os
import sys

TOKEN = os.environ.get('BOT_TOKEN', '')

if not TOKEN:
    print("ERROR: BOT_TOKEN environment variable tidak ditemukan!")
    print("Set BOT_TOKEN di Railway Variables")
    sys.exit(1)

print(f"BOT_TOKEN ditemukan, panjang: {len(TOKEN)} karakter")

# Import dan jalankan bot
import sqlite3
from datetime import datetime, timedelta
import schedule
import threading
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters,
)

DB_FILE = 'cashkeeper.db'
OWNER_USERNAME = "lordputra"
OWNER_PASSWORD = "cashkeeper2026"
OWNER_TELEGRAM_USERNAME = "r4hmtdwi_"

(AMOUNT, CATEGORY, DESCRIPTION,
 ONBOARD_NAME, ONBOARD_DAILY, ONBOARD_MONTHLY,
 OWNER_LOGIN_USERNAME, OWNER_LOGIN_PASSWORD) = range(8)

DEFAULT_CATEGORIES = {
    'Makanan': '🍔', 'Transport': '🚗', 'Belanja': '🛒',
    'Tagihan': '💳', 'Kesehatan': '🏥', 'Hiburan': '🎮',
    'Pendidikan': '📚', 'Lainnya': '📦'
}

THEMES = {
    'default':    {'name': '🏠 Classic',    'emoji': '🏠'},
    'pink_cute':  {'name': '💖 Pink Cute',  'emoji': '💖'},
    'dark_mode':  {'name': '🌙 Dark Mode',  'emoji': '🌙'},
    'neon_vibes': {'name': '✨ Neon Vibes', 'emoji': '✨'},
    'nature':     {'name': '🌿 Nature',     'emoji': '🌿'},
}

def init_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        display_name TEXT, daily_limit REAL DEFAULT 0, monthly_limit REAL DEFAULT 0,
        current_theme TEXT DEFAULT 'default', notification_enabled INTEGER DEFAULT 1,
        is_owner INTEGER DEFAULT 0, onboarding_completed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_active DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        amount REAL NOT NULL, category TEXT NOT NULL, description TEXT,
        date DATE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        name TEXT NOT NULL, emoji TEXT DEFAULT '💰')''')
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL, description TEXT, badge_emoji TEXT,
        requirement_type TEXT, requirement_value INTEGER, difficulty TEXT DEFAULT 'easy')''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        achievement_code TEXT, unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    achievements = [
        ('first_expense',   'Langkah Pertama',      'Catat pengeluaran pertama',          '🌟', 'expense_count', 1,   'easy'),
        ('five_expenses',   'Pemula Rajin',          'Catat 5 pengeluaran',                '⭐', 'expense_count', 5,   'easy'),
        ('ten_expenses',    'Pencatat Handal',       'Catat 10 pengeluaran',               '⭐⭐','expense_count', 10,  'medium'),
        ('thirty_expenses', 'Dedikasi Tinggi',       'Catat 30 pengeluaran',               '⭐⭐⭐','expense_count',30, 'medium'),
        ('hundred_expenses','Legenda Pencatat',      'Catat 100 pengeluaran',              '👑', 'expense_count', 100, 'hard'),
        ('first_week',      'Survivor Minggu',       'Aktif 7 hari',                       '📅', 'days_active',   7,   'easy'),
        ('thirty_days',     'Konsisten Sebulan',     'Aktif 30 hari',                      '📆', 'days_active',   30,  'medium'),
        ('ninety_days',     'Komitmen 3 Bulan',      'Aktif 90 hari',                      '🏆', 'days_active',   90,  'hard'),
        ('all_categories',  'Eksplorer Lengkap',     'Gunakan semua kategori',             '🎯', 'all_categories',8,   'medium'),
        ('under_budget_day','Hemat Hari Ini',         'Pengeluaran di bawah budget harian', '💚', 'under_daily',   1,   'easy'),
        ('zero_day',        'Hari Tanpa Belanja',    'Tidak belanja sehari',               '🎖️','zero_day',      1,   'medium'),
        ('early_bird',      'Early Bird',            'Input sebelum jam 8 pagi',           '🌅', 'early_expense', 1,   'medium'),
        ('perfect_month',   'Bulan Sempurna',        'Catat setiap hari 30 hari',          '💫', 'perfect_month', 30,  'ultra_hard'),
        ('frugal_legend',   'Legenda Hemat',         'Budget aman 30 hari berturut',       '🏅', 'streak_daily',  30,  'ultra_hard'),
        ('five_hundred',    'Ultimate Tracker',      'Catat 500 pengeluaran',              '🌟👑','expense_count',500, 'ultra_hard'),
    ]
    for ach in achievements:
        c.execute('INSERT OR IGNORE INTO achievements (code,name,description,badge_emoji,requirement_type,requirement_value,difficulty) VALUES (?,?,?,?,?,?,?)', ach)
    conn.commit()
    conn.close()

def fmt(amount):
    return f"Rp {amount:,.0f}".replace(',', '.')

def theme_header(theme_code):
    headers = {
        'default':    '💰 CashKeeper 💰',
        'pink_cute':  '✨💖 CashKeeper 💖✨',
        'dark_mode':  '🌙 CashKeeper 🌙',
        'neon_vibes': '✨🎆 CashKeeper 🎆✨',
        'nature':     '🌿 CashKeeper 🌿',
    }
    return headers.get(theme_code, '💰 CashKeeper 💰')

def check_and_unlock(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM expenses WHERE user_id=?', (user_id,))
    exp_count = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id=?', (user_id,))
    days = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT category) FROM expenses WHERE user_id=?', (user_id,))
    cats = c.fetchone()[0]
    c.execute('SELECT daily_limit FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone(); daily_limit = row[0] if row else 0
    today = datetime.now().date()
    c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND date=?', (user_id, today))
    today_total = c.fetchone()[0]
    c.execute('SELECT achievement_code FROM user_achievements WHERE user_id=?', (user_id,))
    unlocked = {r[0] for r in c.fetchall()}
    c.execute('SELECT code,requirement_type,requirement_value FROM achievements')
    all_ach = c.fetchall()
    newly = []
    for code, rtype, rval in all_ach:
        if code in unlocked: continue
        ok = False
        if rtype == 'expense_count' and exp_count >= rval: ok = True
        elif rtype == 'days_active' and days >= rval: ok = True
        elif rtype == 'all_categories' and cats >= rval: ok = True
        elif rtype == 'under_daily' and daily_limit > 0 and today_total < daily_limit and today_total > 0: ok = True
        elif rtype == 'early_expense' and datetime.now().hour < 8 and exp_count > 0: ok = True
        if ok:
            c.execute('INSERT INTO user_achievements (user_id, achievement_code) VALUES (?,?)', (user_id, code))
            newly.append(code)
    conn.commit()
    conn.close()
    return newly

def motivation(today_total, daily_limit):
    import random
    if daily_limit <= 0 or today_total <= 0: return ""
    pct = (today_total / daily_limit) * 100
    if pct < 30:
        msgs = ["🌟 Wow keren banget! Super hemat hari ini!", "💚 Amazing! Budget masih sangat aman!", "✨ Luar biasa! Kamu jago ngatur keuangan!"]
    elif pct < 60:
        msgs = ["👍 Good job! Masih di jalur yang benar!", "💙 Oke banget! Budget masih terkendali!", "😊 Nice! Terus pertahankan ya!"]
    elif pct < 85:
        msgs = ["⚠️ Hati-hati, udah lebih dari setengah budget!", "💛 Awas, jangan sampai over budget ya!", "🤔 Coba hemat sedikit lagi!"]
    elif pct < 100:
        msgs = ["🚨 Warning! Budget hampir habis!", "⚡ Bahaya! Sudah 85%+ terpakai!", "💸 Waspada! Jaga pengeluaran!"]
    else:
        msgs = ["💥 OVER BUDGET! Sudah melebihi target hari ini!", "❌ OVERLIMIT! Besok harus lebih hemat!", "😱 Budget sudah terlewati! Saatnya evaluasi!"]
    return "\n\n" + random.choice(msgs)

def main_kb(user_id=None):
    kb = [
        [InlineKeyboardButton("➕ Tambah Pengeluaran", callback_data='add_expense'),
         InlineKeyboardButton("📊 Hari Ini", callback_data='today')],
        [InlineKeyboardButton("📅 Bulan Ini", callback_data='month'),
         InlineKeyboardButton("📈 Statistik", callback_data='stats')],
        [InlineKeyboardButton("🏆 Achievement", callback_data='achievements'),
         InlineKeyboardButton("⚙️ Pengaturan", callback_data='settings')],
    ]
    if user_id:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT is_owner FROM users WHERE user_id=?', (user_id,))
        r = c.fetchone(); conn.close()
        if r and r[0] == 1:
            kb.append([InlineKeyboardButton("👑 Owner Panel", callback_data='owner_panel')])
    return InlineKeyboardMarkup(kb)

class CashKeeperBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        init_database()
        self._setup()

    def _setup(self):
        onboard = ConversationHandler(
            entry_points=[CommandHandler('start', self.cmd_start)],
            states={
                ONBOARD_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ob_name)],
                ONBOARD_DAILY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ob_daily)],
                ONBOARD_MONTHLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ob_monthly)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        add_exp = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.exp_start, pattern='^add_expense$')],
            states={
                AMOUNT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, self.exp_amount)],
                CATEGORY:    [CallbackQueryHandler(self.exp_category, pattern='^cat_')],
                DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.exp_desc)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        owner_login = ConversationHandler(
            entry_points=[CommandHandler('owner', self.owner_start)],
            states={
                OWNER_LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.owner_check_user)],
                OWNER_LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.owner_check_pass)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        self.app.add_handler(onboard)
        self.app.add_handler(add_exp)
        self.app.add_handler(owner_login)
        self.app.add_handler(CommandHandler('menu',   self.cmd_menu))
        self.app.add_handler(CommandHandler('help',   self.cmd_help))
        self.app.add_handler(CommandHandler('cancel', self.cancel))
        self.app.add_handler(CallbackQueryHandler(self.cb_today,        pattern='^today$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_month,        pattern='^month$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_stats,        pattern='^stats$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_achievements, pattern='^achievements$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_settings,     pattern='^settings$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_themes,       pattern='^themes$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_apply_theme,  pattern='^theme_'))
        self.app.add_handler(CallbackQueryHandler(self.cb_toggle_notif, pattern='^toggle_notif$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_back,         pattern='^back$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_panel,  pattern='^owner_panel$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_users,  pattern='^owner_users$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_stats,  pattern='^owner_stats$'))

    # ── ONBOARDING ──────────────────────────────────────────────
    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT onboarding_completed FROM users WHERE user_id=?', (user.id,))
        row = c.fetchone(); conn.close()
        if row and row[0] == 1:
            await self.cmd_menu(update, ctx); return ConversationHandler.END
        await update.message.reply_text(
            f"👋 Halo <b>{user.first_name}</b>!\n\n"
            f"Selamat datang di <b>CashKeeper</b> 💰\n"
            f"Bot pencatat pengeluaran harian!\n\n"
            f"✨ Fitur:\n"
            f"🎨 5 Tema Keren  🏆 18 Achievement\n"
            f"📊 Laporan Lengkap  🔔 Smart Reminder\n\n"
            f"<b>Dibuat oleh:</b> Lord Putra a.k.a Rahmet\n"
            f"@{OWNER_TELEGRAM_USERNAME}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Pertama, <b>siapa nama kamu?</b> 😊",
            parse_mode='HTML')
        return ONBOARD_NAME

    async def ob_name(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        ctx.user_data['display_name'] = update.message.text.strip()
        await update.message.reply_text(
            f"Halo <b>{ctx.user_data['display_name']}</b>! 😊\n\n"
            f"Sekarang atur <b>budget harian</b> kamu:\n"
            f"(contoh: <code>100000</code> untuk Rp 100.000)\n\n"
            f"Ketik <code>0</code> jika tidak mau set limit",
            parse_mode='HTML')
        return ONBOARD_DAILY

    async def ob_daily(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            v = float(update.message.text.replace(',','').replace('.',''))
            if v < 0: raise ValueError
            ctx.user_data['daily_limit'] = v
            await update.message.reply_text(
                f"✅ Budget harian: <b>{fmt(v) if v > 0 else 'Tanpa limit'}</b>\n\n"
                f"Terakhir, <b>budget bulanan</b> kamu:\n"
                f"(contoh: <code>3000000</code>)\n\n"
                f"Ketik <code>0</code> jika tidak mau set limit",
                parse_mode='HTML')
            return ONBOARD_MONTHLY
        except:
            await update.message.reply_text("❌ Angka tidak valid, coba lagi (contoh: 100000)")
            return ONBOARD_DAILY

    async def ob_monthly(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            v = float(update.message.text.replace(',','').replace('.',''))
            if v < 0: raise ValueError
            user = update.effective_user
            name = ctx.user_data['display_name']
            daily = ctx.user_data['daily_limit']
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO users (user_id,username,first_name,display_name,daily_limit,monthly_limit,onboarding_completed) VALUES (?,?,?,?,?,?,1)',
                      (user.id, user.username, user.first_name, name, daily, v))
            for cn, em in DEFAULT_CATEGORIES.items():
                c.execute('INSERT OR IGNORE INTO categories (user_id,name,emoji) VALUES (?,?,?)', (user.id,cn,em))
            conn.commit(); conn.close()
            await update.message.reply_text(
                f"🎉 <b>Setup Selesai!</b>\n\n"
                f"👤 Nama: <b>{name}</b>\n"
                f"📅 Budget Harian: <b>{fmt(daily) if daily>0 else 'Tanpa limit'}</b>\n"
                f"📆 Budget Bulanan: <b>{fmt(v) if v>0 else 'Tanpa limit'}</b>\n\n"
                f"✨ Selamat mencatat pengeluaran!\n"
                f"💡 Kumpulkan achievement untuk motivasi!\n"
                f"🎨 Ganti tema di Pengaturan!\n\n"
                f"Gunakan menu di bawah untuk mulai!",
                parse_mode='HTML', reply_markup=main_kb(user.id))
            ctx.user_data.clear(); return ConversationHandler.END
        except:
            await update.message.reply_text("❌ Angka tidak valid, coba lagi (contoh: 3000000)")
            return ONBOARD_MONTHLY

    # ── MENU ────────────────────────────────────────────────────
    async def cmd_menu(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            q = update.callback_query; await q.answer(); user = q.from_user
        else:
            user = update.effective_user
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT display_name, current_theme FROM users WHERE user_id=?', (user.id,))
        row = c.fetchone(); conn.close()
        if not row:
            if update.message: await self.cmd_start(update, ctx)
            return
        name, theme = row
        txt = f"{theme_header(theme)}\n\nHalo, <b>{name}</b>! 👋\n\nMau ngapain hari ini? 😊"
        kb = main_kb(user.id)
        if update.callback_query:
            await update.callback_query.edit_message_text(txt, parse_mode='HTML', reply_markup=kb)
        else:
            await update.message.reply_text(txt, parse_mode='HTML', reply_markup=kb)

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 <b>Panduan CashKeeper</b>\n\n"
            "/start — Mulai & setup\n/menu — Menu utama\n"
            "/owner — Login owner panel\n/cancel — Batalkan\n\n"
            "🏆 Kumpulkan achievement!\n🎨 Ganti tema di Pengaturan!\n\n"
            f"Dibuat oleh: Lord Putra a.k.a Rahmet\n@{OWNER_TELEGRAM_USERNAME}",
            parse_mode='HTML', reply_markup=main_kb(update.effective_user.id))

    async def cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Dibatalkan. Ketik /menu untuk kembali.",
            reply_markup=main_kb(update.effective_user.id))
        ctx.user_data.clear(); return ConversationHandler.END

    # ── ADD EXPENSE ─────────────────────────────────────────────
    async def exp_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        await q.edit_message_text(
            "💰 <b>Tambah Pengeluaran</b>\n\nMasukkan nominal:\n(contoh: <code>50000</code>)\n\nKetik /cancel untuk batal",
            parse_mode='HTML'); return AMOUNT

    async def exp_amount(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            amt = float(update.message.text.replace(',','').replace('.',''))
            if amt <= 0: raise ValueError
            ctx.user_data['amount'] = amt
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT name, emoji FROM categories WHERE user_id=? ORDER BY name', (update.effective_user.id,))
            cats = c.fetchall(); conn.close()
            kb = []
            row = []
            for nm, em in cats:
                row.append(InlineKeyboardButton(f"{em} {nm}", callback_data=f'cat_{nm}'))
                if len(row) == 2: kb.append(row); row = []
            if row: kb.append(row)
            await update.message.reply_text(
                f"✅ Nominal: <b>{fmt(amt)}</b>\n\nPilih kategori:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb)); return CATEGORY
        except:
            await update.message.reply_text("❌ Tidak valid! Masukkan angka saja (contoh: 50000)"); return AMOUNT

    async def exp_category(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        cat = q.data.replace('cat_', ''); ctx.user_data['category'] = cat
        amt = ctx.user_data['amount']
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT emoji FROM categories WHERE user_id=? AND name=?', (update.effective_user.id, cat))
        r = c.fetchone(); conn.close()
        em = r[0] if r else '💰'
        await q.edit_message_text(
            f"✅ Nominal: <b>{fmt(amt)}</b>\n{em} Kategori: <b>{cat}</b>\n\n"
            f"Tambah deskripsi?\n(atau ketik <code>-</code> untuk skip)",
            parse_mode='HTML'); return DESCRIPTION

    async def exp_desc(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        desc = '' if update.message.text == '-' else update.message.text
        uid = update.effective_user.id
        amt = ctx.user_data['amount']
        cat = ctx.user_data['category']
        today = datetime.now().date()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO expenses (user_id,amount,category,description,date) VALUES (?,?,?,?,?)',
                  (uid, amt, cat, desc, today))
        c.execute('UPDATE users SET last_active=? WHERE user_id=?', (today, uid))
        c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND date=?', (uid, today))
        total_today = c.fetchone()[0]
        c.execute('SELECT daily_limit, current_theme FROM users WHERE user_id=?', (uid,))
        row = c.fetchone(); daily_limit = row[0]; theme = row[1]
        c.execute('SELECT emoji FROM categories WHERE user_id=? AND name=?', (uid, cat))
        r = c.fetchone(); em = r[0] if r else '💰'
        conn.commit(); conn.close()
        new_ach = check_and_unlock(uid)
        txt = (f"✅ <b>Pengeluaran Tersimpan!</b>\n\n"
               f"💰 {fmt(amt)}\n{em} {cat}\n"
               f"{f'📝 {desc}' if desc else ''}\n"
               f"📅 {today.strftime('%d %B %Y')}\n\n"
               f"━━━━━━━━━━━━━━━━\n"
               f"📊 <b>Total Hari Ini: {fmt(total_today)}</b>")
        if daily_limit > 0:
            pct = (total_today / daily_limit) * 100
            txt += f"\n💳 {pct:.1f}% dari {fmt(daily_limit)}"
        txt += motivation(total_today, daily_limit)
        if new_ach:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            codes = ','.join('?' * len(new_ach))
            c.execute(f'SELECT name, badge_emoji FROM achievements WHERE code IN ({codes})', new_ach)
            badges = c.fetchall(); conn.close()
            txt += "\n\n🎉 <b>Achievement Unlocked!</b>\n"
            for nm, bg in badges: txt += f"{bg} {nm}\n"
        await update.message.reply_text(txt, parse_mode='HTML', reply_markup=main_kb(uid))
        ctx.user_data.clear(); return ConversationHandler.END

    # ── LAPORAN ─────────────────────────────────────────────────
    async def cb_today(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id; today = datetime.now().date()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT e.amount, e.category, e.description, c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? AND e.date=? ORDER BY e.created_at DESC', (uid, today))
        exps = c.fetchall()
        c.execute('SELECT daily_limit, current_theme FROM users WHERE user_id=?', (uid,))
        row = c.fetchone(); daily_limit = row[0]; theme = row[1]
        conn.close()
        total = sum(e[0] for e in exps)
        hdr = theme_header(theme)
        if not exps:
            txt = f"{hdr}\n\n📊 <b>Hari Ini</b> — {today.strftime('%d %B %Y')}\n\nBelum ada pengeluaran hari ini 💪\nYuk mulai catat!"
        else:
            txt = f"{hdr}\n\n📊 <b>Hari Ini</b> — {today.strftime('%d %B %Y')}\n\n"
            for amt, cat, desc, em in exps:
                em = em or '💰'
                txt += f"{em} <b>{fmt(amt)}</b> — {cat}\n"
                if desc: txt += f"   <i>{desc}</i>\n"
            txt += f"\n━━━━━━━━━━━━━━━━\n💰 <b>Total: {fmt(total)}</b>"
            if daily_limit > 0:
                pct = (total/daily_limit)*100
                status = "✅ Aman!" if total < daily_limit else "⚠️ Over budget!"
                txt += f"\n💳 {pct:.1f}% dari {fmt(daily_limit)} — {status}"
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    async def cb_month(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id; now = datetime.now()
        first = now.replace(day=1).date()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id=? AND date>=?', (uid, first))
        total, count = c.fetchone(); total = total or 0; count = count or 0
        c.execute('SELECT e.category, SUM(e.amount), c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? AND e.date>=? GROUP BY e.category ORDER BY SUM(e.amount) DESC', (uid, first))
        cats = c.fetchall()
        c.execute('SELECT monthly_limit, current_theme FROM users WHERE user_id=?', (uid,))
        row = c.fetchone(); monthly_limit = row[0]; theme = row[1]
        conn.close()
        hdr = theme_header(theme)
        txt = f"{hdr}\n\n📅 <b>Bulan {now.strftime('%B %Y')}</b>\n\n"
        if not cats:
            txt += "Belum ada pengeluaran bulan ini."
        else:
            txt += "<b>Breakdown Kategori:</b>\n\n"
            for cat, amt, em in cats:
                em = em or '💰'; pct = (amt/total*100) if total > 0 else 0
                bar = '█'*int(pct/10) + '░'*(10-int(pct/10))
                txt += f"{em} <b>{cat}</b>\n   {fmt(amt)} ({pct:.1f}%)\n   {bar}\n\n"
            txt += f"━━━━━━━━━━━━━━━━\n💰 <b>Total: {fmt(total)}</b>\n📝 {count} transaksi"
            if monthly_limit > 0:
                pct = (total/monthly_limit)*100
                status = "✅ Aman!" if total < monthly_limit else "⚠️ Over budget!"
                txt += f"\n💳 {pct:.1f}% dari {fmt(monthly_limit)} — {status}"
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    async def cb_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id; now = datetime.now()
        today = now.date(); first = now.replace(day=1).date()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=?', (uid,))
        ta, ca = c.fetchone(); ta = ta or 0; ca = ca or 0
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=? AND date>=?', (uid, first))
        tm, cm = c.fetchone(); tm = tm or 0; cm = cm or 0
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=? AND date=?', (uid, today))
        tt, ct = c.fetchone(); tt = tt or 0; ct = ct or 0
        c.execute('SELECT e.category, SUM(e.amount), c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? GROUP BY e.category ORDER BY SUM(e.amount) DESC LIMIT 1', (uid,))
        top = c.fetchone()
        c.execute('SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id=?', (uid,))
        days = c.fetchone()[0]
        c.execute('SELECT current_theme FROM users WHERE user_id=?', (uid,))
        theme = c.fetchone()[0]; conn.close()
        hdr = theme_header(theme)
        txt = (f"{hdr}\n\n📈 <b>Statistik Kamu</b>\n\n"
               f"<b>📊 Hari Ini:</b>\n💰 {fmt(tt)} ({ct} transaksi)\n\n"
               f"<b>📅 Bulan Ini:</b>\n💰 {fmt(tm)} ({cm} transaksi)\n"
               f"{f'📊 Rata-rata: {fmt(tm/now.day)}/hari' if cm > 0 else ''}\n\n"
               f"<b>🎯 All Time:</b>\n💰 {fmt(ta)} ({ca} transaksi)\n📅 Aktif {days} hari")
        if top:
            em = top[2] or '💰'
            txt += f"\n\n<b>🏆 Kategori Terbesar:</b>\n{em} {top[0]} — {fmt(top[1])}"
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    async def cb_achievements(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT a.name,a.badge_emoji,a.description,a.difficulty,ua.unlocked_at FROM user_achievements ua JOIN achievements a ON ua.achievement_code=a.code WHERE ua.user_id=? ORDER BY ua.unlocked_at DESC', (uid,))
        unlocked = c.fetchall()
        c.execute('SELECT COUNT(*) FROM achievements')
        total = c.fetchone()[0]
        c.execute('SELECT current_theme FROM users WHERE user_id=?', (uid,))
        theme = c.fetchone()[0]; conn.close()
        hdr = theme_header(theme)
        pct = (len(unlocked)/total*100) if total > 0 else 0
        bar = '█'*int(pct/10) + '░'*(10-int(pct/10))
        txt = f"{hdr}\n\n🏆 <b>Achievement & Badge</b>\n\n📊 {len(unlocked)}/{total} ({pct:.1f}%)\n{bar}\n\n"
        if unlocked:
            txt += "<b>🎉 Badge yang Diraih:</b>\n\n"
            diff_map = {'easy':'⭐','medium':'⭐⭐','hard':'⭐⭐⭐','ultra_hard':'👑'}
            for nm, bg, desc, diff, at in unlocked:
                date_str = datetime.fromisoformat(at).strftime('%d/%m/%Y')
                txt += f"{bg} <b>{nm}</b> {diff_map.get(diff,'⭐')}\n   <i>{desc}</i>\n   📅 {date_str}\n\n"
        else:
            txt += "Belum ada badge 😅\n\nCara dapat badge:\n💡 Catat pengeluaran pertama → 🌟\n💡 Aktif 7 hari → 📅\n💡 Hemat budget → 💚"
        if len(unlocked) < total:
            txt += f"\n🎯 Masih ada <b>{total-len(unlocked)} badge</b> lagi! Semangat! 💪"
        else:
            txt += "\n\n🎊 <b>LUAR BIASA!</b> Semua badge sudah terkumpul! 🏆"
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    # ── SETTINGS & TEMA ─────────────────────────────────────────
    async def cb_settings(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT notification_enabled,display_name,daily_limit,monthly_limit,current_theme FROM users WHERE user_id=?', (uid,))
        notif, name, daily, monthly, theme = c.fetchone(); conn.close()
        hdr = theme_header(theme)
        theme_name = THEMES.get(theme, THEMES['default'])['name']
        txt = (f"{hdr}\n\n⚙️ <b>Pengaturan</b>\n\n"
               f"👤 Nama: <b>{name}</b>\n"
               f"📅 Budget Harian: <b>{fmt(daily) if daily>0 else 'Tidak ada'}</b>\n"
               f"📆 Budget Bulanan: <b>{fmt(monthly) if monthly>0 else 'Tidak ada'}</b>\n\n"
               f"🎨 Tema: <b>{theme_name}</b>\n"
               f"🔔 Notifikasi: <b>{'🔔 Aktif' if notif else '🔕 Nonaktif'}</b>\n\n"
               f"Notifikasi dikirim jam 20:00 WIB jika belum input hari ini")
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎨 Ganti Tema", callback_data='themes')],
                [InlineKeyboardButton("🔄 Toggle Notifikasi", callback_data='toggle_notif')],
                [InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    async def cb_themes(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT current_theme FROM users WHERE user_id=?', (uid,))
        cur = c.fetchone()[0]; conn.close()
        txt = ("🎨 <b>Pilih Tema Favoritmu!</b>\n\n"
               "💖 Pink Cute — lucu & imut buat cewek\n"
               "🌙 Dark Mode — gelap & keren\n"
               "✨ Neon Vibes — Gen Z vibes!\n"
               "🌿 Nature — natural & calming\n"
               "🏠 Classic — elegan & bersih\n")
        kb = []
        for code, data in THEMES.items():
            mark = " ✅" if code == cur else ""
            kb.append([InlineKeyboardButton(f"{data['emoji']} {data['name']}{mark}", callback_data=f'theme_{code}')])
        kb.append([InlineKeyboardButton("🔙 Pengaturan", callback_data='settings')])
        await q.edit_message_text(txt, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

    async def cb_apply_theme(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        code = q.data.replace('theme_', '')
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE users SET current_theme=? WHERE user_id=?', (code, uid))
        conn.commit(); conn.close()
        name = THEMES.get(code, THEMES['default'])['name']
        await q.answer(f"✨ Tema berubah ke {name}!", show_alert=True)
        await self.cb_settings(update, ctx)

    async def cb_toggle_notif(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE users SET notification_enabled=1-notification_enabled WHERE user_id=?', (uid,))
        c.execute('SELECT notification_enabled FROM users WHERE user_id=?', (uid,))
        new = c.fetchone()[0]; conn.commit(); conn.close()
        await q.answer(f"Notifikasi {'diaktifkan 🔔' if new else 'dinonaktifkan 🔕'}", show_alert=True)
        await self.cb_settings(update, ctx)

    async def cb_back(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self.cmd_menu(update, ctx)

    # ── OWNER PANEL ─────────────────────────────────────────────
    async def owner_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👑 <b>Owner Login</b>\n\nMasukkan username:", parse_mode='HTML')
        return OWNER_LOGIN_USERNAME

    async def owner_check_user(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.message.text.strip() == OWNER_USERNAME:
            ctx.user_data['owner_ok'] = True
            await update.message.reply_text("✅ Username benar!\n\nMasukkan password:")
            return OWNER_LOGIN_PASSWORD
        await update.message.reply_text("❌ Username salah! Akses ditolak.")
        return ConversationHandler.END

    async def owner_check_pass(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.message.text.strip() == OWNER_PASSWORD:
            uid = update.effective_user.id
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('UPDATE users SET is_owner=1 WHERE user_id=?', (uid,))
            conn.commit(); conn.close()
            await update.message.reply_text(
                "✅ <b>Login Berhasil!</b>\n\nWelcome, Owner! 👑\nGunakan menu untuk akses Owner Panel.",
                parse_mode='HTML', reply_markup=main_kb(uid))
            ctx.user_data.clear(); return ConversationHandler.END
        await update.message.reply_text("❌ Password salah! Akses ditolak.")
        return ConversationHandler.END

    async def cb_owner_panel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        uid = update.effective_user.id
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT is_owner FROM users WHERE user_id=?', (uid,))
        r = c.fetchone()
        if not r or r[0] != 1:
            await q.answer("❌ Akses ditolak!", show_alert=True); conn.close(); return
        c.execute('SELECT COUNT(*) FROM users WHERE onboarding_completed=1')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM expenses')
        total_exp = c.fetchone()[0]
        c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses')
        total_amt = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM user_achievements')
        total_badges = c.fetchone()[0]
        conn.close()
        txt = (f"👑 <b>OWNER PANEL</b>\n\n"
               f"<b>📊 Statistik Global:</b>\n"
               f"👥 Total User: <b>{total_users}</b>\n"
               f"📝 Total Transaksi: <b>{total_exp}</b>\n"
               f"💰 Total Pengeluaran: <b>{fmt(total_amt)}</b>\n"
               f"🏆 Total Badge Diraih: <b>{total_badges}</b>")
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Daftar User", callback_data='owner_users')],
                [InlineKeyboardButton("📈 Statistik Detail", callback_data='owner_stats')],
                [InlineKeyboardButton("🔙 Menu", callback_data='back')]]))

    async def cb_owner_users(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT u.user_id,u.display_name,u.username,COUNT(e.id),COALESCE(SUM(e.amount),0),u.created_at FROM users u LEFT JOIN expenses e ON u.user_id=e.user_id WHERE u.onboarding_completed=1 GROUP BY u.user_id ORDER BY COUNT(e.id) DESC LIMIT 15')
        users = c.fetchall(); conn.close()
        txt = "👑 <b>OWNER — Daftar User</b>\n\n"
        for i, (uid2, name, uname, cnt, amt, created) in enumerate(users, 1):
            uname_txt = f"@{uname}" if uname else "no username"
            created_dt = datetime.fromisoformat(created).strftime('%d/%m/%y')
            txt += f"{i}. <b>{name}</b> ({uname_txt})\n   📝 {cnt} transaksi | 💰 {fmt(amt)} | 📅 {created_dt}\n\n"
        if not users: txt += "Belum ada user."
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Owner Panel", callback_data='owner_panel')]]))

    async def cb_owner_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query; await q.answer()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        today = datetime.now().date(); first = today.replace(day=1)
        c.execute('SELECT COUNT(DISTINCT user_id),COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE date=?', (today,))
        du, de, da = c.fetchone()
        c.execute('SELECT COUNT(DISTINCT user_id),COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE date>=?', (first,))
        mu, me, ma = c.fetchone()
        c.execute('SELECT category,COUNT(*),SUM(amount) FROM expenses GROUP BY category ORDER BY COUNT(*) DESC LIMIT 1')
        top = c.fetchone(); conn.close()
        txt = (f"👑 <b>OWNER — Statistik Detail</b>\n\n"
               f"<b>📊 Hari Ini:</b>\n👥 {du} aktif | 📝 {de} transaksi | 💰 {fmt(da)}\n\n"
               f"<b>📅 Bulan Ini:</b>\n👥 {mu} aktif | 📝 {me} transaksi | 💰 {fmt(ma)}")
        if top: txt += f"\n\n<b>🏆 Kategori Terpopuler:</b>\n{top[0]} — {top[1]}x ({fmt(top[2])})"
        await q.edit_message_text(txt, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Owner Panel", callback_data='owner_panel')]]))

    # ── NOTIFIKASI ──────────────────────────────────────────────
    async def send_reminders(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        today = datetime.now().date()
        c.execute('SELECT user_id,display_name,current_theme FROM users WHERE notification_enabled=1 AND onboarding_completed=1')
        users = c.fetchall(); conn.close()
        for uid, name, theme in users:
            conn2 = sqlite3.connect(DB_FILE)
            c2 = conn2.cursor()
            c2.execute('SELECT COUNT(*) FROM expenses WHERE user_id=? AND date=?', (uid, today))
            cnt = c2.fetchone()[0]; conn2.close()
            if cnt == 0:
                try:
                    await self.app.bot.send_message(chat_id=uid,
                        text=(f"{theme_header(theme)}\n\n"
                              f"🔔 <b>Pengingat Harian!</b>\n\n"
                              f"Halo {name}! 👋\n\n"
                              f"Kamu belum catat pengeluaran hari ini.\n"
                              f"Jangan lupa ya biar budget tetap terkontrol! 💪"),
                        parse_mode='HTML', reply_markup=main_kb(uid))
                except Exception as e:
                    print(f"Reminder error for {uid}: {e}")

    def _run_scheduler(self):
        schedule.every().day.at("20:00").do(
            lambda: self.app.create_task(self.send_reminders()))
        while True:
            schedule.run_pending()
            time.sleep(60)

    def run(self):
        t = threading.Thread(target=self._run_scheduler, daemon=True)
        t.start()
        print("=" * 52)
        print("  🚀 CashKeeper Bot Started!")
        print("  👑 Lord Putra a.k.a Rahmet | @r4hmtdwi_")
        print("=" * 52)
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

# ── ENTRY POINT ─────────────────────────────────────────────────
print(f"Starting CashKeeper... TOKEN length: {len(TOKEN)}")
bot = CashKeeperBot(TOKEN)
bot.run()
