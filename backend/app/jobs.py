import threading
import time


class JobStore:
    """In-memory job state. Phase 2 replaces this with Postgres/Redis.
    NOTE: run uvicorn with a single process until then (no --workers N)."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str):
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id, "status": "queued", "stage": "queued", "progress": 0,
                "error": None, "created_at": time.time(),
                "video_path": None, "srt_path": None, "slides": None, "duration": None,
            }

    def update(self, job_id: str, **fields):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            j = self._jobs.get(job_id)
            return dict(j) if j else None

    def public(self, job_id: str) -> dict | None:
        j = self.get(job_id)
        if not j:
            return None
        j["has_subtitles"] = bool(j.pop("srt_path"))
        j.pop("video_path")
        return j

    def remove(self, job_id: str):
        with self._lock:
            self._jobs.pop(job_id, None)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j["status"] in ("queued", "running"))


store = JobStore()