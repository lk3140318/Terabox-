import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

# Load .env file if it exists (for local development)
load_dotenv()

def get_env_variable(name: str, default=None, required=True, var_type=str):
    """Gets an environment variable, logs, and performs type conversion."""
    value = os.getenv(name, default)
    if required and value is None:
        LOGGER.error(f"Missing required environment variable: {name}")
        raise ValueError(f"Environment variable '{name}' is required but not set.")
    if value is None: # Not required and not set
        return None
    try:
        if var_type == bool:
            if isinstance(value, str):
                return value.lower() in ('true', '1', 't', 'y', 'yes')
            return bool(value)
        elif var_type == int:
            return int(value)
        elif var_type == list:
            # Expects comma-separated string for lists
            return [item.strip() for item in value.split(',') if item.strip()]
        else: # Default is str
            return str(value)
    except ValueError as e:
        LOGGER.error(f"Invalid type for environment variable {name}. Expected {var_type}. Value: {value}. Error: {e}")
        raise ValueError(f"Invalid type for environment variable {name}. Expected {var_type}.") from e

LOGGER.info("Loading configuration from environment variables...")

try:
    # Mandatory Variables
    API_ID = get_env_variable("24335028", var_type=int)
    API_HASH = get_env_variable("b204ec833fb451fb913fc8e683b232d0")
    BOT_TOKEN = get_env_variable("BOT_TOKEN")
    DUMP_CHAT_ID = get_env_variable("-1002428113336", var_type=int)
    FSUB_ID = get_env_variable("FSUB_ID", var_type=int)
    ADMIN_ID = get_env_variable("5213073489", var_type=list) # Returns a list of strings
    TERABOX_COOKIE = get_env_variable("TERABOX_COOKIE")

    # Convert ADMIN_ID elements to int after validation
    ADMIN_IDS = []
    for admin_id_str in ADMIN_ID:
        try:
            ADMIN_IDS.append(int(admin_id_str))
        except ValueError:
            LOGGER.warning(f"Invalid admin ID found: {admin_id_str}. Skipping.")
    if not ADMIN_IDS:
         raise ValueError("No valid ADMIN_ID found. Please provide at least one valid integer user ID.")


    # Optional Variables with Defaults
    BROADCAST_ENABLED = get_env_variable("BROADCAST", default="True", required=False, var_type=bool)
    DATABASE_FILE = get_env_variable("DATABASE_FILE", default="bot_database.json", required=False)
    DOWNLOAD_DIR = get_env_variable("DOWNLOAD_DIR", default="downloads/", required=False)
    ADULT_KEYWORDS = get_env_variable("ADULT_KEYWORDS", default="porn,xxx,sex,hentai,nudity,adult", required=False, var_type=list)
    SPAM_DELAY_SECONDS = get_env_variable("SPAM_DELAY_SECONDS", default="60", required=False, var_type=int)
    TOKEN_EXPIRY_HOURS = get_env_variable("TOKEN_EXPIRY_HOURS", default="24", required=False, var_type=int)

    # Create download directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
        LOGGER.info(f"Created download directory: {DOWNLOAD_DIR}")

    LOGGER.info("Configuration loaded successfully.")

except ValueError as e:
    LOGGER.critical(f"Configuration Error: {e}")
    # In a real deployment, you might exit here or raise the exception further
    exit(1) # Exit if config is invalid

# Make ADULT_KEYWORDS lowercase for case-insensitive comparison
ADULT_KEYWORDS_LOWER = [keyword.lower() for keyword in ADULT_KEYWORDS]
