import json
import logging
import asyncio
from datetime import datetime, timezone
from . import config

LOGGER = logging.getLogger(__name__)
DB_FILE = config.DATABASE_FILE
_db_lock = asyncio.Lock()
_database = {}

async def load_db():
    """Loads the database from the JSON file."""
    global _database
    async with _db_lock:
        try:
            with open(DB_FILE, 'r') as f:
                _database = json.load(f)
                LOGGER.info(f"Database loaded successfully from {DB_FILE}")
                # Ensure necessary keys exist
                _database.setdefault('users', [])
                _database.setdefault('tokens', {}) # { user_id: {"token": "...", "expires": timestamp_str} }
                _database.setdefault('spam_tracker', {}) # { user_id: timestamp_str }
        except FileNotFoundError:
            LOGGER.warning(f"Database file {DB_FILE} not found. Initializing empty database.")
            _database = {'users': [], 'tokens': {}, 'spam_tracker': {}}
            await save_db() # Create the file
        except json.JSONDecodeError:
            LOGGER.error(f"Error decoding JSON from {DB_FILE}. Backing up and starting fresh.")
            # Simple backup, consider more robust strategies if needed
            try:
                import shutil
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{DB_FILE}.backup_{timestamp}"
                shutil.copy(DB_FILE, backup_file)
                LOGGER.info(f"Backed up corrupted database to {backup_file}")
            except Exception as backup_err:
                 LOGGER.error(f"Could not back up corrupted database: {backup_err}")
            _database = {'users': [], 'tokens': {}, 'spam_tracker': {}}
            await save_db()

async def save_db():
    """Saves the current database state to the JSON file."""
    async with _db_lock:
        try:
            with open(DB_FILE, 'w') as f:
                json.dump(_database, f, indent=4)
            # LOGGER.debug(f"Database saved successfully to {DB_FILE}") # Can be noisy
        except Exception as e:
            LOGGER.error(f"Failed to save database to {DB_FILE}: {e}")

async def add_user(user_id: int):
    """Adds a user ID to the database if not already present."""
    if user_id not in _database.get('users', []):
        _database.setdefault('users', []).append(user_id)
        await save_db()
        LOGGER.info(f"User {user_id} added to database.")
        return True
    return False

async def get_all_users() -> list[int]:
    """Returns a list of all registered user IDs."""
    return _database.get('users', [])

async def store_token(user_id: int, token: str, expires_at: datetime):
    """Stores or updates a user's token and expiry."""
    _database.setdefault('tokens', {})[str(user_id)] = {
        'token': token,
        'expires': expires_at.isoformat() # Store as ISO string
    }
    await save_db()
    LOGGER.info(f"Token stored for user {user_id}")

async def get_user_token_data(user_id: int) -> dict | None:
    """Gets token data for a user, returns None if not found."""
    token_data = _database.get('tokens', {}).get(str(user_id))
    if token_data:
        # Convert expiry back to datetime object
        try:
            token_data['expires'] = datetime.fromisoformat(token_data['expires']).replace(tzinfo=timezone.utc)
            return token_data
        except (ValueError, TypeError):
             LOGGER.error(f"Could not parse expiry date for user {user_id}: {token_data.get('expires')}")
             # Optionally remove invalid entry
             # del _database['tokens'][str(user_id)]
             # await save_db()
             return None
    return None

async def update_spam_time(user_id: int):
    """Updates the last action timestamp for spam tracking."""
    now_utc = datetime.now(timezone.utc)
    _database.setdefault('spam_tracker', {})[str(user_id)] = now_utc.isoformat()
    await save_db()
    # LOGGER.debug(f"Spam timestamp updated for user {user_id}")

async def get_last_spam_time(user_id: int) -> datetime | None:
    """Gets the last action timestamp for a user."""
    timestamp_str = _database.get('spam_tracker', {}).get(str(user_id))
    if timestamp_str:
        try:
            # Return timezone-aware datetime object
            return datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            LOGGER.error(f"Could not parse spam timestamp for user {user_id}: {timestamp_str}")
            return None
    return None

# Load the DB when the module is imported
# asyncio.get_event_loop().run_until_complete(load_db()) # This might not work well outside main async context
# Better to call load_db() explicitly in main.py after loop starts
