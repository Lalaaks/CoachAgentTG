import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_config
from app.db.db import Database
from app.handlers import begin, study, stats, settings, admin, help, status, reset, stats, agents, opp
from app.handlers.opp import handle_opp

async def main():
    config = load_config()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    db = Database(config.db_path)
    await db.init(config.owner_telegram_id, config.tz)

    # Provide db & config to handlers via middleware-ish simple injection:
    # aiogram v3 supports passing "kwargs" into handler via dp.update.outer_middleware,
    # but simplest: use dp["db"]=db and dp["config"]=config, then request them as args.
    dp["db"] = db
    dp["config"] = config

    # Include routers
    dp.include_router(begin.router)
    dp.include_router(study.router)
    dp.include_router(settings.router)
    dp.include_router(admin.router)
    dp.include_router(help.router)
    dp.include_router(status.router)
    dp.include_router(reset.router)
    dp.include_router(stats.router)
    dp.include_router(agents.router)
    dp.include_router(opp.router)

    # Start polling
    await dp.start_polling(bot, db=db, config=config)

if __name__ == "__main__":
    asyncio.run(main())
