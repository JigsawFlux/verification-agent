# tests/test_fetcher.py
import socket
from unittest.mock import MagicMock, patch

import pytest

import src.fetcher as fetcher
from src.fetcher import (
    ERR_BAD_CONTENT_TYPE,
    ERR_FETCH_ERROR,
    ERR_INVALID_URL,
    ERR_SSRF_BLOCKED,
    ERR_TIMEOUT,
    fetch_url,
    is_url,
    prepare_content,
)


# ─── is_url ──────────────────────────────────────────────────────────────────

class TestIsUrl:
    def test_http_url(self):
        assert is_url("http://example.com") is True

    def test_https_url(self):
        assert is_url("https://www.bbc.co.uk/news/article") is True

    def test_plain_text_is_not_url(self):
        assert is_url("URGENT: click now to verify your account") is False

    def test_ftp_not_allowed(self):
        assert is_url("ftp://files.example.com/data.csv") is False

    def test_empty_string(self):
        assert is_url("") is False

    def test_url_with_path_and_query(self):
        assert is_url("https://example.com/path?q=test&page=1") is True


# ─── SSRF blocking ───────────────────────────────────────────────────────────

class TestSsrfBlocking:
    def test_private_class_a(self):
        result = fetch_url("http://10.0.0.1/admin")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_private_class_b(self):
        result = fetch_url("http://172.16.5.1/config")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_private_class_c(self):
        result = fetch_url("http://192.168.1.100/page")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_loopback_ip(self):
        result = fetch_url("http://127.0.0.1/secret")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_localhost_hostname(self):
        result = fetch_url("http://localhost/admin")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_aws_metadata_endpoint(self):
        result = fetch_url("http://169.254.169.254/latest/meta-data/")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_hostname_resolving_to_private_ip(self):
        # Mock DNS so an innocent-looking hostname resolves to a private IP
        with patch.object(fetcher.socket, "getaddrinfo") as mock_dns:
            mock_dns.return_value = [(socket.AF_INET, None, None, None, ("10.0.0.1", 0))]
            result = fetch_url("http://evil-internal.example.com/page")
        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED

    def test_redirect_to_private_ip_blocked(self):
        # DNS mock: example.com → public IP, but 192.168.0.1 must resolve as itself
        def fake_getaddrinfo(host, port, *args, **kwargs):
            if host == "example.com":
                return [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]
            # For IP literals, return the IP unchanged so the SSRF check fires
            return [(socket.AF_INET, None, None, None, (host, 0))]

        redirect_resp = MagicMock()
        redirect_resp.is_redirect = True
        redirect_resp.status_code = 301
        redirect_resp.headers = {"Location": "http://192.168.0.1/internal"}
        redirect_resp.iter_content.return_value = iter([])

        with patch.object(fetcher.socket, "getaddrinfo", side_effect=fake_getaddrinfo), \
             patch.object(fetcher.requests, "get", return_value=redirect_resp):
            result = fetch_url("http://example.com/page")

        assert result.success is False
        assert result.error_reason == ERR_SSRF_BLOCKED


# ─── Invalid URLs ─────────────────────────────────────────────────────────────

class TestInvalidUrls:
    def test_no_scheme(self):
        result = fetch_url("www.example.com/page")
        assert result.success is False
        assert result.error_reason == ERR_INVALID_URL

    def test_ftp_scheme_rejected(self):
        result = fetch_url("ftp://files.example.com/data.csv")
        assert result.success is False
        assert result.error_reason == ERR_INVALID_URL

    def test_dns_failure_returns_invalid_url(self):
        with patch.object(fetcher.socket, "getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")):
            result = fetch_url("http://this-domain-does-not-exist-xyz.example/page")
        assert result.success is False
        assert result.error_reason == ERR_INVALID_URL


# ─── Content-type gate ───────────────────────────────────────────────────────

