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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hello! Send me a video link and I will download and send it to you."
    )


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download and send the video to the user."""
    video_url = update.message.text

    is_valid_url = validators.url(video_url)
    if not is_valid_url:
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
    ydl = yt_dlp.YoutubeDL(ydl_options)

    try:
        # Download the video
        video_info = ydl.extract_info(video_url, download=True)

        # Get the video file path
        video_path = ydl.prepare_filename(video_info)

        # Check the video size
        video_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if video_size_mb > 50:
            error_message = "Video size exceeds 50MB. Please choose a smaller video."
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=error_message
            )
            os.remove(video_path)
            return

        # Send the video file
        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=open(video_path, "rb"),
            supports_streaming=True,
        )

        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=hourglass_message.message_id,
        )

        # Delete the downloaded video file
        os.remove(video_path)

    except yt_dlp.DownloadError as e:
        error_message = "Failed to download the video."
        logger.error(e + "\n" + error_message)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=error_message
        )


def main() -> None:
    """Start the bot."""
    application = (
        Application.builder()
        .token(os.environ['TELEGRAM_BOT_TOKEN'])
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
