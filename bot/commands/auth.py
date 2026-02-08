"""Auth command: /auth <password>."""

import os
from telegram import Update
from telegram.ext import ContextTypes

from bot.stores.auth_store import add as auth_add
from bot.commands.help import HELP_MESSAGE


AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")


async def auth_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not AUTH_PASSWORD:
        await update.message.reply_text("Auth not configured.")
        return
    if not context.args or context.args[0] != AUTH_PASSWORD:
        await update.message.reply_text("Invalid password.")
        return
    auth_add(update.effective_user.id)
    await update.message.reply_text(
        "Authenticated.\n\n" + HELP_MESSAGE.strip()
    )
