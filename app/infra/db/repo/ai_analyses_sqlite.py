from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from app.infra.db.connection import Database


@dataclass(frozen=True)
class AiAnalysis:
    analysis_id: str
    user_id: int
    kind: str
    period_days: int
    period_start: str
    period_end: str
    model: str
    input: dict[str, Any]
    output_text: str
    created_at: str


class AiAnalysesRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def insert(
        self,
        *,
        analysis_id: str,
        user_id: int,
        kind: str,
        period_days: int,
        period_start: str,
        period_end: str,
        model: str,
        input_dict: dict[str, Any],
        output_text: str,
        created_at: str,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO ai_analyses(
              analysis_id, user_id,
              kind, period_days, period_start, period_end,
              model, input_json, output_text,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                analysis_id,
                user_id,
                kind,
                int(period_days),
                period_start,
                period_end,
                model,
                json.dumps(input_dict, ensure_ascii=False),
                output_text,
                created_at,
            ),
        )

    async def get_latest(self, *, user_id: int, kind: str, period_days: int) -> Optional[AiAnalysis]:
        row = await self._db.fetchone(
            """
            SELECT *
            FROM ai_analyses
            WHERE user_id=? AND kind=? AND period_days=?
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (user_id, kind, int(period_days)),
        )
        if not row:
            return None

        input_dict = {}
        try:
            input_dict = json.loads(row["input_json"] or "{}")
        except Exception:
            input_dict = {}

        return AiAnalysis(
            analysis_id=row["analysis_id"],
            user_id=int(row["user_id"]),
            kind=row["kind"],
            period_days=int(row["period_days"]),
            period_start=row["period_start"],
            period_end=row["period_end"],
            model=row["model"],
            input=input_dict,
            output_text=row["output_text"],
            created_at=row["created_at"],
        )
