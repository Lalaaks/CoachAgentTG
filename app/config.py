from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_telegram_id: int
    tz: str
    db_path: str

def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    owner_id = int(os.getenv("OWNER_TELEGRAM_ID", "OWNER_TELEGRAM_ID=").strip())
    tz = os.getenv("TZ", "Europe/Helsinki").strip()
    db_path = os.getenv("DB_PATH", "data/app.db").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN missing in .env")
    if owner_id <= 0:
        raise RuntimeError("OWNER_TELEGRAM_ID missing/invalid in .env")

    return Config(
        bot_token=bot_token,
        owner_telegram_id=owner_id,
        tz=tz,
        db_path=db_path,
    )
