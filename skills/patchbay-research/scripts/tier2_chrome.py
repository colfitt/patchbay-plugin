"""Tier-2 escalation via the Claude_in_Chrome MCP surface.

Plan 05 of `/patchbay:research`. Exposes two callables:

  - `precheck_chrome_extension(mcp_tools)` — REQUIRED before any tier-2
    network call. Invokes `list_connected_browsers`; if the result is empty,
    prints install instructions and returns False. The caller MUST honor the
    False return value by appending a resolution record with
    `outcome: "extension-missing"` and moving on — NEVER auto-falling-through
    to tier 3.
  - `fetch_tier2(url, mcp_tools)` — drives the real-browser fetch sequence:
    select_browser → tabs_context_mcp(createIfEmpty=True) → browser_batch
    (navigate, wait, screenshot) → javascript_tool(outerHTML). Returns the
    shared fetch-result shape used by every source class:
        {status, body, json, url_attempted, headers, elapsed_ms, exc, tier}

    The Phase-3 production smoke established that `get_page_text` strips
    structural cues (it returns plaintext), which the downstream HTML
    parsers (equipboard, reddit) cannot work with. `fetch_tier2` therefore
    extracts `document.documentElement.outerHTML` via `javascript_tool` so
    `body` is the raw, structured HTML BeautifulSoup expects.

DEPENDENCY INJECTION:
  Every MCP tool callable is passed through `mcp_tools` rather than imported
  from the MCP SDK directly. This makes the module testable AND keeps Plan
  05 free of MCP-SDK dependencies the rest of the codebase doesn't need.

SECURITY (T-03-28 — tier-2 RCE via shell metachars):
  This module makes NO `subprocess` calls. All work is dispatched through
  the MCP tool surface (which itself sanitizes argv). No shell invocation
  anywhere — shell mode is never enabled in this codepath.

SECURITY (T-03-33 — auto-fallback bypasses user consent):
  `precheck_chrome_extension` returns a boolean. It NEVER calls fetch_tier3
  or any other escalation path. The caller (`review_failures.review_failures`)
  is the single dispatcher of user consent; this module participates in tier
  2 only.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

# Install URL is a stable Chrome Web Store path — surfaced verbatim to the
# user when the extension is not connected.
_INSTALL_URL = (
    "https://chrome.google.com/webstore/detail/claude-in-chrome/"
    "<extension-id>"
)

_INSTALL_INSTRUCTIONS = (
    "Claude in Chrome extension is not connected. Install from "
    f"{_INSTALL_URL} and reload the page. Then re-run "
    "`/patchbay:research --review-failures` and choose `escalate to tier 2` "
    "again. (No automatic fallback to tier 3 — the user retains agency.)"
)


def precheck_chrome_extension(mcp_tools: Mapping[str, Callable]) -> bool:
    """Return True iff at least one browser is connected via the Chrome
    extension; False otherwise (and print install instructions on False).

    Calls `mcp_tools["list_connected_browsers"]()`. Any non-list / falsy /
    empty-list result is treated as "extension missing" and returns False.
    The MCP tool surface is trusted infrastructure (T-03-29 accepted), so
    a non-empty list is taken at face value.
    """
    list_browsers = mcp_tools.get("list_connected_browsers")
    if list_browsers is None:
        # No tool available at all. Treat as missing.
        print(_INSTALL_INSTRUCTIONS)
        return False

    try:
        browsers = list_browsers()
    except Exception as exc:  # noqa: BLE001 — MCP errors are runtime-only
        print(
            f"Could not query connected browsers ({type(exc).__name__}: {exc}). "
            f"Treating as extension-missing.\n{_INSTALL_INSTRUCTIONS}"
        )
        return False

    if not browsers:
        # extension-missing — print install instructions, do NOT proceed.
        print(_INSTALL_INSTRUCTIONS)
        return False

    return True


def fetch_tier2(
    url: str,
    mcp_tools: Mapping[str, Callable],
) -> dict:
    """Drive a real-browser fetch of `url` via the Claude_in_Chrome MCP.

    Sequence:
        1. `select_browser(deviceId)` against the first connected browser.
        2. `tabs_context_mcp(createIfEmpty=True)` → tab context (contains tabId).
        3. `browser_batch(actions=[navigate(url), wait(4), screenshot])`.
        4. `javascript_tool(code="document.documentElement.outerHTML")` →
           raw rendered HTML.

    Returns the shared fetch-result shape with `tier: 2`. Body is the RAW
    HTML string (NOT plaintext) — downstream parsers do
    `BeautifulSoup(body, "html.parser")` and rely on the structural cues
    (class names, anchors, JSON-LD `<script>` blocks) which a plaintext
    extractor like `get_page_text` strips. Status is 200 on success (the
    MCP doesn't expose HTTP status the same way a static GET does — we
    treat a returned body as 200 + page-rendered).

    The function does NOT catch exceptions — a runtime error in the MCP
    surface propagates to the caller, which records a `tier-error`
    resolution (NEVER an auto-fallback).
    """
    # Step 1: pick the first connected browser.
    browsers = mcp_tools["list_connected_browsers"]()
    if not browsers:
        # Belt-and-suspenders — precheck should have caught this. If it
        # didn't, raise to surface a `tier-error` resolution upstream.
        raise RuntimeError(
            "fetch_tier2 invoked but no browsers connected — precheck was "
            "skipped or the extension disconnected mid-flow."
        )
    device_id = _first_device_id(browsers)
    if device_id is None:
        raise RuntimeError(
            f"Connected browsers list does not expose a deviceId: {browsers!r}"
        )
    mcp_tools["select_browser"](deviceId=device_id)

    # Step 2: tab context.
    tab_ctx = mcp_tools["tabs_context_mcp"](createIfEmpty=True)
    tab_id = _extract_tab_id(tab_ctx)

    # Step 3: batch — navigate, wait, screenshot.
    actions = [
        {"action": "navigate", "url": url},
        {"action": "wait", "duration": 4},
        {"action": "screenshot"},
    ]
    mcp_tools["browser_batch"](actions=actions)

    # Step 4: pull raw HTML. The script is a fixed literal — it does NOT
    # interpolate the URL or any user input, so there is no JS-injection
    # surface here (T-03-28 stays mitigated).
    js_tool = mcp_tools.get("javascript_tool")
    if js_tool is None:
        raise RuntimeError(
            "fetch_tier2 requires `javascript_tool` in mcp_tools — the "
            "production fetch path uses outerHTML to return raw HTML rather "
            "than plaintext from get_page_text."
        )
    html_result = _invoke_javascript_outer_html(js_tool, tab_id)
    body = _coerce_body(html_result)

    return {
        "status": 200,
        "body": body,
        "json": None,
        "url_attempted": url,
        "headers": {},
        "elapsed_ms": 0,
        "exc": None,
        "tier": 2,
    }


# The fixed JS expression handed to `javascript_tool`. Literal — does NOT
# interpolate user input. Captured as a module constant so a future audit
# can grep for the exact string and the SKILL driver can re-use it.
_OUTER_HTML_EXPR = "document.documentElement.outerHTML"


def _invoke_javascript_outer_html(js_tool: Callable, tab_id: Any) -> Any:
    """Call the MCP `javascript_tool` permissively across known argument
    shapes. Different MCP server builds accept `code=`, `script=`, or
    `expression=`; we try them in order and fall back to a positional call.
    """
    last_exc: Optional[BaseException] = None
    for kwargs in (
        {"code": _OUTER_HTML_EXPR, "tabId": tab_id},
        {"code": _OUTER_HTML_EXPR},
        {"script": _OUTER_HTML_EXPR, "tabId": tab_id},
        {"expression": _OUTER_HTML_EXPR, "tabId": tab_id},
    ):
        try:
            return js_tool(**kwargs)
        except TypeError as exc:
            last_exc = exc
            continue
    # Final fall-through: positional. Surface any TypeError verbatim so the
    # caller's `tier-error` resolution is informative.
    if last_exc is not None:
        return js_tool(_OUTER_HTML_EXPR)
    return js_tool(_OUTER_HTML_EXPR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_device_id(browsers: Any) -> Optional[str]:
    """Pull the deviceId off the first browser entry. Permissive on shape."""
    if not browsers:
        return None
    if isinstance(browsers, list):
        first = browsers[0]
    else:
        first = browsers
    if isinstance(first, dict):
        return first.get("deviceId") or first.get("device_id") or first.get("id")
    return None


def _extract_tab_id(tab_ctx: Any) -> Optional[str]:
    """Pull a tabId from the tabs-context response. Permissive on shape."""
    if isinstance(tab_ctx, dict):
        return (
            tab_ctx.get("tabId")
            or tab_ctx.get("tab_id")
            or (tab_ctx.get("tab") or {}).get("id")
            or tab_ctx.get("activeTabId")
        )
    return None


def _coerce_body(page_result: Any) -> str:
    """Coerce a permissive MCP result into a single string body.

    Different MCP servers return raw strings, `{"result": "..."}`,
    `{"value": "..."}`, `{"text": "..."}`, `{"body": "..."}`, or
    `{"content": "..."}` — accept any of them. Returns empty string on a
    None / completely unrecognized shape rather than raising; the
    downstream parser will see an empty body and emit zero chunks, and
    the caller records a `tier-error` resolution if needed.
    """
    if isinstance(page_result, str):
        return page_result
    if isinstance(page_result, dict):
        for key in ("result", "value", "text", "body", "content"):
            v = page_result.get(key)
            if isinstance(v, str):
                return v
    return str(page_result or "")
