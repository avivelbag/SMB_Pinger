from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: Path = Path("data/smb_pinger.db")

    # Pinger
    check_interval_minutes: int = 15
    concurrency_limit: int = 30
    timeout_seconds: int = 15
    max_redirects: int = 5
    user_agent: str = "SMBPinger/1.0 (uptime-monitor)"

    # Auth
    admin_password_hash: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_prefix": "SMB_PINGER_", "env_file": ".env"}
