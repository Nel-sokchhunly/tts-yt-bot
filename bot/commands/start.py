"""Start command: /start."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.stores.auth_store import is_authenticated
from bot.commands.config import CMD_AUTH
from bot.commands.help import HELP_MESSAGE


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not is_authenticated(update.effective_user.id):
        await update.message.reply_text(f"Use {CMD_AUTH} <password> to authorize.")
        return
    await update.message.reply_text(HELP_MESSAGE.strip())
