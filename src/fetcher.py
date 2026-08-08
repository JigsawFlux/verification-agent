# src/fetcher.py
import ipaddress
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 8
_MAX_CONTENT_BYTES = 500_000   # cap download at 500 KB before parsing
_MAX_CONTENT_CHARS = 4_000     # chars forwarded to the LLM tools

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_CONTENT_TYPES = {"text/html", "text/plain"}
_MAX_REDIRECTS = 3

# RFC 1918 private ranges, loopback, link-local (incl. AWS metadata 169.254.x.x),
# IPv6 loopback and ULA ranges — all blocked to prevent SSRF
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),   # CGNAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Error reason sentinels
ERR_INVALID_URL = "invalid_url"
ERR_SSRF_BLOCKED = "ssrf_blocked"
ERR_BAD_CONTENT_TYPE = "bad_content_type"
ERR_TOO_LARGE = "too_large"
ERR_TIMEOUT = "timeout"
ERR_FETCH_ERROR = "fetch_error"


@dataclass
class FetchResult:
    success: bool
    content: str
    url_sanitized: str        # URL with query/fragment stripped — safe to log
    input_type: str           # "url" | "text"
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    truncated: bool = False
    error_reason: Optional[str] = None
    fetch_latency_ms: Optional[float] = None


def is_url(text: str) -> bool:
    try:
        parsed = urlparse(text.strip())
        return parsed.scheme in _ALLOWED_SCHEMES and bool(parsed.netloc)
    except Exception:
        return False


def _safe_url(url: str) -> str:
    """Strip query string and fragment for safe logging."""
    try:
        p = urlparse(url)
        return urlunparse(p._replace(query="", fragment=""))
    except Exception:
        return "[unparseable url]"


def _check_ssrf(hostname: str) -> Optional[str]:
    """
    Return an error reason if the hostname resolves to a blocked address range,
    or None if it is safe to connect.
    """
    if hostname.lower() in ("localhost",):
        return ERR_SSRF_BLOCKED

    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return ERR_INVALID_URL

    for addrinfo in addrs:
        ip_str = addrinfo[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        # Primary guard: is_global rejects loopback, link-local, private, reserved
        if not ip.is_global:
            return ERR_SSRF_BLOCKED
        # Belt-and-braces: explicit network list catches edge cases
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return ERR_SSRF_BLOCKED

    return None


def _validate_url(url: str) -> Optional[str]:
    """Return an error reason string if the URL is invalid or unsafe, else None."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return ERR_INVALID_URL

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return ERR_INVALID_URL

    hostname = parsed.hostname
    if not hostname:
        return ERR_INVALID_URL

    return _check_ssrf(hostname)


def _fetch_with_redirects(url: str) -> tuple[str, requests.Response]:
    """
    Follow redirects manually, re-running SSRF validation at each hop.
    Returns (final_url, response) or raises requests exceptions.
    Raises ValueError with ERR_SSRF_BLOCKED message if a redirect targets a blocked host.
    """
    headers = {"User-Agent": "Mozilla/5.0 (VerificationAgent/1.0)"}
    hops = 0
    current_url = url

    while True:
        resp = requests.get(
            current_url,
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
            stream=True,
            allow_redirects=False,
        )
        if not resp.is_redirect or hops >= _MAX_REDIRECTS:
            return current_url, resp

        next_url = resp.headers.get("Location", "").strip()
        if not next_url:
            return current_url, resp

        # Handle relative redirects
        if next_url.startswith("/"):
            p = urlparse(current_url)
            next_url = urlunparse(p._replace(path=next_url, query="", fragment=""))

        err = _validate_url(next_url)
        if err:
            raise ValueError(err)

        current_url = next_url
        hops += 1


def fetch_url(url: str) -> FetchResult:
    url_sanitized = _safe_url(url)

    err = _validate_url(url)
    if err:
        logger.warning("URL rejected: %s reason=%s", url_sanitized, err)
        return FetchResult(
            success=False, content="", url_sanitized=url_sanitized,
            input_type="url", error_reason=err,
        )

    t0 = time.monotonic()
    try:
        final_url, resp = _fetch_with_redirects(url)

        # Content-type check before reading body
        ct_header = resp.headers.get("Content-Type", "")
        ct_base = ct_header.split(";")[0].strip().lower()
        if ct_base not in _ALLOWED_CONTENT_TYPES:
            logger.warning("Rejected content-type=%s for %s", ct_base, url_sanitized)
            return FetchResult(
                success=False, content="", url_sanitized=url_sanitized,
                input_type="url", status_code=resp.status_code,
                content_type=ct_base, error_reason=ERR_BAD_CONTENT_TYPE,
                fetch_latency_ms=(time.monotonic() - t0) * 1000,
            )

        # Stream body, cap at _MAX_CONTENT_BYTES
        chunks = []
        total = 0
        truncated = False
        for chunk in resp.iter_content(chunk_size=8192):
            remaining = _MAX_CONTENT_BYTES - total
            if len(chunk) >= remaining:
                chunks.append(chunk[:remaining])
                truncated = True
                break
            chunks.append(chunk)
            total += len(chunk)

        raw_bytes = b"".join(chunks)
        latency_ms = (time.monotonic() - t0) * 1000

        soup = BeautifulSoup(raw_bytes, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))

        content = text[:_MAX_CONTENT_CHARS]
        truncated = truncated or len(text) > _MAX_CONTENT_CHARS

        return FetchResult(
            success=True, content=content, url_sanitized=url_sanitized,
            input_type="url", status_code=resp.status_code,
            content_type=ct_base, truncated=truncated,
            fetch_latency_ms=latency_ms,
        )

    except ValueError as exc:
        # Raised by _fetch_with_redirects when a redirect targets a blocked host
        err_reason = str(exc) if str(exc) in (ERR_SSRF_BLOCKED, ERR_INVALID_URL) else ERR_SSRF_BLOCKED
        return FetchResult(
            success=False, content="", url_sanitized=url_sanitized,
            input_type="url", error_reason=err_reason,
            fetch_latency_ms=(time.monotonic() - t0) * 1000,
        )
    except requests.Timeout:
        return FetchResult(
            success=False, content="", url_sanitized=url_sanitized,
            input_type="url", error_reason=ERR_TIMEOUT,
            fetch_latency_ms=(time.monotonic() - t0) * 1000,
        )
    except Exception as exc:
        logger.warning("Fetch error for %s: %s", url_sanitized, type(exc).__name__)
        return FetchResult(
            success=False, content="", url_sanitized=url_sanitized,
            input_type="url", error_reason=ERR_FETCH_ERROR,
            fetch_latency_ms=(time.monotonic() - t0) * 1000,
        )


def prepare_content(user_input: str) -> FetchResult:
    """
    Route user input to URL fetch or passthrough text.
    Always returns a FetchResult; callers check .success and .error_reason.
    """
    user_input = user_input.strip()
    if is_url(user_input):
        return fetch_url(user_input)
    return FetchResult(
        success=True, content=user_input, url_sanitized="",
        input_type="text", truncated=False,
    )
