"""Logout command: /logout."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth_store import remove as auth_remove


async def logout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    auth_remove(update.effective_user.id)
    await update.message.reply_text("Logged out.")
