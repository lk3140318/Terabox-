import uuid
import logging
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .. import config, database
from ..decorators import fsub_required # Needs FSUB check
from ..utils.helpers import format_time_diff

LOGGER = logging.getLogger(__name__)

@Client.on_message(filters.command("get_token") & filters.private)
@fsub_required # Ensure user is subscribed before getting token
async def get_token_command(client: Client, message: Message):
    user = message.from_user
    LOGGER.info(f"/get_token command received from {user.id}")

    await _generate_and_send_token(client, user.id, message)


@Client.on_callback_query(filters.regex("^get_token_cb$"))
@fsub_required # Also check FSUB on callback
async def get_token_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    LOGGER.info(f"Get token callback received from {user.id}")
    await callback_query.answer("Generating your token...", show_alert=False) # Give feedback
    # Use the original message from the callback query to reply or edit
    await _generate_and_send_token(client, user.id, callback_query.message)


async def _generate_and_send_token(client: Client, user_id: int, source_message: Message):
    """Generates, stores, and sends a token to the user."""
    token_expiry_hours = config.TOKEN_EXPIRY_HOURS
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(hours=token_expiry_hours)

    # Check if user already has a recent, valid token
    existing_token_data = await database.get_user_token_data(user_id)
    if existing_token_data and existing_token_data['expires'] > now_utc:
        existing_token = existing_token_data['token']
        time_left = existing_token_data['expires'] - now_utc
        time_left_str = format_time_diff(int(time_left.total_seconds()))
        await source_message.reply_text(
            f"✅ **You already have an active token:**\n\n"
            f"`{existing_token}`\n\n"
            f"It's valid for another **{time_left_str}**.\n\n"
            f"You can use this token to download links.",
            quote=True
        )
        return

    # Generate a new token
    new_token = str(uuid.uuid4()) # Simple unique token
    await database.store_token(user_id, new_token, expires_at)

    expiry_time_str = expires_at.strftime("%Y-%m-%d %H:%M:%S %Z") # Format for display

    await source_message.reply_text(
        f"🔑 **Your New Access Token:**\n\n"
        f"`{new_token}`\n\n"
        f"This token is valid for **{token_expiry_hours} hours** (until {expiry_time_str}).\n\n"
        f"You can now send me Terabox links to download.",
        quote=True
)
