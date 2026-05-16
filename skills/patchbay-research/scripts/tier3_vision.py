"""Tier-3 escalation via the computer-use MCP + Claude vision.

Plan 05 of `/patchbay:research`. Exposes one callable:

  - `fetch_tier3(url, mcp_tools, prompt_user)` — opens `url` in Chrome via
    a system-level `open` invocation, screenshots the viewport, and returns
    the screenshot path for the SKILL driver to Read with the vision-capable
    Read tool. The driver is responsible for converting the screenshot
    into a `body` string before passing the fetch_result to `parse_to_chunks`.

SEQUENCE:
    1. `request_access(["Google Chrome"], reason=...)` — per-session permission.
    2. `subprocess.run(argv=["open", "-na", "Google Chrome", "--args",
       "--new-window", url], shell=False, check=False, timeout=30)` — argv-only
       handoff. URL is one argv element; nothing is interpolated into a string.
    3. Sleep ~5 seconds for the page to render (or honor `prompt_user`'s
       "ready" signal in interactive use).
    4. `screenshot()` → image path.
    5. Return `{status: 200, body: "", json: None, url_attempted: url,
       headers: {}, elapsed_ms: 0, exc: None, tier: 3, screenshot_path: <path>}`.

The actual vision-extracted body is filled in by the SKILL.md driver
after Reading the screenshot path. For testability, this function returns
`body == ""` and lets the driver enrich.

SECURITY (T-03-28 — RCE via crafted URL):
  - `subprocess.run` uses `shell=False` with an explicit argv list. The URL
    is one element of argv, NEVER interpolated into a string. Shell metachars
    in the URL cannot escape into the shell because there is no shell.
  - URL is re-validated via `urlparse` before invocation; non-http(s)
    schemes are rejected.

SECURITY (T-03-33 — auto-fallback bypasses user consent):
  This module is ONLY called when the user explicitly picked `tier-3`. It
  NEVER tries tier-2 or tier-0 paths internally.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _validate_url(url: str) -> None:
    """Raise ValueError on a non-http(s) URL — prevents `javascript:`,
    `file://`, etc. from being handed to `open`."""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"tier-3: malformed URL: {url!r}") from exc
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"tier-3: refusing non-http(s) URL: {url!r} (scheme={parsed.scheme!r})"
        )


def fetch_tier3(
    url: str,
    mcp_tools: Mapping[str, Callable],
    prompt_user: Optional[Callable[[Any], str]] = None,
) -> dict:
    """Open `url` in Chrome via system handoff, capture the viewport,
    and return the screenshot path for the SKILL driver to vision-extract.

    `prompt_user` is accepted but not strictly required — interactive uses
    may prompt the user to scroll or confirm the page rendered. The test
    suite injects a no-op stub.

    Returns the shared fetch-result shape with `tier: 3` and an additional
    `screenshot_path` key. `body` is empty by design — the driver fills it.
    """
    _validate_url(url)

    request_access = mcp_tools["request_access"]
    screenshot = mcp_tools["screenshot"]

    # 1. Per-session permission grant.
    request_access(["Google Chrome"], reason=f"tier-3 escalation for {url}")

    # 2. System-level navigation handoff. argv-only, shell=False, URL is one
    #    element (T-03-28 mitigation).
    argv = ["open", "-na", "Google Chrome", "--args", "--new-window", url]
    subprocess.run(argv, shell=False, check=False, timeout=30)

    # 3. Wait for the page to render. In interactive use the SKILL driver
    #    can re-prompt to scroll; here we sleep a fixed amount.
    time.sleep(5)

    # 4. Capture the viewport.
    shot = screenshot()
    screenshot_path = _extract_screenshot_path(shot)

    return {
        "status": 200,
        "body": "",  # Filled by SKILL driver after Read(screenshot_path).
        "json": None,
        "url_attempted": url,
        "headers": {},
        "elapsed_ms": 0,
        "exc": None,
        "tier": 3,
        "screenshot_path": screenshot_path,
    }


def _extract_screenshot_path(shot: Any) -> Optional[str]:
    """Pull a path string out of the screenshot return value. Permissive."""
    if isinstance(shot, str):
        return shot
    if isinstance(shot, dict):
        for key in ("path", "screenshot_path", "file", "filepath"):
            v = shot.get(key)
            if isinstance(v, str):
                return v
    return None
