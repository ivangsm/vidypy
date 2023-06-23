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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update, context):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hello! Send me a video link and I'll download and send it to you."
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download and send the video to the user."""
    video_url = update.message.text

    if not validators.url(video_url):
        error_message = "Please send a valid URL"
        logger.error(error_message)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=error_message
        )
        return

    hourglass_message = await context.bot.send_message(
        chat_id=update.effective_chat.id, text="⏳"
    )

    ydl_options = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "outtmpl": "%(title)s.%(ext)s",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            video_info = ydl.extract_info(video_url, download=True)
            video_path = ydl.prepare_filename(video_info)

            if (os.path.getsize(video_path) / (1024 * 1024)) > 50:
                error_message = (
                    "Video size exceeds 50MB. Please choose a smaller video."
                )
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=error_message
                )
                os.remove(video_path)
                return

            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=open(video_path, "rb"),
                supports_streaming=True,
            )

            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=hourglass_message.message_id,
            )

            os.remove(video_path)

    except yt_dlp.DownloadError as e:
        error_message = "Failed to download the video."
        logger.error(f"{e}\n{error_message}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=error_message
        )


def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
