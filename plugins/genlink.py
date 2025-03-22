import re
import os
import json
import base64
import logging
from typing import Optional, Tuple, Dict, Any
from pyrogram import filters, Client, enums
from pyrogram.types import Message
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, UsernameInvalid, UsernameNotModified
from config import ADMINS, LOG_CHANNEL, PUBLIC_FILE_STORE, WEBSITE_URL, WEBSITE_URL_MODE
from plugins.database import unpack_new_file_id
from plugins.users_api import get_user, get_short_link

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LinkGenerator:
    def __init__(self, bot: Client, message: Message):
        self.bot = bot
        self.message = message
        self.username = None

    async def get_bot_username(self) -> str:
        if not self.username:
            self.username = (await self.bot.get_me()).username
        return self.username

    async def generate_share_link(self, file_id: str, is_batch: bool = False) -> str:
        username = await self.get_bot_username()
        if WEBSITE_URL_MODE:
            prefix = "BATCH-" if is_batch else ""
            return f"{WEBSITE_URL}?Zahid={prefix}{file_id}"
        return f"https://t.me/{username}?start={'BATCH-' if is_batch else ''}{file_id}"

    async def send_link_message(self, share_link: str, user: Dict[str, Any], 
                              additional_text: str = "") -> Message:
        if user["base_site"] and user["shortener_api"]:
            short_link = await get_short_link(user, share_link)
            link_text = f"🖇️ sʜᴏʀᴛ ʟɪɴᴋ :- {short_link}"
        else:
            link_text = f"🔗 ᴏʀɪɢɪɴᴀʟ ʟɪɴᴋ :- {share_link}"
        
        return await self.message.reply(
            f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\n{additional_text}{link_text}</b>"
        )

async def allowed(_, __, message: Message) -> bool:
    return PUBLIC_FILE_STORE or (message.from_user and message.from_user.id in ADMINS)

@Client.on_message((filters.document | filters.video | filters.audio) & filters.private & filters.create(allowed))
async def incoming_gen_link(bot: Client, message: Message):
    link_gen = LinkGenerator(bot, message)
    file_type = message.media
    file_id, _ = unpack_new_file_id((getattr(message, file_type.value)).file_id)
    
    string = f'file_{file_id}'
    outstr = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    user = await get_user(message.from_user.id)
    share_link = await link_gen.generate_share_link(outstr)
    await link_gen.send_link_message(share_link, user)

