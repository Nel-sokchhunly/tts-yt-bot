"""Command names (with leading slash). Single source of truth for bot commands."""

CMD_AUTH = "/auth"
CMD_LOGOUT = "/logout"
CMD_START = "/start"
CMD_YT = "/yt"

# Commands that don't require authentication
ALLOWED_WITHOUT_AUTH = (CMD_AUTH, CMD_START, CMD_LOGOUT)
