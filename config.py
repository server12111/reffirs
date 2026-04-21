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
    FLYER_KEY: str = os.getenv("FLYER_KEY", "")
    FLYERSERVICE_KEY: str = os.getenv("FLYERSERVICE_KEY", "")
    FLYERSERVICE_URL: str = os.getenv("FLYERSERVICE_URL", "")
    PIARFLOW_KEY: str = os.getenv("PIARFLOW_KEY", "")
    SUBGRAM_KEY: str = os.getenv("SUBGRAM_KEY", "")
    LINKNI_CODE: str = os.getenv("LINKNI_CODE", os.getenv("TGRASS_CODE", ""))
    GRAMADS_TOKEN: str = os.getenv("GRAMADS_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
    REFERRAL_REWARD: float = float(os.getenv("REFERRAL_REWARD", "5"))
    BONUS_COOLDOWN_HOURS: int = int(os.getenv("BONUS_COOLDOWN_HOURS", "24"))
    BONUS_MIN: float = float(os.getenv("BONUS_MIN", "0.5"))
    BONUS_MAX: float = float(os.getenv("BONUS_MAX", "1.0"))
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))


config = Config()
