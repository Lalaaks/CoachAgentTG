from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from app.ui.telegram.keyboards.mainmenu import main_menu_kb

router = Router()


async def send_mainmenu(message: Message, text: str = "Menu") -> None:
    """
    Yhteinen apufunktio, jota muut handlerit voivat importata:
    from app.ui.telegram.handlers.mainmenu import send_mainmenu
    """
    await message.answer(text, reply_markup=main_menu_kb())


# --- Main menu button handlers (reply keyboard) ---
# Note: "Agentit" button is handled by agents.py router


@router.message(F.text == "Tilastot")
async def menu_stats(message: Message):
    # jos /stats on komento-handler, ohjataan sinne:
    await message.answer("/stats")


@router.message(F.text == "Lisää tehtävä")
async def menu_add_task(message: Message):
    # avaa FSM-polun (tai jos haluat suoran, vaihda /td_add <...>)
    await message.answer("/td_add")


@router.message(F.text == "Tehtävät")
async def menu_tasks(message: Message):
    await message.answer("/td")


@router.message(F.text == "Asetukset")
async def menu_settings(message: Message):
    await send_mainmenu(message, "Asetukset tulossa.")
