import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from .. import config, database
from ..decorators import fsub_required # Import fsub decorator

LOGGER = logging.getLogger(__name__)

# Define START_TEXT and HELP_TEXT
START_TEXT = """
👋 Hello {mention}!

I am the **Terabox Downloader Bot** 🚀.

Send me any valid Terabox video link (from `1024terabox.com`, `teraboxlink.com`, or `terafileshare.com`) and I'll download the video and send it directly to you!

**Features:**
✨ Fast Downloads
🔒 Secure & Private
🔞 Adult Content Filter
⏳ Anti-Spam Protection

**Before you start:**
1.  Make sure you are subscribed to our update channel (button below if required).
2.  Use the /get_token command to get your daily access token.

Happy Downloading!
"""

HELP_TEXT = """
**Terabox Downloader Bot Help**

1.  **Get Started:** Use the /start command.
2.  **Force Subscription:** You might need to join a specific channel first (the bot will tell you).
3.  **Get Token:** Use /get_token to receive a token valid for 24 hours. You need this before downloading.
4.  **Download:** Simply send a valid Terabox video link to the bot.
    - Supported domains: `1024terabox.com`, `teraboxlink.com`, `terafileshare.com`
    - The video will be downloaded and sent as an MP4 file (up to 2GB).
5.  **Troubleshooting:**
    - *Invalid Link:* Ensure the link is correct and publicly accessible or use a valid `TERABOX_COOKIE` in the bot's config for private links.
    - *Download Failed:* Terabox might be blocking the download, or the file might be too large/removed.
    - *Token Expired:* Use /get_token again.
    - *Spam Wait:* Wait for the cooldown period before trying again.

**Admin Commands (for authorized users only):**
- `/broadcast <message>`: Send a message to all bot users.

If you encounter issues, please report them to the bot admin.
"""


@Client.on_message(filters.command("start") & filters.private)
@fsub_required # Apply FSUB check on start
async def start_command(client: Client, message: Message):
    user = message.from_user
    LOGGER.info(f"/start command received from {user.id} ({user.first_name})")
    await database.add_user(user.id) # Add user to DB for potential broadcasts

    # Prepare button for FSUB channel if needed, otherwise maybe a help button?
    buttons = []
    if config.FSUB_ID:
         try:
             fsub_chat = await client.get_chat(config.FSUB_ID)
             if fsub_chat.invite_link:
                 buttons.append([InlineKeyboardButton(f"📢 Join {fsub_chat.title}", url=fsub_chat.invite_link)])
             elif fsub_chat.username:
                  buttons.append([InlineKeyboardButton(f"📢 Join {fsub_chat.title}", url=f"https://t.me/{fsub_chat.username}")])
         except Exception as e:
             LOGGER.warning(f"Could not get details for FSUB_ID {config.FSUB_ID}: {e}")
    buttons.append([InlineKeyboardButton("🔑 Get Token", callback_data="get_token_cb"), InlineKeyboardButton("❓ Help", callback_data="help_cb")])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    await message.reply_text(
        START_TEXT.format(mention=user.mention),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        quote=True
    )

@Client.on_message(filters.command("help") & filters.private)
@fsub_required # Apply FSUB check on help too
async def help_command(client: Client, message: Message):
     user = message.from_user
     LOGGER.info(f"/help command received from {user.id}")
     await message.reply_text(HELP_TEXT, disable_web_page_preview=True, quote=True)

@Client.on_callback_query(filters.regex("^help_cb$"))
async def help_callback(client: Client, callback_query: CallbackQuery):
    LOGGER.info(f"Help callback received from {callback_query.from_user.id}")
    await callback_query.answer() # Answer the callback first
    await callback_query.message.edit_text(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="start_cb")]]) # Add a back button
    )

@Client.on_callback_query(filters.regex("^start_cb$"))
async def start_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    LOGGER.info(f"Start callback received from {user.id}")
    await callback_query.answer()

    buttons = []
    if config.FSUB_ID:
         try:
             fsub_chat = await client.get_chat(config.FSUB_ID)
             if fsub_chat.invite_link:
                 buttons.append([InlineKeyboardButton(f"📢 Join {fsub_chat.title}", url=fsub_chat.invite_link)])
             elif fsub_chat.username:
                  buttons.append([InlineKeyboardButton(f"📢 Join {fsub_chat.title}", url=f"https://t.me/{fsub_chat.username}")])
         except Exception: pass # Ignore errors here
    buttons.append([InlineKeyboardButton("🔑 Get Token", callback_data="get_token_cb"), InlineKeyboardButton("❓ Help", callback_data="help_cb")])

    await callback_query.message.edit_text(
        START_TEXT.format(mention=user.mention),
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
                                                     )