@Client.on_message(filters.command(['link', 'plink']) & filters.create(allowed))
async def gen_link_s(bot: Client, message: Message):
    link_gen = LinkGenerator(bot, message)
    replied = message.reply_to_message
    if not replied:
        return await message.reply('Reply to a message to get a shareable link.')

    if replied.media:
        # Handle media messages
        file_type = replied.media
        if file_type not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, 
                            enums.MessageMediaType.DOCUMENT]:
            return await message.reply("**ʀᴇᴘʟʏ ᴛᴏ ᴀ sᴜᴘᴘᴏʀᴛᴇᴅ ᴍᴇᴅɪᴀ**")
        
        if message.has_protected_content and message.chat.id not in ADMINS:
            return await message.reply("okDa")

        file_id, _ = unpack_new_file_id((getattr(replied, file_type.value)).file_id)
        prefix = 'filep_' if message.text.lower().strip() == "/plink" else 'file_'
        outstr = base64.urlsafe_b64encode(f"{prefix}{file_id}".encode("ascii")).decode().strip("=")
        
        user = await get_user(message.from_user.id)
        share_link = await link_gen.generate_share_link(outstr)
        await link_gen.send_link_message(share_link, user)

    elif replied.text:
        # Handle text messages
        text_content = replied.text.strip()
        encoded_text = base64.urlsafe_b64encode(text_content.encode("utf-8")).decode("ascii").strip("=")
        username = await link_gen.get_bot_username()
        deep_link = f"https://t.me/{username}?start=text_{encoded_text}"
        await message.reply(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ text link:</b>\n\n🔗 Link: {deep_link}")
    
    else:
        await message.reply("Unsupported message type. Please reply to a media or text message.")




@Client.on_message(filters.command(['batch', 'pbatch']) & filters.create(allowed))
async def gen_link_batch(bot, message):
    username = (await bot.get_me()).username
    if " " not in message.text:
        return await message.reply("Use correct format.\nExample /batch https://t.me/vj_botz/10 https://t.me/vj_botz/20.")
    links = message.text.strip().split(" ")
    if len(links) != 3:
        return await message.reply("Use correct format.\nExample /batch https://t.me/vj_botz/10 https://t.me/vj_botz/20.")
    cmd, first, last = links
    regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
    match = regex.match(first)
    if not match:
        return await message.reply('Invalid link')
    f_chat_id = match.group(4)
    f_msg_id = int(match.group(5))
    if f_chat_id.isnumeric():
        f_chat_id = int(("-100" + f_chat_id))


    
    match = regex.match(last)
    if not match:
        return await message.reply('Invalid link')
    l_chat_id = match.group(4)
    l_msg_id = int(match.group(5))
    if l_chat_id.isnumeric():
        l_chat_id = int(("-100" + l_chat_id))

    if f_chat_id != l_chat_id:
        return await message.reply("Chat ids not matched.")
    try:
        chat_id = (await bot.get_chat(f_chat_id)).id
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')


    
    sts = await message.reply("**ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ ғᴏʀ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ**.\n**ᴛʜɪs ᴍᴀʏ ᴛᴀᴋᴇ ᴛɪᴍᴇ ᴅᴇᴘᴇɴᴅɪɴɢ ᴜᴘᴏɴ ɴᴜᴍʙᴇʀ ᴏғ ᴍᴇssᴀɢᴇs**")

    FRMT = "**ɢᴇɴᴇʀᴀᴛɪɴɢ ʟɪɴᴋ...**\n**ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs:** {total}\n**ᴅᴏɴᴇ:** {current}\n**ʀᴇᴍᴀɪɴɪɴɢ:** {rem}\n**sᴛᴀᴛᴜs:** {sts}"

    outlist = []

    # file store without db channel
    og_msg = 0
    tot = 0
    async for msg in bot.iter_messages(f_chat_id, l_msg_id, f_msg_id):
        tot += 1
        if msg.empty or msg.service:
            continue
        if not msg.media:
            # only media messages supported.
            continue
        try:
            file_type = msg.media
            file = getattr(msg, file_type.value)
            caption = getattr(msg, 'caption', '')
            if caption:
                caption = caption.html
            if file:
                file = {
                    "file_id": file.file_id,
                    "caption": caption,
                    "title": getattr(file, "file_name", ""),
                    "size": file.file_size,
                    "protect": cmd.lower().strip() == "/pbatch",
                }

                og_msg +=1
                outlist.append(file)
        except:
            pass
        if not og_msg % 20:
            try:
                await sts.edit(FRMT.format(total=l_msg_id-f_msg_id, current=tot, rem=((l_msg_id-f_msg_id) - tot), sts="Saving Messages"))
            except:
                pass
    with open(f"batchmode_{message.from_user.id}.json", "w+") as out:
        json.dump(outlist, out)
    post = await bot.send_document(LOG_CHANNEL, f"batchmode_{message.from_user.id}.json", file_name="Batch.json", caption="⚠️Generated for filestore.")
    os.remove(f"batchmode_{message.from_user.id}.json")
    file_id, ref = unpack_new_file_id(post.document.file_id)
    user_id = message.from_user.id
    user = await get_user(user_id)
    if WEBSITE_URL_MODE == True:
        share_link = f"{WEBSITE_URL}?Zahid=BATCH-{file_id}"
    else:
        share_link = f"https://t.me/{username}?start=BATCH-{file_id}"
    if user["base_site"] and user["shortener_api"] != None:
        short_link = await get_short_link(user, share_link)
        await sts.edit(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\nContains `{og_msg}` files.\n\n🖇️ sʜᴏʀᴛ ʟɪɴᴋ :- {short_link}</b>")
    else:
        await sts.edit(f"<b>⭕ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ:\n\nContains `{og_msg}` files.\n\n🔗 ᴏʀɪɢɪɴᴀʟ ʟɪɴᴋ :- {share_link}</b>")
        