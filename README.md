# Telegram Terabox Downloader Bot

A powerful and secure Telegram bot written in Python using Pyrogram to download videos from Terabox links, with features like force subscription, token verification, anti-spam, and admin broadcast. Designed for easy deployment on platforms like Koyeb using environment variables.

## Features

-   **Public Access:** Anyone can interact with the bot.
-   **Force Subscription:** Users must join a specified channel (`FSUB_ID`) before using download features.
-   **24-Hour Tokens:** Users need to obtain a temporary token (`/get_token`) valid for 24 hours.
-   **Multi-Domain Support:** Recognizes links from:
    -   `1024terabox.com`
    -   `teraboxlink.com`
    -   `terafileshare.com`
-   **Direct Video Download:** Fetches the actual video file using `TERABOX_COOKIE` and uploads it directly to Telegram as an MP4 (up to 2GB).
-   **Logging Channel:** Automatically forwards successfully downloaded videos to a designated channel/chat (`DUMP_CHAT_ID`).
-   **Adult Content Filter:** Blocks downloads if the filename contains configurable explicit keywords.
-   **Anti-Spam:** Limits users to one download attempt per minute (configurable).
-   **Admin Broadcast:** Allows admins (`ADMIN_ID`) to send messages to all registered bot users (enable/disable via `BROADCAST`).
-   **Environment Driven:** Fully configurable via environment variables – no hardcoding.
-   **Deployment Ready:** Includes `Procfile`, `requirements.txt`, `runtime.txt` for platforms like Koyeb.

## Required Environment Variables

You **MUST** set these environment variables for the bot to function correctly.

| Variable           | Description                                                                                                                            | Example                                                                          |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------- |
| `TELEGRAM_API`     | Your Telegram API ID. Get from [my.telegram.org/apps](https://my.telegram.org/apps).                                                     | `1234567`                                                                        |
| `TELEGRAM_HASH`    | Your Telegram API Hash. Get from [my.telegram.org/apps](https://my.telegram.org/apps).                                                   | `abcdef1234567890abcdef1234567890`                                               |
| `BOT_TOKEN`        | The token for your Telegram bot. Get from [@BotFather](https://t.me/BotFather).                                                         | `1234567890:ABCDEFGHIJKL-MNOPQRSTUVWXYZ12345`                                  |
| `DUMP_CHAT_ID`     | Channel/Group/User ID where successfully downloaded files are logged/forwarded. Use negative ID for channels/groups (e.g., -100...).      | `-1001234567890`                                                                 |
| `FSUB_ID`          | Channel ID for Force Subscription. Bot needs to be admin or channel must be public. Use negative ID (e.g., -100...).                       | `-1009876543210`                                                                 |
| `BROADCAST`        | Enable (`True`) or disable (`False`) the `/broadcast` command for admins.                                                                | `True`                                                                           |
| `ADMIN_ID`         | Comma-separated list of Telegram User IDs who are admins of the bot.                                                                    | `987654321,135792468`                                                            |
| `TERABOX_COOKIE`   | **CRUCIAL:** Your Terabox session cookies needed to fetch download links. **This is the most sensitive and potentially fragile part.** | `panlogin=...; browserid=...; ndus=...; csrfToken=...; lang=en; TSID=...; ...` |

### Optional Environment Variables

| Variable             | Description                                                            | Default Value                          |
| :------------------- | :--------------------------------------------------------------------- | :------------------------------------- |
| `DATABASE_FILE`      | Filename for the simple JSON database storing user data.               | `bot_database.json`                    |
| `DOWNLOAD_DIR`       | Temporary directory for downloading files before uploading.            | `downloads/`                           |
| `ADULT_KEYWORDS`     | Comma-separated list of keywords for the adult content filter (case-insensitive). | `porn,xxx,sex,hentai,nudity,adult` |
| `SPAM_DELAY_SECONDS` | Cooldown period in seconds between download attempts per user.         | `60`                                   |
| `TOKEN_EXPIRY_HOURS` | Duration in hours for which a user's token remains valid.              | `24`                                   |

### How to get `TERABOX_COOKIE`:

1.  Open your web browser and log in to your Terabox account.
2.  Open the Developer Tools (usually by pressing `F12`).
3.  Go to the "Network" tab.
4.  Refresh the Terabox page or navigate within it.
5.  Find a request to `terabox.com` (e.g., the main page load or an API call).
6.  In the request details, look for the "Request Headers" section.
7.  Find the `Cookie:` header. Copy its **entire value**. This is your `TERABOX_COOKIE`.
    *   *Note:* This cookie contains sensitive session information and allows the bot to act "as you" on Terabox for downloads. Keep it secure! It might expire or change, requiring updates.

## Deployment

### Koyeb (Recommended)

1.  **Fork this repository** to your GitHub account.
2.  Go to the [Koyeb dashboard](https://app.koyeb.com/) and click "Create App".
3.  Choose **GitHub** as the deployment method and select your forked repository.
4.  **Configure the Service:**
    *   **Service Type:** `Worker`
    *   **Builder:** `Buildpack` (usually auto-detected)
    *   **Run command:** Ensure Koyeb detects or set it based on the `Procfile` (`python main.py`).
    *   **Environment Variables:** Add all the **Required Environment Variables** listed above. This is the most crucial step. Add Optional ones if you need to change defaults.
    *   **Instance Size:** Choose an appropriate size (e.g., `eco` or `micro` might be sufficient to start).
5.  **Deploy:** Click "Deploy". Koyeb will build and run your bot. Monitor the logs for any errors during startup.

### Local Development

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YourUsername/terabox-downloader-bot.git
    cd terabox-downloader-bot
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # Linux/macOS
    # venv\Scripts\activate # Windows
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create a `.env` file:** Copy `.env.example` to `.env`:
    ```bash
    cp .env.example .env
    ```
5.  **Edit `.env`:** Fill in your actual API credentials, bot token, IDs, and Terabox cookie.
6.  **Run the bot:**
    ```bash
    python main.py
    ```

## Important Notes

-   **Terabox Changes:** Terabox frequently changes its website structure and download mechanisms. The download logic (`bot/utils/terabox.py`) is the most likely part to break and may require updates to keep the bot functional.
-   **Cookie Security:** The `TERABOX_COOKIE` is sensitive. Do not share it publicly. If it expires or becomes invalid, the bot will likely fail to download files.
-   **Rate Limits:** Be mindful of Telegram's API limits, especially during broadcasts or heavy usage, to avoid temporary bans. The code includes basic delays, but adjust if needed.
-   **File Size Limits:** Telegram bots have an upload limit of 2 GB per file by default. The bot checks for this limit based on the `Content-Length` header if available.

## Contributing

Feel free to fork the repository, make improvements, and submit pull requests. Please ensure your code follows the existing structure and maintains configurability via environment variables.
