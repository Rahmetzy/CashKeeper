import os, sys, sqlite3, threading, time, random
from datetime import datetime
import schedule
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler,
    ContextTypes, filters,
)

TOKEN = os.environ.get('BOT_TOKEN', '')
if not TOKEN:
    print("ERROR: BOT_TOKEN tidak ditemukan!"); sys.exit(1)
print(f"✅ BOT_TOKEN OK (len={len(TOKEN)})")

DB_FILE    = 'cashkeeper.db'
OWNER_USR  = "lordputra"
OWNER_PWD  = "cashkeeper2026"
OWNER_TG   = "r4hmtdwi_"

# ── States ──────────────────────────────────────────────────────
(S_AMT, S_CAT, S_DESC,
 S_OB_NAME, S_OB_DAILY, S_OB_MONTHLY,
 S_OWN_USR, S_OWN_PWD,
 S_SMART_DESC) = range(9)

# ── Kategori & Kata Kunci (untuk AI kategori otomatis) ──────────
CATEGORY_KEYWORDS = {
    'Makanan': {
        'emoji': '🍔',
        'keywords': [
            'makan','minum','nasi','ayam','soto','bakso','mie','mi','indomie',
            'noodle','burger','pizza','kfc','mcdonalds','mcd','warteg','warung',
            'restoran','restaurant','cafe','kafe','kopi','coffee','teh','susu',
            'milk','juice','jus','es','minuman','drink','snack','cemilan','jajan',
            'camilan','roti','bread','cake','kue','pizza','sushi','steak',
            'rokok','cigarette','sigaret','kretek','djarum','gudang','sampoerna',
            'bako','tembakau','vape','liquid','nasi goreng','gorengan','batagor',
            'siomay','gado','pecel','rendang','sate','seafood','ikan','udang',
            'grabfood','gofood','shopeefood','tokopedia food','delivery food',
        ]
    },
    'Transport': {
        'emoji': '🚗',
        'keywords': [
            'grab','gojek','ojek','ojol','taksi','taxi','uber','maxim','indriver',
            'bus','busway','transjakarta','mrt','lrt','kereta','krl','commuter',
            'angkot','angkutan','bensin','bbm','pertamax','pertalite','solar',
            'premium','shell','spbu','parkir','tol','motor','mobil','sepeda',
            'gocar','grabcar','grabbike','transport','ongkir','ongkos kirim',
            'pengiriman','titip','kirim','ekspedisi','jne','jnt','sicepat','anteraja',
        ]
    },
    'Belanja': {
        'emoji': '🛒',
        'keywords': [
            'beli','belanja','shopee','tokopedia','lazada','tiktok shop','bukalapak',
            'alfamart','indomaret','minimarket','supermarket','hypermart','carrefour',
            'mall','plaza','pasar','market','online shop','olshop','fashion','baju',
            'celana','sepatu','sandal','tas','dompet','jam','jam tangan','aksesoris',
            'kosmetik','skincare','makeup','parfum','sabun','shampoo','conditioner',
            'detergen','pembersih','perabot','furniture','elektronik','handphone',
            'hp','gadget','charger','kabel','headset','earphone','keyboard','mouse',
        ]
    },
    'Tagihan': {
        'emoji': '💳',
        'keywords': [
            'tagihan','bayar','cicilan','kredit','pinjaman','hutang','utang',
            'listrik','pln','air','pdam','internet','wifi','indihome','biznet',
            'firstmedia','xl','telkomsel','simpati','im3','axis','tri','smartfren',
            'pulsa','paket data','data','token','voucher','netflix','spotify',
            'youtube premium','disney','apple','google','icloud','ipay','gopay','ovo',
            'dana','shopeepay','linkaja','briva','bni','bca','mandiri','btn',
            'kpr','sewa','kontrakan','kos','kost','rent','asuransi','premi',
            'bpjs','kesehatan','insurance','bulanan','tahunan','langganan',
        ]
    },
    'Kesehatan': {
        'emoji': '🏥',
        'keywords': [
            'dokter','doctor','obat','medicine','apotek','apotik','klinik','clinic',
            'rumah sakit','rs','hospital','puskesmas','periksa','check up','tes',
            'laboratorium','lab','vitamin','suplemen','supplement','masker','mask',
            'sanitizer','alkohol','perban','plester','thermometer','tensi','bpjs',
            'konsultasi','terapi','therapy','gym','olahraga','fitness','yoga',
            'pilates','nutrisi','diet','sehat','health','medical','dental','gigi',
            'kacamata','optik','lensa','psikolog','psikiater',
        ]
    },
    'Hiburan': {
        'emoji': '🎮',
        'keywords': [
            'game','gaming','steam','playstation','ps','xbox','nintendo','mobile legend',
            'ml','pubg','ff','freefire','genshin','valorant','top up','topup','diamond',
            'uc','voucher game','bioskop','cinema','nonton','film','movie','konser',
            'concert','event','tiket','ticket','wisata','jalan','liburan','travel',
            'hotel','penginapan','airbnb','booking','musik','music','spotify',
            'karaoke','bowling','biliar','playground','taman','kebun binatang','zoo',
            'museum','galeri','buku','komik','novel','majalah','netflix','youtube',
        ]
    },
    'Pendidikan': {
        'emoji': '📚',
        'keywords': [
            'buku','buku tulis','alat tulis','pensil','pulpen','pen','kertas','tinta',
            'kursus','les','bimbel','bimbingan','privat','tutor','sekolah','kampus',
            'kuliah','spp','ukt','beasiswa','ujian','sertifikasi','sertifikat',
            'pelatihan','training','workshop','seminar','webinar','online course',
            'udemy','coursera','ruangguru','zenius','quipper','pendidikan','education',
            'perpustakaan','library','stationery','atk',
        ]
    },
    'Lainnya': {
        'emoji': '📦',
        'keywords': []
    },
}

THEMES = {
    'default':    {'name': '🏠 Classic',    'emoji': '🏠'},
    'pink_cute':  {'name': '💖 Pink Cute',  'emoji': '💖'},
    'dark_mode':  {'name': '🌙 Dark Mode',  'emoji': '🌙'},
    'neon_vibes': {'name': '✨ Neon Vibes', 'emoji': '✨'},
    'nature':     {'name': '🌿 Nature',     'emoji': '🌿'},
}

