import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import settings
from ..errors import PipelineError

log = logging.getLogger(__name__)
FPS = 5          # slides are static; 24fps is wasted work
END_PAD = 0.6    # breathing room after narration


def _run(cmd: list[str]):
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=settings.ffmpeg_timeout)
    except FileNotFoundError:
        raise PipelineError("The server is missing FFmpeg.")
    except subprocess.TimeoutExpired:
        raise PipelineError("Video encoding timed out.")
    except subprocess.CalledProcessError as e:
        log.error("ffmpeg failed: %s", e.stderr.decode(errors="ignore")[-2000:])
        raise PipelineError("Video encoding failed.")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()
    return float(out)


def make_segment(image: Path, audio: Path | None, out: Path) -> tuple[float, float]:
    W, H = settings.video_width, settings.video_height
    # Fixed even-sized canvas: fixes odd dimensions and mixed slide aspect ratios (4:3 vs 16:9)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,format=yuv420p")

    if audio:
        speech = probe_duration(audio)
        audio_in = ["-i", str(audio)]
    else:
        speech = 0.0
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    seg = (speech + END_PAD) if audio else settings.silent_slide_seconds

    _run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(image), *audio_in,
        "-t", f"{seg:.3f}", "-vf", vf, "-af", "aresample=44100,apad",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "23",
        "-r", str(FPS), "-g", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        str(out),
    ])
    return speech, seg


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _cues(text: str, start: float, dur: float):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text) if s.strip()]
    total = sum(len(s) for s in sentences) or 1
    t = start
    for s in sentences:
        d = dur * len(s) / total
        yield t, t + d, s
        t += d


def build_video(images, audios, scripts, work_dir: Path, out_dir: Path, report) -> tuple[Path, Path | None, float]:
    seg_dir = work_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    seg_paths = [seg_dir / f"seg_{i:04d}.mp4" for i in range(len(images))]

    with ThreadPoolExecutor(max_workers=settings.encode_workers) as pool:
        futures = [pool.submit(make_segment, img, aud, sp)
                   for img, aud, sp in zip(images, audios, seg_paths)]
        timings = []
        for n, f in enumerate(futures, 1):
            timings.append(f.result())
            report("encoding", 70 + 22 * n / len(futures))

    # Join with stream copy: no re-encode, near-instant
    list_file = work_dir / "concat.txt"
    list_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in seg_paths), encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / "lecture.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(list_file), "-c", "copy", "-movflags", "+faststart", str(video)])

    # Subtitles come almost for free: we already know every slide's audio duration
    srt_lines, cue_no, offset = [], 1, 0.0
    for script, (speech, seg) in zip(scripts, timings):
        if script and speech:
            for a, b, text in _cues(script, offset, speech):
                srt_lines += [str(cue_no), f"{_ts(a)} --> {_ts(b)}", text, ""]
                cue_no += 1
        offset += seg
    srt = None
    if srt_lines:
        srt = out_dir / "subtitles.srt"
        srt.write_text("\n".join(srt_lines), encoding="utf-8")

    return video, srt, offset