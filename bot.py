import os
import random
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

print("BOT STARTING...")

TOKEN = os.getenv("TOKEN")

users = {}

# =====================
# USER SYSTEM
# =====================

def get_user(uid):
    if uid not in users:
        users[uid] = {
            "money": 0,
            "xp": 0,
            "level": 1,
            "last_msg": 0,
            "streak": 0,
            "daily": 0,
            "boost": {},
            "shield": False
        }
    return users[uid]

LEVELS = [
    (1,0),(2,100),(3,250),(4,450),(5,700),
    (6,1000),(7,1400),(8,1900),(9,2500),(10,3200),
    (11,4000),(12,5000),(13,6200),(14,7500),(15,9000),
    (16,11000),(17,13500),(18,16500),(19,20000),(20,25000)
]

def update_level(u):
    for lvl, xp in reversed(LEVELS):
        if u["xp"] >= xp:
            u["level"] = lvl
            break

# =====================
# BOOSTERS
# =====================

def point_mult(u):
    if "points" in u["boost"] and u["boost"]["points"] > time.time():
        return u["boost"]["points_mult"]
    return 1

def xp_mult(u):
    if "xp" in u["boost"] and u["boost"]["xp"] > time.time():
        return u["boost"]["xp_mult"]
    return 1

# =====================
# EARNING SYSTEM
# =====================

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    now = time.time()
    m = point_mult(u)
    x = xp_mult(u)

    u["money"] += int(1 * m)
    u["xp"] += int(2 * x)

    # streak
    if now - u["last_msg"] < 60:
        u["streak"] += 1
        if u["streak"] == 5:
            u["money"] += int(10 * m)
            u["xp"] += int(15 * x)
    else:
        u["streak"] = 1

    u["last_msg"] = now
    update_level(u)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["money"] += int(5 * point_mult(u))
    u["xp"] += int(10 * xp_mult(u))
    update_level(u)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["money"] += int(40 * point_mult(u))
    u["xp"] += int(30 * xp_mult(u))
    update_level(u)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["money"] += int(75 * point_mult(u))
    u["xp"] += int(60 * xp_mult(u))
    update_level(u)

# =====================
# COMMANDS
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id)
    await update.message.reply_text("🎮 Game Started 😏")

async def bal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"💰 {u['money']}\n⭐ {u['xp']}\n📈 Level {u['level']}"
    )

# =====================
# DAILY
# =====================

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    now = time.time()

    if now - u["daily"] > 86400:
        u["money"] += 20
        u["xp"] += 25
        u["daily"] = now
        await update.message.reply_text("🎁 Daily claimed")
    else:
        await update.message.reply_text("❌ Already claimed")

# =====================
# BOOSTERS
# =====================

async def booster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    if not context.args:
        return await update.message.reply_text("Use /booster 2x or god")

    b = context.args[0]

    if b == "2x":
        if u["money"] >= 100:
            u["money"] -= 100
            u["boost"]["points"] = time.time() + 600
            u["boost"]["points_mult"] = 2
            await update.message.reply_text("⚡ 2x points activated")

    elif b == "god":
        if u["money"] >= 500:
            u["money"] -= 500
            u["boost"]["points"] = time.time() + 600
            u["boost"]["xp"] = time.time() + 600
            u["boost"]["points_mult"] = 3
            u["boost"]["xp_mult"] = 3
            await update.message.reply_text("💥 GOD MODE ACTIVATED")

# =====================
# MYSTERY BOX
# =====================

async def mystery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    if u["money"] < 200:
        return await update.message.reply_text("❌ Need 200 pts")

    u["money"] -= 200

    roll = random.randint(1,5)

    if roll == 1:
        amt = random.randint(100,300)
        u["money"] += amt
        await update.message.reply_text(f"💰 +{amt}")

    elif roll == 2:
        xp = random.randint(100,300)
        u["xp"] += xp
        await update.message.reply_text(f"⭐ +{xp}")

    elif roll == 3:
        u["shield"] = True
        await update.message.reply_text("🛡 Shield Activated")

    else:
        u["money"] -= 50
        await update.message.reply_text("💀 Bad luck")

# =====================
# STEAL
# =====================

async def steal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)

    if u["money"] < 150:
        return await update.message.reply_text("Need 150 pts")

    if not context.args:
        return await update.message.reply_text("Use /steal USER_ID")

    target_id = int(context.args[0])
    t = get_user(target_id)

    if t["shield"]:
        return await update.message.reply_text("🛡 Target protected")

    amt = random.choice([300,400,500,600,700,800])
    t["money"] -= amt
    u["money"] += amt

    await update.message.reply_text(f"💣 Stole {amt}")

# =====================
# APP
# =====================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bal", bal))
app.add_handler(CommandHandler("daily", daily))
app.add_handler(CommandHandler("booster", booster))
app.add_handler(CommandHandler("mystery", mystery))
app.add_handler(CommandHandler("steal", steal))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))

app.run_polling()
