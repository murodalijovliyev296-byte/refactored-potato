import os
import re
import sqlite3
import threading
import time
import telebot
from telebot import types
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@kanalingiz_username")
CARD_NUMBER = os.environ.get("CARD_NUMBER", "8600 0000 0000 0000")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "mehnat_uz_ish_bot")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "adminusername")
SUPPORT_PHONE = os.environ.get("SUPPORT_PHONE", "+998901234567")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot ishlayapti!"


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


DB_PATH = "bot.db"


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT, age TEXT, phone TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, location TEXT, salary TEXT,
        employer_phone TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS applications (
        app_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER, user_id INTEGER,
        status TEXT DEFAULT 'waiting_payment',
        created_at INTEGER
    )""")
    conn.commit()
    conn.close()


init_db()

state = {}


def get_user(user_id):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def save_user(user_id, name, age, phone):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO users (user_id, name, age, phone) VALUES (?,?,?,?)",
        (user_id, name, age, phone),
    )
    conn.commit()
    conn.close()


def get_job(job_id):
    conn = db()
    row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    return row


def add_job(title, location, salary, employer_phone):
    conn = db()
    cur = conn.execute(
        "INSERT INTO jobs (title, location, salary, employer_phone) VALUES (?,?,?,?)",
        (title, location, salary, employer_phone),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def create_application(job_id, user_id):
    conn = db()
    cur = conn.execute(
        "INSERT INTO applications (job_id, user_id, status, created_at) VALUES (?,?,?,?)",
        (job_id, user_id, "waiting_payment", int(time.time())),
    )
    conn.commit()
    app_id = cur.lastrowid
    conn.close()
    return app_id


def update_application_status(app_id, status):
    conn = db()
    conn.execute("UPDATE applications SET status=? WHERE app_id=?", (status, app_id))
    conn.commit()
    conn.close()


def get_application(app_id):
    conn = db()
    row = conn.execute("SELECT * FROM applications WHERE app_id=?", (app_id,)).fetchone()
    conn.close()
    return row


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✏️ Ma'lumotlarni o'zgartirish")
    kb.row("📋 Mening arizalarim")
    kb.row("🆘 Qo'llab-quvvatlash")
    return kb


def status_label(s):
    return {
        "waiting_payment": "⏳ To'lov kutilmoqda",
        "checking": "🔎 Tekshirilmoqda",
        "approved": "✅ Tasdiqlangan",
        "rejected": "❌ Rad etilgan",
        "cancelled": "🚫 Bekor qilingan",
        "expired": "⏱ Muddati tugagan",
    }.get(s, s)


def get_user_applications(user_id):
    conn = db()
    rows = conn.execute(
        "SELECT a.app_id, a.status, j.title FROM applications a "
        "JOIN jobs j ON j.job_id = a.job_id WHERE a.user_id=? ORDER BY a.app_id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


@bot.message_handler(func=lambda m: m.text == "📋 Mening arizalarim")
def my_applications(message):
    uid = message.chat.id
    apps = get_user_applications(uid)
    if not apps:
        bot.send_message(uid, "Sizda hali arizalar yo'q.")
        return
    for a in apps:
        text = f"💼 {a['title']}\nHolat: {status_label(a['status'])}"
        markup = None
        if a["status"] in ("waiting_payment", "checking"):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ Ishni bekor qilish", callback_data=f"cancel_{a['app_id']}"))
        bot.send_message(uid, text, reply_markup=markup)


def ask_name(chat_id):
    state[chat_id] = {"step": "reg_name", "data": {}}
    bot.send_message(chat_id, "👤 Ismingizni kiriting:")


def is_registered(user_id):
    return get_user(user_id) is not None


@bot.message_handler(commands=["start"])
def start(message):
    uid = message.chat.id
    args = message.text.split(maxsplit=1)
    pending_job = None
    if len(args) > 1 and args[1].startswith("job_"):
        try:
            pending_job = int(args[1].replace("job_", ""))
        except ValueError:
            pending_job = None

    if not is_registered(uid):
        state.setdefault(uid, {})
        if pending_job:
            state[uid]["pending_job"] = pending_job
        ask_name(uid)
        return

    if pending_job:
        show_job(uid, pending_job)
    else:
        bot.send_message(uid, "Assalomu alaykum! 👋 Quyidagi menyudan foydalaning.", reply_markup=main_menu())


@bot.message_handler(func=lambda m: state.get(m.chat.id, {}).get("step") == "reg_name")
def reg_name(message):
    uid = message.chat.id
    state[uid]["data"]["name"] = message.text.strip()
    state[uid]["step"] = "reg_age"
    bot.send_message(uid, "🎂 Yoshingizni kiriting (raqamda):")


@bot.message_handler(func=lambda m: state.get(m.chat.id, {}).get("step") == "reg_age")
def reg_age(message):
    uid = message.chat.id
    if not message.text.strip().isdigit():
        bot.send_message(uid, "Iltimos, yoshni faqat raqamda kiriting (masalan: 25):")
        return
    state[uid]["data"]["age"] = message.text.strip()
    state[uid]["step"] = "reg_phone"
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    bot.send_message(uid, "📞 Telefon raqamingizni yuboring:", reply_markup=kb)


@bot.message_handler(content_types=["contact"])
def reg_phone_contact(message):
    uid = message.chat.id
    if state.get(uid, {}).get("step") != "reg_phone":
        return
    finish_registration(uid, message.contact.phone_number)


@bot.message_handler(func=lambda m: state.get(m.chat.id, {}).get("step") == "reg_phone")
def reg_phone_text(message):
    uid = message.chat.id
    text = message.text.strip()
    if not re.match(r"^\+?\d{9,15}$", text):
        bot.send_message(uid, "Raqamni to'g'ri kiriting (masalan: +998901234567) yoki tugmadan foydalaning.")
        return
    finish_registration(uid, text)


def finish_registration(uid, phone):
    data = state[uid]["data"]
    save_user(uid, data["name"], data["age"], phone)
    pending_job = state[uid].get("pending_job")
    state.pop(uid, None)
    bot.send_message(uid, "✅ Ma'lumotlaringiz saqlandi!", reply_markup=main_menu())
    if pending_job:
        show_job(uid, pending_job)


@bot.message_handler(func=lambda m: m.text == "✏️ Ma'lumotlarni o'zgartirish")
def edit_profile(message):
    ask_name(message.chat.id)


@bot.message_handler(func=lambda m: m.text == "🆘 Qo'llab-quvvatlash")
def support(message):
    uid = message.chat.id
    text = f"👤 Admin: @{ADMIN_USERNAME}\n📞 Telefon: {SUPPORT_PHONE}"
    bot.send_message(uid, text)


def show_job(uid, job_id):
    j = get_job(job_id)
    if not j:
        bot.send_message(uid, "Bu ish topilmadi yoki o'chirilgan.")
        return
    text = f"💼 {j['title']}\n📍 {j['location']}\n💰 {j['salary']}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Ishga yozilish", callback_data=f"apply_{job_id}"))
    bot.send_message(uid, text, reply_markup=markup)


@bot.message_handler(commands=["addjob"])
def addjob(message):
    if message.chat.id != ADMIN_ID:
        return
    state[ADMIN_ID] = {"step": "job_title", "data": {}}
   
