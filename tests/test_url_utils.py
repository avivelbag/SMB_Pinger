from smb_pinger.url_utils import normalize_url, validate_url_safe


class TestNormalizeUrl:
    def test_adds_https_scheme(self) -> None:
        assert normalize_url("example.com") == "https://example.com"

    def test_converts_http_to_https(self) -> None:
        assert normalize_url("http://example.com") == "https://example.com"

    def test_strips_www(self) -> None:
        assert normalize_url("https://www.example.com") == "https://example.com"

    def test_lowercases_hostname(self) -> None:
        assert normalize_url("https://EXAMPLE.COM") == "https://example.com"

    def test_strips_trailing_slash(self) -> None:
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_preserves_path(self) -> None:
        assert normalize_url("https://example.com/about") == "https://example.com/about"

    def test_removes_default_port_80(self) -> None:
        assert normalize_url("http://example.com:80") == "https://example.com"

    def test_removes_default_port_443(self) -> None:
        assert normalize_url("https://example.com:443") == "https://example.com"

    def test_keeps_non_default_port(self) -> None:
        assert normalize_url("https://example.com:8080") == "https://example.com:8080"

    def test_removes_fragment(self) -> None:
        assert normalize_url("https://example.com#section") == "https://example.com"

    def test_removes_query_params(self) -> None:
        assert normalize_url("https://example.com?foo=bar") == "https://example.com"

    def test_empty_string(self) -> None:
        assert normalize_url("") == ""

    def test_strips_whitespace(self) -> None:
        assert normalize_url("  example.com  ") == "https://example.com"

    def test_complex_url(self) -> None:
        url = "http://www.Example.COM:80/about/?ref=google#contact"
        assert normalize_url(url) == "https://example.com/about"


class TestValidateUrlSafe:
    def test_rejects_non_http_scheme(self) -> None:
        assert validate_url_safe("ftp://example.com") is False
        assert validate_url_safe("file:///etc/passwd") is False

    def test_rejects_no_hostname(self) -> None:
        assert validate_url_safe("http://") is False

    def test_allows_public_url(self) -> None:
        # This will resolve DNS, so use a well-known public domain
        assert validate_url_safe("https://google.com") is True

    def test_rejects_localhost(self) -> None:
        assert validate_url_safe("http://127.0.0.1") is False

    def test_rejects_private_10(self) -> None:
        assert validate_url_safe("http://10.0.0.1") is False

    def test_rejects_private_172(self) -> None:
        assert validate_url_safe("http://172.16.0.1") is False

    def test_rejects_private_192(self) -> None:
        assert validate_url_safe("http://192.168.1.1") is False

    def test_rejects_metadata_endpoint(self) -> None:
        assert validate_url_safe("http://169.254.169.254") is False

    def test_rejects_unresolvable(self) -> None:
        url = "http://this-domain-definitely-does-not-exist-xyz.invalid"
        assert validate_url_safe(url) is False
