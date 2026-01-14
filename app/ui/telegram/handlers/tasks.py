from __future__ import annotations

from uuid import uuid4

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.domain.common.time import to_iso
from app.infra.clock.system_clock import SystemClock
from app.infra.db.repo.scheduled_jobs_sqlite import ScheduledJobsRepo
from app.ui.telegram.keyboards.mainmenu import main_menu_kb
from app.ui.telegram.keyboards.tasks import tasks_list_kb
from app.ui.telegram.states.tasks import TasksFlow

router = Router()


async def _show_pending(message: Message, jobs_repo: ScheduledJobsRepo) -> None:
    items = await jobs_repo.list_pending_todos(message.from_user.id)
    if not items:
        await message.answer("Ei tekemättömiä tehtäviä.", reply_markup=main_menu_kb())
        return
    await message.answer("Tekemättömät tehtävät:", reply_markup=tasks_list_kb(items))


@router.message(Command("td"))
@router.message(Command("todo"))
async def td_list(message: Message, jobs_repo: ScheduledJobsRepo):
    await _show_pending(message, jobs_repo)


@router.message(Command("td_add"))
async def td_add_cmd(message: Message, state: FSMContext):
    # varalla debugiin / tulevaan: /td_add <title>
    await state.set_state(TasksFlow.add_title)
    await message.answer("Kirjoita tehtävän kuvaus.", reply_markup=main_menu_kb())


@router.message(TasksFlow.add_title)
async def td_add_title(message: Message, state: FSMContext, jobs_repo: ScheduledJobsRepo, clock: SystemClock):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Tyhjä tehtävä ei kelpaa. Kirjoita kuvaus.")
        return

    job_id = uuid4().hex
    await jobs_repo.create_todo(
        job_id=job_id,
        user_id=message.from_user.id,
        title=title,
        chat_id=message.chat.id,
        now_iso=to_iso(clock.now()),
    )
    await state.clear()
    await message.answer("Tehtävä lisätty.", reply_markup=main_menu_kb())
    await _show_pending(message, jobs_repo)


@router.callback_query(F.data.startswith("td:done:"))
async def td_done(cb: CallbackQuery, jobs_repo: ScheduledJobsRepo, clock: SystemClock):
    await cb.answer()
    job_id = cb.data.split(":")[-1]
    await jobs_repo.mark_todo_done(job_id, cb.from_user.id, to_iso(clock.now()))
    await cb.message.answer("Merkitty tehdyksi.", reply_markup=main_menu_kb())
    await _show_pending(cb.message, jobs_repo)


@router.callback_query(F.data.startswith("td:del:"))
async def td_delete(cb: CallbackQuery, jobs_repo: ScheduledJobsRepo, clock: SystemClock):
    await cb.answer()
    job_id = cb.data.split(":")[-1]
    await jobs_repo.delete_todo(job_id, cb.from_user.id, to_iso(clock.now()))
    await cb.message.answer("Poistettu listalta.", reply_markup=main_menu_kb())
    await _show_pending(cb.message, jobs_repo)


@router.callback_query(F.data.startswith("td:edit:"))
async def td_edit(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    job_id = cb.data.split(":")[-1]
    await state.update_data(edit_job_id=job_id)
    await state.set_state(TasksFlow.edit_title)
    await cb.message.answer("Kirjoita uusi kuvaus.", reply_markup=main_menu_kb())


@router.message(TasksFlow.edit_title)
async def td_edit_title(message: Message, state: FSMContext, jobs_repo: ScheduledJobsRepo, clock: SystemClock):
    title = (message.text or "").strip()
    data = await state.get_data()
    job_id = data.get("edit_job_id")

    if not job_id:
        await state.clear()
        await message.answer("Muokkaus keskeytyi.", reply_markup=main_menu_kb())
        return

    if not title:
        await message.answer("Tyhjä kuvaus ei kelpaa. Kirjoita uusi kuvaus.")
        return

    await jobs_repo.update_todo_title(job_id, message.from_user.id, title, to_iso(clock.now()))
    await state.clear()
    await message.answer("Päivitetty.", reply_markup=main_menu_kb())
    await _show_pending(message, jobs_repo)
