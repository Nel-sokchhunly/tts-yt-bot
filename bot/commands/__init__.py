"""Command handlers. Register all with register(app)."""

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.commands import auth, gate, help as help_cmd, logout, start, yt
from bot.commands.config import CMD_AUTH, CMD_LOGOUT, CMD_START, CMD_YT


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(gate.UnauthorizedFilter(), gate.unauthorized),
        group=0,
    )
    # CommandHandler expects the command name without the leading slash
    app.add_handler(CommandHandler(CMD_AUTH.lstrip("/"), auth.auth_cmd), group=0)
    app.add_handler(CommandHandler(CMD_LOGOUT.lstrip("/"), logout.logout_cmd), group=0)
    app.add_handler(CommandHandler(CMD_START.lstrip("/"), start.start_cmd), group=0)
    app.add_handler(CommandHandler(CMD_YT.lstrip("/"), yt.handle_yt_url), group=0)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, help_cmd.send_help),
        group=0,
    )