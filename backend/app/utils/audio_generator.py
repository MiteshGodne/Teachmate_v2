import asyncio
import hashlib
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from gtts import gTTS

from ..config import settings
from ..errors import PipelineError

log = logging.getLogger(__name__)

VOICES = {  # language code -> edge-tts voice
    "en": "en-US-AriaNeural", "hi": "hi-IN-SwaraNeural", "mr": "mr-IN-AarohiNeural",
    "es": "es-ES-ElviraNeural", "fr": "fr-FR-DeniseNeural", "de": "de-DE-KatjaNeural",
}


def _edge(text: str, lang: str, out: Path):
    import edge_tts

    async def run():
        await edge_tts.Communicate(text, VOICES[lang]).save(str(out))

    asyncio.run(run())  # fine: worker threads have no running loop


def _gtts(text: str, lang: str, out: Path):
    gTTS(text=text, lang=lang).save(str(out))


def _key(provider, lang: str, text: str) -> str:
    voice = VOICES[lang] if provider is _edge else "gtts"
    return hashlib.sha256(f"{provider.__name__}|{voice}|{lang}|{text}".encode()).hexdigest()


def synth_one(text: str, lang: str, retries: int = 3) -> Path | None:
    if not text.strip():
        return None
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    order = [_edge, _gtts] if settings.tts_provider == "edge" else [_gtts, _edge]
    last_err = None
    for provider in order:
        cached = settings.cache_dir / f"{_key(provider, lang, text)}.mp3"
        if cached.exists() and cached.stat().st_size > 0:
            return cached
        for attempt in range(retries):
            tmp = cached.with_name(f"{cached.stem}.{uuid.uuid4().hex}.tmp.mp3")
            try:
                provider(text, lang, tmp)
                if tmp.stat().st_size == 0:
                    raise RuntimeError("empty audio")
                tmp.replace(cached)
                return cached
            except Exception as e:
                last_err = e
                tmp.unlink(missing_ok=True)
                log.warning("TTS %s attempt %d failed: %s", provider.__name__, attempt + 1, e)
                time.sleep(0.5 * 2 ** attempt)
    raise PipelineError("Speech synthesis is temporarily unavailable. Please try again shortly.") from last_err


def generate_audio_files(scripts: list[str], lang: str, report) -> list[Path | None]:
    results: list[Path | None] = [None] * len(scripts)
    with ThreadPoolExecutor(max_workers=settings.tts_workers) as pool:
        futures = {pool.submit(synth_one, s, lang): i for i, s in enumerate(scripts)}
        try:
            for n, fut in enumerate(as_completed(futures), 1):
                results[futures[fut]] = fut.result()
                report("narrating", 40 + 30 * n / len(scripts))
        except Exception:
            for f in futures:
                f.cancel()      # don't keep synthesizing slides for a doomed job
            raise
    return results