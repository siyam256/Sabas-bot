import logging
# httpx request log level কমানো
logging.getLogger("httpx").setLevel(logging.WARNING)

import os
import pandas as pd
import asyncio
import nest_asyncio
import json
from functools import wraps

# Apply the patch to allow nested event loops
nest_asyncio.apply()

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, BaseHandler

# --- CONFIGURATION ---

# ⚠️ Replace with your actual Telegram Bot Token
TELEGRAM_BOT_TOKEN = "7862673148:AAEoxky6XWnmivceV6pbRk3oJxJ65oAtSsc"

# --- USER ACCESS CONTROL CONFIG ---
ADMIN_ID = 7145991193  # Default Admin User ID
AUTHORIZED_USERS_FILE = "authorized_users.json"
authorized_users = set()

def load_authorized_users():
    """Loads authorized user IDs from a JSON file."""
    global authorized_users
    try:
        with open(AUTHORIZED_USERS_FILE, 'r') as f:
            user_ids = json.load(f)
            authorized_users = set(user_ids)
    except FileNotFoundError:
        authorized_users = set() # If file doesn't exist, start with an empty set

def save_authorized_users():
    """Saves the current set of authorized user IDs to a JSON file."""
    with open(AUTHORIZED_USERS_FILE, 'w') as f:
        json.dump(list(authorized_users), f)

# --- DECORATORS FOR ACCESS CONTROL ---

def restricted(func):
    """Decorator to restrict access to the bot."""
    @wraps(func)
    async def wrapped(update: Update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == ADMIN_ID or user_id in authorized_users:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("⛔ দুঃখিত, এই বটটি ব্যবহার করার অনুমতি আপনার নেই।")
    return wrapped

def admin_only(func):
    """Decorator to restrict commands to the admin only."""
    @wraps(func)
    async def wrapped(update: Update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == ADMIN_ID:
            return await func(update, context, *args, **kwargs)
        else:
            await update.message.reply_text("⛔ শুধুমাত্র অ্যাডমিন এই কমান্ডটি ব্যবহার করতে পারবেন।")
    return wrapped

# --- SETUP ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
poll_data_storage = {}

# --- BOT HANDLERS ---

@restricted
async def start_csv(update: Update, context) -> None:
    """Handles the /start_csv command."""
    user_id = update.effective_user.id
    poll_data_storage[user_id] = []
    await update.message.reply_text('CSV generation process started. Please forward anonymous polls to me.')

@restricted
async def done_csv(update: Update, context) -> None:
    """Handles the /done_csv command with a dynamic filename."""
    user_id = update.effective_user.id

    # Check if a filename was provided
    if not context.args:
        await update.message.reply_text("⚠️ অনুগ্রহ করে একটি ফাইলের নাম দিন। যেমন: `/done_csv biology_chapter_1`")
        return

    filename = context.args[0]
    csv_file_path = f'{filename}.csv'

    if user_id in poll_data_storage and poll_data_storage[user_id]:
        try:
            df = pd.DataFrame(poll_data_storage[user_id])
            df.to_csv(csv_file_path, index=False)
            with open(csv_file_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=csv_file_path)
        except Exception as e:
            logger.error(f"Error creating or sending CSV: {e}")
            await update.message.reply_text("Sorry, an error occurred while creating the CSV file.")
        finally:
            poll_data_storage[user_id] = []
            if os.path.exists(csv_file_path):
                os.remove(csv_file_path)
    else:
        await update.message.reply_text('No poll data found. Please forward some polls first using /start_csv.')

@restricted
async def handle_poll(update: Update, context) -> None:
    """Processes forwarded polls."""
    user_id = update.effective_user.id
    if user_id not in poll_data_storage:
        await update.message.reply_text('Please start the process with /start_csv before forwarding polls.')
        return
    poll = update.effective_message.poll
    if not poll or not poll.is_anonymous:
        return
    question = poll.question
    options = [option.text for option in poll.options]
    correct_option_id = poll.correct_option_id
    poll_explanation = poll.explanation if poll.explanation else ""
    poll_entry = {
        'questions': question,
        'option1': options[0] if len(options) > 0 else '', 'option2': options[1] if len(options) > 1 else '',
        'option3': options[2] if len(options) > 2 else '', 'option4': options[3] if len(options) > 3 else '',
        'option5': options[4] if len(options) > 4 else '',
        'answer': correct_option_id + 1 if correct_option_id is not None else '',
        'explanation': poll_explanation,
        'type': 1, 'section': 1
    }
    poll_data_storage[user_id].append(poll_entry)
    await update.message.reply_text("Poll received and stored for CSV generation.")

# --- ADMIN COMMAND HANDLERS ---

@admin_only
async def add_user(update: Update, context) -> None:
    """Adds a new user to the authorized list."""
    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার: `/adduser <user_id>`")
        return
    try:
        user_id = int(context.args[0])
        if user_id in authorized_users:
            await update.message.reply_text(f"User ID {user_id} আগে থেকেই তালিকায় রয়েছে।")
        else:
            authorized_users.add(user_id)
            save_authorized_users()
            await update.message.reply_text(f"✅ User ID {user_id} সফলভাবে যোগ করা হয়েছে।")
    except ValueError:
        await update.message.reply_text("❌ ভুল ইউজার আইডি। শুধুমাত্র সংখ্যা ব্যবহার করুন।")

@admin_only
async def del_user(update: Update, context) -> None:
    """Deletes a user from the authorized list."""
    if not context.args:
        await update.message.reply_text("⚠️ ব্যবহার: `/deluser <user_id>`")
        return
    try:
        user_id = int(context.args[0])
        if user_id in authorized_users:
            authorized_users.remove(user_id)
            save_authorized_users()
            await update.message.reply_text(f"🗑️ User ID {user_id} তালিকা থেকে حذف করা হয়েছে।")
        else:
            await update.message.reply_text(f"User ID {user_id} তালিকায় পাওয়া যায়নি।")
    except ValueError:
        await update.message.reply_text("❌ ভুল ইউজার আইডি। শুধুমাত্র সংখ্যা ব্যবহার করুন।")

@admin_only
async def list_users(update: Update, context) -> None:
    """Lists all authorized users."""
    if not authorized_users:
        await update.message.reply_text("অনুমতিপ্রাপ্ত ব্যবহারকারীর তালিকা বর্তমানে খালি।")
        return

    user_list = "📜 **অনুমতিপ্রাপ্ত ব্যবহারকারীর তালিকা:**\n"
    for user_id in authorized_users:
        user_list += f"- `{user_id}`\n"

    await update.message.reply_text(user_list, parse_mode='Markdown')

async def error_handler(update: object, context) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

# --- BOT STARTUP LOGIC ---

async def main() -> None:
    """The main async function to set up and run the bot."""
    load_authorized_users() # Load users on startup

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start_csv", start_csv))
    application.add_handler(CommandHandler("done_csv", done_csv))
    application.add_handler(MessageHandler(filters.POLL, handle_poll))

    # Register Admin commands
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("deluser", del_user))
    application.add_handler(CommandHandler("listusers", list_users))

    application.error_handler = error_handler

    print("Starting bot...")
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        print("Bot is running in the background. Stop the cell to shut it down.")
        await asyncio.Future()
    except (KeyboardInterrupt, SystemExit):
        print("Stopping bot...")
    finally:
        if application.updater and application.updater.is_running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        print("Bot has been shut down.")

if __name__ == '__main__':
    asyncio.run(main())
