import os
import asyncio
import logging
import time
import httpx
import aiofiles
from functools import partial

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, RPCError

from .. import config, database
from ..decorators import fsub_required, token_required, spam_check
from ..utils.terabox import extract_terabox_link, get_terabox_download_link
from ..utils.helpers import progress_callback, is_adult, format_time_diff

LOGGER = logging.getLogger(__name__)
MAX_TG_UPLOAD_SIZE_BYTES = 2 * 1024 * 1024 * 1024 # 2 GB

# --- Main Message Handler for Links ---
@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "get_token", "broadcast"]))
@fsub_required
@token_required
@spam_check
async def message_handler(client: Client, message: Message):
    user = message.from_user
    user_id = user.id
    LOGGER.info(f"Received message from {user_id}: {message.text[:50]}...")

    terabox_link = extract_terabox_link(message.text)

    if not terabox_link:
        LOGGER.warning(f"No valid Terabox link found in message from {user_id}.")
        await message.reply_text(
            "❌ **Invalid Input:**\n"
            "Please send me a valid Terabox link from one of the supported domains:\n"
            "- `1024terabox.com`\n"
            "- `teraboxlink.com`\n"
            "- `terafileshare.com`",
            quote=True
        )
        # Important: Remove spam timestamp if validation fails early, allowing retry
        # This requires modifying the spam_check decorator or the database function
        # For simplicity now, we don't remove it, user has to wait.
        # Alternative: Pass a flag to spam_check or have it return a success/fail status.
        return

    LOGGER.info(f"Processing Terabox link: {terabox_link} for user {user_id}")
    status_msg = await message.reply_text("⏳ Processing your link...", quote=True)

    try:
        direct_link, filename, file_size_str = await get_terabox_download_link(terabox_link)

        if not direct_link or not filename:
            await status_msg.edit_text("❌ **Download Failed:**\nCould not extract the download link or filename. The link might be invalid, private (and cookie missing/invalid), or Terabox changed their system.")
            return

        LOGGER.info(f"Extracted Link: {direct_link[:100]}..., Filename: {filename}, Size: {file_size_str} for user {user_id}")

        # --- Adult Content Check ---
        if is_adult(filename):
            LOGGER.warning(f"Adult content detected in filename: {filename} for user {user_id}. Blocking download.")
            await status_msg.edit_text(
                "🔞 **Content Blocked:**\n"
                "The filename suggests adult content, which is not allowed by this bot.",
            )
            return

        # --- Download and Upload ---
        await download_and_upload(client, message, status_msg, direct_link, filename, file_size_str)

    except Exception as e:
        LOGGER.error(f"Error processing link {terabox_link} for user {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ **An unexpected error occurred:**\n`{str(e)}`\nPlease try again later or contact an admin.")

