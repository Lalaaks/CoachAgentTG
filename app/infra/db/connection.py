from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence


@dataclass
class Database:
    db_path: str

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute(sql, params)
            await conn.commit()

    async def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.executemany(sql, seq_of_params)
            await conn.commit()

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[aiosqlite.Row]:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(sql, params)
            return await cur.fetchone()

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(sql, params)
            rows = await cur.fetchall()
            return list(rows)

    async def executescript(self, script: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.executescript(script)
            await conn.commit()
