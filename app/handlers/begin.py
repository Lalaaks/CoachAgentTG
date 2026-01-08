from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app.keyboards import main_menu

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Koutsiagentti palveluksessanne. Mitä lähdetään kehittämään?\n\n"
        "Aloita komennolla /study tai paina nappia.",
        reply_markup=main_menu(),
    )

@router.callback_query(F.data == "study:start")
async def cb_study_start(call: CallbackQuery):
    await call.message.answer("Aloitetaan. Kirjoita: mitä opiskelet? (kurssi/aihe)")
    await call.answer()
