import os, time, sqlite3, re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
OWNER_ID = 8406272118  # replace with your telegram id

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
username TEXT,
name TEXT,
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

def get_user(uid, user=None):
    uid = str(uid)

    username = ""
    name = ""

    if user:
        username = user.username or ""
        name = user.first_name or ""

    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()

    if row:
        # update username/name
        cursor.execute(
            "UPDATE users SET username=?, name=? WHERE user_id=?",
            (username, name, uid)
        )
        conn.commit()

        return {
            "username":row[1],
            "name":row[2],
            "money":row[3],"xp":row[4],
            "last_msg":row[5],"streak":row[6],
            "daily":row[7],
            "daily_msg":row[8],
            "daily_voice":row[9],
            "daily_laugh":row[10],
            "streak_days":row[11],
            "last_day":row[12]
        }

    cursor.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, username, name, 0,0,0,0,0,0,0,0,1,0)
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

# ================= REMOVE STATE =================
remove_state = {}

# ================= EMOJI =================
def contains_emoji(text):
    return bool(re.search(r'[\U00010000-\U0010ffff]', text))

LAUGH = ["😂","🤣"]
SMILE = ["🙂","🙃"]

# ================= DAILY =================
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

        u["money"] += 20
        u["xp"] += 25

        u["last_day"] = today

# ================= MULT =================
def mult(u):
    if u["streak_days"] >= 7:
        return 1.25
    elif u["streak_days"] >= 3:
        return 1.10
    return 1

# ================= MESSAGE =================
async def msg(update:Update,ctx):
    uid = update.effective_user.id

    # REMOVE FLOW
    if uid in remove_state:
        state = remove_state[uid]

        if state["step"] == 1:
            try:
                state["amount"] = int(update.message.text)
                state["step"] = 2
                await update.message.reply_text("Enter reason:")
            except:
                await update.message.reply_text("Send valid number")
            return

        elif state["step"] == 2:
            reason = update.message.text
            u = get_user(uid)

            amt = state["amount"]

            if u["money"] < amt:
                await update.message.reply_text("Not enough points")
            else:
                u["money"] -= amt
                save(uid, u)
                await update.message.reply_text(
                    f"✅ Reduced {amt} pts for \"{reason}\""
                )

            del remove_state[uid]
            return

    u=get_user(uid, update.effective_user)
    check_day(u)

    text = update.message.text or ""
    now=time.time()
    m=mult(u)

    u["money"]+=int(1*m)
    u["xp"]+=int(2*m)

    if contains_emoji(text):
        u["money"]+=1
        u["xp"]+=1

    if any(e in text for e in SMILE):
        u["money"]+=10
        u["xp"]+=15

    if any(e in text for e in LAUGH) or "haha" in text.lower():
        if u["daily_laugh"]==0:
            u["daily_laugh"]=1
            u["money"]+=40
            u["xp"]+=50

    u["daily_msg"]+=1
    if u["daily_msg"]==20:
        u["money"]+=30
        u["xp"]+=40

    if now-u["last_msg"]<60:
        u["streak"]+=1
        if u["streak"]==5:
            u["money"]+=10
            u["xp"]+=15
    else:
        u["streak"]=1

    u["last_msg"]=now
    save(uid,u)

# ================= VOICE =================
async def voice(update,ctx):
    u=get_user(update.effective_user.id, update.effective_user)
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
    u=get_user(update.effective_user.id, update.effective_user)
    u["money"]+=25
    u["xp"]+=20
    save(update.effective_user.id,u)

# ================= VIDEO =================
async def video(update,ctx):
    u=get_user(update.effective_user.id, update.effective_user)
    u["money"]+=55
    u["xp"]+=40
    save(update.effective_user.id,u)

# ================= UI =================
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Balance",callback_data="bal")],
        [InlineKeyboardButton("🎯 Missions",callback_data="missions")],
        [InlineKeyboardButton("👀 View",callback_data="view_users")],
        [InlineKeyboardButton("➖ Remove Points",callback_data="remove")]
    ])

async def start(update,ctx):
    await update.message.reply_text("🎮 Game Started 😏",reply_markup=menu())

# ================= BUTTON =================
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

    elif q.data=="remove":
        remove_state[q.from_user.id] = {"step":1}
        await q.edit_message_text("Enter points to remove:")

    elif q.data=="view_users":
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()

        keyboard = []
        for r in rows:
            uid = r[0]
            u2 = get_user(uid)
            name = f"@{u2['username']}" if u2["username"] else u2["name"]
            keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"view_{uid}")])

        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="back")])

        await q.edit_message_text("Select user:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data.startswith("view_"):
        uid = q.data.split("_")[1]
        u2 = get_user(uid)
        name = f"@{u2['username']}" if u2["username"] else u2["name"]

        await q.edit_message_text(
            f"""👤 {name}

💰 {u2['money']}
⭐ {u2['xp']}
🔥 Days: {u2['streak_days']}
""",
            reply_markup=menu()
        )

    elif q.data=="back":
        await q.edit_message_text("Menu:", reply_markup=menu())

# ================= OWNER =================
async def owner(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return

    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()

    text = "👑 Users:\n\n"
    for r in rows:
        name = f"@{r[1]}" if r[1] else r[2]
        text += f"{name}\n💰 {r[3]} | ⭐ {r[4]}\n🔥 {r[11]}\n\n"

    await update.message.reply_text(text)

# ================= EDIT =================
async def edit(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        uid = ctx.args[0]
        field = ctx.args[1]
        value = int(ctx.args[2])

        u = get_user(uid)

        if field == "money":
            u["money"] = value
        elif field == "xp":
            u["xp"] = value
        elif field == "streak":
            u["streak_days"] = value

        save(uid, u)
        await update.message.reply_text("✅ Updated")

    except:
        await update.message.reply_text("Usage: /edit user_id money 500")

# ================= APP =================
app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("owner",owner))
app.add_handler(CommandHandler("edit",edit))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
app.add_handler(MessageHandler(filters.VOICE,voice))
app.add_handler(MessageHandler(filters.PHOTO,photo))
app.add_handler(MessageHandler(filters.VIDEO,video))

app.run_polling()
