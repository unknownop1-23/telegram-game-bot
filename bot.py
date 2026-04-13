import os, time, sqlite3
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import *

TOKEN = os.getenv("TOKEN")

# ================= WEB =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Running"

def run_web():
    app_web.run(host="0.0.0.0", port=10000)

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

# ================= DAILY RESET =================
def check_day(u):
    today = int(time.time()//86400)

    if u["last_day"] != today:
        if u["last_day"] == today-1:
            u["streak_days"] += 1
        else:
            u["streak_days"] = 1

        u["daily_msg"] = 0
        u["daily_voice"] = 0
        u["daily_laugh"] = 0
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
    text=update.message.text.lower()
    m=mult(u)
    now=time.time()

    # base
    u["money"]+=int(1*m)
    u["xp"]+=int(2*m)

    # emoji
    if any(e in text for e in "😂😏😍🔥❤️"):
        u["money"]+=1
        u["xp"]+=1

    # laugh
    if ("😂" in text or "haha" in text) and u["daily_laugh"]==0:
        u["daily_laugh"]=1
        u["money"]+=40
        u["xp"]+=50

    # daily msg
    u["daily_msg"]+=1
    if u["daily_msg"]==20:
        u["money"]+=30
        u["xp"]+=40

    # streak 5 msgs
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

# ================= DAILY BONUS =================
async def daily(update,ctx):
    u=get_user(update.effective_user.id)
    now=time.time()

    if now-u["daily"]>86400:
        u["money"]+=20
        u["xp"]+=25
        u["daily"]=now
        save(update.effective_user.id,u)
        await update.message.reply_text("🎁 Daily claimed")
    else:
        await update.message.reply_text("❌ Already claimed")

# ================= BAL =================
async def bal(update,ctx):
    u=get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 {u['money']} | ⭐ {u['xp']}\n🔥 Days: {u['streak_days']}\n"
        f"Msgs:{u['daily_msg']}/20 Voice:{u['daily_voice']}/2 Laugh:{u['daily_laugh']}"
    )

# ================= APP =================
app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bal",bal))
app.add_handler(CommandHandler("daily",daily))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
app.add_handler(MessageHandler(filters.VOICE,voice))
app.add_handler(MessageHandler(filters.PHOTO,photo))
app.add_handler(MessageHandler(filters.VIDEO,video))

app.run_polling()
