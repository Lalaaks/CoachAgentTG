# app/handlers/help.py

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "📖 KOMENNOT – PIKAOPAS\n\n"
    "🔹 Yleiset\n"
    "/start – Esittely ja botin käyttöönotto\n"
    "/help – Näytä tämä ohje\n"
    "/status – Aktiiviset agentit, ajastukset ja viimeisin yhteenveto\n"
    "/settings – Käyttäjäkohtaiset asetukset\n"
    "/reset – Nollaa kaikki käyttäjätiedot\n\n"
    "🔹 Agentit\n"
    "/agents – Listaa kaikki käytettävissä olevat agentit\n"
    "/agent_add – Lisää agentti käyttöön\n"
    "/agent_remove – Poista agentti käytöstä\n"
    "/agent_enable – Aktivoi agentti\n"
    "/agent_disable – Poista agentti väliaikaisesti käytöstä\n"
    "/agent_info – Näytä agentin kuvaus ja tehtävä\n\n"
    "🔹 Päivittäinen käyttö\n"
    "/checkin – Päivän aloitus (mieliala, energia, fokus)\n"
    "/checkout – Päivän päätös ja reflektio\n"
    "/today – Päivän tehtävät ja agenttien näkemykset\n"
    "/tomorrow – Kevyt huomisen suunnittelu\n"
    "/log – Lisää vapaa tekstimerkintä\n\n"
    "🔹 Ajastukset ja muistutukset\n"
    "/schedule – Näytä kaikki ajastukset\n"
    "/schedule_add – Lisää ajastus agentille tai muistutukselle\n"
    "/schedule_remove – Poista ajastus\n"
    "/reminders – Listaa aktiiviset muistutukset\n\n"
    "🔹 Yhteenvedot ja analyysi\n"
    "/summary – Yleinen yhteenveto\n"
    "/summary_daily – Päivän yhteenveto\n"
    "/summary_weekly – Viikon yhteenveto\n"
    "/summary_agents – Agenttikohtainen yhteenveto\n"
    "/compare – Vertaa usean agentin näkemyksiä\n\n"
    "🔹 Tiedonkeruu\n"
    "/track – Yleinen tiedonkeruu\n"
    "/track_mood – Kirjaa mieliala\n"
    "/track_energy – Kirjaa energiataso\n"
    "/track_spending – Kirjaa kulutus\n"
    "/track_habit – Kirjaa tapa tai suoritus\n"
    "/track_weather_on – Ota automaattinen sääseuranta käyttöön\n"
    "/track_weather_off – Poista automaattinen sääseuranta\n\n"
    "🔹 Muokkaus\n"
    "/edit – Muokkaa edellistä vastausta tai kirjausta\n\n"
    "🔹 Kehittäjä\n"
    "/debug – Debug-tiedot\n"
    "/db – Tietokannan tila\n"
    "/export – Vie käyttäjädata\n"
    "/import – Tuo käyttäjädata\n"
)

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)

# --- OWNER-ONLY versio (jos haluat saman mallin kuin study.py) ---
# @router.message(Command("help"))
# async def cmd_help(message: Message, config) -> None:
#     if message.from_user.id != config.owner_telegram_id:
#         return await message.answer("Tämä botti on rajattu omistajalle.")
#     await message.answer(HELP_TEXT)
