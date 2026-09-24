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
    kb.row("📢 Ishlarni ko'rish")
    return kb


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


@bot.message_handler(func=lambda m: m.text == "📢 Ishlarni ko'rish")
def view_jobs(message):
    uid = message.chat.id
    conn = db()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY job_id DESC LIMIT 10").fetchall()
    conn.close()
    if not jobs:
        bot.send_message(uid, "Hozircha ishlar yo'q.")
        return
    for j in jobs:
        text = f"💼 {j['title']}\n📍 {j['location']}\n💰 {j['salary']}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Ishga yozilish", callback_data=f"apply_{j['job_id']}"))
        bot.send_message(uid, text, reply_markup=markup)


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
    bot.send_message(ADMIN_ID, "💼 Ish nomini kiriting:")


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and state.get(ADMIN_ID, {}).get("step") == "job_title")
def job_title(message):
    state[ADMIN_ID]["data"]["title"] = message.text.strip()
    state[ADMIN_ID]["step"] = "job_location"
    bot.send_message(ADMIN_ID, "📍 Ish joyi manzilini kiriting:")


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and state.get(ADMIN_ID, {}).get("step") == "job_location")
def job_location(message):
    state[ADMIN_ID]["data"]["location"] = message.text.strip()
    state[ADMIN_ID]["step"] = "job_salary"
    bot.send_message(ADMIN_ID, "💰 Ish haqi va ish vaqtini kiriting (masalan: 3 mln so'm, 9:00-18:00):")


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and state.get(ADMIN_ID, {}).get("step") == "job_salary")
def job_salary(message):
    state[ADMIN_ID]["data"]["salary"] = message.text.strip()
    state[ADMIN_ID]["step"] = "job_phone"
    bot.send_message(ADMIN_ID, "📞 Ish beruvchi telefon raqamini kiriting:")


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and state.get(ADMIN_ID, {}).get("step") == "job_phone")
def job_phone(message):
    d = state[ADMIN_ID]["data"]
    d["phone"] = message.text.strip()
    job_id = add_job(d["title"], d["location"], d["salary"], d["phone"])
    state.pop(ADMIN_ID, None)

    text = f"💼 {d['title']}\n📍 {d['location']}\n💰 {d['salary']}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "✅ Ishga yozilish",
        url=f"https://t.me/{BOT_USERNAME}?start=job_{job_id}",
    ))
    bot.send_message(CHANNEL_ID, text, reply_markup=markup)
    bot.send_message(ADMIN_ID, "✅ Ish e'lon qilindi va kanalga joylandi.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("apply_"))
def apply_job(call):
    uid = call.from_user.id
    job_id = int(call.data.replace("apply_", ""))
    if not is_registered(uid):
        state[uid] = {"step": "reg_name", "data": {}, "pending_job": job_id}
        bot.send_message(uid, "Avval ro'yxatdan o'ting.\n👤 Ismingizni kiriting:")
        bot.answer_callback_query(call.id)
        return

    app_id = create_application(job_id, uid)
    text = (
        f"💳 To'lov uchun karta: {CARD_NUMBER}\n\n"
        f"To'lovni amalga oshirib, chekni (screenshot yoki rasm) shu yerga yuboring.\n"
        f"⏱ Sizda 3 daqiqa vaqt bor, aks holda ariza avtomatik bekor qilinadi."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Ishni bekor qilish", callback_data=f"cancel_{app_id}"))
    bot.send_message(uid, text, reply_markup=markup)
    state[uid] = {"step": "waiting_receipt", "app_id": app_id}
    bot.answer_callback_query(call.id)

    threading.Timer(180, expire_application, args=(uid, app_id)).start()


def expire_application(uid, app_id):
    a = get_application(app_id)
    if a and a["status"] == "waiting_payment":
        update_application_status(app_id, "expired")
        if state.get(uid, {}).get("app_id") == app_id:
            state.pop(uid, None)
        try:
            bot.send_message(uid, "⏱ Vaqt tugadi, ariza bekor qilindi. Qayta urinib ko'rishingiz mumkin.")
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cancel_application(call):
    uid = call.from_user.id
    app_id = int(call.data.replace("cancel_", ""))
    a = get_application(app_id)
    if a and a["status"] == "waiting_payment":
        update_application_status(app_id, "cancelled")
        state.pop(uid, None)
        bot.send_message(uid, "❌ Ariza bekor qilindi.")
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["photo"])
def receive_receipt(message):
    uid = message.chat.id
    st = state.get(uid)
    if not st or st.get("step") != "waiting_receipt":
        return
    app_id = st["app_id"]
    a = get_application(app_id)
    if not a or a["status"] != "waiting_payment":
        bot.send_message(uid, "Bu ariza uchun vaqt tugagan yoki bekor qilingan.")
        return

    update_application_status(app_id, "checking")
    state.pop(uid, None)

    job = get_job(a["job_id"])
    user = get_user(uid)
    caption = (
        f"🧾 Yangi chek (ariza #{app_id})\n"
        f"👤 {user['name']}, {user['age']} yosh\n"
        f"📞 {user['phone']}\n"
        f"💼 Ish: {job['title']}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"payok_{app_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"payno_{app_id}"),
    )
    bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=markup)
    bot.send_message(uid, "✅ Chek qabul qilindi, admin tekshirmoqda...")


@bot.callback_query_handler(func=lambda call: call.data.startswith(("payok_", "payno_")))
def admin_review_payment(call):
    action, app_id_str = call.data.split("_")
    app_id = int(app_id_str)
    a = get_application(app_id)
    if not a:
        bot.answer_callback_query(call.id, "Topilmadi.")
        return

    job = get_job(a["job_id"])
    uid = a["user_id"]

    if action == "payok":
        update_application_status(app_id, "approved")
        bot.send_message(uid, f"🎉 To'lovingiz tasdiqlandi!\n📞 Ish beruvchi raqami: {job['employer_phone']}")
        bot.edit_message_caption(f"✅ TASDIQLANDI (#{app_id})", call.message.chat.id, call.message.message_id)
    else:
        update_application_status(app_id, "rejected")
        bot.send_message(uid, "❌ To'lovingiz tasdiqlanmadi. Qayta urinib ko'ring yoki admin bilan bog'laning.")
        bot.edit_message_caption(f"❌ RAD ETILDI (#{app_id})", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id, "Qabul qilindi.")


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.chat.id not in state, content_types=["text"])
def admin_direct_post(message):
    if message.text.startswith("/"):
        return
    bot.send_message(CHANNEL_ID, message.text)
    bot.reply_to(message, "✅ To'g'ridan-to'g'ri kanalga joylandi.")


print("Bot ishga tushdi...")
threading.Thread(target=run_web_server).start()
bot.infinity_polling()
