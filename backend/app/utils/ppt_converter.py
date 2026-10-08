import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import settings
from ..errors import PipelineError


def _soffice_bin() -> str:
    path = settings.soffice_bin or shutil.which("soffice") or shutil.which("libreoffice")
    if not path:
        raise PipelineError("The server is missing LibreOffice, so presentations can't be converted.")
    return path


def convert_with_soffice(src: Path, fmt: str, outdir: Path) -> Path:
    """fmt: 'pdf' or 'pptx'. Uses a throwaway profile so parallel jobs don't fight over the lock."""
    outdir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    cmd = [
        _soffice_bin(), "--headless", "--norestore", "--nolockcheck",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to", fmt, "--outdir", str(outdir), str(src),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=settings.soffice_timeout)
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


def pdf_to_images(pdf: Path, outdir: Path, dpi: int = 110) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("pdftoppm"):
        raise PipelineError("The server is missing poppler (pdftoppm).")
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(outdir / "slide")],
            check=True, capture_output=True, timeout=settings.soffice_timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise PipelineError("Could not render the slides to images.")
    images = sorted(outdir.glob("slide-*.png"))  # pdftoppm zero-pads, so lexical order is correct
    if not images:
        raise PipelineError("The presentation has no slides.")
    return images