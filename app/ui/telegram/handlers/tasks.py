from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.infra.db.connection import Database
from app.infra.clock.system_clock import SystemClock
from app.domain.common.time import to_iso
from app.infra.db.repo.scheduled_jobs_sqlite import ScheduledJobsRepo, ScheduledJob

router = Router()

CB_PREFIX = "td"
SYSTEM_AGENT_ID = "system"
TODO_JOB_TYPE = "todo"


def _job_title(job: ScheduledJob) -> str:
    title = (job.payload or {}).get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return f"{job.job_type} @ {job.due_at}"


def _build_list_kb(jobs: list[ScheduledJob]):
    kb = InlineKeyboardBuilder()

    # Add button on top (UI finalize later)
    kb.button(text="➕ Lisää", callback_data=f"{CB_PREFIX}:add")
    kb.adjust(1)

    for job in jobs:
        title = _job_title(job)
        kb.button(text=f"🟩 {title}", callback_data=f"{CB_PREFIX}:done:{job.job_id}")
        kb.button(text="✏️", callback_data=f"{CB_PREFIX}:edit:{job.job_id}")
        kb.button(text="🗑️", callback_data=f"{CB_PREFIX}:del:{job.job_id}")
        kb.adjust(1, 3)

    return kb.as_markup()


async def _render_list(repo: ScheduledJobsRepo, user_id: int):
    jobs = list(await repo.list_pending_todos_for_user(user_id=user_id, limit=5000))
    if not jobs:
        return "Ei tekemättömiä tehtäviä ✅", None

    text = (
        f"Tekemättömät ({len(jobs)}):\n\n"
        "🟩 = done • ✏️ = muokkaa • 🗑️ = poista"
    )
    return text, _build_list_kb(jobs)


def _parse_delay(token: str) -> timedelta:
    # 10m / 2h / 1d
    m = re.fullmatch(r"(\d+)([mhd])", token.strip().lower())
    if not m:
        raise ValueError
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return timedelta(minutes=n)
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)
    raise ValueError


def _parse_due_local(tokens: list[str], tz_name: str, now_local: datetime) -> tuple[datetime, int]:
    """
    Supported:
      in 10m | in 2h | in 1d
      18:30
      2026-01-13 18:30
      2026-01-13T18:30
    Returns (due_local, tokens_consumed)
    """
    if not tokens:
        raise ValueError

    t0 = tokens[0].lower()
    tz = ZoneInfo(tz_name)

    if t0 == "in" and len(tokens) >= 2:
        delta = _parse_delay(tokens[1])
        return now_local + delta, 2

    if re.fullmatch(r"\d{2}:\d{2}", tokens[0]):
        hh = int(tokens[0][:2])
        mm = int(tokens[0][3:])
        due = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if due <= now_local:
            due = due + timedelta(days=1)
        return due, 1

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tokens[0]) and len(tokens) >= 2:
        raw = f"{tokens[0]}T{tokens[1]}"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt, 2

    if "T" in tokens[0] and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", tokens[0]):
        dt = datetime.fromisoformat(tokens[0])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt, 1

    raise ValueError


async def _ensure_user_and_system_agent(db: Database, user_id: int, now_iso: str) -> None:
    # users
    row = await db.fetchone("SELECT user_id FROM users WHERE user_id=?;", (user_id,))
    if row:
        await db.execute("UPDATE users SET last_seen_at=? WHERE user_id=?;", (now_iso, user_id))
    else:
        await db.execute(
            "INSERT INTO users(user_id, created_at, last_seen_at) VALUES (?, ?, ?);",
            (user_id, now_iso, now_iso),
        )

    # system agent
    arow = await db.fetchone("SELECT agent_id FROM agents WHERE agent_id=?;", (SYSTEM_AGENT_ID,))
    if not arow:
        await db.execute(
            "INSERT INTO agents(agent_id, name, category, is_active, created_at) VALUES (?, ?, ?, 1, ?);",
            (SYSTEM_AGENT_ID, "System", "core", now_iso),
        )


