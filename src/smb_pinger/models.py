from dataclasses import dataclass
from enum import StrEnum


class CheckResult(StrEnum):
    UP = "up"
    DOWN = "down"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    SSL_ERROR = "ssl_error"
    REDIRECT_LOOP = "redirect_loop"
    CHALLENGE_PAGE = "challenge_page"

    @property
    def is_up(self) -> bool:
        return self in (CheckResult.UP, CheckResult.CHALLENGE_PAGE)


@dataclass(frozen=True)
class Business:
    id: int
    name: str
    url: str
    normalized_url: str
    category: str | None
    address: str | None
    is_active: bool
    created_at: str


@dataclass(frozen=True)
class PingResult:
    id: int
    business_id: int
    checked_at: str
    cycle_id: str
    status_code: int | None
    response_time_ms: float | None
    is_up: bool
    result: str
    error: str | None


@dataclass(frozen=True)
class CheckOutcome:
    """Result of a single site check, before persistence."""

    result: CheckResult
    status_code: int | None
    response_time_ms: float | None
    error: str | None
