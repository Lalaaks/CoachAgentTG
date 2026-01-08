import asyncio
from datetime import datetime
import pytz
from aiogram import Bot

from app.config import load_config
from app.db import Database
from app.keyboards import reminder_kb

def _daynum_1_to_7(dt_local: datetime) -> int:
    # Python weekday: Mon=0..Sun=6 -> convert to 1..7
    return dt_local.weekday() + 1

async def run():
    config = load_config()
    bot = Bot(token=config.bot_token)
    db = Database(config.db_path)

    s = await db.get_settings(config.owner_telegram_id)
    if not s or int(s["study_reminder_enabled"]) != 1:
        return

    tz = pytz.timezone(s.get("timezone", config.tz))
    now = datetime.now(tz)
    today = now.date().isoformat()
    daynum = _daynum_1_to_7(now)

    allowed_days = set()
    for part in str(s.get("study_reminder_days", "")).split(","):
        part = part.strip()
        if part.isdigit():
            allowed_days.add(int(part))

    if daynum not in allowed_days:
        return

    # match time HH:MM
    hhmm = now.strftime("%H:%M")
    if hhmm != s.get("study_reminder_time", "18:00"):
        return

    # already reminded today?
    if s.get("last_reminder_date") == today:
        return

    # If there is active session, don't remind
    active = await db.get_active_study_session(config.owner_telegram_id)
    if active:
        await db.update_settings(config.owner_telegram_id, last_reminder_date=today)
        return

    await bot.send_message(
        chat_id=config.owner_telegram_id,
        text="⏰ Opiskelusessio tänään? (Telegram-only)",
        reply_markup=reminder_kb(),
    )
    await db.update_settings(config.owner_telegram_id, last_reminder_date=today)

asyncio.run(run())
