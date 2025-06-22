import re
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

import os

BOT_TOKEN = "7635231809:AAGqzxAVLOHgEBTLJXaA7GK0glG7Za6IWiU"
GC_ID = -1002347957556

# -- Flask keep-alive server --
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "Bot is running"

def run_flask():
    flask_app.run(host="0.0.0.0", port=10000)

threading.Thread(target=run_flask).start()

# -- Telegram bot setup --
slot_active = False
check_mode = False
user_data = {}

TWITTER_REGEX = re.compile(r"https://(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)/status/")

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_member = await context.bot.get_chat_member(GC_ID, user_id)
    return chat_member.status in ["administrator", "creator"]

async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global slot_active, check_mode, user_data
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return

    slot_active = True
    check_mode = False
    user_data = {}
    await update.message.reply_text("✅ Slot started. Send Twitter/X links.")

async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    await update.message.reply_text(f"🔢 Total links sent: {len(user_data)}")

async def double(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    dups = [uid for uid, data in user_data.items() if data['count'] > 1]
    if not dups:
        await update.message.reply_text("✅ No duplicate link submissions.")
        return
    msg = "🚫 Duplicate links sent by:\n"
    for uid in dups:
        name = user_data[uid]['tg'] or (await context.bot.get_chat(uid)).first_name
        msg += f"@{name}\n"
    await update.message.reply_text(msg)

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    if not user_data:
        await update.message.reply_text("❌ No data to list.")
        return

    message = ""
    for uid, data in user_data.items():
        try:
            tg_name = f"@{data['tg']}" if data['tg'] else (await context.bot.get_chat(uid)).first_name
        except:
            tg_name = "Unknown"
        xid = data['tw']
        line = f"{tg_name} | xid: @{xid}\n"
        if len(message + line) > 3900:
            await update.message.reply_text(message)
            message = ""
        message += line
    if message:
        await update.message.reply_text(message)

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global check_mode
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    check_mode = True
    await update.message.reply_text("🔍 Check mode activated. Now tracking who sends 'ad' or 'all done'.")

async def scam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    msg = "🚨 These users did not send 'ad' or 'all done':\n"
    found = False
    for uid, data in user_data.items():
        if not data['done']:
            found = True
            try:
                tg = f"@{data['tg']}" if data['tg'] else (await context.bot.get_chat(uid)).first_name
            except:
                tg = "Unknown"
            msg += f"{tg}\n"
    if found:
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("✅ Everyone sent 'ad' or 'all done'.")

async def muteall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    count = 0
    until = datetime.utcnow() + timedelta(days=3)
    for uid, data in user_data.items():
        if not data['done']:
            try:
                await context.bot.restrict_chat_member(
                    GC_ID, uid,
                    ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                count += 1
            except:
                pass
    await update.message.reply_text(f"🔇 Muted {count} users for 3 days.")

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global slot_active, check_mode, user_data
    if update.effective_chat.id != GC_ID or not await is_admin(update, context): return
    slot_active = False
    check_mode = False
    user_data = {}
    await update.message.reply_text("🛑 Session ended. All data cleared.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global user_data
    if update.effective_chat.id != GC_ID:
        return

    user = update.effective_user
    uid = user.id
    text = update.message.text or ""

    if slot_active:
        match = TWITTER_REGEX.search(text)
        if match:
            xid = match.group(1)
            if uid not in user_data:
                user_data[uid] = {
                    "tg": user.username,
                    "tw": xid,
                    "done": False,
                    "count": 1
                }
            else:
                user_data[uid]["count"] += 1

    if check_mode:
        if re.search(r"\b(ad|all done)\b", text, re.IGNORECASE):
            if uid in user_data and not user_data[uid]['done']:
                user_data[uid]['done'] = True
                await update.message.reply_text(
                    f"xid: @{user_data[uid]['tw']}", reply_to_message_id=update.message.message_id
                )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("slot", slot))
app.add_handler(CommandHandler("total", total))
app.add_handler(CommandHandler("double", double))
app.add_handler(CommandHandler("list", list_users))
app.add_handler(CommandHandler("check", check))
app.add_handler(CommandHandler("scam", scam))
app.add_handler(CommandHandler("muteall", muteall))
app.add_handler(CommandHandler("end", end))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_polling()
