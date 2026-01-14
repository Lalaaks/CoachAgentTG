from __future__ import annotations

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.infra.db.connection import Database
from app.infra.db.schema_version import apply_migrations
from app.domain.common.time import to_iso


from app.config import load_settings
from app.ui.telegram.handlers import admin, status, opp, schedule
from app.ui.telegram.handlers.tasks import router as tasks_router
from app.ui.telegram.main import main as telegram_main

async def main():
    config = load_settings()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    db = Database(config.db_path)
    await db.init(config.owner_telegram_id, config.tz)

    dp["db"] = db
    dp["config"] = config
    dp["bot"] = bot  # hyödyllinen job-runnereille, jos haluat lähettää viestejä

    # Routers
#    dp.include_router(begin.router)
#    dp.include_router(study.router)
#    dp.include_router(settings.router)
    dp.include_router(admin.router)
    dp.include_router(help.router)
    dp.include_router(status.router)
#    dp.include_router(reset.router)
#    dp.include_router(stats.router)
#    dp.include_router(agents.router)
    dp.include_router(opp.router)
    dp.include_router(schedule.router)
    dp.include_router(tasks_router)



    # Scheduler
    from app.infra.db.repo.scheduled_jobs_sqlite import ScheduledJobsRepo
    from app.infra.scheduler.loop import SchedulerLoop, JobRunner

    jobs_repo = ScheduledJobsRepo(db)
    runner = JobRunner()

    async def run_ping(job):
        print("JOB RUN:", job.job_id, job.job_type, job.payload)
        # myöhemmin esim:
        # await bot.send_message(chat_id=job.user_id, text=f"Ping: {job.payload}")

    runner.register("ping", run_ping)

    scheduler = SchedulerLoop(repo=jobs_repo, runner=runner)
    scheduler_task = asyncio.create_task(scheduler.run_forever())

    try:
        await dp.start_polling(bot)
    finally:
        # siisti alasajo
        scheduler.stop()
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        await bot.session.close()


    if __name__ == "__main__":
        asyncio.run(telegram_main())
