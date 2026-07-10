from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


TOKEN_RE = re.compile(r"^\d{6,15}:[A-Za-z0-9_-]{30,}$")


def load_env_file(path: str | Path = ".env") -> None:
    """Load a small KEY=VALUE file without third-party dependencies."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} должен быть целым числом") from exc


@dataclass(frozen=True)
class Config:
    token: str
    admin_chat_id: int | None
    site_url: str
    youtube_url: str
    community_url: str
    timezone: str
    daily_hour: int
    daily_minute: int
    data_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        load_env_file()
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not TOKEN_RE.fullmatch(token):
            raise ValueError(
                "Укажите новый токен в TELEGRAM_BOT_TOKEN. "
                "Старый опубликованный токен использовать нельзя."
            )

        admin_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
        admin_chat_id = int(admin_raw) if admin_raw else None
        hour = _int_env("DAILY_HOUR", 9)
        minute = _int_env("DAILY_MINUTE", 0)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("DAILY_HOUR и DAILY_MINUTE задают некорректное время")

        return cls(
            token=token,
            admin_chat_id=admin_chat_id,
            site_url=os.getenv(
                "SITE_URL",
                "https://zhizn-bez-straha-neuro.alexxx117.chatgpt.site",
            ).strip(),
            youtube_url=os.getenv(
                "YOUTUBE_URL",
                "https://www.youtube.com/@%D0%96%D0%B8%D0%B7%D0%BD%D1%8C%D0%91%D0%B5%D0%B7%D0%A1%D1%82%D1%80%D0%B0%D1%85%D0%B0",
            ).strip(),
            community_url=os.getenv("TELEGRAM_COMMUNITY_URL", "").strip(),
            timezone=os.getenv("TIMEZONE", "Europe/Kyiv").strip(),
            daily_hour=hour,
            daily_minute=minute,
            data_dir=Path(os.getenv("DATA_DIR", "./data")).expanduser(),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        )

