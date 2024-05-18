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
from pathlib import Path
from contextlib import suppress

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Directory where user_data.db will reside in the volume
VOLUME_DIRECTORY = Path("/app/data")
# SQLite database filename
DATABASE_FILE = VOLUME_DIRECTORY / "user_data.db"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    ydl_options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": "%(title)s.%(ext)s",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
            "Referer": message.text,
        },
    }

    if "x.com" in video_url:
        video_url = video_url.replace("x.com", "twitter.com")
        user_cookie = get_user_twitter_cookie(message.from_user.id)
        if user_cookie:
            ydl_options["cookiefile"] = user_cookie
        else:
            await context.bot.send_message(
                chat_id=message.chat_id,
                text="Twitter needs a cookie to download videos. Please send a valid cookie txt file using /set_cookie command.",
            )
            return

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            video_info = ydl.extract_info(video_url, download=True)
            video_path = Path(ydl.prepare_filename(video_info))

        if video_path.stat().st_size / (1024 * 1024) > 50:
            error_message = "Video size exceeds 50MB. Please choose a smaller video."
            await context.bot.send_message(chat_id=message.chat_id, text=error_message)
            video_path.unlink(missing_ok=True)
            return

        await context.bot.send_video(
            chat_id=message.chat_id,
            video=open(video_path, "rb"),
            supports_streaming=True,
        )

    except yt_dlp.DownloadError as e:
        error_message = "Failed to download the video."
        logger.error(f"{e}\n{error_message}")
        await context.bot.send_message(chat_id=message.chat_id, text=error_message)
    finally:
        await context.bot.delete_message(
            chat_id=message.chat_id,
            message_id=hourglass_message.message_id,
        )
        with suppress(FileNotFoundError):
            video_path.unlink()


async def save_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save the user's Twitter cookie sent via a text file."""
    await update.message.reply_text("Please send the Twitter cookie as a txt file.")


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the received text file."""
    message = update.message
    user_id = message.from_user.id

    file = await context.bot.get_file(message.document)
    temp_cookie_path = Path(tempfile.gettempdir()) / f"{user_id}_cookie.txt"
    await file.download_to_drive(temp_cookie_path)

    with temp_cookie_path.open("r") as f:
        cookie_text = f.read()
    temp_cookie_path.unlink()

    store_user_twitter_cookie(user_id, cookie_text)

    await context.bot.send_message(
        chat_id=message.chat_id,
        text="Twitter cookie has been saved.",
    )


def store_user_twitter_cookie(user_id: int, cookie: str) -> None:
    """Store the user's Twitter cookie in the SQLite database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS user_cookies (user_id INTEGER PRIMARY KEY, cookie TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO user_cookies (user_id, cookie) VALUES (?, ?)",
            (user_id, cookie),
        )
        conn.commit()


def get_user_twitter_cookie(user_id: int) -> str:
    """Retrieve the user's Twitter cookie from the SQLite database."""
    with sqlite3.connect(DATABASE_FILE) as conn:
        result = conn.execute(
            "SELECT cookie FROM user_cookies WHERE user_id=?", (user_id,)
        ).fetchone()

    if result:
        temp_dir = Path(tempfile.gettempdir())
        cookie_file_path = temp_dir / f"{user_id}_twitter_cookie.txt"
        cookie_file_path.write_text(result[0])
        return str(cookie_file_path)
    return ""


def main() -> None:
    """Start the bot."""
    VOLUME_DIRECTORY.mkdir(parents=True, exist_ok=True)

    if not DATABASE_FILE.exists():
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS user_cookies (user_id INTEGER PRIMARY KEY, cookie TEXT)"
            )

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("set_cookie", save_cookie))
        app.add_handler(MessageHandler(filters.Document.TXT, file_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
