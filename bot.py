import asyncio
import sys
import glob
import importlib
from pathlib import Path
from pyrogram import Client, idle
import logging
from TechVJ.server import web_server
from TechVJ.bot import StreamBot
from TechVJ.utils.keepalive import ping_server
from plugins.clone import restart_bots
from config import LOG_CHANNEL, ON_HEROKU, CLONE_MODE, PORT
from datetime import date, datetime
import pytz

# Setup logging configuration
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# Function to load all plugins dynamically
async def load_plugins():
    ppath = "plugins/*.py"
    files = glob.glob(ppath)
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

# Main function to start the bot
async def start():
    print('\nInitializing Tactitions file store Bot')

    # Start the bot client
    await StreamBot.start()  # Ensure to start the bot before using any methods.
    
    bot_info = await StreamBot.get_me()  # Now it's safe to call get_me
    StreamBot.username = bot_info.username

    await load_plugins()

    if ON_HEROKU:
        asyncio.create_task(ping_server())

    today = date.today()
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")

    app = web.AppRunner(await web_server())
    
    await StreamBot.send_message(chat_id=LOG_CHANNEL, text='/start Running now at {} {}'.format(today, time))
    
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()

    if CLONE_MODE:
        await restart_bots()

    print("Bot Started Powered By @tactition")
    await idle()

# Entry point for the script
if __name__ == '__main__':
    try:
        # Use asyncio.run() to start the main coroutine
        asyncio.run(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')