"""Exact local-debug static asset allowlist."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEBUG_ROOT = ROOT / "frontend" / "local_debug_page"
SHARED_UI_ROOT = ROOT / "frontend" / "browser_extension" / "shared"
FRONTEND_ASSET_ALLOWLIST = {
    "/": LOCAL_DEBUG_ROOT / "index.html",
    "/index.html": LOCAL_DEBUG_ROOT / "index.html",
    "/app.js": LOCAL_DEBUG_ROOT / "app.js",
    "/styles.css": LOCAL_DEBUG_ROOT / "styles.css",
    "/shared/render_analysis.js": SHARED_UI_ROOT / "render_analysis.js",
    "/shared/analysis_components.css": SHARED_UI_ROOT / "analysis_components.css",
}


def frontend_asset_for_path(request_path: object) -> Path | None:
    """Resolve only fixed loopback UI assets; never derive filesystem paths."""
    if type(request_path) is not str:
        return None
    return FRONTEND_ASSET_ALLOWLIST.get(request_path)
