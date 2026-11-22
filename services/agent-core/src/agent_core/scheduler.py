from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, time as dt_time, timedelta
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._interval_jobs: dict[str, dict[str, Any]] = {}
        self._running = False

    def add_daily_job(
        self,
        name: str,
        coro_factory: Callable[[], Any],
        run_at: dt_time = dt_time(3, 0),  # 3 AM UTC
    ) -> None:
        """Add a job that runs daily at specified time."""
        self._jobs[name] = {
            "coro_factory": coro_factory,
            "run_at": run_at,
            "last_run": None,
        }
        logger.info("Scheduled daily job '%s' at %s UTC", name, run_at)

    def add_interval_job(
        self, name: str, coro_factory: Callable[[], Any], interval_seconds: int
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds must be positive")
        self._interval_jobs[name] = {
            "coro_factory": coro_factory,
            "interval_seconds": interval_seconds,
            "next_run_monotonic": time.monotonic(),
            "last_run": None,
        }
        logger.info("Scheduled interval job '%s' every %d seconds", name, interval_seconds)

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info("Scheduler started with %d jobs", len(self._jobs))
        while self._running:
            await self._tick()
            await asyncio.sleep(5)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stopped")

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        current_time = now.timetz()

        for name, job in self._interval_jobs.items():
            if time.monotonic() < job["next_run_monotonic"]:
                continue
            job["next_run_monotonic"] = time.monotonic() + job["interval_seconds"]
            logger.info("Running scheduled interval job: %s", name)
            try:
                result = job["coro_factory"]()
                if asyncio.iscoroutine(result):
                    await result
                job["last_run"] = datetime.now(UTC)
            except Exception as error:
                logger.error("Interval job %s failed: %s", name, error)

        for name, job in self._jobs.items():
            run_at = job["run_at"]
            last_run = job["last_run"]

            # Check if it's time to run (within same minute)
            if (current_time.hour == run_at.hour and
                current_time.minute == run_at.minute and
                (last_run is None or last_run.date() < now.date())):

                logger.info("Running scheduled job: %s", name)
                job["last_run"] = now
                try:
                    coro = job["coro_factory"]()
                    if asyncio.iscoroutine(coro):
                        await coro
                    else:
                        # Run sync function in executor
                        await asyncio.get_event_loop().run_in_executor(None, coro)
                    logger.info("Job %s completed", name)
                except Exception as e:
                    logger.error("Job %s failed: %s", name, e)

    def get_next_runs(self) -> list[dict[str, Any]]:
        """Get next scheduled run times for all jobs."""
        now = datetime.now(UTC)
        result = []
        for name, job in self._jobs.items():
            run_at = job["run_at"]
            next_run = datetime.combine(now.date(), run_at, tzinfo=UTC)
            if next_run <= now:
                next_run = datetime.combine(
                    (now + timedelta(days=1)).date(), run_at, tzinfo=UTC
                )
            result.append({
                "name": name,
                "next_run": next_run.isoformat(),
                "last_run": job["last_run"].isoformat() if job["last_run"] else None,
            })
        monotonic_now = time.monotonic()
        for name, job in self._interval_jobs.items():
            next_run = now + timedelta(seconds=max(0, job["next_run_monotonic"] - monotonic_now))
            result.append({
                "name": name,
                "interval_seconds": job["interval_seconds"],
                "next_run": next_run.isoformat(),
                "last_run": job["last_run"].isoformat() if job["last_run"] else None,
            })
        return result


scheduler = Scheduler()
