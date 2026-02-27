import ipaddress
import socket
import urllib.parse

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fd00::/8"),
]


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    - Lowercase scheme and hostname (preserve path case per RFC 3986)
    - Default to https://
    - Strip www. prefix
    - Remove default ports (:80, :443)
    - Remove fragment and query params
    - Strip trailing slash from path
    """
    url = url.strip()
    if not url:
        return ""

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    scheme = "https"
    hostname = (parsed.hostname or "").lower()

    # Strip www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Remove default ports
    port = parsed.port
    netloc = hostname if port in (80, 443, None) else f"{hostname}:{port}"

    # Strip trailing slash, keep path otherwise
    path = parsed.path.rstrip("/")

    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))


def validate_url_safe(url: str) -> bool:
    """Reject URLs targeting internal/private IPs (SSRF protection)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(sockaddr[0])
            if any(addr in net for net in BLOCKED_NETWORKS):
                return False
    except (socket.gaierror, ValueError):
        return False
    return True
