from __future__ import annotations

import os
from datetime import timezone
from uuid import uuid4

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.domain.common.time import to_iso
from app.infra.clock.system_clock import SystemClock
from app.infra.db.connection import Database
from app.infra.db.repo.ai_analyses_sqlite import AiAnalysesRepo
from app.domain.analytics.tasks_analytics_service import TasksAnalyticsService
from app.ui.telegram.keyboards.stats import stats_menu_kb, stats_result_kb
from app.ui.telegram.keyboards.mainmenu import main_menu_kb

router = Router()

DEFAULT_MODEL = os.getenv("LIFEOPS_ANALYSIS_MODEL", "gpt-4o-mini")


def _now_utc_iso(clock: SystemClock) -> str:
    return to_iso(clock.now().astimezone(timezone.utc))


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    await message.answer("📊 Tilastot", reply_markup=stats_menu_kb())


@router.callback_query(F.data.startswith("stats:tasks:"))
async def stats_tasks_analysis(
    cb: CallbackQuery,
    db: Database,
    clock: SystemClock,
):
    # Parse period days
    try:
        period_days = int((cb.data or "").split(":")[-1])
    except Exception:
        period_days = 7

    # 1) openai package check (do not crash bot)
    try:
        from openai import OpenAI  # type: ignore
    except ModuleNotFoundError:
        await cb.answer()
        await cb.message.answer(
            "AI-analyysi ei ole käytössä, koska python-paketti 'openai' puuttuu.\n\n"
            "Korjaus (venv päällä):\n"
            "pip install openai\n\n"
            "Kun asennus on tehty, käynnistä botti uudelleen.",
            reply_markup=main_menu_kb(),
        )
        return

    # 2) API key check
    if not os.getenv("OPENAI_API_KEY"):
        await cb.answer()
        await cb.message.answer(
            "OPENAI_API_KEY puuttuu ympäristömuuttujista.\n\n"
            "Lisää avain esim. .env / ympäristömuuttujiin ja käynnistä botti uudelleen.",
            reply_markup=main_menu_kb(),
        )
        return

    await cb.answer("Analysoidaan…")

    # Compute metrics
    openai = OpenAI()
    service = TasksAnalyticsService(db=db, openai=openai, model=DEFAULT_MODEL)
    analyses = AiAnalysesRepo(db)

    now_utc = clock.now().astimezone(timezone.utc)
    metrics = await service.compute_metrics(user_id=cb.from_user.id, period_days=period_days, now_utc=now_utc)

    # Generate analysis with LLM
    analysis_text = await service.generate_analysis_text(metrics=metrics)

    # Store analysis
    analysis_id = uuid4().hex
    created_at = _now_utc_iso(clock)
    await analyses.insert(
        analysis_id=analysis_id,
        user_id=cb.from_user.id,
        kind="tasks",
        period_days=period_days,
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        model=DEFAULT_MODEL,
        input_dict={
            "created_in_period": metrics.created_in_period,
            "done_in_period": metrics.done_in_period,
            "deleted_in_period": metrics.deleted_in_period,
            "pending_now": metrics.pending_now,
            "avg_complete_minutes": metrics.avg_complete_minutes,
            "median_complete_minutes": metrics.median_complete_minutes,
            "sample_done_titles": metrics.sample_done_titles,
            "sample_pending_titles": metrics.sample_pending_titles,
        },
        output_text=analysis_text,
        created_at=created_at,
    )

    header = (
        f"🧠 <b>Tehtäväanalyysi ({period_days} päivää)</b>\n"
        f"Ajanjakso: {metrics.period_start} – {metrics.period_end}\n\n"
    )

    await cb.message.answer(header + analysis_text, reply_markup=stats_result_kb(period_days))
    await cb.message.answer("Valmis.", reply_markup=main_menu_kb())
