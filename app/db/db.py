from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import aiosqlite

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class Settings:
    user_id: int
    timezone: str
    study_reminder_enabled: int
    study_reminder_time: str
    study_reminder_days: str
    weekly_summary_day: int
    weekly_summary_time: str
    last_reminder_date: str | None

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self, owner_user_id: int, tz: str) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT OR IGNORE INTO settings (user_id, timezone) VALUES (?, ?)",
                (owner_user_id, tz),
            )
            await db.commit()

    async def get_settings(self, user_id: int) -> Settings:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM settings WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                raise RuntimeError("Settings row missing; init() not called?")
            return Settings(**dict(row))

    async def update_settings(self, user_id: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join([f"{k}=?" for k in fields.keys()])
        vals = list(fields.values()) + [user_id]
        q = f"UPDATE settings SET {cols} WHERE user_id=?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(q, vals)
            await db.commit()

    async def create_study_session(self, user_id: int, topic: str, goal: str, planned_minutes: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                INSERT INTO study_sessions (user_id, started_at, topic, goal, planned_minutes, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (user_id, utc_now_iso(), topic, goal, planned_minutes),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def get_active_study_session(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM study_sessions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def complete_study_session(
        self,
        session_id: int,
        done_minutes: int,
        what_done: str,
        stuck_point: str,
        focus: int,
        difficulty: int,
        next_step: str,
        feynman: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE study_sessions
                SET ended_at=?, done_minutes=?, what_done=?, stuck_point=?, focus=?, difficulty=?, next_step=?, feynman=?, status='completed'
                WHERE id=?
                """,
                (utc_now_iso(), done_minutes, what_done, stuck_point, focus, difficulty, next_step, feynman, session_id),
            )
            await db.commit()

    async def sum_completed_minutes_since(self, user_id: int, since_iso: str) -> tuple[int, int]:
        """returns (sessions_count, minutes_sum)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT COUNT(*) as sessions, COALESCE(SUM(done_minutes), 0) as minutes
                FROM study_sessions
                WHERE user_id=? AND status='completed' AND ended_at >= ?
                """,
                (user_id, since_iso),
            )
            row = await cur.fetchone()
            return int(row["sessions"]), int(row["minutes"])
