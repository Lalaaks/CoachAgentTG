from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from app.keyboards import main_menu

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "ootsä vittu valmis \n\n"
        "starttaa botti painamalla nappia(/study jos oot nörtti) \n\n"
        "tai älä, vittuuks se mua liikuttaa ihan oikeesti on täs omatki hommat kesken",
        reply_markup=main_menu(),
    )

@router.callback_query(F.data == "study:start")
async def cb_study_start(call: CallbackQuery):
    await call.message.answer("Aloitetaan. Kirjoita: mitä opiskelet? (kurssi/aihe)")
    await call.answer()
