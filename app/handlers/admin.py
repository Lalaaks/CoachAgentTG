from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("last"))
async def cmd_last(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    last = await db.get_last_study_session(message.from_user.id)
    if not last:
        return await message.answer("Ei vielä sessioita.")

    await message.answer(
        "🧾 Viimeisin sessio\n"
        f"• ID: {last['id']}\n"
        f"• Status: {last['status']}\n"
        f"• Aihe: {last.get('topic')}\n"
        f"• Tavoite: {last.get('goal')}\n"
        f"• Tehty: {last.get('done_minutes')}\n"
        f"• Seuraava: {last.get('next_step')}\n"
    )

@router.message(Command("undo"))
async def cmd_undo(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    res = await db.undo_last_event(message.from_user.id)
    await message.answer(res)
