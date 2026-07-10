from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Config
from content import (
    DISCLAIMER,
    PRACTICE_STEPS,
    back_keyboard,
    classify,
    crisis_message,
    daily_message,
    main_menu,
    medical_emergency_message,
    pick_response,
    practice_keyboard,
    welcome,
)
from storage import Storage
from telegram_api import TelegramAPI, TelegramAPIError


LOGGER = logging.getLogger("zhizn_bez_straha")


class SupportBot:
    def __init__(self, config: Config, api: TelegramAPI, storage: Storage):
        self.config = config
        self.api = api
        self.storage = storage
        self.bot_id: int | None = None
        self.bot_username = ""
        self.running = True

    def setup(self) -> None:
        self.api.delete_webhook()
        me = self.api.get_me()
        self.bot_id = int(me["id"])
        self.bot_username = str(me.get("username", "")).lower()
        self.api.set_commands()
        LOGGER.info("Бот @%s запущен", self.bot_username)

    def stop(self, *_: Any) -> None:
        self.running = False

    def _directed_at_bot(self, message: dict[str, Any]) -> bool:
        chat_type = str(message.get("chat", {}).get("type", "private"))
        if chat_type == "private":
            return True
        text = str(message.get("text", "")).strip().lower()
        if self.bot_username and f"@{self.bot_username}" in text:
            return True
        reply_from = message.get("reply_to_message", {}).get("from", {})
        return self.bot_id is not None and reply_from.get("id") == self.bot_id

    def _remember_user(self, message: dict[str, Any]) -> None:
        chat = message.get("chat", {})
        sender = message.get("from", {})
        self.storage.upsert_user(
            chat_id=int(chat["id"]),
            user_id=int(sender["id"]) if sender.get("id") is not None else None,
            username=str(sender.get("username", "")),
            first_name=str(sender.get("first_name", "")),
            chat_type=str(chat.get("type", "private")),
        )

    def handle_update(self, update: dict[str, Any]) -> None:
        if "callback_query" in update:
            self._handle_callback(update["callback_query"])
        elif "message" in update:
            self._handle_message(update["message"])

    def _handle_message(self, message: dict[str, Any]) -> None:
        if "text" not in message or "chat" not in message:
            return
        self._remember_user(message)
        chat_id = int(message["chat"]["id"])
        text = str(message.get("text", "")).strip()
        first_name = str(message.get("from", {}).get("first_name", "друг"))
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text.startswith("/") else ""

        if command == "/start":
            self.api.send_message(chat_id, welcome(first_name), main_menu())
            return
        if command in {"/support", "/menu"}:
            self.api.send_message(chat_id, "Выбери, что сейчас ближе, или напиши своими словами.", main_menu())
            return
        if command == "/practice":
            self.api.send_message(chat_id, PRACTICE_STEPS[0], practice_keyboard(0))
            return
        if command == "/daily":
            if str(message.get("chat", {}).get("type", "private")) != "private":
                self.api.send_message(
                    chat_id,
                    "Ежедневные личные сообщения можно включить только в диалоге с ботом. Открой бота лично и отправь /daily.",
                    back_keyboard(),
                )
            else:
                self._toggle_daily(chat_id)
            return
        if command == "/privacy":
            self.api.send_message(
                chat_id,
                "Бот хранит только ID чата, имя профиля, настройку ежедневных сообщений и обезличенный счётчик тем. "
                "Текст личных сообщений в базе не сохраняется. Для чувствительных разговоров лучше писать боту в личные сообщения.",
                back_keyboard(),
            )
            return
        if command == "/id":
            self.api.send_message(chat_id, f"ID этого чата: <code>{chat_id}</code>")
            return
        if command == "/help":
            self.api.send_message(
                chat_id,
                "Напиши, что происходит, или выбери тему в меню. В группе бот отвечает на команды, упоминание его имени или ответ на его сообщение.\n\n"
                f"{DISCLAIMER}\n\nПри непосредственной угрозе жизни обращайся к живому человеку и в экстренную службу.",
                main_menu(),
            )
            return
        if command == "/stats":
            self._send_stats(chat_id)
            return
        if command:
            self.api.send_message(chat_id, "Такой команды пока нет. Открою главное меню.", main_menu())
            return

        if not self._directed_at_bot(message):
            return

        # Remove a group mention before classification.
        if self.bot_username:
            text = text.replace(f"@{self.bot_username}", "").strip()
        intent = classify(text)
        self.storage.log_intent(intent)
        if intent == "crisis":
            self.api.send_message(chat_id, crisis_message(), back_keyboard())
            return
        if intent == "medical_emergency":
            self.api.send_message(chat_id, medical_emergency_message(), back_keyboard())
            return

        variation_key = f"{message.get('message_id', 0)}:{message.get('from', {}).get('id', 0)}:{text}"
        response = pick_response(intent, variation_key)
        self.api.send_message(chat_id, response, back_keyboard())

    def _handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = str(callback.get("id", ""))
        if callback_id:
            self.api.answer_callback(callback_id)
        message = callback.get("message", {})
        chat = message.get("chat", {})
        if not chat or "message_id" not in message:
            return
        chat_id = int(chat["id"])
        message_id = int(message["message_id"])
        data = str(callback.get("data", ""))
        sender = callback.get("from", {})
        self.storage.upsert_user(
            chat_id,
            int(sender["id"]) if sender.get("id") is not None else None,
            str(sender.get("username", "")),
            str(sender.get("first_name", "")),
            str(chat.get("type", "private")),
        )

        try:
            if data == "menu":
                self.api.edit_message(
                    chat_id,
                    message_id,
                    "Выбери, что сейчас ближе, или напиши своими словами.",
                    main_menu(),
                )
            elif data.startswith("topic:"):
                intent = data.split(":", 1)[1]
                self.storage.log_intent(intent)
                response = pick_response(intent, f"callback:{callback_id}")
                self.api.edit_message(chat_id, message_id, response, back_keyboard())
            elif data.startswith("practice:"):
                index = int(data.split(":", 1)[1])
                if not 0 <= index < len(PRACTICE_STEPS):
                    raise ValueError("Некорректный шаг практики")
                self.api.edit_message(
                    chat_id,
                    message_id,
                    PRACTICE_STEPS[index],
                    practice_keyboard(index),
                )
            elif data == "daily:toggle":
                if str(chat.get("type", "private")) != "private":
                    self.api.edit_message(
                        chat_id,
                        message_id,
                        "Ежедневные сообщения можно включить только в личном диалоге с ботом.",
                        back_keyboard(),
                    )
                    return
                enabled = self.storage.toggle_daily(chat_id)
                state = "включена" if enabled else "выключена"
                text = (
                    f"Ежедневная поддержка {state}. "
                    f"Сообщения приходят примерно в {self.config.daily_hour:02d}:{self.config.daily_minute:02d} "
                    f"по часовому поясу {escape(self.config.timezone)}."
                )
                self.api.edit_message(chat_id, message_id, text, back_keyboard())
            elif data == "links":
                self.api.edit_message(
                    chat_id,
                    message_id,
                    "Наши материалы и сообщество «Жизнь без страха».",
                    self._links_keyboard(),
                )
        except TelegramAPIError as exc:
            # Telegram returns this harmlessly when an edit does not change text.
            if "message is not modified" not in str(exc).lower():
                raise

    def _toggle_daily(self, chat_id: int) -> None:
        enabled = self.storage.toggle_daily(chat_id)
        state = "включена" if enabled else "выключена"
        self.api.send_message(
            chat_id,
            f"Ежедневная поддержка {state}. Время: примерно {self.config.daily_hour:02d}:{self.config.daily_minute:02d}, {escape(self.config.timezone)}.",
            back_keyboard(),
        )

    def _links_keyboard(self) -> dict[str, Any]:
        rows: list[list[dict[str, str]]] = []
        if self.config.site_url.startswith("http"):
            rows.append([{"text": "Открыть сайт", "url": self.config.site_url}])
        if self.config.youtube_url.startswith("http"):
            rows.append([{"text": "YouTube", "url": self.config.youtube_url}])
        if self.config.community_url.startswith("http"):
            rows.append([{"text": "Telegram-сообщество", "url": self.config.community_url}])
        rows.append([{"text": "В главное меню", "callback_data": "menu"}])
        return {"inline_keyboard": rows}

    def _send_stats(self, chat_id: int) -> None:
        if self.config.admin_chat_id is None or chat_id != self.config.admin_chat_id:
            self.api.send_message(chat_id, "Эта команда доступна только администратору.")
            return
        users, stats = self.storage.stats()
        lines = [f"Пользователей: {users}", "", "Темы обращений:"]
        lines.extend(f"{escape(intent)}: {count}" for intent, count in stats)
        self.api.send_message(chat_id, "\n".join(lines))

    def send_daily_if_due(self) -> None:
        try:
            now = datetime.now(ZoneInfo(self.config.timezone))
        except ZoneInfoNotFoundError:
            LOGGER.error("Неизвестный часовой пояс: %s", self.config.timezone)
            return
        scheduled = (self.config.daily_hour, self.config.daily_minute)
        if (now.hour, now.minute) < scheduled:
            return
        for chat_id in self.storage.subscribers_due(now.date()):
            try:
                self.api.send_message(
                    chat_id,
                    daily_message(chat_id, now.date()),
                    main_menu(),
                )
                self.storage.mark_daily_sent(chat_id, now.date())
            except TelegramAPIError as exc:
                LOGGER.warning("Не удалось отправить ежедневное сообщение чату %s: %s", chat_id, exc)
                if "blocked" in str(exc).lower() or "chat not found" in str(exc).lower():
                    self.storage.disable_daily(chat_id)

    def run(self) -> None:
        self.setup()
        offset = self.storage.get_offset()
        backoff = 1
        while self.running:
            try:
                updates = self.api.get_updates(offset=offset, timeout=30)
                for update in updates:
                    update_id = int(update["update_id"])
                    try:
                        self.handle_update(update)
                    except Exception:
                        LOGGER.exception("Ошибка обработки update_id=%s", update_id)
                    offset = update_id + 1
                    self.storage.set_offset(offset)
                self.send_daily_if_due()
                backoff = 1
            except TelegramAPIError as exc:
                LOGGER.warning("Связь с Telegram временно недоступна: %s", exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)


def main() -> int:
    try:
        config = Config.from_env()
    except (ValueError, OSError) as exc:
        print(f"Ошибка настройки: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    storage = Storage(config.data_dir / "bot.sqlite3")
    bot = SupportBot(config, TelegramAPI(config.token), storage)
    signal.signal(signal.SIGINT, bot.stop)
    signal.signal(signal.SIGTERM, bot.stop)
    try:
        bot.run()
    except TelegramAPIError as exc:
        LOGGER.error("Не удалось запустить бота: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
