from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("settings"))
async def cmd_settings(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    s = await db.get_settings(message.from_user.id)
    await message.answer(
        "⚙️ Asetukset\n"
        f"• Muistutus: {'päällä' if s['study_reminder_enabled'] else 'pois'}\n"
        f"• Aika: {s['study_reminder_time']}\n"
        f"• Päivät (1=ma..7=su): {s['study_reminder_days']}\n\n"
        "Komennot:\n"
        "• /remind_on\n"
        "• /remind_off\n"
        "• /remind_time HH:MM (esim. /remind_time 18:00)\n"
        "• /remind_days 1,2,3,4,5\n"
    )

@router.message(Command("remind_on"))
async def remind_on(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await db.update_settings(message.from_user.id, study_reminder_enabled=1)
    await message.answer("✅ Muistutus päälle.")

@router.message(Command("remind_off"))
async def remind_off(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await db.update_settings(message.from_user.id, study_reminder_enabled=0)
    await message.answer("🚫 Muistutus pois.")

@router.message(Command("remind_time"))
async def remind_time(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or ":" not in parts[1]:
        return await message.answer("Käyttö: /remind_time HH:MM (esim. /remind_time 18:00)")
    await db.update_settings(message.from_user.id, study_reminder_time=parts[1])
    await message.answer(f"⏱️ Muistutusaika asetettu: {parts[1]}")

@router.message(Command("remind_days"))
async def remind_days(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.answer("Käyttö: /remind_days 1,2,3,4,5")
    await db.update_settings(message.from_user.id, study_reminder_days=parts[1])
    await message.answer(f"📅 Muistutuspäivät asetettu: {parts[1]}")
