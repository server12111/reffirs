import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = field(
        default_factory=lambda: list(
            map(int, filter(None, os.getenv("ADMIN_IDS", "").split(",")))
        )
    )
    ADMIN_CHANNEL_ID: int = int(os.getenv("ADMIN_CHANNEL_ID", "0"))
    BOTOHUB_KEY: str = os.getenv("BOTOHUB_KEY", "")
    SUBGRAM_KEY: str = os.getenv("SUBGRAM_KEY", "")
    GRAMADS_TOKEN: str = os.getenv("GRAMADS_TOKEN", "")
    BOTOHUB_VIEWS_KEY: str = os.getenv("BOTOHUB_VIEWS_KEY", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    REFERRAL_REWARD: float = float(os.getenv("REFERRAL_REWARD", "5"))
    BONUS_COOLDOWN_HOURS: int = int(os.getenv("BONUS_COOLDOWN_HOURS", "24"))
    BONUS_MIN: float = float(os.getenv("BONUS_MIN", "0.5"))
    BONUS_MAX: float = float(os.getenv("BONUS_MAX", "1.0"))
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))


config = Config()
