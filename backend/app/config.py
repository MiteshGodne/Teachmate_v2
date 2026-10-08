from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    allowed_origins: str = "http://localhost:5173,https://teachmate-web-app.vercel.app"
    data_dir: Path = Path("data")

    max_upload_mb: int = 50
    max_slides: int = 100
    max_unzipped_mb: int = 300
    max_queue: int = 10

    job_workers: int = 2        # concurrent jobs
    tts_workers: int = 4        # concurrent TTS calls per job
    encode_workers: int = 2     # concurrent ffmpeg segment encodes
    job_ttl_minutes: int = 60

    tts_provider: str = "edge"  # "edge" or "gtts"
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