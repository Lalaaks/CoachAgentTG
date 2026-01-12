from __future__ import annotations

import asyncio

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# optional dotenv support (safe if you have python-dotenv installed)
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from app.config import load_settings
from app.domain.common.time import to_iso
from app.domain.oppari.service import OppariService
from app.infra.clock.system_clock import SystemClock
from app.infra.db.connection import Database
from app.infra.db.schema_version import apply_migrations
from app.infra.db.repo.oppari_sqlite import OppariSqliteRepo
from app.infra.ids.uuid_gen import UuidGenerator

from app.ui.telegram.middlewares.auth import OwnerOnlyMiddleware
from app.ui.telegram.middlewares.di import DIMiddleware
from app.ui.telegram.handlers.admin import router as admin_router
from app.ui.telegram.handlers.oppari import router as oppari_router


async def main() -> None:
    if load_dotenv is not None:
        load_dotenv()

    settings = load_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    db = Database(settings.db_path)
    clock = SystemClock(settings.timezone)
    ids = UuidGenerator()

    repo_root = Path(__file__).resolve().parents[3]  # .../app/ui/telegram/main.py -> parents[3] = repo root
    migrations_dir = repo_root / "app" / "infra" / "db" / "migrations"
    print("DB_PATH:", settings.db_path)
    print("MIGRATIONS:", migrations_dir)
    
    await apply_migrations(
        db=db,
        migrations_dir=str(migrations_dir),
        now_iso=to_iso(clock.now()),
    )


    opp_repo = OppariSqliteRepo(db)
    opp_service = OppariService(repo=opp_repo, clock=clock, ids=ids)
    await opp_service.bootstrap()

    dp.message.middleware(OwnerOnlyMiddleware(settings.owner_telegram_id))
    dp.callback_query.middleware(OwnerOnlyMiddleware(settings.owner_telegram_id))

    dp.message.middleware(DIMiddleware(opp_service, db=db, clock=clock, timezone=settings.timezone))
    dp.callback_query.middleware(DIMiddleware(opp_service, db=db, clock=clock, timezone=settings.timezone))

    dp.include_router(admin_router)
    dp.include_router(oppari_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