# ── DB ───────────────────────────────────────────────────────────
def init_db():
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
    c.execute('''CREATE TABLE IF NOT EXISTS no_expense_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        date DATE NOT NULL, UNIQUE(user_id, date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        name TEXT NOT NULL, emoji TEXT DEFAULT '💰')''')
    c.execute('''CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL, description TEXT, badge_emoji TEXT,
        requirement_type TEXT, requirement_value INTEGER,
        difficulty TEXT DEFAULT 'easy')''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        achievement_code TEXT, unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, achievement_code))''')
    achs = [
        ('first_expense',   'Langkah Pertama',    'Catat pengeluaran pertama',        '🌟','expense_count',1,   'easy'),
        ('five_expenses',   'Pemula Rajin',        'Catat 5 pengeluaran',              '⭐','expense_count',5,   'easy'),
        ('ten_expenses',    'Pencatat Handal',     'Catat 10 pengeluaran',             '⭐⭐','expense_count',10,'medium'),
        ('thirty_expenses', 'Dedikasi Tinggi',     'Catat 30 pengeluaran',             '⭐⭐⭐','expense_count',30,'medium'),
        ('hundred_expenses','Legenda Pencatat',    'Catat 100 pengeluaran',            '👑','expense_count',100,'hard'),
        ('first_week',      'Survivor Minggu',     'Aktif 7 hari',                     '📅','days_active',7,   'easy'),
        ('thirty_days',     'Konsisten Sebulan',   'Aktif 30 hari',                    '📆','days_active',30,  'medium'),
        ('ninety_days',     'Komitmen 3 Bulan',    'Aktif 90 hari',                    '🏆','days_active',90,  'hard'),
        ('all_categories',  'Eksplorer Lengkap',   'Gunakan semua kategori',           '🎯','all_categories',8,'medium'),
        ('under_budget_day','Hemat Hari Ini',       'Pengeluaran di bawah budget',      '💚','under_daily',1,  'easy'),
        ('no_spend_day',    'Zero Spending',       'Catat hari tanpa belanja',         '🎖️','zero_day',1,     'medium'),
        ('early_bird',      'Early Bird',          'Input sebelum jam 8 pagi',         '🌅','early_expense',1,'medium'),
        ('perfect_month',   'Bulan Sempurna',      'Catat atau log setiap hari 30 hari','💫','perfect_month',30,'ultra_hard'),
        ('frugal_legend',   'Legenda Hemat',       'Budget aman 30 hari berturut',     '🏅','streak_daily',30,'ultra_hard'),
        ('five_hundred',    'Ultimate Tracker',    'Catat 500 pengeluaran',            '🌟👑','expense_count',500,'ultra_hard'),
        ('smart_user',      'Pengguna Cerdas',     'Pakai fitur AI kategori 5x',       '🤖','smart_count',5,  'easy'),
    ]
    for a in achs:
        c.execute('INSERT OR IGNORE INTO achievements (code,name,description,badge_emoji,requirement_type,requirement_value,difficulty) VALUES (?,?,?,?,?,?,?)', a)
    conn.commit(); conn.close()

# ── Helpers ──────────────────────────────────────────────────────
def fmt(n):
    return f"Rp {n:,.0f}".replace(',', '.')

def theme_hdr(t):
    return {
        'default':   '💰 CashKeeper 💰',
        'pink_cute': '✨💖 CashKeeper 💖✨',
        'dark_mode': '🌙 CashKeeper 🌙',
        'neon_vibes':'✨🎆 CashKeeper 🎆✨',
        'nature':    '🌿 CashKeeper 🌿',
    }.get(t, '💰 CashKeeper 💰')

def ai_category(text: str):
    """Deteksi kategori otomatis dari teks pengeluaran."""
    text_lower = text.lower()
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for cat, data in CATEGORY_KEYWORDS.items():
        for kw in data['keywords']:
            if kw in text_lower:
                scores[cat] += len(kw)          # bobot panjang keyword
    scores.pop('Lainnya', None)
    best = max(scores, key=scores.get) if scores else 'Lainnya'
    if scores.get(best, 0) == 0:
        best = 'Lainnya'
    return best, CATEGORY_KEYWORDS[best]['emoji']

def motivation_msg(today_total, daily_limit):
    if daily_limit <= 0 or today_total <= 0: return ""
    pct = (today_total / daily_limit) * 100
    if pct < 30:
        pool = ["🌟 Wow, super hemat hari ini! Kamu luar biasa!",
                "💚 Amazing! Budget masih sangat aman banget!",
                "✨ Keren abis! Kamu jago ngatur keuangan!"]
    elif pct < 60:
        pool = ["👍 Good job! Masih di jalur yang benar!",
                "💙 Oke banget, budget masih terkendali!",
                "😊 Nice! Terus pertahankan ya!"]
    elif pct < 85:
        pool = ["⚠️ Hati-hati, udah lebih dari setengah budget!",
                "💛 Awas jangan sampai over budget ya!",
                "🤔 Coba hemat dikit lagi deh!"]
    elif pct < 100:
        pool = ["🚨 Warning! Budget hampir habis nih!",
                "⚡ Bahaya! Sudah 85%+ budget terpakai!"]
    else:
        pool = ["💥 OVER BUDGET! Sudah melebihi target hari ini!",
                "❌ OVERLIMIT! Besok harus lebih hemat ya!"]
    return "\n\n" + random.choice(pool)

def check_unlock(uid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM expenses WHERE user_id=?',(uid,))
    exp_cnt = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id=?',(uid,))
    days = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT category) FROM expenses WHERE user_id=?',(uid,))
    cats = c.fetchone()[0]
    c.execute('SELECT daily_limit FROM users WHERE user_id=?',(uid,))
    row=c.fetchone(); daily_limit=row[0] if row else 0
    today=datetime.now().date()
    c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND date=?',(uid,today))
    today_total=c.fetchone()[0]
    # no_spend_days count
    c.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=?',(uid,))
    no_spend=c.fetchone()[0]
    # smart count (expenses with auto category — tracked via description containing '[AI]')
    c.execute("SELECT COUNT(*) FROM expenses WHERE user_id=? AND description LIKE '%[AI]%'",(uid,))
    smart_cnt=c.fetchone()[0]
    c.execute('SELECT achievement_code FROM user_achievements WHERE user_id=?',(uid,))
    unlocked={r[0] for r in c.fetchall()}
    c.execute('SELECT code,requirement_type,requirement_value FROM achievements')
    all_a=c.fetchall()
    newly=[]
    for code,rtype,rval in all_a:
        if code in unlocked: continue
        ok=False
        if rtype=='expense_count' and exp_cnt>=rval: ok=True
        elif rtype=='days_active' and days>=rval: ok=True
        elif rtype=='all_categories' and cats>=rval: ok=True
        elif rtype=='under_daily' and daily_limit>0 and 0<today_total<daily_limit: ok=True
        elif rtype=='zero_day' and no_spend>=rval: ok=True
        elif rtype=='early_expense' and datetime.now().hour<8 and exp_cnt>0: ok=True
        elif rtype=='smart_count' and smart_cnt>=rval: ok=True
        if ok:
            try:
                c.execute('INSERT OR IGNORE INTO user_achievements (user_id,achievement_code) VALUES (?,?)',(uid,code))
                newly.append(code)
            except: pass
    conn.commit(); conn.close()
    return newly

