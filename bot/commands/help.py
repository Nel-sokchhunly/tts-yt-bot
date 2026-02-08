"""Fallback: send help when user sends non-command text."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.commands.config import CMD_AUTH, CMD_LOGOUT, CMD_START, CMD_YT

HELP_MESSAGE = f"""Available commands:

{CMD_START} — Show auth hint or usage
{CMD_AUTH} <password> — Authenticate to use the bot
{CMD_LOGOUT} — Remove your auth session
{CMD_YT} <youtube_url> — Process a YouTube video
"""


async def send_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_MESSAGE.strip())