async def download_and_upload(client: Client, original_message: Message, status_msg: Message, download_url: str, filename: str, file_size_str: str):
    user_id = original_message.from_user.id
    download_path = os.path.join(config.DOWNLOAD_DIR, f"{user_id}_{filename}") # User-specific temp filename
    start_time = time.time()

    LOGGER.info(f"Starting download for {filename} (User: {user_id})")
    await status_msg.edit_text(f"📥 Starting download: **{filename}** ({file_size_str})...")

    downloaded_successfully = False
    file_size_bytes = 0
    try:
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as dl_client: # No timeout for download stream
             async with dl_client.stream("GET", download_url, headers={"Referer": "https://www.terabox.com/"}) as response:
                response.raise_for_status() # Check if request was successful

                # Get file size from header if possible
                content_length_header = response.headers.get("Content-Length")
                if content_length_header:
                    file_size_bytes = int(content_length_header)
                    LOGGER.info(f"File size from header: {file_size_bytes} bytes")
                    if file_size_bytes > MAX_TG_UPLOAD_SIZE_BYTES:
                         await status_msg.edit_text(
                            f"❌ **File Too Large:**\n"
                            f"The file `({_format_bytes(file_size_bytes)})` exceeds the Telegram upload limit of 2 GB."
                         )
                         return # Stop processing
                else:
                    LOGGER.warning("Content-Length header not found. Cannot pre-check size.")
                    # We might still hit the limit during upload

                # Partial function for progress callback
                progress = partial(progress_callback, message=status_msg, start_time=start_time, status="Downloading")

                # Ensure directory exists
                os.makedirs(os.path.dirname(download_path), exist_ok=True)

                current_downloaded = 0
                async with aiofiles.open(download_path, mode='wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024*1024): # Read in 1MB chunks
                        await f.write(chunk)
                        current_downloaded += len(chunk)
                        if file_size_bytes > 0: # Only show progress if total size known
                            await progress(current=current_downloaded, total=file_size_bytes)
                        # Basic check during download if size becomes available or exceeds limit
                        if current_downloaded > MAX_TG_UPLOAD_SIZE_BYTES:
                             raise ValueError("File exceeds Telegram upload limit (detected during download).")

                # Final progress update after download finishes
                if file_size_bytes > 0:
                    await progress(current=file_size_bytes, total=file_size_bytes)
                else:
                    # If size wasn't known, update status without percentage
                     elapsed_time = round(time.time() - start_time)
                     await status_msg.edit_text(f"✅ Download complete: **{filename}**\nElapsed: {format_time_diff(elapsed_time)}")

                file_size_bytes = current_downloaded # Update size with actual downloaded bytes
                downloaded_successfully = True
                LOGGER.info(f"Download complete: {filename} ({_format_bytes(file_size_bytes)}) for user {user_id}")

    except httpx.HTTPStatusError as e:
        LOGGER.error(f"HTTP Error during download: {e.response.status_code} for {download_url}")
        await status_msg.edit_text(f"❌ **Download Failed:** Received status code {e.response.status_code} from download server.")
        return
    except httpx.RequestError as e:
        LOGGER.error(f"Network error during download: {e}")
        await status_msg.edit_text(f"❌ **Download Failed:** Network error: {e}")
        return
    except ValueError as e: # Catch our custom size error
         LOGGER.error(f"Download stopped: {e} for {filename}")
         await status_msg.edit_text(f"❌ **File Too Large:** {e}")
         return
    except Exception as e:
        LOGGER.error(f"Error during file download/write for {filename}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ **Download Failed:** An error occurred: `{str(e)}`")
        return
    finally:
        # Clean up partially downloaded file if download failed mid-way
        if not downloaded_successfully and os.path.exists(download_path):
            try:
                os.remove(download_path)
                LOGGER.info(f"Removed incomplete download: {download_path}")
            except OSError as err:
                LOGGER.error(f"Error removing incomplete file {download_path}: {err}")


    if not downloaded_successfully:
        return # Stop if download failed

    # --- Uploading ---
    LOGGER.info(f"Starting upload: {filename} ({_format_bytes(file_size_bytes)}) for user {user_id}")
    await status_msg.edit_text(f"⬆️ Uploading: **{filename}** ({_format_bytes(file_size_bytes)})...")
    upload_start_time = time.time()
    uploaded_message = None

    try:
        # Partial function for upload progress
        upload_progress = partial(progress_callback, message=status_msg, start_time=upload_start_time, status="Uploading")

        # Attempt to send as video
        uploaded_message = await client.send_video(
            chat_id=user_id,
            video=download_path,
            caption=f"✅ **Downloaded:** `{filename}`\n\n__via {client.me.mention}__",
            file_name=filename,
            supports_streaming=True,
            progress=upload_progress
        )
        upload_duration = time.time() - upload_start_time
        LOGGER.info(f"Upload successful for {filename} to user {user_id} in {upload_duration:.2f}s")
        await status_msg.delete() # Remove the status message

    except FloodWait as fw:
        LOGGER.warning(f"FloodWait during upload: sleeping for {fw.value} seconds.")
        await status_msg.edit_text(f"FloodWait: Upload paused for {fw.value}s...")
        await asyncio.sleep(fw.value + 2)
        # Retry upload
        try:
             uploaded_message = await client.send_video(
                chat_id=user_id, video=download_path, caption=f"✅ **Downloaded:** `{filename}`\n\n__via {client.me.mention}__",
                file_name=filename, supports_streaming=True, progress=upload_progress
            )
             await status_msg.delete()
        except Exception as retry_err:
            LOGGER.error(f"Upload failed after FloodWait retry for {filename}: {retry_err}")
            await status_msg.edit_text(f"❌ **Upload Failed:** Error after FloodWait: `{retry_err}`")
    except RPCError as e:
         # Catch specific errors like FILE_PARTS_TOO_BIG if needed, though size check should prevent this
         LOGGER.error(f"Telegram RPC Error during upload for {filename}: {e}")
         await status_msg.edit_text(f"❌ **Upload Failed:** Telegram API error: `{e}`")
    except Exception as e:
        LOGGER.error(f"Error during upload for {filename}: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ **Upload Failed:** An unexpected error occurred: `{str(e)}`")

    # --- Forward to Dump Channel ---
    if uploaded_message and config.DUMP_CHAT_ID:
        try:
            await uploaded_message.forward(config.DUMP_CHAT_ID)
            LOGGER.info(f"Forwarded {filename} to dump channel {config.DUMP_CHAT_ID}")
        except FloodWait as fw:
            LOGGER.warning(f"FloodWait forwarding to dump channel: sleeping {fw.value}s")
            await asyncio.sleep(fw.value + 1)
            try:
                await uploaded_message.forward(config.DUMP_CHAT_ID)
            except Exception as dump_retry_err:
                 LOGGER.error(f"Failed to forward {filename} to dump channel after FloodWait: {dump_retry_err}")
        except Exception as dump_err:
            LOGGER.error(f"Failed to forward {filename} to dump channel {config.DUMP_CHAT_ID}: {dump_err}")

    # --- Cleanup ---
    if os.path.exists(download_path):
        try:
            os.remove(download_path)
            # LOGGER.debug(f"Removed downloaded file: {download_path}")
        except OSError as err:
            LOGGER.error(f"Error removing file {download_path}: {err}")

# Helper to format bytes for display within the handler
def _format_bytes(size_bytes: int) -> str:
    import math
    import humanize
    if size_bytes == 0: return "0 B"
    try:
        return humanize.naturalsize(size_bytes, binary=True)
    except Exception: # Fallback if humanize fails for some reason
        size_name = ("B", "KiB", "MiB", "GiB", "TiB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
