from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

@router.message(Command("reset"))
async def cmd_reset(message: Message, config):
    if message.from_user.id != config.owner_telegram_id:
        return await message.answer("Tämä botti on rajattu omistajalle.")

    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Kyllä, poista kaikki", callback_data="reset:confirm")
    kb.button(text="❌ Peruuta", callback_data="reset:cancel")
    kb.adjust(1)

    await message.answer(
        "⚠️ Tämä poistaa KAIKKI tietosi (study, agentit, ajastukset, yhteenvedot).\n"
        "Oletko varma?",
        reply_markup=kb.as_markup()
    )

@router.callback_query(F.data == "reset:confirm")
async def reset_confirm(call: CallbackQuery, db, config):
    if call.from_user.id != config.owner_telegram_id:
        return await call.answer("Ei oikeutta.", show_alert=True)

    await db.reset_user(call.from_user.id)
    await call.message.answer("✅ Kaikki tiedot poistettu. Aloita uudelleen: /start")
    await call.answer()

@router.callback_query(F.data == "reset:cancel")
async def reset_cancel(call: CallbackQuery):
    await call.message.answer("👍 Reset peruttu.")
    await call.answer()
