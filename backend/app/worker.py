import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from arq import cron, run_worker
from arq.connections import RedisSettings

from .config import settings
from .jobs import store
from .pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("worker")


async def startup(ctx):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(store.open)


async def shutdown(ctx):
    await asyncio.to_thread(store.close)


async def process_job(ctx, job_id: str, ext: str, language: str, script_mode: str):
    src: Path = settings.jobs_dir / job_id / "work" / f"source{ext}"
    await asyncio.to_thread(run_pipeline, job_id, src, ext, language, script_mode, store)


def _cleanup():
    for jid in store.stuck_ids(settings.stuck_job_minutes):
        store.update(jid, status="failed", stage="failed",
                     error="Processing took too long and was stopped.")
    for jid in store.expired_ids(settings.job_ttl_minutes):
        shutil.rmtree(settings.jobs_dir / jid, ignore_errors=True)
        store.remove(jid)
    cutoff = time.time() - 7 * 86400
    for f in settings.cache_dir.glob("*.mp3"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)


async def cleanup(ctx):
    await asyncio.to_thread(_cleanup)


class WorkerSettings:
    functions = [process_job]
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [cron(cleanup, minute=set(range(0, 60, 5)), run_at_startup=True)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.job_workers
    job_timeout = settings.job_timeout_seconds
    max_tries = 1
    keep_result = 0
    handle_signals = os.name != "nt"   # arq's signal handlers don't work on Windows


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())   # needed on Python 3.14
    run_worker(WorkerSettings)