"""Append-only JSONL writer for `failures.log` and reason classification.

Satisfies **RESEARCH-03**: the locked nine-field schema
    {timestamp, url, tier_attempted, http_status, reason, reason_detail,
     suggested_escalation, last_attempted, retry_count}
is written exactly once per call, as a single JSON-encoded line.

`reason` ∈ cloudflare-block | bot-detected | js-required | rate-limited |
            paywall | 404 | timeout | other
`suggested_escalation` ∈ 2 | 3 | "either" | "manual-paste" | "skip"

SECURITY (T-03-03 — JSONL injection):
  Every line is the output of `json.dumps()` on a structured dict — never
  raw user input concatenated as a string. Newlines inside string fields
  are JSON-escaped by the encoder, preserving the one-entry-per-line
  invariant that downstream `--review-failures` parsing depends on.

SECURITY (T-03-04 — Path traversal):
  If a `gear_root` argument is provided, the resolved `failures_log_path`
  MUST live under `gear_root` (via `Path.resolve().is_relative_to()`).
  Refuses with `ValueError` if the path escapes — this stops a malicious
  gear arg containing `..` from coercing the writer into clobbering files
  outside the user's gear knowledge directory.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union

import requests

Escalation = Union[int, str]  # 2 | 3 | "either" | "manual-paste" | "skip"

_TIMEOUT_REASON = ("timeout", "either")
_CLOUDFLARE_MARKERS = ("Just a moment...", "Checking your browser")
_PAYWALL_MARKER = "subscribe to read"
_JS_REQUIRED_MARKER = "<noscript>"


def classify_reason(
    status: int,
    body: str,
    exc: Optional[Exception],
) -> Tuple[str, Escalation]:
    """Classify a tier-1 outcome into (reason, suggested_escalation).

    Order of checks matters — timeout exceptions short-circuit before any
    body inspection, and Cloudflare-marker checks run before generic 403.
    """
    if isinstance(exc, requests.Timeout):
        return _TIMEOUT_REASON

    body = body or ""
    body_lower = body.lower()

    if status == 403:
        if any(marker in body for marker in _CLOUDFLARE_MARKERS):
            return ("cloudflare-block", 2)
        if "captcha" in body_lower:
            return ("bot-detected", 3)

    if status == 429:
        return ("rate-limited", "skip")

    if status == 404:
        return ("404", "skip")

    if status == 402 or _PAYWALL_MARKER in body_lower:
        return ("paywall", "manual-paste")

    if status == 200 and _JS_REQUIRED_MARKER in body and len(body) < 5000:
        return ("js-required", 2)

    # Anything else that isn't a 2xx falls into "other".
    if status < 200 or status >= 300:
        return ("other", "either")

    # 2xx with no markers — caller shouldn't have called us, but classify safely.
    return ("other", "either")


def _validate_path_containment(
    failures_log_path: str,
    gear_root: Optional[str],
) -> Path:
    """Resolve `failures_log_path` and assert it lives under `gear_root`.

    Returns the resolved path. Raises ValueError if escape detected.
    """
    resolved = Path(failures_log_path).resolve()
    if gear_root is not None:
        gear_root_resolved = Path(gear_root).resolve()
        # Path.is_relative_to landed in 3.9; emulate for any older runtime.
        if hasattr(resolved, "is_relative_to"):
            contained = resolved.is_relative_to(gear_root_resolved)
        else:
            try:
                resolved.relative_to(gear_root_resolved)
                contained = True
            except ValueError:
                contained = False
        if not contained:
            raise ValueError(
                f"Refusing to write failures.log at {resolved}: path is outside "
                f"gear_root {gear_root_resolved}."
            )
    return resolved


def log_failure(
    failures_log_path: str,
    url: str,
    status: int,
    body: str,
    exc: Optional[Exception],
    gear_root: Optional[str] = None,
) -> None:
    """Append one JSONL entry to `failures_log_path`.

    All nine schema fields are populated. `tier_attempted` is always 1
    (this module owns the tier-1 path only). `retry_count` is always 1
    on first write — the `--review-failures` flow (Plan 05) bumps it on
    re-attempts.
    """
    resolved = _validate_path_containment(failures_log_path, gear_root)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    reason, suggested = classify_reason(status, body, exc)
    now = datetime.utcnow().isoformat() + "Z"

    body_snippet = (body or "")[:200]
    if exc is not None:
        reason_detail = f"Exception: {type(exc).__name__}: {exc}"
    else:
        reason_detail = f"Server returned {status}. Body snippet: {body_snippet}"

    entry = {
        "timestamp": now,
        "url": url,
        "tier_attempted": 1,
        "http_status": status,
        "reason": reason,
        "reason_detail": reason_detail,
        "suggested_escalation": suggested,
        "last_attempted": now,
        "retry_count": 1,
    }

    # `json.dumps` on a structured dict — never raw concat. T-03-03 mitigation.
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(resolved, "a", encoding="utf-8") as f:
        f.write(line)
