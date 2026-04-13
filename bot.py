import os, time, random, sqlite3
from flask import Flask
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *

TOKEN = os.getenv("TOKEN")

# =========================
# WEB SERVER (FIX TIMEOUT)
# =========================

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot running 😏"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    money INTEGER,
    xp INTEGER,
    level INTEGER,
    streak INTEGER,
    last_msg REAL,
    daily REAL
)
""")
conn.commit()

def get_user(uid):
    uid = str(uid)
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()

    if row:
        return {
            "money": row[1],
            "xp": row[2],
            "level": row[3],
            "streak": row[4],
            "last_msg": row[5],
            "daily": row[6]
        }

    cursor.execute("INSERT INTO users VALUES (?,0,0,1,0,0,0)", (uid,))
    conn.commit()
    return get_user(uid)

def save_user(uid, u):
    cursor.execute("""
    UPDATE users SET money=?, xp=?, level=?, streak=?, last_msg=?, daily=?
    WHERE user_id=?
    """, (
        u["money"], u["xp"], u["level"],
        u["streak"], u["last_msg"], u["daily"], str(uid)
    ))
    conn.commit()

# =========================
# LEVEL SYSTEM
# =========================

LEVELS = [
(1,0),(2,100),(3,250),(4,450),(5,700),
(6,1000),(7,1400),(8,1900),(9,2500),(10,3200),
(11,4000),(12,5000),(13,6200),(14,7500),(15,9000),
(16,11000),(17,13500),(18,16500),(19,20000),(20,25000)
]

def update_level(u):
    for lvl,xp in reversed(LEVELS):
        if u["xp"]>=xp:
            u["level"]=lvl

# =========================
# EARNING
# =========================

async def handle_msg(update: Update, ctx):
    u = get_user(update.effective_user.id)
    now = time.time()

    u["money"] += 1
    u["xp"] += 2

    if any(e in update.message.text for e in "😂😏😍🔥❤️"):
        u["money"] += 1
        u["xp"] += 2

    if now - u["last_msg"] < 60:
        u["streak"] += 1
        if u["streak"] == 5:
            u["money"] += 10
            u["xp"] += 15
    else:
        u["streak"] = 1

    u["last_msg"] = now

    update_level(u)
    save_user(update.effective_user.id, u)

async def handle_voice(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 5
    u["xp"] += 10
    update_level(u)
    save_user(update.effective_user.id, u)

async def handle_photo(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 40
    u["xp"] += 30
    update_level(u)
    save_user(update.effective_user.id, u)

async def handle_video(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 75
    u["xp"] += 60
    update_level(u)
    save_user(update.effective_user.id, u)

# =========================
# MAIN MENU UI
# =========================

def main_menu():
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data="bal")],
        [InlineKeyboardButton("🛒 Shop", callback_data="shop")],
        [InlineKeyboardButton("🎁 Daily", callback_data="daily")],
        [InlineKeyboardButton("🎲 Mystery", callback_data="mystery")]
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================
# COMMANDS
# =========================

async def start(update, ctx):
    await update.message.reply_text(
        "🎮 Welcome to Chat Game 😏",
        reply_markup=main_menu()
    )

# =========================
# BUTTON HANDLER
# =========================

async def button(update: Update, ctx):
    query = update.callback_query
    await query.answer()

    u = get_user(query.from_user.id)

    if query.data == "bal":
        await query.edit_message_text(
            f"💰 {u['money']}\n⭐ {u['xp']}\n📈 L{u['level']}",
            reply_markup=main_menu()
        )

    elif query.data == "daily":
        now = time.time()
        if now - u["daily"] > 86400:
            u["money"] += 20
            u["xp"] += 25
            u["daily"] = now
            save_user(query.from_user.id, u)
            msg = "🎁 Daily claimed"
        else:
            msg = "❌ Already claimed"

        await query.edit_message_text(msg, reply_markup=main_menu())

    elif query.data == "shop":
        keyboard = [
            [InlineKeyboardButton("📸 Selfie (50)", callback_data="buy_selfie")],
            [InlineKeyboardButton("🎤 Voice (60)", callback_data="buy_voice")],
            [InlineKeyboardButton("🎥 Video (350)", callback_data="buy_video")],
            [InlineKeyboardButton("⬅ Back", callback_data="back")]
        ]
        await query.edit_message_text(
            "🛒 Shop:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif "buy_" in query.data:
        item = query.data.split("_")[1]
        prices = {"selfie":50,"voice":60,"video":350}

        if u["money"] < prices[item]:
            msg = "❌ Not enough"
        else:
            u["money"] -= prices[item]
            save_user(query.from_user.id, u)
            msg = f"✅ Bought {item}"

        await query.edit_message_text(msg, reply_markup=main_menu())

    elif query.data == "mystery":
        if u["money"] < 200:
            msg = "Need 200"
        else:
            u["money"] -= 200
            reward = random.choice(["money","xp","lose"])

            if reward == "money":
                amt = random.randint(100,300)
                u["money"] += amt
                msg = f"💰 +{amt}"
            elif reward == "xp":
                xp = random.randint(100,300)
                u["xp"] += xp
                msg = f"⭐ +{xp}"
            else:
                u["money"] -= 50
                msg = "💀 Bad luck"

            save_user(query.from_user.id, u)

        await query.edit_message_text(msg, reply_markup=main_menu())

    elif query.data == "back":
        await query.edit_message_text("Menu:", reply_markup=main_menu())

# =========================
# APP
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))

app.run_polling()
