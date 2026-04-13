import os, time, sqlite3, re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *

TOKEN = os.getenv("TOKEN")
OWNER_ID = 8406272118

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

# ================= STATES =================
remove_state = {}
name_state = {}

# ================= USER =================
def get_user(uid):
    uid = str(uid)
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()

    if row:
        return {
            "name":row[1],
            "money":row[2],"xp":row[3],
            "last_msg":row[4],"streak":row[5],
            "daily":row[6],
            "daily_msg":row[7],
            "daily_voice":row[8],
            "daily_laugh":row[9],
            "streak_days":row[10],
            "last_day":row[11]
        }

    name_state[uid] = True
    cursor.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid,"",0,0,0,0,0,0,0,0,1,0)
    )
    conn.commit()
    return get_user(uid)

def get_user_by_name(name):
    cursor.execute("SELECT user_id FROM users WHERE name=?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return None

def save(uid,u):
    cursor.execute("""
    UPDATE users SET name=?,money=?,xp=?,last_msg=?,streak=?,daily=?,
    daily_msg=?,daily_voice=?,daily_laugh=?,streak_days=?,last_day=?
    WHERE user_id=?
    """,(
        u["name"],u["money"],u["xp"],u["last_msg"],u["streak"],u["daily"],
        u["daily_msg"],u["daily_voice"],u["daily_laugh"],
        u["streak_days"],u["last_day"],str(uid)
    ))
    conn.commit()

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
    uid = str(update.effective_user.id)

    # NAME SETUP
    if uid in name_state:
        u = get_user(uid)
        u["name"] = update.message.text
        save(uid,u)
        del name_state[uid]
        await update.message.reply_text(f"✅ Name set as {u['name']}")
        return

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

    u=get_user(uid)
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
    u["money"]+=25
    u["xp"]+=20
    save(update.effective_user.id,u)

# ================= VIDEO =================
async def video(update,ctx):
    u=get_user(update.effective_user.id)
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
    uid = str(update.effective_user.id)
    if uid in name_state:
        await update.message.reply_text("Enter your name:")
    else:
        await update.message.reply_text("🎮 Game Started 😏",reply_markup=menu())

# ================= BUTTON =================
async def button(update,ctx):
    q=update.callback_query
    await q.answer()

    u=get_user(q.from_user.id)

    if q.data=="bal":
        await q.edit_message_text(
            f"""👤 {u['name']}

💰 {u['money']}
⭐ {u['xp']}
🔥 Days: {u['streak_days']}""",
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
            keyboard.append([
                InlineKeyboardButton(f"👤 {u2['name']}", callback_data=f"view_{uid}")
            ])

        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="menu_back")])

        await q.edit_message_text("Select user:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data.startswith("view_"):
        uid = q.data.split("_")[1]
        u2 = get_user(uid)

        await q.edit_message_text(
            f"""👤 {u2['name']}

💰 {u2['money']}
⭐ {u2['xp']}
🔥 Days: {u2['streak_days']}
""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅ Back", callback_data="view_users")]
            ])
        )

    elif q.data=="menu_back":
        await q.edit_message_text("Menu:", reply_markup=menu())

# ================= OWNER =================
async def owner(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return

    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()

    text = "👑 Users:\n\n"
    for r in rows:
        text += f"{r[1]}\n💰 {r[2]} | ⭐ {r[3]}\n🔥 {r[10]}\n\n"

    await update.message.reply_text(text)

# ================= EDIT =================
async def edit(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        name = ctx.args[0]
        field = ctx.args[1]
        value = int(ctx.args[2])

        uid = get_user_by_name(name)

        if not uid:
            await update.message.reply_text("❌ User not found")
            return

        u = get_user(uid)

        if field == "money":
            u["money"] = value
        elif field == "xp":
            u["xp"] = value
        elif field == "streak":
            u["streak_days"] = value
        else:
            await update.message.reply_text("❌ Invalid field")
            return

        save(uid, u)
        await update.message.reply_text(f"✅ Updated {name}")

    except:
        await update.message.reply_text(
            "Usage:\n/edit name money 500\n/edit name xp 200"
        )

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
