import logging
import shutil
from pathlib import Path

from .config import settings
from .errors import JobCancelled, PipelineError
from .jobs import JobStore
from .utils.audio_generator import generate_audio_files
from .utils.file_validation import validate_upload
from .utils.ppt_converter import convert_with_soffice, pdf_to_images
from .utils.ppt_parser import extract_pdf_content, extract_ppt_content, pick_script
from .utils.video_creator import build_video

log = logging.getLogger(__name__)


def _pair_slides_with_images(slides: list[dict], images: list[Path]):
    """LibreOffice may or may not render hidden slides. Handle both."""
    visible = [s for s in slides if not s["hidden"]]
    if len(images) == len(visible):
        return list(zip(images, visible))
    if len(images) == len(slides):
        return [(i, s) for i, s in zip(images, slides) if not s["hidden"]]
    raise PipelineError("Slide rendering didn't match the presentation's slide count.")


def run_pipeline(job_id: str, src: Path, ext: str, language: str, script_mode: str, store: JobStore):
    job_dir = src.parent.parent        # data/jobs/<id>/
    work = src.parent                  # data/jobs/<id>/work/
    out_dir = job_dir / "out"

    def report(stage: str, pct: float):
        # Called often, so it doubles as the cancel checkpoint.
        if store.is_cancelled(job_id):
            raise JobCancelled()
        store.update(job_id, stage=stage, progress=int(pct))

    try:
        log.info("job=%s started ext=%s lang=%s", job_id, ext, language)
        store.update(job_id, status="running")
        report("validating", 5)
        validate_upload(src, ext)

        if ext == ".pdf":
            report("parsing", 20)
            slides = extract_pdf_content(src)
            pdf = src
        else:
            report("converting", 12)
            pptx = src if ext == ".pptx" else convert_with_soffice(src, "pptx", work / "converted")
            report("parsing", 22)
            slides = extract_ppt_content(pptx)
            if not slides:
                raise PipelineError("This presentation has no slides.")
            if len(slides) > settings.max_slides:
                raise PipelineError(f"Too many slides ({len(slides)}). The limit is {settings.max_slides}.")
            report("rendering", 28)
            pdf = convert_with_soffice(pptx, "pdf", work / "pdf")

        if ext == ".pdf" and len(slides) > settings.max_slides:
            raise PipelineError(f"Too many pages ({len(slides)}). The limit is {settings.max_slides}.")

        report("rendering", 35)
        images = pdf_to_images(pdf, work / "slides")
        pairs = _pair_slides_with_images(slides, images)
        if not pairs:
            raise PipelineError("All slides are hidden, so there is nothing to render.")

        scripts = [pick_script(s, script_mode)[: settings.max_script_chars].strip() for _, s in pairs]
        if not any(scripts):
            raise PipelineError("No narration text found. Add speaker notes, or use a deck with real text "
                                "(scanned or image-only files can't be narrated).")
        if sum(len(s) for s in scripts) > settings.max_total_chars:
            raise PipelineError("This deck has too much text for one video. Try splitting it.")

        audios = generate_audio_files(scripts, language, report)
        video, srt, duration = build_video([i for i, _ in pairs], audios, scripts, work, out_dir, report)

        report("encoding", 95)             # last chance to honour a cancel
        store.update(job_id, status="done", stage="done", progress=100,
                     video_path=str(video), srt_path=str(srt) if srt else None,
                     slides=len(pairs), duration=round(duration, 1))
        log.info("job=%s done slides=%d duration=%.1fs", job_id, len(pairs), duration)
    except JobCancelled:
        log.info("job=%s cancelled", job_id)
        store.update(job_id, status="cancelled", stage="cancelled")
        shutil.rmtree(job_dir, ignore_errors=True)
    except PipelineError as e:
        log.warning("job=%s failed: %s", job_id, e)
        store.update(job_id, status="failed", stage="failed", error=str(e))
    except Exception:
        log.exception("job=%s crashed", job_id)
        store.update(job_id, status="failed", stage="failed", error="Something went wrong on our side.")
    finally:
        shutil.rmtree(work, ignore_errors=True)   # source file + intermediates are never kept