@router.message(Command(commands=["td", "todo"]))
async def td_entry(message: Message, db: Database, clock: SystemClock, timezone: str):
    """
    /td or /todo -> list
    /td help
    /td a <task>  (also /td add <task>)
    /td r         (also /td remove)
    /td clear
    /td add t <time> <task>   (also timed)
    """
    raw = (message.text or "").strip()

    # remove /td or /todo prefix
    tail = raw
    if raw.lower().startswith("/td"):
        tail = raw[3:].strip()
    elif raw.lower().startswith("/todo"):
        tail = raw[5:].strip()

    repo = ScheduledJobsRepo(db)
    user_id = message.from_user.id

    # No subcommand => list
    if not tail:
        text, kb = await _render_list(repo, user_id)
        await message.answer(text, reply_markup=kb)
        return

    parts = tail.split()
    sub = parts[0].lower()

    # help
    if sub in ("help", "h", "?"):
        await message.answer(
            "TD-komennot:\n"
            "/td  (tai /todo) = listaa tehtävät nappuloina\n"
            "/td help\n"
            "/td a <tehtävä>\n"
            "/td add <tehtävä>\n"
            "/td add t <aika> <tehtävä>\n"
            "/td add timed <aika> <tehtävä>\n"
            "  Aika: 18:30 | in 10m | 2026-01-13 18:30 | 2026-01-13T18:30\n"
            "/td r  (poistaa ylimmän)\n"
            "/td remove\n"
            "/td clear (poistaa kaikki)\n"
        )
        return

    now_iso = to_iso(clock.now())
    await _ensure_user_and_system_agent(db, user_id, now_iso)

    # ADD (you prefer /td a and /td add)
    if sub in ("a", "add"):
        # timed add: /td add t <time> <task> OR /td add timed <time> <task>
        if len(parts) >= 2 and parts[1].lower() in ("t", "timed"):
            if len(parts) < 4:
                await message.answer("Käyttö: /td add t <aika> <tehtävä>")
                return

            tz = ZoneInfo(timezone)
            now_local = clock.now().astimezone(tz)

            try:
                due_local, consumed = _parse_due_local(parts[2:], timezone, now_local)
            except Exception:
                await message.answer("Aika väärässä muodossa. Katso: /td help")
                return

            title = " ".join(parts[2 + consumed:]).strip()
            if not title:
                await message.answer("Puuttuu tehtävän teksti.")
                return

            due_utc = due_local.astimezone(timezone.utc)
            job_id = str(uuid.uuid4())

            await repo.create_todo(
                job_id=job_id,
                user_id=user_id,
                agent_id=SYSTEM_AGENT_ID,
                title=title,
                chat_id=message.chat.id,
                due_at_iso_utc=to_iso(due_utc),
                now_iso=now_iso,
            )

            text, kb = await _render_list(repo, user_id)
            await message.answer(
                f"⏰ Ajastettu: {due_local.strftime('%Y-%m-%d %H:%M')} — {title}\n\n{text}",
                reply_markup=kb,
            )
            return

        # normal add: /td a <task> OR /td add <task>
        title = " ".join(parts[1:]).strip()
        if not title:
            await message.answer("Käyttö: /td a <tehtävä>")
            return

        job_id = str(uuid.uuid4())

        # Non-timed todo: put due far in future so it stays list-only
        await repo.create_todo(
            job_id=job_id,
            user_id=user_id,
            agent_id=SYSTEM_AGENT_ID,
            title=title,
            chat_id=message.chat.id,
            due_at_iso_utc="9999-12-31T23:59:59+00:00",
            now_iso=now_iso,
        )

        text, kb = await _render_list(repo, user_id)
        await message.answer(f"➕ Lisätty: {title}\n\n{text}", reply_markup=kb)
        return

    # REMOVE TOP (you prefer /td r)
    if sub in ("r", "remove"):
        ok = await repo.cancel_top_todo_for_user(user_id=user_id, now_iso=now_iso)
        if not ok:
            await message.answer("Ei poistettavaa.")
            return
        text, kb = await _render_list(repo, user_id)
        await message.answer("🗑️ Poistettu ylin tehtävä.\n\n" + text, reply_markup=kb)
        return

    # CLEAR
    if sub == "clear":
        n = await repo.cancel_all_todos_for_user(user_id=user_id, now_iso=now_iso)
        await message.answer(f"🧹 Tyhjennetty: {n} tehtävää.")
        return

    await message.answer("Tuntematon td-komento. Katso: /td help")


@router.callback_query(lambda c: (c.data or "").startswith(f"{CB_PREFIX}:"))
async def td_callbacks(cb: CallbackQuery, db: Database, clock: SystemClock):
    await cb.answer()

    if not cb.message:
        return

    data = cb.data or ""
    parts = data.split(":", 2)
    if len(parts) < 2:
        return

    action = parts[1]
    job_id = parts[2] if len(parts) == 3 else None

    repo = ScheduledJobsRepo(db)
    user_id = cb.from_user.id
    now_iso = to_iso(clock.now())

    if action == "add":
        await cb.message.answer("Lisää tehtävä: /td a <tehtävä>\nAjasta: /td add t 18:30 <tehtävä>")
        return

    if not job_id:
        return

    if action == "done":
        await repo.mark_done_for_user(job_id=job_id, user_id=user_id, now_iso=now_iso)
    elif action == "del":
        await repo.cancel_for_user(job_id=job_id, user_id=user_id, now_iso=now_iso)
    elif action == "edit":
        await cb.message.answer("✏️ Muokkaus viimeistellään seuraavaksi. (Toistaiseksi: poista ja lisää uudestaan.)")
    else:
        return

    # refresh list in same message
    text, kb = await _render_list(repo, user_id)
    if kb is None:
        await cb.message.edit_text(text)
    else:
        await cb.message.edit_text(text, reply_markup=kb)
