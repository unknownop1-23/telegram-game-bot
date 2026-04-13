import os, time, sqlite3, re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *

TOKEN = os.getenv("TOKEN")

# ================= WEB =================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot running 😏"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()

# ================= DB =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
user_id TEXT PRIMARY KEY,
money INTEGER,
xp INTEGER,
last_msg REAL,
streak INTEGER,
daily REAL,
daily_msg INTEGER,
daily_voice INTEGER,
daily_laugh INTEGER,
streak_days INTEGER,
last_day INTEGER
)
""")
conn.commit()

def get_user(uid):
    uid = str(uid)
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()

    if row:
        return {
            "money":row[1],"xp":row[2],
            "last_msg":row[3],"streak":row[4],
            "daily":row[5],
            "daily_msg":row[6],
            "daily_voice":row[7],
            "daily_laugh":row[8],
            "streak_days":row[9],
            "last_day":row[10]
        }

    cursor.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (uid,0,0,0,0,0,0,0,0,1,0)
    )
    conn.commit()
    return get_user(uid)

def save(uid,u):
    cursor.execute("""
    UPDATE users SET money=?,xp=?,last_msg=?,streak=?,daily=?,
    daily_msg=?,daily_voice=?,daily_laugh=?,streak_days=?,last_day=?
    WHERE user_id=?
    """,(
        u["money"],u["xp"],u["last_msg"],u["streak"],u["daily"],
        u["daily_msg"],u["daily_voice"],u["daily_laugh"],
        u["streak_days"],u["last_day"],str(uid)
    ))
    conn.commit()

# ================= EMOJI DETECTION =================
def contains_emoji(text):
    return bool(re.search(r'[\U00010000-\U0010ffff]', text))

LAUGH = ["😂","🤣"]
SMILE = ["🙂","🙃"]

# ================= DAILY RESET =================
def check_day(u):
    today = int(time.time()//86400)

    if u["last_day"] != today:
        # streak days
        if u["last_day"] == today-1:
            u["streak_days"] += 1
        else:
            u["streak_days"] = 1

        # reset missions
        u["daily_msg"] = 0
        u["daily_voice"] = 0
        u["daily_laugh"] = 0

        # auto daily bonus
        u["money"] += 20
        u["xp"] += 25

        u["last_day"] = today

# ================= MULTIPLIER =================
def mult(u):
    if u["streak_days"] >= 7:
        return 1.25
    elif u["streak_days"] >= 3:
        return 1.10
    return 1

# ================= MESSAGE =================
async def msg(update:Update,ctx):
    u=get_user(update.effective_user.id)
    check_day(u)

    text = update.message.text or ""
    now=time.time()
    m=mult(u)

    # base earning
    u["money"]+=int(1*m)
    u["xp"]+=int(2*m)

    # ANY emoji
    if contains_emoji(text):
        u["money"]+=1
        u["xp"]+=1

    # smile reward
    if any(e in text for e in SMILE):
        u["money"]+=10
        u["xp"]+=15

    # laugh reward (once/day)
    if any(e in text for e in LAUGH) or "haha" in text.lower():
        if u["daily_laugh"]==0:
            u["daily_laugh"]=1
            u["money"]+=40
            u["xp"]+=50

    # daily messages
    u["daily_msg"]+=1
    if u["daily_msg"]==20:
        u["money"]+=30
        u["xp"]+=40

    # 5 msg streak
    if now-u["last_msg"]<60:
        u["streak"]+=1
        if u["streak"]==5:
            u["money"]+=10
            u["xp"]+=15
    else:
        u["streak"]=1

    u["last_msg"]=now
    save(update.effective_user.id,u)

# ================= VOICE =================
async def voice(update,ctx):
    u=get_user(update.effective_user.id)
    check_day(u)

    m=mult(u)

    u["money"]+=int(5*m)
    u["xp"]+=int(10*m)

    u["daily_voice"]+=1
    if u["daily_voice"]==2:
        u["money"]+=25
        u["xp"]+=30

    save(update.effective_user.id,u)

# ================= PHOTO =================
async def photo(update,ctx):
    u=get_user(update.effective_user.id)
    u["money"]+=40
    u["xp"]+=30
    save(update.effective_user.id,u)

# ================= VIDEO =================
async def video(update,ctx):
    u=get_user(update.effective_user.id)
    u["money"]+=75
    u["xp"]+=60
    save(update.effective_user.id,u)

# ================= UI =================
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Balance",callback_data="bal")],
        [InlineKeyboardButton("🎯 Missions",callback_data="missions")]
    ])

async def start(update,ctx):
    await update.message.reply_text("🎮 Game Started 😏",reply_markup=menu())

async def button(update,ctx):
    q=update.callback_query
    await q.answer()
    u=get_user(q.from_user.id)

    if q.data=="bal":
        await q.edit_message_text(
            f"💰 {u['money']} | ⭐ {u['xp']}\n🔥 Days: {u['streak_days']}",
            reply_markup=menu()
        )

    elif q.data=="missions":
        await q.edit_message_text(
            f"""🎯 Missions

Msgs: {u['daily_msg']}/20
Voice: {u['daily_voice']}/2
Laugh: {'✅' if u['daily_laugh'] else '❌'}
""",
            reply_markup=menu()
        )

# ================= APP =================
app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
app.add_handler(MessageHandler(filters.VOICE,voice))
app.add_handler(MessageHandler(filters.PHOTO,photo))
app.add_handler(MessageHandler(filters.VIDEO,video))

app.run_polling()
