import os
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes, TypeHandler

from bot.commands import register

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not token:
        raise SystemExit("Set BOT_TOKEN in .env")
    if not webhook_url:
        raise SystemExit("Set WEBHOOK_URL in .env, or leave unset and set NGROK_AUTHTOKEN for local dev")
    if not os.environ.get("AUTH_PASSWORD"):
        raise SystemExit("Set AUTH_PASSWORD in .env")
    port = int(os.environ.get("PORT", "8080"))
    webhook_full = f"{webhook_url.rstrip('/')}/webhook"
    logger.info("Starting bot with webhook %s (port %s)", webhook_full, port)
    app = Application.builder().token(token).build()

    register(app)

    async def log_update(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        logger.info("Update %s", update.update_id)

    app.add_handler(TypeHandler(Update, log_update), group=1)

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=webhook_full,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
