import os, time, random, sqlite3
from telegram import Update
from telegram.ext import *

TOKEN = os.getenv("TOKEN")

# =========================
# DATABASE SETUP
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
    daily REAL,
    shield REAL
)
""")
conn.commit()

# =========================
# USER SYSTEM
# =========================

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
            "daily": row[6],
            "shield": row[7]
        }

    cursor.execute(
        "INSERT INTO users VALUES (?,0,0,1,0,0,0,0)",
        (uid,)
    )
    conn.commit()
    return get_user(uid)

def save_user(uid, u):
    cursor.execute("""
    UPDATE users SET money=?, xp=?, level=?, streak=?, last_msg=?, daily=?, shield=?
    WHERE user_id=?
    """, (
        u["money"], u["xp"], u["level"],
        u["streak"], u["last_msg"], u["daily"], u["shield"], str(uid)
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
# EARNING SYSTEM
# =========================

async def msg(update: Update, ctx):
    u = get_user(update.effective_user.id)
    now = time.time()

    # base
    u["money"] += 1
    u["xp"] += 2

    # emoji bonus
    if any(e in update.message.text for e in "😂😏😍🔥❤️"):
        u["money"] += 1
        u["xp"] += 2

    # streak
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

async def voice(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 5
    u["xp"] += 10
    update_level(u)
    save_user(update.effective_user.id, u)

async def photo(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 40
    u["xp"] += 30
    update_level(u)
    save_user(update.effective_user.id, u)

async def video(update, ctx):
    u = get_user(update.effective_user.id)
    u["money"] += 75
    u["xp"] += 60
    update_level(u)
    save_user(update.effective_user.id, u)

# =========================
# COMMANDS
# =========================

async def start(update, ctx):
    get_user(update.effective_user.id)
    await update.message.reply_text("🎮 Game Started 😏")

async def bal(update, ctx):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 {u['money']}\n⭐ {u['xp']}\n📈 Level {u['level']}"
    )

# =========================
# DAILY BONUS
# =========================

async def daily(update, ctx):
    u = get_user(update.effective_user.id)
    now = time.time()

    if now - u["daily"] > 86400:
        u["money"] += 20
        u["xp"] += 25
        u["daily"] = now
        save_user(update.effective_user.id, u)
        await update.message.reply_text("🎁 Daily claimed")
    else:
        await update.message.reply_text("❌ Already claimed")

# =========================
# SHOP (SIMPLE BASE)
# =========================

SHOP = {
    "selfie":50,
    "voice":60,
    "photo":220,
    "call":250,
    "secret":280,
    "video":350
}

async def shop(update, ctx):
    text = "🛒 Shop:\n"
    for k,v in SHOP.items():
        text += f"{k} → {v} pts\n"
    await update.message.reply_text(text)

async def buy(update, ctx):
    u = get_user(update.effective_user.id)

    if not ctx.args:
        return await update.message.reply_text("Use /buy item")

    item = ctx.args[0]

    if item not in SHOP:
        return await update.message.reply_text("Invalid item")

    cost = SHOP[item]

    if u["money"] < cost:
        return await update.message.reply_text("Not enough")

    u["money"] -= cost
    save_user(update.effective_user.id, u)

    await update.message.reply_text(f"✅ Bought {item}")

# =========================
# MYSTERY BOX
# =========================

async def mystery(update, ctx):
    u = get_user(update.effective_user.id)

    if u["money"] < 200:
        return await update.message.reply_text("Need 200")

    u["money"] -= 200

    roll = random.randint(1,5)

    if roll == 1:
        amt = random.randint(100,300)
        u["money"] += amt
        msg = f"💰 +{amt}"
    elif roll == 2:
        xp = random.randint(100,300)
        u["xp"] += xp
        msg = f"⭐ +{xp}"
    elif roll == 3:
        u["shield"] = time.time() + 3600
        msg = "🛡 Shield activated"
    else:
        u["money"] -= 50
        msg = "💀 Bad luck"

    save_user(update.effective_user.id, u)
    await update.message.reply_text(msg)

# =========================
# STEAL SYSTEM
# =========================

async def steal(update, ctx):
    u = get_user(update.effective_user.id)

    if u["money"] < 150:
        return await update.message.reply_text("Need 150")

    if not ctx.args:
        return await update.message.reply_text("Use /steal USER_ID")

    target_id = ctx.args[0]
    t = get_user(target_id)

    if t["shield"] > time.time():
        return await update.message.reply_text("🛡 Target protected")

    amt = random.choice([300,400,500,600,700,800])
    t["money"] -= amt
    u["money"] += amt

    save_user(update.effective_user.id, u)
    save_user(target_id, t)

    await update.message.reply_text(f"💣 Stole {amt}")

# =========================
# APP START
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bal", bal))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("shop", shop))
app.add_handler(CommandHandler("buy", buy))
app.add_handler(CommandHandler("mystery", mystery))
app.add_handler(CommandHandler("steal", steal))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
app.add_handler(MessageHandler(filters.VOICE, voice))
app.add_handler(MessageHandler(filters.PHOTO, photo))
app.add_handler(MessageHandler(filters.VIDEO, video))

app.run_polling()
