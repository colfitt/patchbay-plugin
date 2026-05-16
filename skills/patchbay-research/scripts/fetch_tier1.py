"""Tier-1 static fetch helper for `/patchbay:research`.

Satisfies **RESEARCH-02**: tier-1 static fetch attempted first for every URL,
returning a `{status, body, headers, elapsed_ms}` dict the caller classifies.

This module does NOT raise on non-2xx — it returns the status so the caller
(`log_failure.classify_reason`) can route to the correct failure category and
suggested escalation. The caller — never this module — decides whether to log
or to dispatch to a source-class parser.

SECURITY (T-03-01 — Information Disclosure / SSRF):
  - Refuses any URL whose scheme is not `http` or `https`. Prevents
    `file://`, `ftp://`, `gopher://`, etc. exfiltration vectors.
  - Refuses URLs whose hostname resolves to a private/loopback IP range
    (127/8, 10/8, 192.168/16, 172.16/12, ::1, fc00::/7). Uses the
    `ipaddress` stdlib for the check. Stops a malicious gear arg or
    redirect chain from coercing the fetcher into hitting localhost or
    internal infrastructure.

SECURITY (T-03-05 — Denial of Service):
  - 15-second hard timeout on the HTTP call. Oversized bodies are accepted
    (the user runs one URL at a time) but a slow-loris server cannot pin
    the fetcher indefinitely.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from typing import Optional
from urllib.parse import urlsplit

import requests

# Desktop Chrome UA, matched verbatim to the spike-findings reference.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

ALLOWED_SCHEMES = {"http", "https"}
TIMEOUT_SECONDS = 15


def _is_private_address(host: str) -> bool:
    """Return True if `host` resolves to a private/loopback/link-local address.

    Resolves every A/AAAA record via `socket.getaddrinfo`. If ANY resolved
    address is in a private range, the request is refused. This guards
    against DNS rebinding (one record public, one private) being abused
    to reach internal services.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # If DNS fails we let `requests` produce the canonical error later.
        return False

    for info in infos:
        sockaddr = info[4]
        raw_ip = sockaddr[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _assert_safe_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"Refusing to fetch {url}: scheme '{parts.scheme}' not allowed "
            f"(only http/https permitted)."
        )
    host = parts.hostname
    if not host:
        raise ValueError(f"Refusing to fetch {url}: missing hostname.")

    # Direct IP literals bypass DNS — still must pass the private-range check.
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(
                f"Refusing to fetch {url}: host resolves to private/loopback range."
            )
    except ValueError as exc:
        # If `host` was not a bare IP literal, fall through to DNS resolution.
        if "Refusing to fetch" in str(exc):
            raise

    if _is_private_address(host):
        raise ValueError(
            f"Refusing to fetch {url}: host resolves to private/loopback range."
        )
    return url


def fetch_tier1(url: str) -> dict:
    """Attempt a tier-1 static GET of `url`.

    Returns a dict with keys:
        status      — HTTP status code (int). 0 if the request never reached
                      a response (timeout, connection error).
        body        — Response body as str, or None on non-2xx / error.
        headers     — Response headers dict (empty on error).
        elapsed_ms  — Wall-clock duration of the call in milliseconds.
        exc         — Optional[Exception] — set on network-layer failures so
                      the caller can pass it to `classify_reason`.

    Does NOT raise on non-2xx. The caller classifies the result via
    `log_failure.classify_reason` and either dispatches to a source-class
    parser (on 2xx) or appends to `failures.log` (on failure).
    """
    _assert_safe_url(url)

    headers = {"User-Agent": UA}
    started = time.monotonic()
    exc: Optional[Exception] = None
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        body = response.text if response.ok else (response.text or None)
        return {
            "status": response.status_code,
            "body": body,
            "headers": dict(response.headers),
            "elapsed_ms": elapsed_ms,
            "exc": None,
        }
    except requests.Timeout as e:
        exc = e
    except requests.RequestException as e:
        exc = e

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "status": 0,
        "body": None,
        "headers": {},
        "elapsed_ms": elapsed_ms,
        "exc": exc,
    }
