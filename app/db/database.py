class Database:
    def __init__(self, conn):
        self.conn = conn



    async def create_study_session(self, user_id: int, topic: str, goal: str, planned_minutes: int) -> int:


        cur = await self.conn.execute(
            """
            INSERT INTO study_sessions (user_id, started_at, topic, goal, planned_minutes, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (user_id, utc_now_iso(), topic, goal, planned_minutes),
        )
        await self.conn.commit()
        return int(cur.lastrowid)