from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.utils import week_start_utc_iso

router = Router()

@router.message(Command("stats"))
async def cmd_stats(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    settings = await db.get_settings(message.from_user.id)
    since = week_start_utc_iso(settings.get("timezone", config.tz))
    s = await db.get_week_stats(message.from_user.id, since)

    base = s["base"]
    top_topics = s["top_topics"]
    top_stuck = s["top_stuck"]

    lines = [
        "📊 Tämä viikko",
        f"• Sessioita: {base['sessions']}",
        f"• Minuutteja: {base['minutes']}",
        "",
        "🏷️ Top-aiheet:",
    ]
    if top_topics:
        for t in top_topics:
            lines.append(f"• {t['topic']}: {t['minutes']} min")
    else:
        lines.append("• (ei vielä dataa)")

    lines.append("")
    lines.append("🧩 Top-jumit:")
    if top_stuck:
        for j in top_stuck:
            lines.append(f"• {j['stuck_point']}: {j['cnt']}x")
    else:
        lines.append("• (ei vielä dataa)")

    await message.answer("\n".join(lines))

@router.callback_query(F.data == "stats:week")
async def cb_stats(call: CallbackQuery, db, config):
    # ohjaa samaan kuin /stats
    msg = call.message
    # luodaan "fake" Message-käsittely: kutsutaan suoraan logiikkaa
    settings = await db.get_settings(call.from_user.id)
    since = week_start_utc_iso(settings.get("timezone", config.tz))
    s = await db.get_week_stats(call.from_user.id, since)
    base = s["base"]

    await msg.answer(f"📊 Tämä viikko: {base['sessions']} sessiota, {base['minutes']} min.\n\nKatso lisää: /stats")
    await call.answer()
