import asyncio

from apscheduler.schedulers.blocking import BlockingScheduler

from .runner import run_sync


def sync_source(source: str) -> None:
    asyncio.run(run_sync(source=source))


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(sync_source, "interval", hours=2, args=["openai"], id="news")
    scheduler.add_job(sync_source, "cron", hour=2, args=["sec"], id="sec-daily")
    scheduler.start()


if __name__ == "__main__":
    main()
