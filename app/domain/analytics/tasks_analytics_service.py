from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_iso(dt: str) -> datetime:
    s = (dt or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TasksMetrics:
    period_days: int
    period_start: str
    period_end: str

    created_in_period: int
    done_in_period: int
    deleted_in_period: int
    pending_now: int

    avg_complete_minutes: float | None
    median_complete_minutes: float | None

    sample_done_titles: list[str]
    sample_pending_titles: list[str]


class TasksAnalyticsService:
    """
    Service is intentionally decoupled from OpenAI imports.
    It expects an object with method:
      client.responses.create(model=..., input=[...])
    """

    def __init__(self, *, db, openai_client: Any, model: str) -> None:
        self._db = db
        self._openai = openai_client
        self._model = model

    async def compute_metrics(self, *, user_id: int, period_days: int, now_utc: datetime) -> TasksMetrics:
        end = now_utc.astimezone(timezone.utc)
        start = end - timedelta(days=int(period_days))

        start_iso = _iso_utc(start)
        end_iso = _iso_utc(end)

        # created in period
        row = await self._db.fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo'
              AND created_at >= ? AND created_at <= ?;
            """,
            (user_id, start_iso, end_iso),
        )
        created_in_period = int(row["cnt"] or 0) if row else 0

        # done in period
        row = await self._db.fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='done'
              AND completed_at IS NOT NULL
              AND completed_at >= ? AND completed_at <= ?;
            """,
            (user_id, start_iso, end_iso),
        )
        done_in_period = int(row["cnt"] or 0) if row else 0

        # deleted in period (use updated_at as deletion time)
        row = await self._db.fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='deleted'
              AND updated_at >= ? AND updated_at <= ?;
            """,
            (user_id, start_iso, end_iso),
        )
        deleted_in_period = int(row["cnt"] or 0) if row else 0

        # pending now
        row = await self._db.fetchone(
            """
            SELECT COUNT(*) AS cnt
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='pending';
            """,
            (user_id,),
        )
        pending_now = int(row["cnt"] or 0) if row else 0

        # completion times for done in period
        rows = await self._db.fetchall(
            """
            SELECT created_at, completed_at
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='done'
              AND completed_at IS NOT NULL
              AND completed_at >= ? AND completed_at <= ?
            ORDER BY completed_at ASC;
            """,
            (user_id, start_iso, end_iso),
        )
        durations_min: list[float] = []
        for r in rows:
            try:
                ca = _parse_iso(r["created_at"])
                da = _parse_iso(r["completed_at"])
                durations_min.append((da - ca).total_seconds() / 60.0)
            except Exception:
                pass

        avg_complete_minutes = (sum(durations_min) / len(durations_min)) if durations_min else None
        median_complete_minutes = None
        if durations_min:
            xs = sorted(durations_min)
            n = len(xs)
            mid = n // 2
            median_complete_minutes = xs[mid] if (n % 2 == 1) else (xs[mid - 1] + xs[mid]) / 2.0

        # sample done titles
        rows = await self._db.fetchall(
            """
            SELECT payload_json
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='done'
              AND completed_at IS NOT NULL
              AND completed_at >= ? AND completed_at <= ?
            ORDER BY completed_at DESC
            LIMIT 8;
            """,
            (user_id, start_iso, end_iso),
        )
        sample_done_titles: list[str] = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"] or "{}")
                t = (payload.get("title") or "").strip()
                if t:
                    sample_done_titles.append(t)
            except Exception:
                pass

        # sample pending titles (current)
        rows = await self._db.fetchall(
            """
            SELECT payload_json
            FROM scheduled_jobs
            WHERE user_id=? AND job_type='todo' AND status='pending'
            ORDER BY created_at ASC
            LIMIT 8;
            """,
            (user_id,),
        )
        sample_pending_titles: list[str] = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"] or "{}")
                t = (payload.get("title") or "").strip()
                if t:
                    sample_pending_titles.append(t)
            except Exception:
                pass

        return TasksMetrics(
            period_days=int(period_days),
            period_start=start_iso,
            period_end=end_iso,
            created_in_period=created_in_period,
            done_in_period=done_in_period,
            deleted_in_period=deleted_in_period,
            pending_now=pending_now,
            avg_complete_minutes=avg_complete_minutes,
            median_complete_minutes=median_complete_minutes,
            sample_done_titles=sample_done_titles,
            sample_pending_titles=sample_pending_titles,
        )

    async def generate_analysis_text(self, *, metrics: TasksMetrics) -> str:
        sys = (
            "Olet tuottavuusvalmentaja. Kirjoita analyysi suomeksi, napakasti mutta hyödyllisesti. "
            "Älä keksi faktoja: käytä vain annettuja lukuja ja esimerkkitehtäviä."
        )

        user_payload = {
            "period_days": metrics.period_days,
            "period_start": metrics.period_start,
            "period_end": metrics.period_end,
            "created_in_period": metrics.created_in_period,
            "done_in_period": metrics.done_in_period,
            "deleted_in_period": metrics.deleted_in_period,
            "pending_now": metrics.pending_now,
            "avg_complete_minutes": metrics.avg_complete_minutes,
            "median_complete_minutes": metrics.median_complete_minutes,
            "sample_done_titles": metrics.sample_done_titles,
            "sample_pending_titles": metrics.sample_pending_titles,
            "instructions": [
                "Tee 3–6 bullet-pointtia havainnoista.",
                "Nosta esiin 1–2 mahdollista pullonkaulaa tai toistuvaa teemaa esimerkeistä (jos aineisto riittää).",
                "Anna 3 konkreettista seuraavaa askelta.",
                "Lopuksi: yksi lyhyt 'tämän viikon fokus' -lause.",
            ],
        }

        resp = self._openai.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": sys},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        text = (getattr(resp, "output_text", None) or "").strip()
        return text or "Analyysi epäonnistui: tyhjä vastaus."
