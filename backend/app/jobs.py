from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    status           TEXT NOT NULL DEFAULT 'queued',   -- queued|running|done|failed|cancelled
    stage            TEXT NOT NULL DEFAULT 'queued',
    progress         INT  NOT NULL DEFAULT 0,
    error            TEXT,
    ext              TEXT,
    language         TEXT,
    script_mode      TEXT,
    client_ip        TEXT,
    video_path       TEXT,
    srt_path         TEXT,
    slides           INT,
    duration         DOUBLE PRECISION,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status, created_at);
"""

# Only these columns may be changed through update() (guards the f-string below)
UPDATABLE = {"status", "stage", "progress", "error", "video_path", "srt_path", "slides", "duration"}


class JobStore:
    """Job state in Postgres: survives restarts and is shared by the API and the worker."""

    def __init__(self, dsn: str):
        self.pool = ConnectionPool(dsn, min_size=1, max_size=10,
                                   kwargs={"row_factory": dict_row}, open=False)

    def open(self):
        self.pool.open(wait=True, timeout=30)
        with self.pool.connection() as conn:
            conn.execute(SCHEMA)

    def close(self):
        self.pool.close()

    def ping(self) -> bool:
        try:
            with self.pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def create(self, job_id: str, ext: str, language: str, script_mode: str, client_ip: str):
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, ext, language, script_mode, client_ip) VALUES (%s,%s,%s,%s,%s)",
                (job_id, ext, language, script_mode, client_ip),
            )

    def update(self, job_id: str, **fields):
        bad = set(fields) - UPDATABLE
        if bad:
            raise ValueError(f"Cannot update columns: {bad}")
        if not fields:
            return
        sets = ", ".join(f"{k} = %s" for k in fields)
        with self.pool.connection() as conn:
            conn.execute(f"UPDATE jobs SET {sets}, updated_at = now() WHERE id = %s",
                         (*fields.values(), job_id))

    def get(self, job_id: str) -> dict | None:
        with self.pool.connection() as conn:
            return conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()

    def public(self, job_id: str) -> dict | None:
        """What the browser is allowed to see (no server paths, no IPs)."""
        j = self.get(job_id)
        if not j:
            return None
        out = {
            "id": j["id"], "status": j["status"], "stage": j["stage"],
            "progress": j["progress"], "error": j["error"],
            "slides": j["slides"], "duration": j["duration"],
            "has_subtitles": bool(j["srt_path"]),
        }
        if j["status"] == "queued":
            out["queue_position"] = self.queue_position(job_id)
        return out

    def queue_position(self, job_id: str) -> int:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM jobs WHERE status = 'queued' "
                "AND created_at < (SELECT created_at FROM jobs WHERE id = %s)", (job_id,)
            ).fetchone()
        return row["n"] + 1

    def request_cancel(self, job_id: str) -> bool:
        with self.pool.connection() as conn:
            cur = conn.execute(
                "UPDATE jobs SET cancel_requested = TRUE, updated_at = now() "
                "WHERE id = %s AND status IN ('queued','running')", (job_id,))
            return cur.rowcount > 0

    def is_cancelled(self, job_id: str) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT cancel_requested FROM jobs WHERE id = %s", (job_id,)).fetchone()
        return row is None or row["cancel_requested"]     # deleted row counts as cancelled

    def remove(self, job_id: str):
        with self.pool.connection() as conn:
            conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))

    def active_count(self) -> int:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT count(*) AS n FROM jobs WHERE status IN ('queued','running')").fetchone()["n"]

    # --- used by the worker's cleanup task ---
    def stuck_ids(self, minutes: int) -> list[str]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs WHERE "
                "(status = 'running' AND updated_at < now() - make_interval(mins => %s::int)) OR "
                "(status = 'queued'  AND created_at < now() - interval '3 hours')", (minutes,)
            ).fetchall()
        return [r["id"] for r in rows]

    def expired_ids(self, minutes: int) -> list[str]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs WHERE status IN ('done','failed','cancelled') "
                "AND updated_at < now() - make_interval(mins => %s::int)", (minutes,)
            ).fetchall()
        return [r["id"] for r in rows]


from .config import settings  # noqa: E402

store = JobStore(settings.database_url)   