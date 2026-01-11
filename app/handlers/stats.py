from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@router.message(Command("stats"))
async def cmd_stats(message: Message, db, config):
    # Owner-only (sama tyyli kuin study.py)
    if message.from_user.id != config.owner_telegram_id:
        return await message.answer("Tämä botti on rajattu omistajalle.")

    user_id = message.from_user.id

    # Viimeiset 7 päivää (UTC, riittää MVP:hen)
    now = datetime.now(timezone.utc)
    since_7d = _iso_utc(now - timedelta(days=7))

    sessions_7d, minutes_7d = await db.sum_completed_minutes_since(user_id, since_7d)

    # Bonus: jos aktiivinen sessio käynnissä
    active = await db.get_active_study_session(user_id)

    text = "📈 STUDY STATS\n\n"
    text += f"🗓️ Viimeiset 7 päivää:\n"
    text += f"• Sessioita: {sessions_7d}\n"
    text += f"• Minuutteja: {minutes_7d}\n"

    if sessions_7d > 0:
        avg = minutes_7d / sessions_7d
        text += f"• Keskiarvo: {avg:.1f} min / sessio\n"

    text += "\n"

    if active:
        text += "⏳ Aktiivinen sessio:\n"
        text += f"• Aihe: {active.get('topic')}\n"
        text += f"• Tavoite: {active.get('goal')}\n"
        text += f"• Suunniteltu: {active.get('planned_minutes')} min\n"
        text += "Lopeta: /end\n"
    else:
        text += "✅ Ei aktiivista sessiota.\n"
        text += "Aloita uusi: /study\n"

    await message.answer(text)
