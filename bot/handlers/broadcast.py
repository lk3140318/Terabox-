import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from .. import config, database
from ..decorators import admin_required

LOGGER = logging.getLogger(__name__)

@Client.on_message(filters.command("broadcast") & filters.private)
@admin_required
async def broadcast_command(client: Client, message: Message):
    if not config.BROADCAST_ENABLED:
        return await message.reply_text("❌ Broadcast feature is currently disabled.")

    if not message.reply_to_message and len(message.command) == 1:
        return await message.reply_text(
            "**Usage:** Reply to a message or type `/broadcast <message text>` to broadcast."
        )

    broadcast_msg = message.reply_to_message if message.reply_to_message else message
    text_to_send = message.text.split(None, 1)[1] if len(message.command) > 1 else None # Text after /broadcast command

    user_ids = await database.get_all_users()
    total_users = len(user_ids)

    if total_users == 0:
        return await message.reply_text("No users found in the database to broadcast to.")

    status_message = await message.reply_text(
        f"📣 Starting broadcast to **{total_users}** users..."
    )

    success_count = 0
    failed_count = 0
    blocked_count = 0
    deactivated_count = 0
    start_time = asyncio.get_event_loop().time()

    for user_id in user_ids:
        try:
            if text_to_send: # Send text provided after /broadcast command
                await client.send_message(user_id, text_to_send)
            elif broadcast_msg: # Forward the replied-to message
                await broadcast_msg.forward(user_id)
            else:
                 # This case should ideally not be reached due to initial check
                 LOGGER.warning("Broadcast attempted without message content.")
                 continue # Skip if somehow no message content

            success_count += 1
            # Avoid hitting limits too quickly
            await asyncio.sleep(0.1) # Sleep 100ms between sends

        except FloodWait as fw:
            LOGGER.warning(f"FloodWait encountered during broadcast: sleeping for {fw.value} seconds.")
            await status_message.edit_text(
                f"FloodWait: Sleeping for {fw.value}s... "
                f"({success_count}/{total_users} sent)"
            )
            await asyncio.sleep(fw.value + 2) # Sleep a bit longer than required
             # Retry sending to the same user after sleep
            try:
                if text_to_send:
                    await client.send_message(user_id, text_to_send)
                elif broadcast_msg:
                     await broadcast_msg.forward(user_id)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as retry_err: # Handle errors on retry
                 LOGGER.error(f"Failed to send broadcast to {user_id} after FloodWait retry: {retry_err}")
                 failed_count += 1 # Count as failed if retry fails
        except UserIsBlocked:
            LOGGER.info(f"User {user_id} has blocked the bot. Skipping.")
            blocked_count += 1
            failed_count += 1
        except InputUserDeactivated:
            LOGGER.info(f"User {user_id} is deactivated. Skipping.")
            deactivated_count += 1
            failed_count += 1
        except Exception as e:
            LOGGER.error(f"Failed to send broadcast message to {user_id}: {e}")
            failed_count += 1

        # Update status message periodically
        if (success_count + failed_count) % 50 == 0: # Update every 50 users
             current_time = asyncio.get_event_loop().time()
             elapsed = current_time - start_time
             await status_message.edit_text(
                 f"📣 Broadcasting...\n"
                 f"Sent: {success_count}/{total_users}\n"
                 f"Failed: {failed_count} (Blocked: {blocked_count}, Deactivated: {deactivated_count})\n"
                 f"Elapsed: {int(elapsed)}s"
            )

    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    await status_message.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"Total Users: {total_users}\n"
        f"Successfully Sent: {success_count}\n"
        f"Failed: {failed_count}\n"
        f"  - Blocked: {blocked_count}\n"
        f"  - Deactivated: {deactivated_count}\n"
        f"Total Time: {total_time:.2f} seconds"
    )
    LOGGER.info(f"Broadcast finished. Success: {success_count}, Failed: {failed_count}")
