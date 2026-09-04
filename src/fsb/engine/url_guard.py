import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_outbound_url(url: str) -> tuple[bool, str]:
    if not url or not isinstance(url, str):
        return False, "url is empty"
    try:
        parsed = urlparse(url)
    except ValueError as e:
        return False, f"url parse error: {e}"
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return False, f"scheme '{scheme}' not allowed (http/https only)"
    host = parsed.hostname or ""
    if not host:
        return False, "url has no host"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        return False, f"host resolve failed: {e}"
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            logger.warning("url_guard blocked host=%s ip=%s", host, ip)
            return False, f"host resolves to blocked ip {ip} (loopback/private/link-local)"
    return True, "ok"


def resolve_pinned_url(url: str) -> tuple[str, str | None]:
    # Returns (pinned_url, original_host). pinned_url replaces the host with a
    # verified non-private IP so the actual connect cannot be rebinding DNS to
    # an internal address after validation. original_host kept for the Host header.
    # On any failure returns ("", None) — caller must reject.
    try:
        parsed = urlparse(url)
    except ValueError:
        return "", None
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return "", None
    host = parsed.hostname or ""
    if not host:
        return "", None
    # already an IP literal — validate directly
    try:
        ipaddress.ip_address(host)
        if _is_blocked_ip(host):
            logger.warning("url_guard blocked literal ip=%s", host)
            return "", None
        return url, host
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return "", None
    pinned_ip = None
    for info in infos:
        ip = info[4][0]
        if not _is_blocked_ip(ip):
            pinned_ip = ip
            break
    if pinned_ip is None:
        return "", None
    port = parsed.port
    if port:
        netloc = f"[{pinned_ip}]:{port}" if ":" in pinned_ip else f"{pinned_ip}:{port}"
    else:
        netloc = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
    pinned = parsed._replace(netloc=netloc).geturl()
    return pinned, host