class TestContentTypeGate:
    def _make_mock_response(self, content_type: str) -> MagicMock:
        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {"Content-Type": content_type}
        resp.iter_content.return_value = iter([b"data"])
        return resp

    def _public_dns(self):
        return [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]

    def test_pdf_rejected(self):
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", return_value=self._make_mock_response("application/pdf")):
            result = fetch_url("http://example.com/doc.pdf")
        assert result.success is False
        assert result.error_reason == ERR_BAD_CONTENT_TYPE

    def test_json_api_rejected(self):
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", return_value=self._make_mock_response("application/json")):
            result = fetch_url("http://example.com/api/data")
        assert result.success is False
        assert result.error_reason == ERR_BAD_CONTENT_TYPE

    def test_html_with_charset_accepted(self):
        body = b"<html><body>Hello world</body></html>"
        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp.iter_content.return_value = iter([body])
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", return_value=resp):
            result = fetch_url("http://example.com/article")
        assert result.success is True
        assert "Hello world" in result.content

    def test_text_plain_accepted(self):
        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {"Content-Type": "text/plain"}
        resp.iter_content.return_value = iter([b"Some plain text content"])
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", return_value=resp):
            result = fetch_url("http://example.com/file.txt")
        assert result.success is True
        assert result.content == "Some plain text content"


# ─── Size cap ────────────────────────────────────────────────────────────────

class TestSizeCap:
    def test_large_response_is_truncated(self):
        # Generate a response larger than _MAX_CONTENT_BYTES (500 KB)
        chunk_size = 8192
        big_chunk = b"A" * chunk_size
        num_chunks = (fetcher._MAX_CONTENT_BYTES // chunk_size) + 5

        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {"Content-Type": "text/plain"}
        resp.iter_content.return_value = iter([big_chunk] * num_chunks)

        public_dns = [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]
        with patch.object(fetcher.socket, "getaddrinfo", return_value=public_dns), \
             patch.object(fetcher.requests, "get", return_value=resp):
            result = fetch_url("http://example.com/huge")

        assert result.success is True
        assert result.truncated is True


# ─── Error paths ─────────────────────────────────────────────────────────────

class TestErrorPaths:
    def _public_dns(self):
        return [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]

    def test_timeout_returns_err_timeout(self):
        import requests as req_lib
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", side_effect=req_lib.Timeout()):
            result = fetch_url("http://example.com/slow")
        assert result.success is False
        assert result.error_reason == ERR_TIMEOUT

    def test_connection_error_returns_err_fetch(self):
        import requests as req_lib
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", side_effect=req_lib.ConnectionError()):
            result = fetch_url("http://example.com/gone")
        assert result.success is False
        assert result.error_reason == ERR_FETCH_ERROR

    def test_url_sanitized_strips_query_params(self):
        with patch.object(fetcher.socket, "getaddrinfo", return_value=self._public_dns()), \
             patch.object(fetcher.requests, "get", side_effect=fetcher.requests.Timeout()):
            result = fetch_url("http://example.com/page?token=SECRET&user=me")
        assert "SECRET" not in result.url_sanitized
        assert "token" not in result.url_sanitized


# ─── prepare_content passthrough ─────────────────────────────────────────────

class TestPrepareContent:
    def test_plain_text_returns_text_input_type(self):
        result = prepare_content("URGENT: click here to claim your prize")
        assert result.success is True
        assert result.input_type == "text"
        assert result.content == "URGENT: click here to claim your prize"

    def test_url_triggers_fetch(self):
        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {"Content-Type": "text/html"}
        resp.iter_content.return_value = iter([b"<html><body>Article text</body></html>"])
        public_dns = [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]
        with patch.object(fetcher.socket, "getaddrinfo", return_value=public_dns), \
             patch.object(fetcher.requests, "get", return_value=resp):
            result = prepare_content("http://example.com/article")
        assert result.input_type == "url"
        assert result.success is True
        assert "Article text" in result.content
