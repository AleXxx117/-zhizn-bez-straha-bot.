from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


class TelegramAPIError(RuntimeError):
    pass


class TelegramAPI:
    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}"

    def request(self, method: str, payload: dict[str, Any] | None = None, timeout: int = 70) -> Any:
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout) as exc:
            raise TelegramAPIError(f"Сетевая ошибка Telegram API: {type(exc).__name__}") from exc
        except json.JSONDecodeError as exc:
            raise TelegramAPIError("Telegram API вернул некорректный ответ") from exc
        if not result.get("ok"):
            description = result.get("description", "неизвестная ошибка")
            raise TelegramAPIError(f"Telegram API: {description}")
        return result.get("result")

    def get_me(self) -> dict[str, Any]:
        return self.request("getMe")

    def delete_webhook(self) -> None:
        self.request("deleteWebhook", {"drop_pending_updates": False})

    def set_commands(self) -> None:
        self.request(
            "setMyCommands",
            {
                "commands": [
                    {"command": "start", "description": "Начать и открыть меню"},
                    {"command": "support", "description": "Получить поддержку"},
                    {"command": "practice", "description": "Практика на 5 минут"},
                    {"command": "daily", "description": "Ежедневная поддержка"},
                    {"command": "help", "description": "Возможности и безопасность"},
                    {"command": "privacy", "description": "Какие данные сохраняются"},
                    {"command": "id", "description": "Показать ID этого чата"},
                ]
            },
        )

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = self.request("getUpdates", payload, timeout=timeout + 10)
        return result or []

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.request("sendMessage", payload)

    def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any] | bool:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.request("editMessageText", payload)

    def answer_callback(self, callback_query_id: str, text: str = "") -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        self.request("answerCallbackQuery", payload)

