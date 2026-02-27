import logging
import time

import httpx

from smb_pinger.models import CheckOutcome, CheckResult

logger = logging.getLogger(__name__)


async def check_site(
    url: str,
    client: httpx.AsyncClient,
    request_timeout: float = 15.0,
    max_redirects: int = 5,
) -> CheckOutcome:
    """Perform an HTTP health check on a single URL and classify the result."""
    start = time.monotonic()
    try:
        response = await client.get(
            url,
            timeout=request_timeout,
            follow_redirects=True,
            extensions={"max_redirects": max_redirects},
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        if 200 <= response.status_code < 300:
            return CheckOutcome(
                result=CheckResult.UP,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                error=None,
            )

        # CloudFlare challenge detection
        if response.status_code == 403 and "cf-ray" in response.headers:
            return CheckOutcome(
                result=CheckResult.CHALLENGE_PAGE,
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                error=None,
            )

        return CheckOutcome(
            result=CheckResult.DOWN,
            status_code=response.status_code,
            response_time_ms=round(elapsed_ms, 2),
            error=f"HTTP {response.status_code}",
        )

    except httpx.TimeoutException:
        elapsed_ms = (time.monotonic() - start) * 1000
        return CheckOutcome(
            result=CheckResult.TIMEOUT,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error="Connection timed out",
        )

    except httpx.TooManyRedirects:
        elapsed_ms = (time.monotonic() - start) * 1000
        return CheckOutcome(
            result=CheckResult.REDIRECT_LOOP,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error=f"Too many redirects (>{max_redirects})",
        )

    except OSError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        error_str = str(exc)

        # DNS resolution failure
        if "Name or service not known" in error_str or "getaddrinfo" in error_str:
            return CheckOutcome(
                result=CheckResult.DNS_ERROR,
                status_code=None,
                response_time_ms=round(elapsed_ms, 2),
                error=f"DNS resolution failed: {error_str}",
            )

        # SSL errors
        if "SSL" in error_str or "certificate" in error_str.lower():
            return CheckOutcome(
                result=CheckResult.SSL_ERROR,
                status_code=None,
                response_time_ms=round(elapsed_ms, 2),
                error=f"SSL error: {error_str}",
            )

        return CheckOutcome(
            result=CheckResult.DOWN,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error=error_str,
        )

    except httpx.HTTPError as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        error_str = str(exc)

        if "SSL" in error_str or "certificate" in error_str.lower():
            return CheckOutcome(
                result=CheckResult.SSL_ERROR,
                status_code=None,
                response_time_ms=round(elapsed_ms, 2),
                error=f"SSL error: {error_str}",
            )

        return CheckOutcome(
            result=CheckResult.DOWN,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
            error=error_str,
        )
