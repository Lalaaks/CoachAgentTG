from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import StudyFlow
from app.keyboards import minutes_kb, scale_1_5, reminder_kb

router = Router()

def is_owner(message_or_call, owner_id: int) -> bool:
    uid = message_or_call.from_user.id
    return uid == owner_id

@router.message(Command("study"))
async def cmd_study(message: Message, state: FSMContext, db, config):
    if not is_owner(message, config.owner_telegram_id):
        return await message.answer("Tämä botti on rajattu omistajalle.")
    active = await db.get_active_study_session(message.from_user.id)
    if active:
        return await message.answer(
            f"Sinulla on jo aktiivinen sessio:\n"
            f"• Aihe: {active.get('topic')}\n"
            f"• Tavoite: {active.get('goal')}\n\n"
            f"Lopeta: /end"
        )

    await state.clear()
    await state.set_state(StudyFlow.start_topic)
    await message.answer("📚 Mitä opiskelet? (kurssi/aihe)")

@router.message(StudyFlow.start_topic)
async def study_topic(message: Message, state: FSMContext, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await state.update_data(topic=message.text.strip())
    await state.set_state(StudyFlow.start_goal)
    await message.answer("🎯 Mikä on tämän session tavoite yhdellä lauseella?")

@router.message(StudyFlow.start_goal)
async def study_goal(message: Message, state: FSMContext, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await state.update_data(goal=message.text.strip())
    await state.set_state(StudyFlow.start_planned)
    await message.answer("⏱️ Kuinka monta minuuttia aiot opiskella?", reply_markup=minutes_kb("study:planned"))

@router.callback_query(F.data.startswith("study:planned:"))
async def study_planned(call: CallbackQuery, state: FSMContext, db, config):
    if call.from_user.id != config.owner_telegram_id:
        return await call.answer("Ei oikeutta.", show_alert=True)

    planned = int(call.data.split(":")[-1])
    data = await state.get_data()
    topic = data.get("topic", "")
    goal = data.get("goal", "")

    session_id = await db.create_study_session(call.from_user.id, topic, goal, planned)
    await state.clear()

    await call.message.answer(
        f"✅ Sessio aloitettu!\n"
        f"• Aihe: {topic}\n"
        f"• Tavoite: {goal}\n"
        f"• Suunniteltu: {planned} min\n\n"
        f"Kun lopetat, kirjoita: /end"
    )
    await call.answer()

@router.message(Command("end"))
async def cmd_end(message: Message, state: FSMContext, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    active = await db.get_active_study_session(message.from_user.id)
    if not active:
        return await message.answer("Ei aktiivista sessiota. Aloita: /study")

    await state.clear()
    await state.update_data(active_session_id=active["id"])
    await state.set_state(StudyFlow.end_done_minutes)
    await message.answer("⏱️ Kuinka monta minuuttia teit oikeasti?", reply_markup=minutes_kb("study:done"))

@router.callback_query(F.data.startswith("study:done:"))
async def end_done_minutes(call: CallbackQuery, state: FSMContext, config):
    if call.from_user.id != config.owner_telegram_id:
        return await call.answer("Ei oikeutta.", show_alert=True)
    done = int(call.data.split(":")[-1])
    await state.update_data(done_minutes=done)
    await state.set_state(StudyFlow.end_what_done)
    await call.message.answer("✅ Mitä sait aikaan? (max 2 riviä)")
    await call.answer()

@router.message(StudyFlow.end_what_done)
async def end_what_done(message: Message, state: FSMContext, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await state.update_data(what_done=message.text.strip())
    await state.set_state(StudyFlow.end_stuck)
    await message.answer("🧩 Mihin jäit jumiin? (tai kirjoita: ei)")

@router.message(StudyFlow.end_stuck)
async def end_stuck(message: Message, state: FSMContext, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await state.update_data(stuck_point=message.text.strip())
    await state.set_state(StudyFlow.end_focus)
    await message.answer("🎛️ Arvioi fokus 1–5", reply_markup=scale_1_5("study:focus"))

@router.callback_query(F.data.startswith("study:focus:"))
async def end_focus(call: CallbackQuery, state: FSMContext, config):
    if call.from_user.id != config.owner_telegram_id:
        return await call.answer("Ei oikeutta.", show_alert=True)
    focus = int(call.data.split(":")[-1])
    await state.update_data(focus=focus)
    await state.set_state(StudyFlow.end_difficulty)
    await call.message.answer("📈 Arvioi vaikeus 1–5", reply_markup=scale_1_5("study:difficulty"))
    await call.answer()

@router.callback_query(F.data.startswith("study:difficulty:"))
async def end_difficulty(call: CallbackQuery, state: FSMContext, config):
    if call.from_user.id != config.owner_telegram_id:
        return await call.answer("Ei oikeutta.", show_alert=True)
    diff = int(call.data.split(":")[-1])
    await state.update_data(difficulty=diff)
    await state.set_state(StudyFlow.end_next_step)
    await call.message.answer("➡️ Mikä on seuraava askel (täsmälleen yksi)?")
    await call.answer()

@router.message(StudyFlow.end_next_step)
async def end_next_step(message: Message, state: FSMContext, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    await state.update_data(next_step=message.text.strip())
    await state.set_state(StudyFlow.end_feynman)
    await message.answer("🧠 Selitä 3–5 lauseella: mitä opit? (Feynman)")

@router.message(StudyFlow.end_feynman)
async def end_feynman(message: Message, state: FSMContext, db, config):
    if message.from_user.id != config.owner_telegram_id:
        return
    data = await state.get_data()
    session_id = data["active_session_id"]

    await db.complete_study_session(
        session_id=session_id,
        done_minutes=int(data.get("done_minutes", 0)),
        what_done=data.get("what_done", ""),
        stuck_point=data.get("stuck_point", ""),
        focus=int(data.get("focus", 3)),
        difficulty=int(data.get("difficulty", 3)),
        next_step=data.get("next_step", ""),
        feynman=message.text.strip(),
    )
    await state.clear()

    await message.answer(
        "✅ Tallennettu!\n\n"
        f"• Tehty: {data.get('done_minutes')} min\n"
        f"• Fokus: {data.get('focus')}/5 | Vaikeus: {data.get('difficulty')}/5\n"
        f"• Seuraava askel: {data.get('next_step')}\n\n"
        "Haluatko uuden session? /study\n"
        "Tilastot: /stats"
    )

# Reminder callbacks (cron lähettää viestin, jossa nämä napit)
@router.callback_query(F.data == "remind:start_now")
async def remind_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Päivän aihe?")
    await state.clear()
    await state.set_state(StudyFlow.start_topic)
    await call.answer()

@router.callback_query(F.data == "remind:snooze")
async def remind_snooze(call: CallbackQuery, db, config):
    # Toteutus: cron_remind hoitaa snoozen kirjaamalla esim. settingsiin "last_reminder_date" + erillinen "snooze_until"
    # Tässä MVP: vastataan vain vahvistus.
    await call.message.answer("⏰ Ok, siirretään (MVP: snooze-logiikka lisätään cron-skriptiin).")
    await call.answer()

@router.callback_query(F.data == "remind:not_today")
async def remind_not_today(call: CallbackQuery, db, config):
    # MVP: merkitään last_reminder_date tänään, ettei enää muistuteta.
    from datetime import datetime
    today = datetime.now().date().isoformat()
    await db.update_settings(call.from_user.id, last_reminder_date=today)
    await call.message.answer("👍 Selvä. Ei muistuteta enää tänään.")
    await call.answer()
