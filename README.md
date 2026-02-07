# Telegram Bot (Scaffolding)

A generic Telegram bot starter: auth, webhook, optional ngrok for local dev, Docker + Makefile. Add your commands in `bot/commands/`.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- A bot token from [@BotFather](https://t.me/BotFather)
- For local dev: a free [ngrok](https://ngrok.com/) account (authtoken)

## Setup

1. **Clone and enter the project**
   ```bash
   cd <your-project-dir>
   ```

2. **Create `.env` from the example**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` and set**
   - `BOT_TOKEN` – from @BotFather
   - `AUTH_PASSWORD` – password users will use with `/auth <password>`
   - For **local dev**: leave `WEBHOOK_URL` empty and set `NGROK_AUTHTOKEN` (from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken))
   - For **production**: set `WEBHOOK_URL` to your public HTTPS URL (e.g. `https://your-domain.com`)

4. **Build and start**
   ```bash
   make build
   make up
   ```

5. In Telegram, open your bot and send `/start`, then `/auth <your AUTH_PASSWORD>` to use the bot.

## Makefile

| Command   | Description                    |
|----------|--------------------------------|
| `make up`   | Start the bot (background)     |
| `make down` | Stop and remove containers     |
| `make build`| Rebuild the Docker image        |
| `make logs` | Stream bot logs                 |
| `make shell`| Open a shell in the bot container |

## Local development

- With `WEBHOOK_URL` unset, the container starts ngrok and uses its URL as the webhook. Open **http://localhost:4040** to inspect requests.
- Set `DEV=1` in `.env` to auto-restart the bot when you change code under `bot/`.
- Data (e.g. authenticated users) is stored in `./data/` and persisted across restarts.

## Bot commands

| Command   | Auth required | Description                          |
|----------|----------------|--------------------------------------|
| `/start` | No             | Show auth hint or usage              |
| `/auth <password>` | No  | Authenticate to use the bot          |
| `/logout`| No             | Remove your auth session             |

## Adding a command

1. **`bot/commands/config.py`** – Add the command name and, if it should work without auth, add it to `ALLOWED_WITHOUT_AUTH`:
   ```python
   CMD_PING = "/ping"
   # If unauthed users can call it:
   ALLOWED_WITHOUT_AUTH = (..., CMD_PING)
   ```

2. **`bot/commands/<name>.py`** – New module with your handler:
   ```python
   """Ping command: /ping."""
   from telegram import Update
   from telegram.ext import ContextTypes

   async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
       await update.message.reply_text("Pong.")
   ```

3. **`bot/commands/__init__.py`** – Import the module and register the handler:
   ```python
   from bot.commands.config import ..., CMD_PING
   from bot.commands import ..., ping
   # In register():
   app.add_handler(CommandHandler(CMD_PING.lstrip("/"), ping.ping_cmd), group=0)
   ```

## Project structure

```
bot/
  commands/       # Command handlers (auth, logout, start, gate)
  auth_store.py   # Persisted list of authenticated user IDs
  __main__.py     # App entry, webhook config
.env.example      # Env template
docker-compose.yml
Makefile
```
