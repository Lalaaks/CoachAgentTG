from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from contextlib import asynccontextmanager

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

    @asynccontextmanager
    async def _connect(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    # --------------------
    # GENERIC SQL HELPERS (UUSI)
    # --------------------
    # Näiden avulla agentit voivat käyttää suoraa SQL:ää (execute/fetchone/fetchall)
    # ilman että jokaista agenttia varten täytyy lisätä nippu uusia DB-metodeja.

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        """
        Suorita SQL (INSERT/UPDATE/DELETE/DDL) ja commit.
        """
        if params is None:
            params = ()
        async with self._connect() as db:
            await db.execute(sql, params)
            await db.commit()

    async def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> aiosqlite.Row | None:
        """
        Palauttaa yhden rivin (aiosqlite.Row) tai None.
        """
        if params is None:
            params = ()
        async with self._connect() as db:
            cur = await db.execute(sql, params)
            row = await cur.fetchone()
            return row

    async def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[aiosqlite.Row]:
        """
        Palauttaa listan rivejä (aiosqlite.Row).
        """
        if params is None:
            params = ()
        async with self._connect() as db:
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            return list(rows)

    async def executescript(self, sql_script: str) -> None:
        """
        Suorita useampi SQL-lause (schema/migraatiot) ja commit.
        """
        async with self._connect() as db:
            await db.executescript(sql_script)
            await db.commit()

    async def init(self, owner_user_id: int, tz: str) -> None:
        """
        - luo db-kansion
        - aja schema.sql (sun nykyinen)
        - lisää puuttuvat taulut (agents/schedules/summaries) IF NOT EXISTS
        - varmistaa settings-row omistajalle
        """
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")

        async with self._connect() as db:
            # 1) vanha schema
            await db.executescript(schema_sql)

            # 2) uudet taulut (ei riko mitään, jos jo olemassa)
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_agents (
                    user_id     INTEGER NOT NULL,
                    agent       TEXT    NOT NULL,
                    enabled     INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT    NOT NULL,
                    PRIMARY KEY (user_id, agent)
                );

                CREATE TABLE IF NOT EXISTS schedules (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    agent       TEXT    NOT NULL,
                    time        TEXT    NOT NULL,   -- "HH:MM"
                    rrule       TEXT    NULL,       -- esim "FREQ=DAILY" tms, tai NULL
                    enabled     INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    kind        TEXT    NOT NULL,   -- "daily" | "weekly" | "agents" | "custom"
                    title       TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    created_at  TEXT    NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_schedules_user ON schedules(user_id);
                CREATE INDEX IF NOT EXISTS idx_summaries_user_created ON summaries(user_id, created_at);
                """
            )

            # 3) settings-rivi
            await db.execute(
                "INSERT OR IGNORE INTO settings (user_id, timezone) VALUES (?, ?)",
                (owner_user_id, tz),
            )
            await db.commit()

    # --------------------
    # SETTINGS
    # --------------------

    async def get_settings(self, user_id: int) -> Settings:
        async with self._connect() as db:
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
        async with self._connect() as db:
            await db.execute(q, vals)
            await db.commit()

    # --------------------
    # STUDY (nykyiset)
    # --------------------

    async def create_study_session(self, user_id: int, topic: str, goal: str, planned_minutes: int) -> int:
        async with self._connect() as db:
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
        async with self._connect() as db:
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
        async with self._connect() as db:
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
        async with self._connect() as db:
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

    # --------------------
    # AGENTS (PUUTTUI)
    # --------------------

    async def get_active_agents(self, user_id: int) -> list[str]:
        """
        Palauttaa enabled=1 agentit listana.
        Jos käyttäjälle ei ole lisätty vielä mitään, palautetaan tyhjä lista.
        """
        async with self._connect() as db:
            cur = await db.execute(
                "SELECT agent FROM user_agents WHERE user_id=? AND enabled=1 ORDER BY agent",
                (user_id,),
            )
            rows = await cur.fetchall()
            return [r["agent"] for r in rows]

    async def set_agent_enabled(self, user_id: int, agent: str, enabled: bool) -> None:
        """
        Lisää agentin jos puuttuu, tai päivittää enabled-tilan.
        """
        agent = agent.strip().lower()
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO user_agents (user_id, agent, enabled, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, agent) DO UPDATE SET enabled=excluded.enabled
                """,
                (user_id, agent, 1 if enabled else 0, utc_now_iso()),
            )
            await db.commit()

    async def remove_agent(self, user_id: int, agent: str) -> None:
        agent = agent.strip().lower()
        async with self._connect() as db:
            await db.execute(
                "DELETE FROM user_agents WHERE user_id=? AND agent=?",
                (user_id, agent),
            )
            await db.commit()

    # --------------------
    # SCHEDULES (PUUTTUI)
    # --------------------

    async def get_schedules(self, user_id: int) -> list[dict[str, Any]]:
        """
        Palauttaa listan: {id, agent, time, rrule, enabled}
        """
        async with self._connect() as db:
            cur = await db.execute(
                """
                SELECT id, agent, time, rrule, enabled
                FROM schedules
                WHERE user_id=? AND enabled=1
                ORDER BY time
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def add_schedule(self, user_id: int, agent: str, time_hhmm: str, rrule: str | None = None) -> int:
        """
        Lisää ajastuksen. time_hhmm esim "08:00". rrule esim "FREQ=DAILY" tai "FREQ=WEEKLY;BYDAY=MO".
        """
        agent = agent.strip().lower()
        async with self._connect() as db:
            cur = await db.execute(
                """
                INSERT INTO schedules (user_id, agent, time, rrule, enabled, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (user_id, agent, time_hhmm, rrule, utc_now_iso()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def remove_schedule(self, user_id: int, schedule_id: int) -> None:
        async with self._connect() as db:
            await db.execute(
                "DELETE FROM schedules WHERE user_id=? AND id=?",
                (user_id, schedule_id),
            )
            await db.commit()

    # --------------------
    # SUMMARIES (PUUTTUI)
    # --------------------

    async def create_summary(self, user_id: int, kind: str, title: str, content: str) -> int:
        """
        kind: daily/weekly/agents/custom
        """
        async with self._connect() as db:
            cur = await db.execute(
                """
                INSERT INTO summaries (user_id, kind, title, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, kind, title, content, utc_now_iso()),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def get_last_summary(self, user_id: int) -> dict[str, Any] | None:
        """
        Palauttaa viimeisimmän yhteenvedon: {id, kind, title, created_at}
        (sisältöä ei palauteta /statusiin turhaan)
        """
        async with self._connect() as db:
            cur = await db.execute(
                """
                SELECT id, kind, title, created_at
                FROM summaries
                WHERE user_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    # --------------------
    # RESET (PUUTTUI)
    # --------------------

    async def reset_user(self, user_id: int) -> None:
        """
        Poistaa käyttäjän datan (study_sessions, agentit, ajastukset, yhteenvedot).
        Jättää settings-rivin olemassaolevaksi, mutta nollaa lisäkentät defaulttiin.
        """
        async with self._connect() as db:
            await db.execute("DELETE FROM study_sessions WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM user_agents WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM schedules WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM summaries WHERE user_id=?", (user_id,))

            # Nollaa asetuksia turvallisesti (pidä timezone ennallaan)
            await db.execute(
                """
                UPDATE settings
                SET
                    study_reminder_enabled = 0,
                    study_reminder_time = '08:00',
                    study_reminder_days = '1,2,3,4,5',
                    weekly_summary_day = 7,
                    weekly_summary_time = '18:00',
                    last_reminder_date = NULL
                WHERE user_id=?
                """,
                (user_id,),
            )
            await db.commit()
