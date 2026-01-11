from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("status"))
async def cmd_status(message: Message, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return await message.answer("Tämä botti on rajattu omistajalle.")

    user_id = message.from_user.id

    agents = await db.get_active_agents(user_id)
    schedules = await db.get_schedules(user_id)
    last_summary = await db.get_last_summary(user_id)
    active_study = await db.get_active_study_session(user_id)

    text = "📊 TILANNEKATSAUS\n\n"

    text += "🤖 Aktiiviset agentit:\n"
    text += ("\n".join(f"• {a}" for a in agents) if agents else "– Ei aktiivisia agentteja")
    text += "\n\n"

    text += "⏰ Ajastukset:\n"
    if schedules:
        for s in schedules:
            rule = f" ({s['rrule']})" if s.get("rrule") else ""
            text += f"• #{s['id']} {s['agent']} @ {s['time']}{rule}\n"
    else:
        text += "– Ei ajastuksia"
    text += "\n"

    text += "\n📚 Opiskelu:\n"
    if active_study:
        text += (
            "• Aktiivinen sessio käynnissä\n"
            f"• Aihe: {active_study.get('topic')}\n"
            f"• Tavoite: {active_study.get('goal')}\n"
            f"• Suunniteltu: {active_study.get('planned_minutes')} min\n"
            "Lopeta: /end"
        )
    else:
        text += "– Ei aktiivista sessiota (aloita: /study)"
    text += "\n\n"

    text += "🧾 Viimeisin yhteenveto:\n"
    if last_summary:
        text += f"• {last_summary['title']}\n• {last_summary['created_at']}"
    else:
        text += "– Ei yhteenvetoja vielä"

    await message.answer(text)
