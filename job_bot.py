"""
ISH E'LONLARI BOTI
-------------------
Foydalanuvchi botga ish e'loni (oddiy matn) yuboradi.
Admin uni ko'radi, tasdiqlasa yoki rad etsa bo'ladi.
Tasdiqlangan e'lon avtomatik kanalga chiqadi.

ADMIN uchun: agar SIZ botga to'g'ridan-to'g'ri xabar yozsangiz,
u tasdiqsiz, darhol kanalga chiqadi (chunki siz o'zingiz adminsiz).

O'RNATISH (Termux - telefonda ishlatish uchun):
1) Termux ilovasini o'rnating (Google Play yoki F-Droid).
2) Termux ichida quyidagilarni yozing:
   pkg update && pkg install python -y
   pip install pyTelegramBotAPI
3) Shu faylni telefoningizga saqlang (masalan job_bot.py nomi bilan).
4) Pastdagi 3 ta sozlamani to'ldiring (BOT_TOKEN, ADMIN_ID, CHANNEL_ID).
5) Termuxda ishga tushiring:  python job_bot.py

BOT_TOKEN olish: Telegramda @BotFather ga yozing -> /newbot
ADMIN_ID olish: Telegramda @userinfobot ga yozing, u sizga ID beradi
CHANNEL_ID: kanalingiz username bo'lsa "@kanalim" deb yozasiz.
            Botni albatta kanalingizga ADMIN qilib qo'shing (post joylash huquqi bilan)!
"""

import os
import threading
import telebot
from telebot import types
from flask import Flask

# ============ SOZLAMALAR ============
# Render'da bularni "Environment Variables" qismiga qo'shasiz (pastdagi
# qo'riqchi qiymatlar faqat Termuxda sinash uchun, Render'da ishlatilmaydi).
BOT_TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@kanalingiz_username")
# =====================================

bot = telebot.TeleBot(BOT_TOKEN)

# --- Render kabi bepul serverlar bot "tirikligini" tekshirish uchun
# HTTP so'rov yuboradi. Shuning uchun kichik veb-server ochamiz. ---
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot ishlayapti!"


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Tasdiqlash kutayotgan e'lonlar shu yerda vaqtincha saqlanadi
pending = {}  # {submission_id: {"user_id": ..., "text": ...}}
next_id = 1


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! 👋\n\n"
        "Ish e'loningizni shu yerga oddiy matn qilib yuboring.\n"
        "Men uni ko'rib chiqib, tasdiqlangandan so'ng kanalga joylayman."
    )


@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID, content_types=["text"])
def admin_direct_post(message):
    # Admin botga to'g'ridan-to'g'ri yozsa, tasdiqsiz kanalga chiqadi
    bot.send_message(CHANNEL_ID, message.text)
    bot.reply_to(message, "✅ To'g'ridan-to'g'ri kanalga joylandi.")


@bot.message_handler(func=lambda m: m.chat.id != ADMIN_ID, content_types=["text"])
def receive_job_post(message):
    global next_id
    sub_id = next_id
    next_id += 1
    pending[sub_id] = {"user_id": message.chat.id, "text": message.text}

    # Foydalanuvchiga tasdiq
    bot.reply_to(message, "✅ E'loningiz qabul qilindi, admin tasdiqlashini kuting.")

    # Adminga yuborish, tugmalar bilan
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{sub_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{sub_id}"),
    )
    bot.send_message(
        ADMIN_ID,
        f"🆕 Yangi e'lon (#{sub_id}):\n\n{message.text}",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def handle_decision(call):
    action, sub_id_str = call.data.split("_")
    sub_id = int(sub_id_str)
    sub = pending.pop(sub_id, None)

    if sub is None:
        bot.answer_callback_query(call.id, "Bu e'lon allaqachon ko'rib chiqilgan.")
        return

    if action == "approve":
        bot.send_message(CHANNEL_ID, sub["text"])
        bot.send_message(sub["user_id"], "🎉 E'loningiz kanalga joylandi!")
        bot.edit_message_text(
            f"✅ TASDIQLANDI (#{sub_id}):\n\n{sub['text']}",
            call.message.chat.id,
            call.message.message_id,
        )
    else:
        bot.send_message(sub["user_id"], "😔 Afsuski, e'loningiz rad etildi.")
        bot.edit_message_text(
            f"❌ RAD ETILDI (#{sub_id}):\n\n{sub['text']}",
            call.message.chat.id,
            call.message.message_id,
        )

    bot.answer_callback_query(call.id, "Qabul qilindi.")


print("Bot ishga tushdi...")
threading.Thread(target=run_web_server).start()
bot.infinity_polling()

0
