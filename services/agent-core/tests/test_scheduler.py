import unittest
from unittest.mock import AsyncMock

from agent_core.scheduler import Scheduler


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_interval_job_runs_and_is_reported(self) -> None:
        scheduler = Scheduler()
        job = AsyncMock()
        scheduler.add_interval_job("reminder_dispatch", job, interval_seconds=10)
        jobs = scheduler.get_next_runs()
        self.assertEqual(jobs[0]["name"], "reminder_dispatch")
        self.assertEqual(jobs[0]["interval_seconds"], 10)
        await scheduler._tick()
        job.assert_awaited_once()
        self.assertIsNotNone(scheduler.get_next_runs()[0]["last_run"])

    def test_interval_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            Scheduler().add_interval_job("invalid", AsyncMock(), interval_seconds=0)


if __name__ == "__main__":
    unittest.main()
