import time
import math
import humanize
from pyrogram.types import Message

async def progress_callback(current, total, message: Message, start_time: float, status: str):
    """Updates the message with progress information."""
    now = time.time()
    diff = now - start_time
    if diff == 0:  # Avoid division by zero
        diff = 0.01

    percent = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff)
    eta = round((total - current) / speed) if speed > 0 else 0

    progress_str = (
        f"**{status}**: `{humanize.naturalsize(current)}` / `{humanize.naturalsize(total)}` "
        f"(`{percent:.1f}%`)\n"
        f"**Speed**: `{humanize.naturalsize(speed)}/s`\n"
        f"**ETA**: `{humanize.naturaldelta(eta)}` | **Elapsed**: `{humanize.naturaldelta(elapsed_time)}`"
    )

    # Edit message only every few seconds to avoid flood waits
    if hasattr(message, 'last_update_time') and now - message.last_update_time < 3:
         return # Don't update too frequently
    try:
        await message.edit_text(progress_str)
        message.last_update_time = now # Store last update time in the message object itself
    except Exception: # Ignore potential errors like message not modified
        pass

def is_adult(text: str | None) -> bool:
    """Checks if text contains adult keywords."""
    if not text:
        return False
    from .. import config # Local import to avoid circular dependency issues at module level
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in config.ADULT_KEYWORDS_LOWER)

def format_time_diff(seconds: int) -> str:
    """Formats seconds into a human-readable string (e.g., 1 minute 5 seconds)."""
    return humanize.naturaldelta(seconds)
