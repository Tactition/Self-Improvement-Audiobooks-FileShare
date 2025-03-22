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

from config import LOG_CHANNEL, ON_HEROKU, CLONE_MODE, PORT, ADMINS
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

# Start the default client (StreamBot)
StreamBot.start()

async def start():
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
            import_path = "plugins.{}".format(plugin_name)
            spec = importlib.util.spec_from_file_location(import_path, plugins_dir)
            load = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(load)
            sys.modules["plugins." + plugin_name] = load
            print(" Imported => " + plugin_name)

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    me = await StreamBot.get_me()
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
