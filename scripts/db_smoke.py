import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # nousee CoachAgent -> AiogramPlusCoachAgent

import asyncio
from app.db.db import Database

async def main():
    db = Database("data/app.db")
    await db.init(owner_user_id=123, tz="Europe/Helsinki")
    sid = await db.create_study_session(123, "Testi", "Testitavoite", 30)
    active = await db.get_active_study_session(123)
    print("active:", active["id"], active["topic"])
    await db.complete_study_session(sid, 25, "Tein X", "ei", 4, 3, "Seuraava Y", "Opin Z")
    print("done")

asyncio.run(main())
