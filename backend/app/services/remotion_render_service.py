"""HTTP client for the local Remotion render sidecar (R3)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class RemotionRenderError(Exception):
    """Remotion sidecar failed or is unreachable."""


def remotion_service_configured() -> bool:
    return bool((settings.remotion_service_url or "").strip())


def remotion_service_base_url() -> str:
    return (settings.remotion_service_url or "").strip().rstrip("/")


def check_remotion_service_health(*, timeout_seconds: float = 3.0) -> dict[str, Any]:
    """Probe remotion-service GET /health. Never raises."""
    base = remotion_service_base_url()
    engine = (settings.blog_render_engine or "remotion").strip().lower()
    result: dict[str, Any] = {
        "engine": engine,
        "configured": bool(base),
        "url": base or None,
        "ok": False,
        "detail": None,
    }
    if engine != "remotion":
        result["ok"] = True
        result["detail"] = "remotion engine not selected"
        return result
    if not base:
        result["detail"] = "REMOTION_SERVICE_URL is empty"
        return result
    try:
        response = requests.get(f"{base}/health", timeout=timeout_seconds)
        if response.status_code >= 400:
            result["detail"] = f"HTTP {response.status_code}: {response.text[:300]}"
            return result
        payload = response.json() if response.content else {}
        result["ok"] = bool(payload.get("ok", True))
        result["detail"] = payload if result["ok"] else payload.get("detail", "unhealthy")
        return result
    except requests.RequestException as exc:
        result["detail"] = str(exc)
        return result


def render_blog_shorts_with_remotion(props: dict[str, Any], output_path: str | Path) -> Path:
    """
    POST props to remotion-service and write an MP4 to output_path.
    Raises RemotionRenderError on failure.
    """
    base = remotion_service_base_url()
    if not base:
        raise RemotionRenderError("REMOTION_SERVICE_URL is not configured.")

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = (settings.remotion_service_token or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    clip_id = props.get("blogClipId")
    board_count = len(props.get("boards") or [])
    started = time.perf_counter()
    logger.info(
        "Remotion render start clip=%s boards=%s out=%s timeout=%ss",
        clip_id,
        board_count,
        out,
        settings.remotion_render_timeout_seconds,
    )

    try:
        response = requests.post(
            f"{base}/render",
            headers=headers,
            json={
                "compositionId": "BlogShorts",
                "props": props,
                "outputPath": str(out),
            },
            timeout=settings.remotion_render_timeout_seconds,
        )
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - started
        logger.error("Remotion unreachable clip=%s after %.1fs: %s", clip_id, elapsed, exc)
        raise RemotionRenderError(f"Remotion service unreachable at {base}: {exc}") from exc

    elapsed = time.perf_counter() - started
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        logger.error(
            "Remotion render failed clip=%s status=%s after %.1fs: %s",
            clip_id,
            response.status_code,
            elapsed,
            detail,
        )
        raise RemotionRenderError(f"Remotion render failed ({response.status_code}): {detail}")

    if not out.is_file() or out.stat().st_size < 1:
        logger.error("Remotion success but missing output clip=%s path=%s", clip_id, out)
        raise RemotionRenderError(f"Remotion reported success but output missing: {out}")

    logger.info(
        "Remotion render ok clip=%s bytes=%s after %.1fs path=%s",
        clip_id,
        out.stat().st_size,
        elapsed,
        out,
    )
    return out


def ensure_remotion_or_http_error() -> None:
    if not remotion_service_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remotion 렌더가 설정되지 않았습니다. remotion-service를 실행하고 REMOTION_SERVICE_URL을 확인하세요.",
        )
