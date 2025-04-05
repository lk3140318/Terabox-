import time
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant, FloodWait

from . import config, database
from .utils.helpers import format_time_diff

LOGGER = logging.getLogger(__name__)

# --- Decorator for Admin Check ---
def admin_required(func):
    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        if message.from_user.id not in config.ADMIN_IDS:
            return await message.reply_text("❌ **Access Denied:** You are not authorized to use this command.")
        return await func(client, message, *args, **kwargs)
    return wrapper

# --- Decorator for Forced Subscription ---
def fsub_required(func):
    @wraps(func)
    async def wrapper(client: Client, update: Message | CallbackQuery, *args, **kwargs):
        user = update.from_user
        fsub_channel_id = config.FSUB_ID

        if user.id in config.ADMIN_IDS: # Admins bypass FSUB
             # LOGGER.debug(f"Admin {user.id} bypassed FSUB check.")
             return await func(client, update, *args, **kwargs)

        if not fsub_channel_id:
            LOGGER.warning("FSUB_ID not set, skipping force subscription check.")
            return await func(client, update, *args, **kwargs)

        try:
            member = await client.get_chat_member(chat_id=fsub_channel_id, user_id=user.id)
            # LOGGER.debug(f"User {user.id} membership status in {fsub_channel_id}: {member.status}")
            if member.status not in ["member", "administrator", "creator"]:
                raise UserNotParticipant
        except UserNotParticipant:
            try:
                # Try to get channel link
                chat = await client.get_chat(fsub_channel_id)
                invite_link = chat.invite_link
                if not invite_link: # Fallback if no invite link (e.g., bot removed)
                    # Attempt to generate one if the bot has rights (unlikely for public channels)
                     try:
                         invite_link = await client.export_chat_invite_link(fsub_channel_id)
                     except Exception:
                         invite_link = f"https://t.me/{chat.username}" if chat.username else None

                channel_name = chat.title
                msg_text = f"👋 Hey {user.mention},\n\n" \
                           f"You need to join our channel **'{channel_name}'** to use this bot.\n\n" \
                           "Please join and then try again!"
                button_text = f"Join {channel_name}"

                markup = None
                if invite_link:
                     markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=invite_link)]])
                else:
                     msg_text += "\n\n*Could not find an invite link for the required channel.*"

                if isinstance(update, Message):
                     await update.reply_text(msg_text, quote=True, reply_markup=markup, disable_web_page_preview=True)
                elif isinstance(update, CallbackQuery):
                     await update.answer("You must join our channel first!", show_alert=True)
                     # Send a new message in the chat if possible
                     try:
                        await client.send_message(update.message.chat.id, msg_text, reply_markup=markup, disable_web_page_preview=True)
                     except Exception as e:
                        LOGGER.error(f"Failed to send FSUB message after CBQ: {e}")
                return # Stop processing

            except FloodWait as fw:
                LOGGER.warning(f"FloodWait during FSUB check: {fw.value} seconds. User: {user.id}")
                await asyncio.sleep(fw.value + 1)
                # Optionally retry or just return
                return
            except Exception as e:
                LOGGER.error(f"Error during FSUB check for {user.id} in {fsub_channel_id}: {e}", exc_info=True)
                error_message = "⚠️ An error occurred while checking subscription. Please try again later."
                if isinstance(update, Message):
                    await update.reply_text(error_message, quote=True)
                elif isinstance(update, CallbackQuery):
                    await update.answer(error_message, show_alert=True)
                return # Stop processing

        # User is subscribed, proceed with the original function
        return await func(client, update, *args, **kwargs)
    return wrapper

# --- Decorator for Token Verification ---
def token_required(func):
    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        user_id = message.from_user.id

        if user_id in config.ADMIN_IDS: # Admins bypass token check
            # LOGGER.debug(f"Admin {user_id} bypassed token check.")
            return await func(client, message, *args, **kwargs)

        token_data = await database.get_user_token_data(user_id)
        now_utc = datetime.now(timezone.utc)

        if not token_data or 'expires' not in token_data:
            await message.reply_text(
                "❌ **Token Required:**\n"
                "You need a valid token to perform this action. Please use the /get_token command first.",
                quote=True
            )
            return

        expires_at = token_data['expires']

        if now_utc > expires_at:
             await message.reply_text(
                f"⏳ **Token Expired:**\n"
                f"Your token has expired ({humanize.naturaltime(now_utc - expires_at)} ago). "
                f"Please use /get_token to get a new one.",
                quote=True
            )
             return

        # Token is valid, proceed
        # LOGGER.debug(f"User {user_id} token check passed.")
        return await func(client, message, *args, **kwargs)
    return wrapper


# --- Decorator for Anti-Spam ---
def spam_check(func):
    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        user_id = message.from_user.id

        if user_id in config.ADMIN_IDS: # Admins bypass spam check
            # LOGGER.debug(f"Admin {user_id} bypassed spam check.")
            return await func(client, message, *args, **kwargs)

        last_action_time = await database.get_last_spam_time(user_id)
        now_utc = datetime.now(timezone.utc)
        delay = timedelta(seconds=config.SPAM_DELAY_SECONDS)

        if last_action_time:
            time_since_last = now_utc - last_action_time
            if time_since_last < delay:
                wait_time = delay - time_since_last
                wait_seconds = int(wait_time.total_seconds())
                await message.reply_text(
                    f"⏳ **Spam Protection:**\n"
                    f"Please wait `{format_time_diff(wait_seconds)}` before starting another download.",
                    quote=True
                )
                return

        # Proceed, but update timestamp *before* calling the function
        # to prevent race conditions if the function takes time
        await database.update_spam_time(user_id)
        # LOGGER.debug(f"User {user_id} spam check passed.")
        return await func(client, message, *args, **kwargs)
    return wrapper
