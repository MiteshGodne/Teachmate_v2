from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    allowed_origins: str = "http://localhost:5173"   # set your real domain in production
    data_dir: Path = Path("data")
    database_url: str = "postgresql://teachmate:teachmate@localhost:5432/teachmate"
    redis_url: str = "redis://localhost:6379"

    # Limits
    max_upload_mb: int = 50
    max_slides: int = 100
    max_unzipped_mb: int = 300
    max_queue: int = 10               # queued + running jobs allowed at once
    max_script_chars: int = 3000      # per-slide narration cap
    max_total_chars: int = 60000      # whole deck (~1 hour of speech)
    rate_limit_per_hour: int = 10     # uploads per IP per hour

    # Worker
    job_workers: int = 2              # jobs one worker runs at once
    job_timeout_seconds: int = 1800
    stuck_job_minutes: int = 40       # a "running" job with no progress for this long is failed
    tts_workers: int = 4
    encode_workers: int = 2
    job_ttl_minutes: int = 60

    tts_provider: str = "edge"
    video_width: int = 1280
    video_height: int = 720
    silent_slide_seconds: float = 3.0

    soffice_bin: str = ""
    soffice_timeout: int = 180
    ffmpeg_timeout: int = 300

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache" / "audio"


settings = Settings()