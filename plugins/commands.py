
import os
import logging
import random
import asyncio
from typing import List, Optional, Dict, Any, Union
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardButton, InlineKeyboardMarkup, 
    CallbackQuery, WebAppInfo, InputMediaPhoto
)
from plugins.users_api import get_user, update_user_info
from plugins.database import get_file_details
from pyrogram.errors import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
from urllib.parse import quote_plus
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size

logger = logging.getLogger(__name__)

BATCH_FILES = {}

async def is_subscribed(bot, query, channel):
    btn = []
    for id in channel:
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(id, query.from_user.id)
        except UserNotParticipant:
            btn.append([InlineKeyboardButton(f'Join {chat.title}', url=chat.invite_link)])
        except Exception as e:
            pass
    return btn

def get_size(size):
    """Get size in readable format"""

    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

class MessageHandler:
    def __init__(self, client: Client, message: Message):
        self.client = client
        self.message = message
        self.user_id = message.from_user.id if message.from_user else None

    async def get_bot_username(self) -> str:
        return (await self.client.get_me()).username

    async def handle_verification(self) -> Optional[Message]:
        if not await check_verification(self.client, self.user_id) and VERIFY_MODE:
            username = await self.get_bot_username()
            btn = self._get_verification_buttons(username)
            return await self.message.reply_text(
                text="<b>You are not verified!\nKindly verify to continue!</b>",
                protect_content=True,
                reply_markup=InlineKeyboardMarkup(btn)
            )
        return None

    def _get_verification_buttons(self, username: str) -> List[List[InlineKeyboardButton]]:
        return [[
            InlineKeyboardButton(
                "Verify", 
                url=f"https://telegram.me/{username}?start="
            )
        ],[
            InlineKeyboardButton(
                "How To Open Link & Verify", 
                url=VERIFY_TUTORIAL
            )
        ]]

class StreamLinkGenerator:
    def __init__(self, client: Client, log_channel: int):
        self.client = client
        self.log_channel = log_channel

    async def generate_links(self, file_id: str, user_info: Dict[str, Any]) -> Dict[str, str]:
        log_msg = await self.client.send_cached_media(
            chat_id=self.log_channel,
            file_id=file_id,
        )
        file_name = quote_plus(get_name(log_msg))
        msg_id = str(log_msg.id)
        hash_value = get_hash(log_msg)

        return {
            'stream': f"{URL}watch/{msg_id}/{file_name}?hash={hash_value}",
            'download': f"{URL}{msg_id}/{file_name}?hash={hash_value}",
            'file_name': file_name
        }

class AutoDeleteHandler:
    def __init__(self, client: Client, chat_id: int):
        self.client = client
        self.chat_id = chat_id

    async def schedule_delete(self, messages: List[Message]) -> None:
        if not AUTO_DELETE_MODE:
            return

        notice = await self.send_delete_notice()
        await asyncio.sleep(AUTO_DELETE_TIME)
        
        for msg in messages:
            try:
                await msg.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

        await self.update_delete_notice(notice)

    async def send_delete_notice(self) -> Message:
        return await self.client.send_message(
            chat_id=self.chat_id,
            text=f"<b><u>❗️IMPORTANT❗️</u></b>\n\n"
                 f"This File will be deleted Within <b><u>{AUTO_DELETE} Minutes</u></b>"
                 f"<i>(Due to Copyright Issues)</i>.\n\n"
                 f"<b>Please forward the File to Saved Messages</b>"
        )

    async def update_delete_notice(self, notice: Message) -> None:
        try:
            await notice.edit_text("<b>File deleted successfully!</b>")
        except Exception as e:
            logger.error(f"Error updating delete notice: {e}")

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client: Client, message: Message):
    handler = MessageHandler(client, message)
    
    if AUTH_CHANNEL:
        try:
            btn = await is_subscribed(client, message, AUTH_CHANNEL)
            if btn:
                username = await handler.get_bot_username()
                btn.append([
                    InlineKeyboardButton(
                        "♻️ Try Again ♻️",
                        url=f"https://t.me/{username}?start={''.join(message.command[1:])}"
                    )
                ])
                await message.reply_text(
                    text=f"<b>👋 Hello {message.from_user.mention},\n\n"
                         f"Please join the channel then click on try again button. 😇</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return
        except Exception as e:
            logger.error(f"Error in subscription check: {e}")

    if len(message.command) > 1:
        param = message.command[1]
        if param.startswith("text_"):
            encoded_text = param[len("text_"):]
            # Add missing padding if needed (Base64 strings require a length multiple of 4)
            missing_padding = len(encoded_text) % 4
            if missing_padding:
                encoded_text += "=" * (4 - missing_padding)
            try:
                decoded_text = base64.urlsafe_b64decode(encoded_text.encode("ascii")).decode("utf-8")
                # Send the saved text as a reply and store the message object in link_msg.
                link_msg = await message.reply_text(f"<b>Here is the saved text:</b>\n\n{decoded_text}")
                
                # If auto-delete mode is enabled, send a notice, wait, then delete the link message.
                if AUTO_DELETE_MODE == True:
                    notice_msg = await bot.send_message(
                        chat_id=message.from_user.id,
                        text=f"<b><u>❗️IMPORTANT❗️</u></b>\n\nThis message will be deleted within <b><u>{AUTO_DELETE} Minutes</u></b> (Due to Copyright Issues).\n\n<b>Please forward the text to Saved Messages.</b>"
                    )
                    await asyncio.sleep(AUTO_DELETE_TIME)
                    try:
                        await link_msg.delete()
                    except Exception as e:
                        logger.error("Error deleting text link message: %s", e)
                    try:
                        await notice_msg.edit_text("<b>Message deleted successfully. You are always welcome to request again.</b>")
                    except Exception as e:
                        logger.error("Error editing auto-delete notice: %s", e)
                return
            except Exception as e:
                return await message.reply_text(f"Error decoding text: {e}")
        else:
            return await message.reply_text("Parameter not recognized.")
    else:
        return await message.reply_text("Welcome! Use the /link command to generate a shareable link.")