import asyncio
import json
import logging
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .config import settings
from .jobs import store
from .utils.audio_generator import VOICES
from .utils.file_validation import ALLOWED_EXTENSIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("teachmate")

JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SCRIPT_MODES = {"auto", "notes", "slide"}
TERMINAL = {"done", "failed", "cancelled"}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi",
                  "es": "Spanish", "fr": "French", "de": "German"}


def _binaries() -> dict[str, bool]:
    soffice = bool(shutil.which("soffice") or shutil.which("libreoffice")
                   or (settings.soffice_bin and Path(settings.soffice_bin).exists()))
    return {"soffice": soffice, "ffmpeg": bool(shutil.which("ffmpeg")),
            "ffprobe": bool(shutil.which("ffprobe")), "pdftoppm": bool(shutil.which("pdftoppm"))}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    for name, ok in _binaries().items():
        if not ok:
            log.warning("Required binary missing: %s", name)
    await run_in_threadpool(store.open)
    app.state.queue = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.queue.aclose()
    await run_in_threadpool(store.close)


app = FastAPI(title="Teach-Mate API", lifespan=lifespan)


# Registered BEFORE the CORS middleware, so CORS wraps it and its error replies still get CORS headers.
@app.middleware("http")
async def reject_oversized_uploads(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/jobs":
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_upload_mb * 1024 * 1024 + 1_000_000:
            return JSONResponse({"detail": f"File too large. Maximum is {settings.max_upload_mb} MB."},
                                status_code=413)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _valid_id(job_id: str):
    if not JOB_ID_RE.match(job_id):          # also blocks path traversal
        raise HTTPException(404, "Job not found")


async def _rate_limit(request: Request, ip: str):
    redis = request.app.state.queue
    key = f"rl:jobs:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 3600)
    if count > settings.rate_limit_per_hour:
        ttl = max(await redis.ttl(key), 1)
        raise HTTPException(429, f"Too many uploads. Try again in about {ttl // 60 + 1} minutes.",
                            headers={"Retry-After": str(ttl)})


@app.get("/health")
async def health(request: Request):
    bins = _binaries()
    db_ok = await run_in_threadpool(store.ping)
    try:
        redis_ok = bool(await request.app.state.queue.ping())
    except Exception:
        redis_ok = False
    ok = all(bins.values()) and db_ok and redis_ok
    body = {"ok": ok, "binaries": bins, "database": db_ok, "redis": redis_ok}
    return JSONResponse(body, status_code=200 if ok else 503)


@app.get("/api/config")
def public_config():
    """Single source of truth for the UI, so frontend and backend limits can't drift apart."""
    return {
        "max_upload_mb": settings.max_upload_mb,
        "extensions": sorted(ALLOWED_EXTENSIONS),
        "languages": [[c, LANGUAGE_NAMES.get(c, c)] for c in VOICES],
    }


@app.post("/api/jobs", status_code=202)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("en"),
    script_mode: str = Form("auto"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if language not in VOICES:
        raise HTTPException(400, f"Unsupported language. Allowed: {', '.join(VOICES)}")
    if script_mode not in SCRIPT_MODES:
        raise HTTPException(400, "Invalid script_mode")

    ip = request.client.host if request.client else "unknown"
    await _rate_limit(request, ip)
    if await run_in_threadpool(store.active_count) >= settings.max_queue:
        raise HTTPException(429, "The server is busy. Please try again in a few minutes.")

    job_id = uuid.uuid4().hex
    work = settings.jobs_dir / job_id / "work"
    work.mkdir(parents=True)
    src = work / f"source{ext}"          # never use the client's filename on disk

    limit, size = settings.max_upload_mb * 1024 * 1024, 0
    try:
        with open(src, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File too large. Maximum is {settings.max_upload_mb} MB.")
                await run_in_threadpool(out.write, chunk)
    except BaseException:
        shutil.rmtree(work.parent, ignore_errors=True)
        raise

    await run_in_threadpool(store.create, job_id, ext, language, script_mode, ip)
    try:
        await request.app.state.queue.enqueue_job("process_job", job_id, ext, language, script_mode)
    except Exception:
        log.exception("job=%s could not be queued", job_id)
        await run_in_threadpool(store.update, job_id, status="failed", stage="failed",
                                error="The queue is unavailable. Please try again.")
        shutil.rmtree(work.parent, ignore_errors=True)
        raise HTTPException(503, "The queue is unavailable. Please try again shortly.")
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    _valid_id(job_id)
    job = store.public(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired")
    return job


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """Server-Sent Events: one open connection, the server pushes each change."""
    _valid_id(job_id)
    first = await run_in_threadpool(store.public, job_id)
    if not first:
        raise HTTPException(404, "Job not found or expired")

    async def stream():
        yield "retry: 3000\n\n"                      # browser reconnect delay (ms)
        current, last, quiet = first, None, 0
        while True:
            if current is None:
                yield "event: gone\ndata: {}\n\n"    # job was deleted while we watched
                return
            payload = json.dumps(current)
            if payload != last:
                yield f"data: {payload}\n\n"
                last, quiet = payload, 0
            else:
                quiet += 1
                if quiet % 15 == 0:
                    yield ": keepalive\n\n"          # stops proxies closing an idle connection
            if current["status"] in TERMINAL:
                return
            await asyncio.sleep(1)
            if await request.is_disconnected():
                return
            current = await run_in_threadpool(store.public, job_id)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _result_file(job_id: str, key: str) -> Path:
    _valid_id(job_id)
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired")
    if job["status"] != "done" or not job.get(key):
        raise HTTPException(409, "Result not ready")
    path = Path(job[key])
    if not path.exists():
        raise HTTPException(410, "Result has expired")
    return path


@app.get("/api/jobs/{job_id}/video")
def job_video(job_id: str, download: bool = False):
    path = _result_file(job_id, "video_path")
    return FileResponse(path, media_type="video/mp4", filename="lecture.mp4",
                        content_disposition_type="attachment" if download else "inline")


@app.get("/api/jobs/{job_id}/subtitles")
def job_subtitles(job_id: str):
    path = _result_file(job_id, "srt_path")
    return FileResponse(path, media_type="application/x-subrip", filename="lecture.srt")


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    _valid_id(job_id)
    job = store.get(job_id)
    if not job:
        return
    if job["status"] in ("queued", "running"):
        store.request_cancel(job_id)     # the worker stops at its next checkpoint and cleans up
        return
    shutil.rmtree(settings.jobs_dir / job_id, ignore_errors=True)
    store.remove(job_id)