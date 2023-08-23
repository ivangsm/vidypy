import logging
import os
import yt_dlp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)
import validators
import sqlite3
import tempfile

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# SQLite database filename
DATABASE_FILE = "user_data.db"


async def start(update, context):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hello! Send me a video link and I'll download and send it to you."
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download and send the video to the user."""
    message = update.message

    video_url = message.text

    if not validators.url(video_url):
        error_message = "Please send a valid URL"
        logger.error(error_message)
        await context.bot.send_message(chat_id=message.chat_id, text=error_message)
        return

    hourglass_message = await context.bot.send_message(
        chat_id=message.chat_id, text="⏳"
    )

    try:
        ydl_options = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "outtmpl": "%(title)s.%(ext)s",
        }

        if "twitter.com" in message.text or "x.com" in message.text:
            user_cookie = get_user_twitter_cookie(message.from_user.id)
            if user_cookie:
                ydl_options["cookiefile"] = user_cookie
            else:
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text="Twitter cookie not found. Please send a valid cookie using /set_cookie command.",
                )
                return

        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            video_info = ydl.extract_info(video_url, download=True)
            video_path = ydl.prepare_filename(video_info)

            if (os.path.getsize(video_path) / (1024 * 1024)) > 50:
                error_message = (
                    "Video size exceeds 50MB. Please choose a smaller video."
                )
                await context.bot.send_message(
                    chat_id=message.chat_id, text=error_message
                )
                os.remove(video_path)
                return

            await context.bot.send_video(
                chat_id=message.chat_id,
                video=open(video_path, "rb"),
                supports_streaming=True,
            )

            await context.bot.delete_message(
                chat_id=message.chat_id,
                message_id=hourglass_message.message_id,
            )

            os.remove(video_path)

    except yt_dlp.DownloadError as e:
        error_message = "Failed to download the video."
        logger.error(f"{e}\n{error_message}")
        await context.bot.send_message(chat_id=message.chat_id, text=error_message)


async def save_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the user's Twitter cookie sent via a text file."""
    await update.message.reply_text("Please send the Twitter cookie as a text file.")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the received text file."""
    message = update.message
    user_id = message.from_user.id

    file = await context.bot.get_file(message.document)
    await file.download_to_drive("cookie.txt")

    with open("cookie.txt", "r") as f:
        cookie_text = f.read()
    os.remove("cookie.txt")  # Remove the temporary file

    # Store the cookie in the database
    store_user_twitter_cookie(user_id, cookie_text)

    await context.bot.send_message(
        chat_id=message.chat_id,
        text="Twitter cookie has been saved.",
    )


def store_user_twitter_cookie(user_id: int, cookie: str) -> None:
    """Store the user's Twitter cookie in the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    c.execute(
        "CREATE TABLE IF NOT EXISTS user_cookies (user_id INTEGER PRIMARY KEY, cookie TEXT)"
    )

    c.execute(
        "INSERT OR REPLACE INTO user_cookies (user_id, cookie) VALUES (?, ?)",
        (user_id, cookie),
    )

    conn.commit()
    conn.close()


def get_user_twitter_cookie(user_id: int) -> str:
    """Retrieve the user's Twitter cookie from the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    c.execute("SELECT cookie FROM user_cookies WHERE user_id=?", (user_id,))
    result = c.fetchone()

    conn.close()

    if result:
        temp_dir = tempfile.gettempdir()
        cookie_file_path = os.path.join(temp_dir, f"{user_id}_twitter_cookie.txt")

        # Write the cookie string to the temporary file
        with open(cookie_file_path, "w") as file:
            file.write(result[0])
        return cookie_file_path
    return ""


def main() -> None:
    """Start the bot."""
    # Create the database if it doesn't exist
    if not os.path.exists(DATABASE_FILE):
        with sqlite3.connect(DATABASE_FILE) as conn:
            c = conn.cursor()
            c.execute(
                "CREATE TABLE IF NOT EXISTS user_cookies (user_id INTEGER PRIMARY KEY, cookie TEXT)"
            )

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("set_cookie", save_cookie))
        app.add_handler(
            MessageHandler(filters.Document.TXT, file_handler)
        )  # Handle text file
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
