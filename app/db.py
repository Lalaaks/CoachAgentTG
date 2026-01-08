import json
from datetime import datetime, timezone
import aiosqlite

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

CREATE_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS settings (
  user_id INTEGER PRIMARY KEY,
  timezone TEXT NOT NULL,
  study_reminder_enabled INTEGER NOT NULL DEFAULT 1,
  study_reminder_time TEXT NOT NULL DEFAULT '18:00',
  study_reminder_days TEXT NOT NULL DEFAULT '1,2,3,4,5',
  study_snooze_minutes INTEGER NOT NULL DEFAULT 30,
  daily_summary_time TEXT NOT NULL DEFAULT '21:00',
  weekly_summary_day INTEGER NOT NULL DEFAULT 7,
  weekly_summary_time TEXT NOT NULL DEFAULT '19:00',
  last_reminder_date TEXT
);

CREATE TABLE IF NOT EXISTS study_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  topic TEXT,
  goal TEXT,
  planned_minutes INTEGER,
  done_minutes INTEGER,
  what_done TEXT,
  stuck_point TEXT,
  focus INTEGER,
  difficulty INTEGER,
  next_step TEXT,
  feynman TEXT,
  created_from TEXT NOT NULL DEFAULT 'telegram',
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  ref_id INTEGER,
  payload TEXT,
  created_at TEXT NOT NULL
);
"""

class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self, owner_user_id: int, tz: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(CREATE_SQL)
            # Ensure settings row exists
            await db.execute(
                "INSERT OR IGNORE INTO settings (user_id, timezone) VALUES (?, ?)",
                (owner_user_id, tz),
            )
            await db.commit()

    async def get_settings(self, user_id: int) -> dict:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM settings WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else {}

    async def update_settings(self, user_id: int, **fields) -> None:
        if not fields:
            return
        cols = ", ".join([f"{k}=?" for k in fields.keys()])
        vals = list(fields.values()) + [user_id]
        q = f"UPDATE settings SET {cols} WHERE user_id=?"
        async with aiosqlite.connect(self.path) as db:
            await db.execute(q, vals)
            await db.commit()

    async def create_study_session(self, user_id: int, topic: str, goal: str, planned_minutes: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """
                INSERT INTO study_sessions (user_id, started_at, topic, goal, planned_minutes, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (user_id, utc_now_iso(), topic, goal, planned_minutes),
            )
            sid = cur.lastrowid
            await db.execute(
                "INSERT INTO events (user_id, type, ref_id, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, "study_created", sid, None, utc_now_iso()),
            )
            await db.commit()
            return int(sid)

    async def get_active_study_session(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
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
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE study_sessions
                SET ended_at=?, done_minutes=?, what_done=?, stuck_point=?, focus=?, difficulty=?, next_step=?, feynman=?, status='completed'
                WHERE id=?
                """,
                (utc_now_iso(), done_minutes, what_done, stuck_point, focus, difficulty, next_step, feynman, session_id),
            )
            await db.execute(
                "INSERT INTO events (user_id, type, ref_id, payload, created_at) "
                "SELECT user_id, 'study_completed', id, NULL, ? FROM study_sessions WHERE id=?",
                (utc_now_iso(), session_id),
            )
            await db.commit()

    async def get_last_study_session(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM study_sessions WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_week_stats(self, user_id: int, since_iso: str) -> dict:
        # since_iso: ISO UTC string for start of window (e.g., monday 00:00 local converted to UTC)
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT
                  COUNT(*) as sessions,
                  COALESCE(SUM(done_minutes), 0) as minutes
                FROM study_sessions
                WHERE user_id=? AND status='completed' AND ended_at >= ?
                """,
                (user_id, since_iso),
            )
            base = dict(await cur.fetchone())

            cur2 = await db.execute(
                """
                SELECT topic, COALESCE(SUM(done_minutes),0) as minutes
                FROM study_sessions
                WHERE user_id=? AND status='completed' AND ended_at >= ?
                GROUP BY topic
                ORDER BY minutes DESC
                LIMIT 3
                """,
                (user_id, since_iso),
            )
            top_topics = [dict(r) for r in await cur2.fetchall()]

            cur3 = await db.execute(
                """
                SELECT stuck_point, COUNT(*) as cnt
                FROM study_sessions
                WHERE user_id=? AND status='completed' AND ended_at >= ? AND stuck_point IS NOT NULL AND TRIM(stuck_point) != '' AND stuck_point != 'ei'
                GROUP BY stuck_point
                ORDER BY cnt DESC
                LIMIT 3
                """,
                (user_id, since_iso),
            )
            top_stuck = [dict(r) for r in await cur3.fetchall()]

            return {"base": base, "top_topics": top_topics, "top_stuck": top_stuck}

    async def undo_last_event(self, user_id: int) -> str:
        """
        Simple undo:
        - If last event is study_created => delete that session (only if still active)
        - If last event is study_completed => revert to active and clear end fields
        """
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM events WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            ev = await cur.fetchone()
            if not ev:
                return "Ei peruttavaa."

            ev_type = ev["type"]
            ref_id = ev["ref_id"]

            if ev_type == "study_created":
                # delete only if still active
                cur2 = await db.execute("SELECT status FROM study_sessions WHERE id=?", (ref_id,))
                row = await cur2.fetchone()
                if not row:
                    return "Viimeisin tapahtuma löytyi, mutta sessiota ei enää ole."
                if row["status"] != "active":
                    return "Viimeisin tapahtuma oli session luonti, mutta sessio ei ole enää aktiivinen."
                await db.execute("DELETE FROM study_sessions WHERE id=?", (ref_id,))
                await db.execute("DELETE FROM events WHERE id=?", (ev["id"],))
                await db.commit()
                return "Peruttu: viimeisin (aktiivinen) opiskelusessio poistettu."

            if ev_type == "study_completed":
                # revert completion
                await db.execute(
                    """
                    UPDATE study_sessions
                    SET ended_at=NULL, done_minutes=NULL, what_done=NULL, stuck_point=NULL, focus=NULL, difficulty=NULL, next_step=NULL, feynman=NULL, status='active'
                    WHERE id=?
                    """,
                    (ref_id,),
                )
                await db.execute("DELETE FROM events WHERE id=?", (ev["id"],))
                await db.commit()
                return "Peruttu: viimeisin lopetus peruttu ja sessio palautettu aktiiviseksi."

            return f"Undo ei tue vielä tapahtumatyyppiä: {ev_type}"
