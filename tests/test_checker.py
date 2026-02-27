import httpx
import pytest
import respx

from smb_pinger.checker import check_site
from smb_pinger.models import CheckResult


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


@pytest.mark.asyncio
class TestCheckSite:
    @respx.mock
    async def test_200_returns_up(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(return_value=httpx.Response(200))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.UP
        assert outcome.status_code == 200
        assert outcome.response_time_ms is not None
        assert outcome.error is None

    @respx.mock
    async def test_500_returns_down(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(return_value=httpx.Response(500))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.DOWN
        assert outcome.status_code == 500
        assert outcome.error == "HTTP 500"

    @respx.mock
    async def test_403_with_cf_ray_returns_challenge(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(403, headers={"cf-ray": "abc123"})
        )
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.CHALLENGE_PAGE
        assert outcome.status_code == 403

    @respx.mock
    async def test_403_without_cf_ray_returns_down(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(return_value=httpx.Response(403))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.DOWN
        assert outcome.status_code == 403

    @respx.mock
    async def test_timeout_returns_timeout(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(side_effect=httpx.ReadTimeout("timeout"))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.TIMEOUT
        assert outcome.status_code is None
        assert "timed out" in (outcome.error or "").lower()

    @respx.mock
    async def test_dns_error_returns_dns_error(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(
            side_effect=OSError("Name or service not known")
        )
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.DNS_ERROR

    @respx.mock
    async def test_ssl_error_returns_ssl_error(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(
            side_effect=OSError("SSL: CERTIFICATE_VERIFY_FAILED")
        )
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.SSL_ERROR

    @respx.mock
    async def test_connection_error_returns_down(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.DOWN

    @respx.mock
    async def test_too_many_redirects(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(
            side_effect=httpx.TooManyRedirects("Too many redirects")
        )
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.REDIRECT_LOOP

    @respx.mock
    async def test_301_followed_to_200_returns_up(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(return_value=httpx.Response(200))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.UP

    @respx.mock
    async def test_404_returns_down(self, client: httpx.AsyncClient) -> None:
        respx.get("https://example.com").mock(return_value=httpx.Response(404))
        outcome = await check_site("https://example.com", client)
        assert outcome.result == CheckResult.DOWN
        assert outcome.status_code == 404
