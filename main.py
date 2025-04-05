import asyncio
import logging
from pyrogram import Client, idle

# Import config first to load environment variables and validate
from bot import config
# Import database and load it
from bot import database

# Setup logging based on config if needed, but basicConfig is often sufficient
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # Output logs to console
)
# Suppress excessively verbose logs from libraries if needed
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

LOGGER = logging.getLogger(__name__)

async def main():
    LOGGER.info("Starting the Terabox Downloader Bot...")

    # Load the database content
    await database.load_db()
    LOGGER.info(f"Database loaded. Found {len(await database.get_all_users())} users initially.")


    # Dynamically discover handlers (optional but good practice)
    # For this structure, explicit imports might be simpler:
    from bot.handlers import start, token, message, broadcast

    # Initialize the Pyrogram Client
    # Using Bot token for bot functionalities
    # API ID/Hash are needed for user actions like checking channel membership efficiently
    app = Client(
        "TeraboxDownloaderBot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        plugins=dict(root="bot.handlers") # Load handlers from the handlers package
    )

    try:
        LOGGER.info("Starting Pyrogram Client...")
        await app.start()
        me = await app.get_me()
        LOGGER.info(f"Bot started as {me.first_name} (@{me.username}) ID: {me.id}")

        # Log some config values for verification (excluding sensitive ones)
        LOGGER.info(f"FSUB_ID: {config.FSUB_ID}")
        LOGGER.info(f"DUMP_CHAT_ID: {config.DUMP_CHAT_ID}")
        LOGGER.info(f"ADMIN_IDS: {config.ADMIN_IDS}")
        LOGGER.info(f"BROADCAST_ENABLED: {config.BROADCAST_ENABLED}")
        LOGGER.info(f"SPAM_DELAY_SECONDS: {config.SPAM_DELAY_SECONDS}")
        LOGGER.info(f"TOKEN_EXPIRY_HOURS: {config.TOKEN_EXPIRY_HOURS}")
        LOGGER.info(f"COOKIE_LOADED: {'Yes' if config.TERABOX_COOKIE else 'No'}")


        # Keep the bot running until interrupted
        LOGGER.info("Bot is now running. Press Ctrl+C to stop.")
        await idle()

    except Exception as e:
        LOGGER.critical(f"Failed to start or run the bot: {e}", exc_info=True)
    finally:
        LOGGER.info("Stopping Pyrogram Client...")
        if app.is_initialized:
             await app.stop()
        LOGGER.info("Bot stopped.")

if __name__ == "__main__":
    # Use asyncio.run for clean startup/shutdown
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped by user (Ctrl+C).")
