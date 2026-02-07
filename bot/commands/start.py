"""Start command: /start."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth_store import is_authenticated
from bot.commands.config import CMD_AUTH


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id or not is_authenticated(user_id):
        await update.message.reply_text(f"Use {CMD_AUTH} <password> to authorize.")
        return
    await update.message.reply_text("You're in. Add your commands in bot/commands/.")
