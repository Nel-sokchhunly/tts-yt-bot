"""Auth gate: blocks unauthorized users from protected commands."""

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.stores.auth_store import is_authenticated
from bot.commands.config import ALLOWED_WITHOUT_AUTH


def _is_unauthorized(update: Update) -> bool:
    if not update.message or not update.effective_user:
        return False
    text = (update.message.text or "").strip().lower()
    if any(text == cmd or text.startswith(cmd + " ") for cmd in ALLOWED_WITHOUT_AUTH):
        return False
    return not is_authenticated(update.effective_user.id)


class UnauthorizedFilter(filters.UpdateFilter):
    def filter(self, update: Update) -> bool:
        return _is_unauthorized(update)


UNAUTHORIZED_MESSAGE = (
    "404 Unauthorized.\n\n"
    "Use /auth <password> to authenticate."
)


async def unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(UNAUTHORIZED_MESSAGE)
