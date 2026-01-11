from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("settings"))
async def cmd_settings(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return await message.answer("Tämä botti on rajattu omistajalle.")

    s = await db.get_settings(message.from_user.id)

    text = (
        "⚙️ ASETUKSET\n\n"
        f"• Timezone: {s.timezone}\n"
        f"• Study reminder: {'ON' if s.study_reminder_enabled else 'OFF'}\n"
        f"• Reminder time: {s.study_reminder_time}\n"
        f"• Reminder days: {s.study_reminder_days}\n"
        f"• Weekly summary day: {s.weekly_summary_day}\n"
        f"• Weekly summary time: {s.weekly_summary_time}\n"
        f"• Last reminder date: {s.last_reminder_date or '—'}\n\n"
        "Muokkaus: tulossa (MVP)."
    )

    await message.answer(text)
