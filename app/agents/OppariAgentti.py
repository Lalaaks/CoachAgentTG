# app/agents/opp.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta, time
from typing import Optional, List, Tuple, Dict, Any


AGENT_ID = "opp"


@dataclass
class OppStatus:
    today_started: bool
    today_start_ts: Optional[str]
    today_minutes: int
    open_session: bool
    open_session_started_ts: Optional[str]
    goal_minutes: Optional[int]
    next_steps: List[Tuple[int, str, bool]]  # (id, text, done)
    streak_days_15min: int


class OppariAgent:
    """
    Oppariagentin domain-logiikka.
    Reminder-logiikka perustuu session aloitukseen.
    Streak/weekly käyttää minuutteja (>=15min).
    """

    def __init__(self, db):
        self.db = db  # expects async db wrapper with execute/fetchone/fetchall

    async def ensure_schema(self) -> None:
        # Events: yleinen loki (voit käyttää muille agenteille myös)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            agent_id TEXT NOT NULL,
            type TEXT NOT NULL,
            payload_json TEXT
        );
        """)

        # Sessions: oppari sessiot
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS opp_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            topic TEXT
        );
        """)

        # Daily state for reminder idempotenssi (18/19 lähetetty tänään?)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS opp_daily_state (
            chat_id INTEGER NOT NULL,
            day TEXT NOT NULL, -- YYYY-MM-DD
            reminder_18_sent INTEGER NOT NULL DEFAULT 0,
            nudge_19_sent INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, day)
        );
        """)

        # Goal: päivän tavoiteminuutit (käyttäjän asettama)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS opp_goal (
            chat_id INTEGER PRIMARY KEY,
            goal_minutes INTEGER,
            updated_ts TEXT NOT NULL
        );
        """)

        # Next steps: max 3 aktiivista (done=0)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS opp_next_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_ts TEXT NOT NULL,
            done_ts TEXT
        );
        """)

        # Blockers / reasons (selityspyyntöön vastaus + vapaa teksti)
        await self.db.execute("""
        CREATE TABLE IF NOT EXISTS opp_blockers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            category TEXT NOT NULL,  -- fatigue/unclear/motivation/anxiety/other
            detail TEXT
        );
        """)

    # ---------- Session tracking ----------

    async def start_session(self, chat_id: int, now: datetime, topic: Optional[str] = None) -> str:
        open_row = await self.db.fetchone(
            "SELECT id, start_ts FROM opp_sessions WHERE chat_id=? AND end_ts IS NULL ORDER BY id DESC LIMIT 1",
            (chat_id,),
        )
        if open_row:
            return "Sinulla on jo käynnissä oleva opparisessio. Lopeta se: /opp stop"

        await self.db.execute(
            "INSERT INTO opp_sessions(chat_id, start_ts, topic) VALUES (?, ?, ?)",
            (chat_id, now.isoformat(), topic),
        )
        await self._log_event(chat_id, now, "session_start", {"topic": topic})
        return "Opparisessio aloitettu. Lopeta: /opp stop"

    async def stop_session(self, chat_id: int, now: datetime) -> str:
        open_row = await self.db.fetchone(
            "SELECT id, start_ts FROM opp_sessions WHERE chat_id=? AND end_ts IS NULL ORDER BY id DESC LIMIT 1",
            (chat_id,),
        )
        if not open_row:
            return "Ei käynnissä olevaa opparisessiota. Aloita: /opp start"

        session_id = open_row["id"] if isinstance(open_row, dict) else open_row[0]
        start_ts = open_row["start_ts"] if isinstance(open_row, dict) else open_row[1]

        await self.db.execute(
            "UPDATE opp_sessions SET end_ts=? WHERE id=?",
            (now.isoformat(), session_id),
        )

        minutes = self._minutes_between(datetime.fromisoformat(start_ts), now)
        await self._log_event(chat_id, now, "session_end", {"minutes": minutes})
        return f"Opparisessio lopetettu. Kesto: {minutes} min"

    async def minutes_today(self, chat_id: int, today: date) -> int:
        day_start = datetime.combine(today, time(0, 0, 0))
        day_end = day_start + timedelta(days=1)

        # Sum completed sessions overlapping today
        rows = await self.db.fetchall(
            """
            SELECT start_ts, end_ts FROM opp_sessions
            WHERE chat_id=?
              AND start_ts < ?
              AND (end_ts IS NULL OR end_ts > ?)
            """,
            (chat_id, day_end.isoformat(), day_start.isoformat()),
        )

        total = 0
        now = datetime.now()
        for r in rows or []:
            start_ts = r["start_ts"] if isinstance(r, dict) else r[0]
            end_ts = r["end_ts"] if isinstance(r, dict) else r[1]
            s = datetime.fromisoformat(start_ts)
            e = datetime.fromisoformat(end_ts) if end_ts else now
            # clamp to today
            s2 = max(s, day_start)
            e2 = min(e, day_end)
            total += max(0, self._minutes_between(s2, e2))
        return total

    async def started_today(self, chat_id: int, today: date) -> Tuple[bool, Optional[str]]:
        day_start = datetime.combine(today, time(0, 0, 0))
        day_end = day_start + timedelta(days=1)
        row = await self.db.fetchone(
            """
            SELECT start_ts FROM opp_sessions
            WHERE chat_id=? AND start_ts >= ? AND start_ts < ?
            ORDER BY start_ts ASC LIMIT 1
            """,
            (chat_id, day_start.isoformat(), day_end.isoformat()),
        )
        if not row:
            return False, None
        ts = row["start_ts"] if isinstance(row, dict) else row[0]
        return True, ts

    async def get_open_session(self, chat_id: int) -> Tuple[bool, Optional[str]]:
        row = await self.db.fetchone(
            "SELECT start_ts FROM opp_sessions WHERE chat_id=? AND end_ts IS NULL ORDER BY id DESC LIMIT 1",
            (chat_id,),
        )
        if not row:
            return False, None
        ts = row["start_ts"] if isinstance(row, dict) else row[0]
        return True, ts

    # ---------- Goal ----------

    async def set_goal(self, chat_id: int, now: datetime, minutes: int) -> str:
        minutes = max(1, min(minutes, 1440))
        await self.db.execute(
            """
            INSERT INTO opp_goal(chat_id, goal_minutes, updated_ts)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET goal_minutes=excluded.goal_minutes, updated_ts=excluded.updated_ts
            """,
            (chat_id, minutes, now.isoformat()),
        )
        await self._log_event(chat_id, now, "goal_set", {"goal_minutes": minutes})
        return f"Päivän tavoite asetettu: {minutes} min."

    async def get_goal(self, chat_id: int) -> Optional[int]:
        row = await self.db.fetchone("SELECT goal_minutes FROM opp_goal WHERE chat_id=?", (chat_id,))
        if not row:
            return None
        return row["goal_minutes"] if isinstance(row, dict) else row[0]

    # ---------- Next steps (max 3 active) ----------

    async def add_step(self, chat_id: int, now: datetime, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Anna askeleelle teksti. Esim: /opp step add Kirjoita johdannon ranskalaiset viivat"

        active = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM opp_next_steps WHERE chat_id=? AND done=0",
            (chat_id,),
        )
        c = active["c"] if isinstance(active, dict) else active[0]
        if c >= 3:
            return "Sinulla on jo 3 aktiivista 'Seuraava askel' -kohtaa. Merkitse joku valmiiksi: /opp step done <id>"

        await self.db.execute(
            "INSERT INTO opp_next_steps(chat_id, text, done, created_ts) VALUES (?, ?, 0, ?)",
            (chat_id, text, now.isoformat()),
        )
        await self._log_event(chat_id, now, "step_add", {"text": text})
        return "Lisätty seuraava askel."

    async def list_steps(self, chat_id: int) -> List[Tuple[int, str, bool]]:
        rows = await self.db.fetchall(
            "SELECT id, text, done FROM opp_next_steps WHERE chat_id=? ORDER BY done ASC, id ASC LIMIT 10",
            (chat_id,),
        )
        out = []
        for r in rows or []:
            _id = r["id"] if isinstance(r, dict) else r[0]
            text = r["text"] if isinstance(r, dict) else r[1]
            done = (r["done"] if isinstance(r, dict) else r[2]) == 1
            out.append((_id, text, done))
        return out

    async def done_step(self, chat_id: int, now: datetime, step_id: int) -> str:
        row = await self.db.fetchone(
            "SELECT id, done FROM opp_next_steps WHERE chat_id=? AND id=?",
            (chat_id, step_id),
        )
        if not row:
            return "Tuota askelta ei löytynyt."
        done = (row["done"] if isinstance(row, dict) else row[1]) == 1
        if done:
            return "Tuo askel on jo merkitty valmiiksi."

        await self.db.execute(
            "UPDATE opp_next_steps SET done=1, done_ts=? WHERE chat_id=? AND id=?",
            (now.isoformat(), chat_id, step_id),
        )
        await self._log_event(chat_id, now, "step_done", {"id": step_id})
        return "Merkitty valmiiksi."

    # ---------- Blocker + diagnosis ----------

    async def record_blocker(self, chat_id: int, now: datetime, category: str, detail: Optional[str]) -> str:
        category = category.strip().lower()
        if category not in {"fatigue", "unclear", "motivation", "anxiety", "other"}:
            category = "other"

        detail = (detail or "").strip() or None
        await self.db.execute(
            "INSERT INTO opp_blockers(chat_id, ts, category, detail) VALUES (?, ?, ?, ?)",
            (chat_id, now.isoformat(), category, detail),
        )
        await self._log_event(chat_id, now, "blocker", {"category": category, "detail": detail})
        suggestion = self._diagnose(category)
        return f"Kirjattu. Ehdotus (15 min): {suggestion}"

    def _diagnose(self, category: str) -> str:
        if category == "fatigue":
            return "Avaa oppari ja tee vain yksi kevyt asia: otsikot + 3 ranskalaista viivaa seuraavaan kappaleeseen."
        if category == "unclear":
            return "Kirjoita ylös ‘Seuraava askel’ yhtenä lauseena ja tee se heti 15 min. Esim: /opp step add ..."
        if category == "motivation":
            return "Sovi minimi: 15 min ‘paska versio’. Ei viimeistelyä, vain raakatekstiä."
        if category == "anxiety":
            return "Aseta ajastin 15 min ja tee ‘rumin versio’ — tarkoitus on tuottaa, ei arvioida."
        return "Valitse pienin mahdollinen tehtävä ja tee se 15 min. Jos kerrot ‘mikä?’, teen siitä mikroaskeleen."

    # ---------- Weekly summary & streak ----------

    async def weekly_summary(self, chat_id: int, today: date) -> str:
        # last 7 days including today
        lines = []
        total = 0
        days_15 = 0
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            m = await self.minutes_today(chat_id, d)
            total += m
            if m >= 15:
                days_15 += 1
            lines.append(f"{d.isoformat()}: {m} min")
        return "Viikkokooste (7 pv):\n" + "\n".join(lines) + f"\n\nYhteensä: {total} min | Päiviä ≥15 min: {days_15}"

    async def streak_15min(self, chat_id: int, today: date) -> int:
        # count consecutive days backwards where minutes>=15
        streak = 0
        for i in range(0, 365):  # safety cap
            d = today - timedelta(days=i)
            m = await self.minutes_today(chat_id, d)
            if m >= 15:
                streak += 1
            else:
                break
        return streak

    # ---------- Status ----------

    async def get_status(self, chat_id: int, now: datetime) -> OppStatus:
        td = now.date()
        started, start_ts = await self.started_today(chat_id, td)
        minutes = await self.minutes_today(chat_id, td)
        open_sess, open_ts = await self.get_open_session(chat_id)
        goal = await self.get_goal(chat_id)
        steps = await self.list_steps(chat_id)
        streak = await self.streak_15min(chat_id, td)
        return OppStatus(
            today_started=started,
            today_start_ts=start_ts,
            today_minutes=minutes,
            open_session=open_sess,
            open_session_started_ts=open_ts,
            goal_minutes=goal,
            next_steps=steps,
            streak_days_15min=streak,
        )

    # ---------- Reminder checks (scheduler later; manual now) ----------

    async def evaluate_reminders(self, chat_id: int, now: datetime) -> Optional[str]:
        """
        Palauttaa viestin jos pitäisi lähettää, muuten None.
        Rules:
          - 18:00 -> reminder if NOT started today (once/day)
          - 19:00 -> nudge/explanation if STILL NOT started today (once/day)
        """
        td = now.date()
        day = td.isoformat()
        await self._ensure_daily_state(chat_id, day)

        started, _ = await self.started_today(chat_id, td)

        st = await self.db.fetchone(
            "SELECT reminder_18_sent, nudge_19_sent FROM opp_daily_state WHERE chat_id=? AND day=?",
            (chat_id, day),
        )
        reminder_18_sent = (st["reminder_18_sent"] if isinstance(st, dict) else st[0]) == 1
        nudge_19_sent = (st["nudge_19_sent"] if isinstance(st, dict) else st[1]) == 1

        # Determine which window we're in: caller can choose exact times; here we decide by hour.
        # You will likely call at exact 18:00 and 19:00 later. For manual: it reacts based on current time.
        if not started and now.time() >= time(18, 0) and now.time() < time(19, 0) and not reminder_18_sent:
            await self.db.execute(
                "UPDATE opp_daily_state SET reminder_18_sent=1 WHERE chat_id=? AND day=?",
                (chat_id, day),
            )
            return "Oppari on tänään vielä aloittamatta. Aloitetaanko nyt? /opp start"

        if not started and now.time() >= time(19, 0) and not nudge_19_sent:
            await self.db.execute(
                "UPDATE opp_daily_state SET nudge_19_sent=1 WHERE chat_id=? AND day=?",
                (chat_id, day),
            )
            return (
                "Huomaan että oppari ei ole vieläkään lähtenyt käyntiin. Mikä esti tänään?\n"
                "Vastaa yhdellä:\n"
                "1) väsymys\n"
                "2) epäselvä seuraava askel\n"
                "3) motivaatio\n"
                "4) ahdistus/perfektionismi\n"
                "5) muu, mikä?"
            )

        return None

    # ---------- Internals ----------

    async def _ensure_daily_state(self, chat_id: int, day: str) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO opp_daily_state(chat_id, day, reminder_18_sent, nudge_19_sent) VALUES (?, ?, 0, 0)",
            (chat_id, day),
        )

    async def _log_event(self, chat_id: int, now: datetime, typ: str, payload: Dict[str, Any]) -> None:
        # payload_json can be str(json.dumps(payload)) if you prefer; keeping simple as repr here
        await self.db.execute(
            "INSERT INTO events(ts, chat_id, agent_id, type, payload_json) VALUES (?, ?, ?, ?, ?)",
            (now.isoformat(), chat_id, AGENT_ID, typ, str(payload)),
        )

    @staticmethod
    def _minutes_between(a: datetime, b: datetime) -> int:
        delta = b - a
        return int(delta.total_seconds() // 60)

    async def update_step_text(self, chat_id: int, now: datetime, step_id: int, new_text: str) -> str:
        new_text = (new_text or "").strip()
        if not new_text:
            return "Uusi teksti ei voi olla tyhjä."

        row = await self.db.fetchone(
            "SELECT id FROM opp_next_steps WHERE chat_id=? AND id=?",
            (chat_id, step_id),
        )
        if not row:
            return "Tuota askelta ei löytynyt."

        await self.db.execute(
            "UPDATE opp_next_steps SET text=? WHERE chat_id=? AND id=?",
            (new_text, chat_id, step_id),
        )
        await self._log_event(chat_id, now, "step_edit", {"id": step_id, "text": new_text})
        return "Päivitetty."



    async def delete_step(self, chat_id: int, now: datetime, step_id: int) -> str:
        row = await self.db.fetchone(
            "SELECT id FROM opp_next_steps WHERE chat_id=? AND id=?",
            (chat_id, step_id),
        )
        if not row:
            return "Tuota askelta ei löytynyt."

        await self.db.execute(
            "DELETE FROM opp_next_steps WHERE chat_id=? AND id=?",
            (chat_id, step_id),
        )
        await self._log_event(chat_id, now, "step_delete", {"id": step_id})
        return "Poistettu."