def get_user(uid):
    conn=sqlite3.connect(DB_FILE)
    c=conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id=?',(uid,))
    row=c.fetchone(); conn.close(); return row

def main_kb(uid=None):
    kb=[
        [InlineKeyboardButton("➕ Tambah Pengeluaran",callback_data='add_expense'),
         InlineKeyboardButton("🚫 Tidak Ada Pengeluaran",callback_data='no_expense')],
        [InlineKeyboardButton("📊 Hari Ini",callback_data='today'),
         InlineKeyboardButton("📅 Bulan Ini",callback_data='month')],
        [InlineKeyboardButton("📈 Statistik",callback_data='stats'),
         InlineKeyboardButton("🏆 Achievement",callback_data='achievements')],
        [InlineKeyboardButton("⚙️ Pengaturan",callback_data='settings')],
    ]
    if uid:
        conn=sqlite3.connect(DB_FILE)
        c=conn.cursor()
        c.execute('SELECT is_owner FROM users WHERE user_id=?',(uid,))
        r=c.fetchone(); conn.close()
        if r and r[0]==1:
            kb.append([InlineKeyboardButton("👑 Owner Panel",callback_data='owner_panel')])
    return InlineKeyboardMarkup(kb)

# ── BOT ──────────────────────────────────────────────────────────
class CashKeeper:
    def __init__(self, token):
        self.token=token
        self.app=Application.builder().token(token).build()
        init_db()
        self._handlers()

    def _handlers(self):
        onboard=ConversationHandler(
            entry_points=[CommandHandler('start',self.start)],
            states={
                S_OB_NAME:    [MessageHandler(filters.TEXT&~filters.COMMAND,self.ob_name)],
                S_OB_DAILY:   [MessageHandler(filters.TEXT&~filters.COMMAND,self.ob_daily)],
                S_OB_MONTHLY: [MessageHandler(filters.TEXT&~filters.COMMAND,self.ob_monthly)],
            },
            fallbacks=[CommandHandler('cancel',self.cancel)],
        )
        add_exp=ConversationHandler(
            entry_points=[CallbackQueryHandler(self.exp_start,pattern='^add_expense$')],
            states={
                S_AMT:        [MessageHandler(filters.TEXT&~filters.COMMAND,self.exp_amt)],
                S_CAT:        [CallbackQueryHandler(self.exp_cat,pattern='^cat_'),
                               CallbackQueryHandler(self.exp_cat_confirm,pattern='^aicat_'),
                               CallbackQueryHandler(self.exp_cat_manual,pattern='^manual_cat$')],
                S_DESC:       [MessageHandler(filters.TEXT&~filters.COMMAND,self.exp_desc)],
            },
            fallbacks=[CommandHandler('cancel',self.cancel)],
        )
        # ── OWNER LOGIN — ConversationHandler terpisah & independen ──
        owner_conv=ConversationHandler(
            entry_points=[CommandHandler('owner',self.owner_cmd)],
            states={
                S_OWN_USR: [MessageHandler(filters.TEXT&~filters.COMMAND,self.owner_usr)],
                S_OWN_PWD: [MessageHandler(filters.TEXT&~filters.COMMAND,self.owner_pwd)],
            },
            fallbacks=[CommandHandler('cancel',self.cancel)],
            allow_reentry=True,
        )
        self.app.add_handler(onboard)
        self.app.add_handler(add_exp)
        self.app.add_handler(owner_conv)           # ← owner login
        self.app.add_handler(CommandHandler('menu', self.menu))
        self.app.add_handler(CommandHandler('help', self.help_cmd))
        self.app.add_handler(CommandHandler('cancel',self.cancel))
        self.app.add_handler(CallbackQueryHandler(self.cb_no_expense,  pattern='^no_expense$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_today,       pattern='^today$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_month,       pattern='^month$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_stats,       pattern='^stats$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_ach,         pattern='^achievements$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_settings,    pattern='^settings$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_themes,      pattern='^themes$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_apply_theme, pattern='^theme_'))
        self.app.add_handler(CallbackQueryHandler(self.cb_notif,       pattern='^toggle_notif$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_back,        pattern='^back$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_panel, pattern='^owner_panel$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_users, pattern='^owner_users$'))
        self.app.add_handler(CallbackQueryHandler(self.cb_owner_stats, pattern='^owner_stats$'))

    # ── START / ONBOARD ─────────────────────────────────────────
    async def start(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        user=u.effective_user
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT onboarding_completed FROM users WHERE user_id=?',(user.id,))
        row=c.fetchone(); conn.close()
        if row and row[0]==1:
            await self.menu(u,ctx); return ConversationHandler.END
        await u.message.reply_text(
            f"👋 Halo <b>{user.first_name}</b>!\n\n"
            f"Selamat datang di <b>CashKeeper</b> 💰\n"
            f"Bot pintar pencatat pengeluaran harian!\n\n"
            f"✨ Fitur unggulan:\n"
            f"🤖 AI deteksi kategori otomatis\n"
            f"🎨 5 Tema keren  🏆 Achievement seru\n"
            f"📊 Laporan lengkap  🔔 Smart reminder\n\n"
            f"<b>Dibuat oleh:</b> Lord Putra a.k.a Rahmet\n"
            f"@{OWNER_TG}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Pertama, <b>siapa nama kamu?</b> 😊",
            parse_mode='HTML')
        return S_OB_NAME

    async def ob_name(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        ctx.user_data['name']=u.message.text.strip()
        await u.message.reply_text(
            f"Halo <b>{ctx.user_data['name']}</b>! 😊\n\n"
            f"Berapa <b>budget harian</b> maksimal kamu?\n"
            f"(contoh: <code>100000</code>)\n\nKetik <code>0</code> jika tanpa limit",
            parse_mode='HTML')
        return S_OB_DAILY

    async def ob_daily(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        try:
            v=float(u.message.text.replace(',','').replace('.',''))
            if v<0: raise ValueError
            ctx.user_data['daily']=v
            await u.message.reply_text(
                f"✅ Budget harian: <b>{fmt(v) if v>0 else 'Tanpa limit'}</b>\n\n"
                f"Berapa <b>budget bulanan</b> maksimal kamu?\n"
                f"(contoh: <code>3000000</code>)\n\nKetik <code>0</code> jika tanpa limit",
                parse_mode='HTML')
            return S_OB_MONTHLY
        except:
            await u.message.reply_text("❌ Angka tidak valid. Contoh: <code>100000</code>",parse_mode='HTML')
            return S_OB_DAILY

    async def ob_monthly(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        try:
            v=float(u.message.text.replace(',','').replace('.',''))
            if v<0: raise ValueError
            user=u.effective_user; name=ctx.user_data['name']; daily=ctx.user_data['daily']
            conn=sqlite3.connect(DB_FILE); c=conn.cursor()
            c.execute('INSERT OR REPLACE INTO users (user_id,username,first_name,display_name,daily_limit,monthly_limit,onboarding_completed) VALUES (?,?,?,?,?,?,1)',
                      (user.id,user.username,user.first_name,name,daily,v))
            for cn,cd in CATEGORY_KEYWORDS.items():
                c.execute('INSERT OR IGNORE INTO categories (user_id,name,emoji) VALUES (?,?,?)',(user.id,cn,cd['emoji']))
            conn.commit(); conn.close()
            await u.message.reply_text(
                f"🎉 <b>Setup Selesai!</b>\n\n"
                f"👤 Nama: <b>{name}</b>\n"
                f"📅 Budget Harian: <b>{fmt(daily) if daily>0 else 'Tanpa limit'}</b>\n"
                f"📆 Budget Bulanan: <b>{fmt(v) if v>0 else 'Tanpa limit'}</b>\n\n"
                f"🤖 <b>Fitur AI aktif!</b> Ketik pengeluaran dan bot akan deteksi kategori otomatis!\n\n"
                f"Gunakan menu di bawah untuk mulai! 🚀",
                parse_mode='HTML',reply_markup=main_kb(user.id))
            ctx.user_data.clear(); return ConversationHandler.END
        except:
            await u.message.reply_text("❌ Angka tidak valid. Contoh: <code>3000000</code>",parse_mode='HTML')
            return S_OB_MONTHLY

    async def menu(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        if u.callback_query:
            q=u.callback_query; await q.answer(); user=q.from_user
        else:
            user=u.effective_user
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT display_name,current_theme FROM users WHERE user_id=?',(user.id,))
        row=c.fetchone(); conn.close()
        if not row:
            if u.message: await self.start(u,ctx)
            return
        name,theme=row
        txt=f"{theme_hdr(theme)}\n\nHalo, <b>{name}</b>! 👋\n\nMau ngapain hari ini? 😊"
        kb=main_kb(user.id)
        if u.callback_query:
            await u.callback_query.edit_message_text(txt,parse_mode='HTML',reply_markup=kb)
        else:
            await u.message.reply_text(txt,parse_mode='HTML',reply_markup=kb)

    async def help_cmd(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        await u.message.reply_text(
            "📖 <b>Panduan CashKeeper</b>\n\n"
            "/start — Mulai & setup\n/menu — Menu utama\n"
            "/owner — Login owner panel\n/cancel — Batalkan\n\n"
            "🤖 <b>Fitur AI Kategori:</b>\n"
            "Ketik pengeluaran seperti <i>'16rb rokok'</i> dan bot otomatis menentukan kategorinya!\n\n"
            f"Dibuat oleh: Lord Putra a.k.a Rahmet @{OWNER_TG}",
            parse_mode='HTML',reply_markup=main_kb(u.effective_user.id))

    async def cancel(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        await u.message.reply_text("❌ Dibatalkan. Ketik /menu untuk kembali.",
            reply_markup=main_kb(u.effective_user.id))
        ctx.user_data.clear(); return ConversationHandler.END

    # ── TAMBAH PENGELUARAN (dengan AI) ──────────────────────────
    async def exp_start(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        await q.edit_message_text(
            "💰 <b>Tambah Pengeluaran</b>\n\n"
            "Ketik nominal + deskripsi sekaligus:\n\n"
            "🤖 <b>Contoh (AI auto-kategori):</b>\n"
            "• <code>16rb rokok</code>\n"
            "• <code>25000 grab ke kampus</code>\n"
            "• <code>50rb makan siang warteg</code>\n"
            "• <code>120000 beli baju shopee</code>\n\n"
            "Atau ketik angka saja untuk pilih kategori manual.\n\n"
            "Ketik /cancel untuk batal",
            parse_mode='HTML')
        return S_AMT

    def _parse_amount(self, text: str):
        """Parse angka dari teks seperti '16rb', '25k', '1.5jt', '50000'"""
        import re
        text = text.lower().strip()
        # cari angka dengan satuan
        m = re.search(r'([\d.,]+)\s*(rb|ribu|k|jt|juta|m|rp)?', text)
        if not m: return None, text
        num_str = m.group(1).replace(',','').replace('.','')
        try: num = float(num_str)
        except: return None, text
        satuan = (m.group(2) or '').strip()
        if satuan in ('rb','ribu','k'): num *= 1000
        elif satuan in ('jt','juta','m'): num *= 1_000_000
        # sisa teks setelah angka = deskripsi
        rest = text[m.end():].strip()
        if not rest:
            rest = text[:m.start()].strip()
        return num, rest

    async def exp_amt(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        raw = u.message.text.strip()
        amount, desc_raw = self._parse_amount(raw)

        if amount is None or amount <= 0:
            await u.message.reply_text(
                "❌ Nominal tidak valid!\n\n"
                "Contoh:\n• <code>16rb rokok</code>\n• <code>50000</code>\n• <code>25k grab</code>",
                parse_mode='HTML')
            return S_AMT

        ctx.user_data['amount'] = amount
        ctx.user_data['raw_input'] = raw

        # Jika ada deskripsi → coba AI deteksi
        if desc_raw:
            cat, em = ai_category(raw)  # analisis full input
            ctx.user_data['ai_cat'] = cat
            ctx.user_data['ai_em']  = em
            ctx.user_data['desc']   = desc_raw

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Ya, {em} {cat}", callback_data='aicat_yes')],
                [InlineKeyboardButton("📝 Pilih Kategori Sendiri", callback_data='manual_cat')],
            ])
            await u.message.reply_text(
                f"🤖 <b>AI Deteksi Kategori</b>\n\n"
                f"💰 Nominal: <b>{fmt(amount)}</b>\n"
                f"📝 Deskripsi: <i>{desc_raw}</i>\n\n"
                f"Kategori yang disarankan:\n"
                f"<b>{em} {cat}</b>\n\n"
                f"Apakah kategori ini sudah benar?",
                parse_mode='HTML', reply_markup=kb)
            return S_CAT
        else:
            # Tidak ada deskripsi → tampilkan pilihan kategori manual
            return await self._show_cat_keyboard(u, amount)

    async def exp_cat_confirm(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        """User setuju dengan kategori AI"""
        q=u.callback_query; await q.answer()
        cat = ctx.user_data['ai_cat']
        em  = ctx.user_data['ai_em']
        desc= ctx.user_data.get('desc','')
        ctx.user_data['category'] = cat
        ctx.user_data['category_em'] = em
        ctx.user_data['use_ai'] = True
        # Langsung simpan tanpa tanya deskripsi lagi
        await self._save_expense(u, ctx, desc=f"{desc} [AI]")
        return ConversationHandler.END

    async def exp_cat_manual(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        """User pilih manual"""
        q=u.callback_query; await q.answer()
        amount = ctx.user_data['amount']
        return await self._show_cat_keyboard(u, amount, edit=True)

    async def _show_cat_keyboard(self, u:Update, amount, edit=False):
        uid = u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT name,emoji FROM categories WHERE user_id=? ORDER BY name',(uid,))
        cats=c.fetchall(); conn.close()
        kb=[]; row=[]
        for nm,em in cats:
            row.append(InlineKeyboardButton(f"{em} {nm}",callback_data=f'cat_{nm}'))
            if len(row)==2: kb.append(row); row=[]
        if row: kb.append(row)
        txt=(f"💰 Nominal: <b>{fmt(amount)}</b>\n\nPilih kategori:")
        if edit and u.callback_query:
            await u.callback_query.edit_message_text(txt,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))
        else:
            await u.message.reply_text(txt,parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))
        return S_CAT

    async def exp_cat(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        cat=q.data.replace('cat_','')
        uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT emoji FROM categories WHERE user_id=? AND name=?',(uid,cat))
        r=c.fetchone(); conn.close()
        em=r[0] if r else '💰'
        ctx.user_data['category']=cat; ctx.user_data['category_em']=em
        await q.edit_message_text(
            f"✅ Nominal: <b>{fmt(ctx.user_data['amount'])}</b>\n"
            f"{em} Kategori: <b>{cat}</b>\n\n"
            f"Tambah deskripsi? (atau ketik <code>-</code> untuk skip)",
            parse_mode='HTML')
        return S_DESC

    async def exp_desc(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        desc='' if u.message.text=='-' else u.message.text
        await self._save_expense(u, ctx, desc=desc)
        return ConversationHandler.END

    async def _save_expense(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE, desc=''):
        uid=u.effective_user.id; amount=ctx.user_data['amount']
        cat=ctx.user_data['category']; em=ctx.user_data.get('category_em','💰')
        today=datetime.now().date()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('INSERT INTO expenses (user_id,amount,category,description,date) VALUES (?,?,?,?,?)',
                  (uid,amount,cat,desc,today))
        c.execute('UPDATE users SET last_active=? WHERE user_id=?',(today,uid))
        c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND date=?',(uid,today))
        total_today=c.fetchone()[0]
        c.execute('SELECT daily_limit,current_theme FROM users WHERE user_id=?',(uid,))
        row=c.fetchone(); daily_limit=row[0]; theme=row[1]
        conn.commit(); conn.close()
        new_ach=check_unlock(uid)
        ai_tag=" 🤖" if '[AI]' in desc else ""
        clean_desc=desc.replace(' [AI]','').replace('[AI]','').strip()
        txt=(f"✅ <b>Pengeluaran Tersimpan!{ai_tag}</b>\n\n"
             f"💰 {fmt(amount)}\n{em} {cat}\n"
             f"{f'📝 {clean_desc}' if clean_desc else ''}\n"
             f"📅 {today.strftime('%d %B %Y')}\n\n"
             f"━━━━━━━━━━━━━━━━\n"
             f"📊 <b>Total Hari Ini: {fmt(total_today)}</b>")
        if daily_limit>0:
            pct=(total_today/daily_limit)*100
            txt+=f"\n💳 {pct:.1f}% dari {fmt(daily_limit)}"
        txt+=motivation_msg(total_today,daily_limit)
        if new_ach:
            conn=sqlite3.connect(DB_FILE); c=conn.cursor()
            ph=','.join('?'*len(new_ach))
            c.execute(f'SELECT name,badge_emoji FROM achievements WHERE code IN ({ph})',new_ach)
            badges=c.fetchall(); conn.close()
            txt+="\n\n🎉 <b>Achievement Unlocked!</b>\n"
            for nm,bg in badges: txt+=f"{bg} {nm}\n"
        # kirim ke message atau callback
        if u.callback_query:
            await u.callback_query.edit_message_text(txt,parse_mode='HTML',reply_markup=main_kb(uid))
        else:
            await u.message.reply_text(txt,parse_mode='HTML',reply_markup=main_kb(uid))
        ctx.user_data.clear()

    # ── TIDAK ADA PENGELUARAN ────────────────────────────────────
    async def cb_no_expense(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        uid=u.effective_user.id; today=datetime.now().date()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        # Cek apakah sudah ada expense hari ini
        c.execute('SELECT COUNT(*) FROM expenses WHERE user_id=? AND date=?',(uid,today))
        exp_count=c.fetchone()[0]
        # Cek apakah sudah log no_expense hari ini
        c.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=? AND date=?',(uid,today))
        already=c.fetchone()[0]
        c.execute('SELECT display_name,current_theme FROM users WHERE user_id=?',(uid,))
        row=c.fetchone(); name=row[0]; theme=row[1]
        conn.close()

        if exp_count>0:
            await q.edit_message_text(
                f"{theme_hdr(theme)}\n\n"
                f"ℹ️ Kamu sudah punya {exp_count} pengeluaran hari ini.\n\n"
                f"Kamu tidak bisa log 'Tidak Ada Pengeluaran' jika sudah ada transaksi.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))
            return

        if already:
            await q.edit_message_text(
                f"{theme_hdr(theme)}\n\n"
                f"✅ Kamu sudah log hari ini sebagai hari tanpa belanja!\n"
                f"Tetap hemat ya {name}! 💪",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))
            return

        # Simpan no_expense_day
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('INSERT OR IGNORE INTO no_expense_days (user_id,date) VALUES (?,?)',(uid,today))
        c.execute('UPDATE users SET last_active=? WHERE user_id=?',(today,uid))
        conn.commit(); conn.close()
        new_ach=check_unlock(uid)
        txt=(f"{theme_hdr(theme)}\n\n"
             f"🎖️ <b>Hari Tanpa Belanja!</b>\n\n"
             f"Keren, {name}! Hari ini kamu tidak mengeluarkan uang sama sekali! 🌟\n\n"
             f"Ini adalah kebiasaan luar biasa untuk menghemat uang!\n"
             f"Terus pertahankan! 💪")
        if new_ach:
            conn=sqlite3.connect(DB_FILE); c=conn.cursor()
            ph=','.join('?'*len(new_ach))
            c.execute(f'SELECT name,badge_emoji FROM achievements WHERE code IN ({ph})',new_ach)
            badges=c.fetchall(); conn.close()
            txt+="\n\n🎉 <b>Achievement Unlocked!</b>\n"
            for nm,bg in badges: txt+=f"{bg} {nm}\n"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    # ── LAPORAN ─────────────────────────────────────────────────
    async def cb_today(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        uid=u.effective_user.id; today=datetime.now().date()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT e.amount,e.category,e.description,c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? AND e.date=? ORDER BY e.created_at DESC',(uid,today))
        exps=c.fetchall()
        c.execute('SELECT daily_limit,current_theme,display_name FROM users WHERE user_id=?',(uid,))
        row=c.fetchone(); daily_limit=row[0]; theme=row[1]; name=row[2]
        c.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=? AND date=?',(uid,today))
        no_exp=c.fetchone()[0]
        conn.close()
        total=sum(e[0] for e in exps); hdr=theme_hdr(theme)
        if not exps and no_exp:
            txt=(f"{hdr}\n\n📊 <b>Hari Ini</b> — {today.strftime('%d %B %Y')}\n\n"
                 f"🎖️ <b>{name} tidak belanja hari ini!</b>\n\nHebat! Kamu berhasil zero spending hari ini! 🌟")
        elif not exps:
            txt=(f"{hdr}\n\n📊 <b>Hari Ini</b> — {today.strftime('%d %B %Y')}\n\n"
                 f"Belum ada pengeluaran hari ini.\nYuk mulai catat atau klik '🚫 Tidak Ada Pengeluaran'!")
        else:
            txt=f"{hdr}\n\n📊 <b>Hari Ini</b> — {today.strftime('%d %B %Y')}\n\n"
            for amt,cat,desc,em in exps:
                em=em or '💰'
                clean=desc.replace(' [AI]','').replace('[AI]','').strip() if desc else ''
                ai_tag=' 🤖' if desc and '[AI]' in desc else ''
                txt+=f"{em} <b>{fmt(amt)}</b> — {cat}{ai_tag}\n"
                if clean: txt+=f"   <i>{clean}</i>\n"
            txt+=f"\n━━━━━━━━━━━━━━━━\n💰 <b>Total: {fmt(total)}</b>"
            if daily_limit>0:
                pct=(total/daily_limit)*100
                s="✅ Aman!" if total<daily_limit else "⚠️ Over!"
                txt+=f"\n💳 {pct:.1f}% dari {fmt(daily_limit)} — {s}"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    async def cb_month(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        uid=u.effective_user.id; now=datetime.now(); first=now.replace(day=1).date()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=? AND date>=?',(uid,first))
        total,count=c.fetchone(); total=total or 0; count=count or 0
        c.execute('SELECT e.category,SUM(e.amount),c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? AND e.date>=? GROUP BY e.category ORDER BY SUM(e.amount) DESC',(uid,first))
        cats=c.fetchall()
        c.execute('SELECT monthly_limit,current_theme FROM users WHERE user_id=?',(uid,))
        row=c.fetchone(); monthly_limit=row[0]; theme=row[1]
        c.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=? AND date>=?',(uid,first))
        no_days=c.fetchone()[0]
        conn.close()
        hdr=theme_hdr(theme)
        txt=f"{hdr}\n\n📅 <b>Bulan {now.strftime('%B %Y')}</b>\n\n"
        if no_days>0:
            txt+=f"🎖️ {no_days} hari tanpa belanja bulan ini!\n\n"
        if not cats:
            txt+="Belum ada pengeluaran bulan ini."
        else:
            txt+="<b>Breakdown Kategori:</b>\n\n"
            for cat,amt,em in cats:
                em=em or '💰'; pct=(amt/total*100) if total>0 else 0
                bar='█'*int(pct/10)+'░'*(10-int(pct/10))
                txt+=f"{em} <b>{cat}</b>\n   {fmt(amt)} ({pct:.1f}%)\n   {bar}\n\n"
            txt+=f"━━━━━━━━━━━━━━━━\n💰 <b>Total: {fmt(total)}</b>\n📝 {count} transaksi"
            if monthly_limit>0:
                pct=(total/monthly_limit)*100
                s="✅ Aman!" if total<monthly_limit else "⚠️ Over!"
                txt+=f"\n💳 {pct:.1f}% dari {fmt(monthly_limit)} — {s}"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    async def cb_stats(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        uid=u.effective_user.id; now=datetime.now(); today=now.date(); first=now.replace(day=1).date()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=?',(uid,))
        ta,ca=c.fetchone(); ta=ta or 0; ca=ca or 0
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=? AND date>=?',(uid,first))
        tm,cm=c.fetchone(); tm=tm or 0; cm=cm or 0
        c.execute('SELECT SUM(amount),COUNT(*) FROM expenses WHERE user_id=? AND date=?',(uid,today))
        tt,ct=c.fetchone(); tt=tt or 0; ct=ct or 0
        c.execute('SELECT e.category,SUM(e.amount),c.emoji FROM expenses e LEFT JOIN categories c ON e.category=c.name AND e.user_id=c.user_id WHERE e.user_id=? GROUP BY e.category ORDER BY SUM(e.amount) DESC LIMIT 1',(uid,))
        top=c.fetchone()
        c.execute('SELECT COUNT(DISTINCT date) FROM expenses WHERE user_id=?',(uid,))
        days=c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=?',(uid,))
        no_days=c.fetchone()[0]
        c.execute('SELECT current_theme FROM users WHERE user_id=?',(uid,))
        theme=c.fetchone()[0]; conn.close()
        hdr=theme_hdr(theme)
        txt=(f"{hdr}\n\n📈 <b>Statistik Kamu</b>\n\n"
             f"<b>📊 Hari Ini:</b>\n💰 {fmt(tt)} ({ct} transaksi)\n\n"
             f"<b>📅 Bulan Ini:</b>\n💰 {fmt(tm)} ({cm} transaksi)\n"
             f"{f'📊 Rata-rata: {fmt(tm/now.day)}/hari' if cm>0 else ''}\n\n"
             f"<b>🎯 All Time:</b>\n💰 {fmt(ta)} ({ca} transaksi)\n"
             f"📅 Aktif {days} hari | 🎖️ {no_days} hari zero spending")
        if top:
            em=top[2] or '💰'
            txt+=f"\n\n<b>🏆 Kategori Terbesar:</b>\n{em} {top[0]} — {fmt(top[1])}"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    async def cb_ach(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT a.name,a.badge_emoji,a.description,a.difficulty,ua.unlocked_at FROM user_achievements ua JOIN achievements a ON ua.achievement_code=a.code WHERE ua.user_id=? ORDER BY ua.unlocked_at DESC',(uid,))
        unlocked=c.fetchall()
        c.execute('SELECT COUNT(*) FROM achievements')
        total=c.fetchone()[0]
        c.execute('SELECT current_theme FROM users WHERE user_id=?',(uid,))
        theme=c.fetchone()[0]; conn.close()
        hdr=theme_hdr(theme); cnt=len(unlocked); pct=(cnt/total*100) if total>0 else 0
        bar='█'*int(pct/10)+'░'*(10-int(pct/10))
        txt=f"{hdr}\n\n🏆 <b>Achievement & Badge</b>\n\n📊 {cnt}/{total} ({pct:.1f}%)\n{bar}\n\n"
        diff_map={'easy':'⭐','medium':'⭐⭐','hard':'⭐⭐⭐','ultra_hard':'👑'}
        if unlocked:
            txt+="<b>🎉 Badge yang Diraih:</b>\n\n"
            for nm,bg,desc,diff,at in unlocked:
                d=datetime.fromisoformat(at).strftime('%d/%m/%Y')
                txt+=f"{bg} <b>{nm}</b> {diff_map.get(diff,'⭐')}\n   <i>{desc}</i>\n   📅 {d}\n\n"
        else:
            txt+="Belum ada badge 😅\n\nTips:\n💡 Catat pengeluaran → 🌟\n💡 Aktif 7 hari → 📅\n💡 Hemat budget → 💚\n💡 Pakai AI kategori 5x → 🤖"
        if cnt<total:
            txt+=f"\n🎯 Masih ada <b>{total-cnt} badge</b> lagi! Semangat! 💪"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    # ── SETTINGS & TEMA ─────────────────────────────────────────
    async def cb_settings(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer(); uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT notification_enabled,display_name,daily_limit,monthly_limit,current_theme FROM users WHERE user_id=?',(uid,))
        notif,name,daily,monthly,theme=c.fetchone(); conn.close()
        hdr=theme_hdr(theme); tn=THEMES.get(theme,THEMES['default'])['name']
        txt=(f"{hdr}\n\n⚙️ <b>Pengaturan</b>\n\n"
             f"👤 Nama: <b>{name}</b>\n"
             f"📅 Budget Harian: <b>{fmt(daily) if daily>0 else 'Tidak ada'}</b>\n"
             f"📆 Budget Bulanan: <b>{fmt(monthly) if monthly>0 else 'Tidak ada'}</b>\n\n"
             f"🎨 Tema: <b>{tn}</b>\n"
             f"🔔 Notifikasi: <b>{'🔔 Aktif' if notif else '🔕 Nonaktif'}</b>\n\n"
             f"Reminder dikirim jam 20:00 jika belum input hari ini")
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎨 Ganti Tema",callback_data='themes')],
                [InlineKeyboardButton("🔄 Toggle Notifikasi",callback_data='toggle_notif')],
                [InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    async def cb_themes(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer(); uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT current_theme FROM users WHERE user_id=?',(uid,))
        cur=c.fetchone()[0]; conn.close()
        kb=[]
        for code,data in THEMES.items():
            mark=" ✅" if code==cur else ""
            kb.append([InlineKeyboardButton(f"{data['emoji']} {data['name']}{mark}",callback_data=f'theme_{code}')])
        kb.append([InlineKeyboardButton("🔙 Pengaturan",callback_data='settings')])
        await q.edit_message_text(
            "🎨 <b>Pilih Tema Favoritmu!</b>\n\n"
            "💖 Pink Cute — lucu & imut buat cewek\n"
            "🌙 Dark Mode — gelap & keren\n"
            "✨ Neon Vibes — Gen Z vibes!\n"
            "🌿 Nature — natural & calming\n"
            "🏠 Classic — elegan & bersih",
            parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))

    async def cb_apply_theme(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        code=q.data.replace('theme_',''); uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('UPDATE users SET current_theme=? WHERE user_id=?',(code,uid))
        conn.commit(); conn.close()
        nm=THEMES.get(code,THEMES['default'])['name']
        await q.answer(f"✨ Tema berubah ke {nm}!",show_alert=True)
        await self.cb_settings(u,ctx)

    async def cb_notif(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer(); uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('UPDATE users SET notification_enabled=1-notification_enabled WHERE user_id=?',(uid,))
        c.execute('SELECT notification_enabled FROM users WHERE user_id=?',(uid,))
        new=c.fetchone()[0]; conn.commit(); conn.close()
        await q.answer(f"Notifikasi {'diaktifkan 🔔' if new else 'dinonaktifkan 🔕'}",show_alert=True)
        await self.cb_settings(u,ctx)

    async def cb_back(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        await self.menu(u,ctx)

    # ── OWNER PANEL ─────────────────────────────────────────────
    async def owner_cmd(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        """Entry point /owner — selalu tanya username dulu"""
        uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT is_owner FROM users WHERE user_id=?',(uid,))
        row=c.fetchone(); conn.close()
        # Jika sudah owner, tampilkan panel langsung
        if row and row[0]==1:
            await u.message.reply_text(
                "👑 <b>Selamat datang kembali, Owner!</b>\n\nGunakan tombol Owner Panel di menu.",
                parse_mode='HTML',reply_markup=main_kb(uid))
            return ConversationHandler.END
        # Belum owner → minta login
        await u.message.reply_text(
            "👑 <b>Owner Login</b>\n\n"
            "Masukkan <b>username</b> owner:\n\n"
            "Ketik /cancel untuk batal",
            parse_mode='HTML')
        return S_OWN_USR

    async def owner_usr(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        if u.message.text.strip()==OWNER_USR:
            await u.message.reply_text(
                "✅ Username benar!\n\nSekarang masukkan <b>password</b>:",
                parse_mode='HTML')
            return S_OWN_PWD
        await u.message.reply_text(
            "❌ Username salah! Akses ditolak.\n\nKetik /owner untuk coba lagi.")
        return ConversationHandler.END

    async def owner_pwd(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        if u.message.text.strip()==OWNER_PWD:
            uid=u.effective_user.id
            conn=sqlite3.connect(DB_FILE); c=conn.cursor()
            c.execute('UPDATE users SET is_owner=1 WHERE user_id=?',(uid,))
            conn.commit(); conn.close()
            await u.message.reply_text(
                "✅ <b>Login Berhasil!</b>\n\n"
                "Selamat datang, Owner Lord Putra! 👑\n\n"
                "Tombol Owner Panel sekarang muncul di menu utama.",
                parse_mode='HTML',reply_markup=main_kb(uid))
            return ConversationHandler.END
        await u.message.reply_text(
            "❌ Password salah! Akses ditolak.\n\nKetik /owner untuk coba lagi.")
        return ConversationHandler.END

    async def cb_owner_panel(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer(); uid=u.effective_user.id
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('SELECT is_owner FROM users WHERE user_id=?',(uid,))
        r=c.fetchone()
        if not r or r[0]!=1:
            await q.answer("❌ Akses ditolak!",show_alert=True); conn.close(); return
        c.execute('SELECT COUNT(*) FROM users WHERE onboarding_completed=1')
        tu=c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM expenses')
        te=c.fetchone()[0]
        c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses')
        ta=c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM user_achievements')
        tb=c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM no_expense_days')
        tzs=c.fetchone()[0]
        conn.close()
        txt=(f"👑 <b>OWNER PANEL</b>\n"
             f"Lord Putra a.k.a Rahmet\n\n"
             f"<b>📊 Statistik Global:</b>\n"
             f"👥 Total User: <b>{tu}</b>\n"
             f"📝 Total Transaksi: <b>{te}</b>\n"
             f"💰 Total Pengeluaran: <b>{fmt(ta)}</b>\n"
             f"🏆 Total Badge: <b>{tb}</b>\n"
             f"🎖️ Total Zero-Spend Log: <b>{tzs}</b>")
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Daftar User",callback_data='owner_users')],
                [InlineKeyboardButton("📈 Statistik Detail",callback_data='owner_stats')],
                [InlineKeyboardButton("🔙 Menu",callback_data='back')]]))

    async def cb_owner_users(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        c.execute('''SELECT u.user_id,u.display_name,u.username,COUNT(e.id),
                     COALESCE(SUM(e.amount),0),u.created_at,u.current_theme
                     FROM users u LEFT JOIN expenses e ON u.user_id=e.user_id
                     WHERE u.onboarding_completed=1
                     GROUP BY u.user_id ORDER BY COUNT(e.id) DESC LIMIT 15''')
        users=c.fetchall(); conn.close()
        txt="👑 <b>OWNER — Daftar User</b>\n\n"
        for i,(uid2,name,uname,cnt,amt,created,theme) in enumerate(users,1):
            un=f"@{uname}" if uname else "no username"
            d=datetime.fromisoformat(created).strftime('%d/%m/%y')
            thm=THEMES.get(theme,THEMES['default'])['emoji']
            txt+=f"{i}. {thm} <b>{name}</b> ({un})\n   📝 {cnt} | 💰 {fmt(amt)} | 📅 {d}\n\n"
        if not users: txt+="Belum ada user."
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Owner Panel",callback_data='owner_panel')]]))

    async def cb_owner_stats(self, u:Update, ctx:ContextTypes.DEFAULT_TYPE):
        q=u.callback_query; await q.answer()
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        today=datetime.now().date(); first=today.replace(day=1)
        c.execute('SELECT COUNT(DISTINCT user_id),COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE date=?',(today,))
        du,de,da=c.fetchone()
        c.execute('SELECT COUNT(DISTINCT user_id),COUNT(*),COALESCE(SUM(amount),0) FROM expenses WHERE date>=?',(first,))
        mu,me,ma=c.fetchone()
        c.execute('SELECT category,COUNT(*),SUM(amount) FROM expenses GROUP BY category ORDER BY COUNT(*) DESC LIMIT 3')
        tops=c.fetchall()
        c.execute('SELECT COUNT(*) FROM no_expense_days WHERE date=?',(today,))
        zd=c.fetchone()[0]
        conn.close()
        txt=(f"👑 <b>OWNER — Statistik Detail</b>\n\n"
             f"<b>📊 Hari Ini:</b>\n"
             f"👥 {du} aktif | 📝 {de} transaksi | 💰 {fmt(da)}\n"
             f"🎖️ {zd} user zero spending\n\n"
             f"<b>📅 Bulan Ini:</b>\n"
             f"👥 {mu} aktif | 📝 {me} transaksi | 💰 {fmt(ma)}\n\n"
             f"<b>🏆 Kategori Terpopuler:</b>\n")
        for cat,cnt,amt in tops:
            txt+=f"• {cat} — {cnt}x ({fmt(amt)})\n"
        await q.edit_message_text(txt,parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Owner Panel",callback_data='owner_panel')]]))

    # ── NOTIFIKASI ───────────────────────────────────────────────
    async def send_reminders(self):
        conn=sqlite3.connect(DB_FILE); c=conn.cursor()
        today=datetime.now().date()
        c.execute('SELECT user_id,display_name,current_theme FROM users WHERE notification_enabled=1 AND onboarding_completed=1')
        users=c.fetchall(); conn.close()
        for uid,name,theme in users:
            conn2=sqlite3.connect(DB_FILE); c2=conn2.cursor()
            c2.execute('SELECT COUNT(*) FROM expenses WHERE user_id=? AND date=?',(uid,today))
            exp=c2.fetchone()[0]
            c2.execute('SELECT COUNT(*) FROM no_expense_days WHERE user_id=? AND date=?',(uid,today))
            nod=c2.fetchone()[0]
            conn2.close()
            if exp==0 and nod==0:
                try:
                    await self.app.bot.send_message(chat_id=uid,
                        text=(f"{theme_hdr(theme)}\n\n"
                              f"🔔 <b>Pengingat!</b>\n\n"
                              f"Halo {name}! 👋\n\n"
                              f"Kamu belum catat pengeluaran hari ini.\n"
                              f"Yuk catat, atau klik '🚫 Tidak Ada Pengeluaran' jika memang tidak belanja! 💪"),
                        parse_mode='HTML',reply_markup=main_kb(uid))
                except Exception as e:
                    print(f"Reminder error {uid}: {e}")

    def _sched(self):
        schedule.every().day.at("20:00").do(
            lambda: self.app.create_task(self.send_reminders()))
        while True: schedule.run_pending(); time.sleep(60)

    def run(self):
        threading.Thread(target=self._sched,daemon=True).start()
        print("="*52)
        print("  🚀 CashKeeper Bot Started!")
        print("  🤖 AI Auto-Category: AKTIF")
        print("  🚫 Zero Spending Log: AKTIF")
        print("  👑 Owner: lordputra")
        print(f"  📱 @{OWNER_TG}")
        print("="*52)
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

CashKeeper(TOKEN).run()
