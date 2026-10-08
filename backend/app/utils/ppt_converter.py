import logging
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from ..config import settings
from ..errors import PipelineError

log = logging.getLogger(__name__)


def _kill_tree(proc: subprocess.Popen):
    """Kill the process AND its children (soffice spawns soffice.bin)."""
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    except ProcessLookupError:
        pass


def _run(cmd: list[str], timeout: int):
    kwargs = {"start_new_session": True} if os.name == "posix" else {}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    try:
        _, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.communicate()
        raise
    if proc.returncode != 0:
        log.error("%s failed (%s): %s", Path(cmd[0]).name, proc.returncode,
                  err.decode(errors="ignore")[-2000:])
        raise subprocess.CalledProcessError(proc.returncode, cmd)


def _soffice_bin() -> str:
    path = settings.soffice_bin or shutil.which("soffice") or shutil.which("libreoffice")
    if not path:
        raise PipelineError("The server is missing LibreOffice, so presentations can't be converted.")
    return path


def convert_with_soffice(src: Path, fmt: str, outdir: Path) -> Path:
    """fmt: 'pdf' or 'pptx'. Fresh profile per call so parallel jobs don't fight over the lock."""
    outdir.mkdir(parents=True, exist_ok=True)
    # Profile lives INSIDE the job's work folder, so job cleanup always removes it.
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_", dir=outdir.resolve().parent)).resolve()
    cmd = [
        _soffice_bin(), "--headless", "--norestore", "--nolockcheck",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to", fmt, "--outdir", str(outdir.resolve()), str(src.resolve()),
    ]
    try:
        _run(cmd, settings.soffice_timeout)
    except subprocess.TimeoutExpired:
        raise PipelineError("Converting the presentation took too long. Try a smaller file.")
    except subprocess.CalledProcessError:
        raise PipelineError("Could not open this presentation. It may be corrupt or protected.")
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    out = outdir / f"{src.stem}.{fmt}"
    if not out.exists():
        raise PipelineError("Conversion produced no output. The file may be unsupported.")
    return out


def pdf_to_images(pdf: Path, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("pdftoppm"):
        raise PipelineError("The server is missing poppler (pdftoppm).")
    try:
        # -scale-to caps the LONGEST side in pixels, whatever the page size
        _run(["pdftoppm", "-png", "-scale-to", "1600", str(pdf), str(outdir / "slide")],
             settings.soffice_timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise PipelineError("Could not render the slides to images.")
    images = sorted(outdir.glob("slide-*.png"))
    if not images:
        raise PipelineError("The presentation has no slides.")
    return images