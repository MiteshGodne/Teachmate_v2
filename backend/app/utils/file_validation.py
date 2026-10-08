import zipfile
from pathlib import Path

from ..config import settings
from ..errors import PipelineError

ALLOWED_EXTENSIONS = {".pptx", ".ppt", ".ppsx", ".odp", ".pdf"}
OLE_MAGIC = b"\xD0\xCF\x11\xE0"   # legacy .ppt AND encrypted .pptx
ZIP_MAGIC = b"PK\x03\x04"


def validate_upload(path: Path, ext: str) -> None:
    head = path.read_bytes()[:8] if path.stat().st_size else b""
    if not head:
        raise PipelineError("The uploaded file is empty.")

    if ext == ".pdf":
        if not head.startswith(b"%PDF"):
            raise PipelineError("This file is not a valid PDF.")
        return

    if ext == ".ppt":
        if not head.startswith(OLE_MAGIC):
            raise PipelineError("This file is not a valid .ppt presentation.")
        return

    # .pptx / .ppsx / .odp are ZIP containers
    if head.startswith(OLE_MAGIC):
        raise PipelineError("This presentation looks password-protected. Remove the password and try again.")
    if not head.startswith(ZIP_MAGIC):
        raise PipelineError("This file is not a valid presentation (corrupt or wrong extension).")

    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > 10_000:
                raise PipelineError("The presentation contains too many internal files.")
            if sum(i.file_size for i in infos) > settings.max_unzipped_mb * 1024 * 1024:
                raise PipelineError("The presentation is too large once unpacked.")
    except zipfile.BadZipFile:
        raise PipelineError("The presentation file is corrupt.")