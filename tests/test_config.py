from pathlib import Path

from smb_pinger.config import Settings


class TestSettings:
    def test_defaults(self) -> None:
        s = Settings(admin_password_hash="test")
        assert s.db_path == Path("data/smb_pinger.db")
        assert s.check_interval_minutes == 15
        assert s.concurrency_limit == 30
        assert s.timeout_seconds == 15
        assert s.max_redirects == 5
        assert s.host == "127.0.0.1"
        assert s.port == 8000

    def test_env_prefix(self, monkeypatch: object) -> None:
        import os

        os.environ["SMB_PINGER_CHECK_INTERVAL_MINUTES"] = "5"
        os.environ["SMB_PINGER_ADMIN_PASSWORD_HASH"] = "abc"
        try:
            s = Settings()
            assert s.check_interval_minutes == 5
            assert s.admin_password_hash == "abc"
        finally:
            del os.environ["SMB_PINGER_CHECK_INTERVAL_MINUTES"]
            del os.environ["SMB_PINGER_ADMIN_PASSWORD_HASH"]
