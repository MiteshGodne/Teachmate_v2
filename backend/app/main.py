import logging, re, shutil, threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .jobs import store
from .pipeline import run_pipeline
from .utils.audio_generator import VOICES
from .utils.file_validation import ALLOWED_EXTENSIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("teachmate")

executor = ThreadPoolExecutor(max_workers=settings.job_workers)
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SCRIPT_MODES = {"auto", "notes", "slide"}


def _cleaner():
    """Delete expired job folders and stale cached audio. Also cleans up after crashes/restarts."""
    while True:
        try:
            now = time.time()
            if settings.jobs_dir.exists():
                for d in settings.jobs_dir.iterdir():
                    job = store.get(d.name)
                    running = job and job["status"] in ("queued", "running")
                    if not running and now - d.stat().st_mtime > settings.job_ttl_minutes * 60:
                        shutil.rmtree(d, ignore_errors=True)
                        store.remove(d.name)
            if settings.cache_dir.exists():
                for f in settings.cache_dir.glob("*.mp3"):
                    if now - f.stat().st_mtime > 7 * 86400:
                        f.unlink(missing_ok=True)
        except Exception:
            log.exception("cleaner failed")
        time.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    for tool in ("soffice", "ffmpeg", "pdftoppm"):
        if not (settings.soffice_bin if tool == "soffice" and settings.soffice_bin else shutil.which(tool)):
            log.warning("Required binary missing: %s", tool)
    threading.Thread(target=_cleaner, daemon=True).start()
    yield
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="TeachMate API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _valid_id(job_id: str):
    if not JOB_ID_RE.match(job_id):          # also blocks path traversal
        raise HTTPException(404, "Job not found")


@app.get("/health")
def health():
    bins = {t: bool(shutil.which(t)) for t in ("soffice", "ffmpeg", "pdftoppm")}
    if settings.soffice_bin:
        bins["soffice"] = Path(settings.soffice_bin).exists()
    return {"ok": all(bins.values()), "binaries": bins, "active_jobs": store.active_count()}


@app.post("/api/jobs", status_code=202)
async def create_job(
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
    if store.active_count() >= settings.max_queue:
        raise HTTPException(429, "The server is busy. Please try again in a few minutes.")

    job_id = uuid.uuid4().hex
    work = settings.jobs_dir / job_id / "work"
    work.mkdir(parents=True)
    src = work / f"source{ext}"          # never use the client's filename on disk

    limit, size = settings.max_upload_mb * 1024 * 1024, 0
    try:
        with open(src, "wb") as out:
            while chunk := await file.read(1024 * 1024):   # stream; never hold the whole file in RAM
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File too large. Maximum is {settings.max_upload_mb} MB.")
                await run_in_threadpool(out.write, chunk)
    except BaseException:
        shutil.rmtree(work.parent, ignore_errors=True)
        raise

    store.create(job_id)
    executor.submit(run_pipeline, job_id, src, ext, language, script_mode, store)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    _valid_id(job_id)
    job = store.public(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired")
    return job


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
    shutil.rmtree(settings.jobs_dir / job_id, ignore_errors=True)
    store.remove(job_id)