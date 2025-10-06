from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
from telegram import Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode


TELEGRAM_FILE = Path("config") / "telegram.txt"


def _load_telegram() -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not TELEGRAM_FILE.exists():
        TELEGRAM_FILE.parent.mkdir(parents=True, exist_ok=True)
        TELEGRAM_FILE.write_text("bot_token=\nchat_id=\nuser_id=\n", encoding="utf-8")
        logger.info(
            "Created {}. Please fill your bot token and chat id.", TELEGRAM_FILE
        )
        return None, None, None
    token: Optional[str] = None
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    for raw in TELEGRAM_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("bot_token="):
            token = line.split("=", 1)[1].strip() or None
        elif line.startswith("chat_id="):
            chat_id = line.split("=", 1)[1].strip() or None
        elif line.startswith("user_id="):
            user_id = line.split("=", 1)[1].strip() or None
    return token, chat_id, user_id


class TelegramNotifier:
    def __init__(self) -> None:
        token, chat_id, user_id = _load_telegram()
        self._token = token
        self._chat_id = chat_id
        self._user_id = user_id
        self._bot: Optional[Bot] = Bot(token) if token else None

    async def _send(self, text: str) -> None:
        if not self._bot or not self._chat_id:
            logger.warning("Telegram not configured; skipping message: {}", text)
            return
        try:
            # python-telegram-bot v21: Bot.send_message es coroutine
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error("Telegram send failed: {}", e)

    async def send_open(self, message: str) -> None:
        await self._send(message)

    async def send_close(self, message: str) -> None:
        await self._send(message)

    async def send_error(self, message: str) -> None:
        await self._send(message)

    async def send_be(self, message: str) -> None:
        await self._send(message)

    async def send_trail(self, message: str) -> None:
        await self._send(message)

    async def send_start(self, exchange: str, mode: str, market: str, symbol: str) -> None:
        dt = __import__("datetime").datetime.utcnow().isoformat()
        await self._send(
            f"🟢 <b>BOT STARTED</b>\n"
            f"• {exchange}/{mode}/{market}\n"
            f"• Symbol: {symbol}\n"
            f"⏱️ {dt}"
        )

    async def send_stop(self, exchange: str, mode: str, market: str, symbol: str) -> None:
        dt = __import__("datetime").datetime.utcnow().isoformat()
        await self._send(
            f"🔴 <b>BOT STOPPED</b>\n"
            f"• {exchange}/{mode}/{market}\n"
            f"• Symbol: {symbol}\n"
            f"⏱️ {dt}"
        )

    # Simple polling commands support (e.g., /status)
    async def fetch_updates(self, offset: int | None = None) -> list:
        if not self._bot:
            return []
        try:
            return await self._bot.get_updates(offset=offset, timeout=10)
        except Exception as e:
            logger.warning("Telegram get_updates failed: {}", e)
            return []

    async def send_text(self, text: str) -> None:
        await self._send(text)

    async def send_menu(self) -> None:
        """Send a reply keyboard with the main bot commands."""
        if not self._bot or not self._chat_id:
            return
        try:
            kb = ReplyKeyboardMarkup(
                [
                    [KeyboardButton("/health"), KeyboardButton("/status")],
                    [KeyboardButton("/start_t"), KeyboardButton("/start_r")],
                    [KeyboardButton("/pause"), KeyboardButton("/resume")],
                    [KeyboardButton("/stop"), KeyboardButton("/restart")],
                ],
                resize_keyboard=True,
                one_time_keyboard=False,
                is_persistent=True,
            )
            await self._bot.send_message(
                chat_id=self._chat_id,
                text="🧭 <b>Menú</b>: comandos rápidos",
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning("Telegram send_menu failed: {}", e)

    # Accessors/authorization helpers
    def get_chat_id(self) -> Optional[str]:
        return self._chat_id

    def get_user_id(self) -> Optional[str]:
        return self._user_id

    def is_authorized(self, chat_id: Optional[int], user_id: Optional[int]) -> bool:
        if self._chat_id and (str(chat_id or "") != str(self._chat_id)):
            return False
        if self._user_id and (str(user_id or "") != str(self._user_id)):
            return False
        return True
