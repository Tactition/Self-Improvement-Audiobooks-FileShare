import sys
import glob
import importlib
from pathlib import Path
import logging
import logging.config
import asyncio
import random
from datetime import date, datetime

import pytz
from aiohttp import web
from pyrogram import Client, __version__, idle, types, enums
from pyrogram.raw.all import layer
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified

from config import LOG_CHANNEL, ON_HEROKU, CLONE_MODE, PORT, ADMINS, AUTH_CHANNEL, CLONE_MODE, VERIFY_MODE, VERIFY_TUTORIAL, AUTO_DELETE_MODE, AUTO_DELETE, AUTO_DELETE_TIME, STREAM_MODE, WEBSITE_URL, WEBSITE_URL_MODE
from Script import script 
from TechVJ.server import web_server
from plugins.clone import restart_bots
from TechVJ.bot import StreamBot
from TechVJ.utils.keepalive import ping_server
from TechVJ.bot.clients import initialize_clients
from plugins.database import unpack_new_file_id, get_file_details
from plugins.users_api import get_user, get_short_link, update_user_info

# Logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

# Glob for plugins
ppath = "plugins/*.py"
files = glob.glob(ppath)

# --- Helper Functions ---
async def encode(string):
    string_bytes = string.encode("utf-8")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = base64_bytes.decode("ascii").strip("=")
    return base64_string

async def decode(base64_string):
    base64_string = base64_string.strip("=")
    base64_bytes = (base64_string + "=" * (-len(base64_string) % 4)).encode("ascii")
    string_bytes = base64.urlsafe_b64decode(base64_bytes)
    string = string_bytes.decode("utf-8")
    return string

async def is_subscribed(bot, message, channels):
    btn = []
    for id in channels:
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(id, message.from_user.id)
        except Exception:
            btn.append([InlineKeyboardButton(f'Join {chat.title}', url=chat.invite_link)])
    return btn

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

# --- Main Start Function ---
async def start():
    # Start StreamBot using the current event loop.
    await StreamBot.start()

    print('\n')
    print('Initializing Tactitions file store Bot')
    bot_info = await StreamBot.get_me()
    StreamBot.username = bot_info.username

    await initialize_clients()
    # Import all plugins
    for name in files:
        with open(name) as a:
            patt = Path(a.name)
            plugin_name = patt.stem.replace(".py", "")
            plugins_dir = Path(f"plugins/{plugin_name}.py")
            import_path = f"plugins.{plugin_name}"
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print(" Imported => " + plugin_name)

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time_str = now.strftime("%H:%M:%S %p")
    await StreamBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time_str))
    
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()

    if CLONE_MODE == True:
        await restart_bots()

    print("Bot Started Powered By @tactition")
    await idle()

if __name__ == '__main__':
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
