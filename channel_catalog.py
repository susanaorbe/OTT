#!/usr/bin/env python3
"""Filtra el catálogo CDN Live TV por estado y URL oficial de reproductor.

La API es la fuente de disponibilidad: se conservan los canales marcados como
online/live cuya URL pertenece al reproductor oficial. No se hace una petición
HTTP desde GitHub Actions para decidir si un canal aparece, porque esa prueba
puede fallar por restricciones de red aunque el canal siga online.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timezone

ALLOWED_PLAYER_HOSTS = {"cdnlivetv.tv", "www.cdnlivetv.tv"}
PLAYER_PATH = "/api/v1/channels/player/"


def channel_key(channel: dict[str, Any]) -> str:
    name = str(channel.get("name") or "").strip().casefold()
    code = str(channel.get("code") or "").strip().casefold()
    return f"{name}|{code}"


def valid_player_url(value: Any) -> bool:
    """Valida el reproductor oficial; `code=` vacío es válido en esta API."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
        query = parse_qs(parsed.query, keep_blank_values=True)
        required = ("name", "code", "user", "plan")
        if any(len(query.get(key, [])) != 1 for key in required):
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_PLAYER_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == PLAYER_PATH
            and not parsed.fragment
            and bool(query["name"][0].strip())
            and query["user"][0] == "cdnlivetv"
            and query["plan"][0] == "free"
        )
    except (TypeError, ValueError):
        return False


def filter_playable_channels(
    payload: dict[str, Any], cache_path: Path | None = None
) -> dict[str, Any]:
    """Devuelve canales online/live con URL oficial válida, sin sondeo HTTP.

    `cache_path` se conserva como argumento opcional por compatibilidad con
    versiones anteriores; ya no se usa para decidir la visibilidad del canal.
    """
    raw = payload.get("channels", [])
    if not isinstance(raw, list):
        raw = []

    playable: list[dict[str, Any]] = []
    excluded_offline = 0
    excluded_url = 0

    for channel in raw:
        if not isinstance(channel, dict) or not str(channel.get("name") or "").strip():
            excluded_url += 1
            continue
        status = str(channel.get("status") or "").strip().casefold()
        if status not in {"online", "live"}:
            excluded_offline += 1
            continue
        url = channel.get("url")
        if not valid_player_url(url):
            excluded_url += 1
            continue

        item = dict(channel)
        item["player_url"] = url.strip()
        item["playback_allowed"] = True
        item["player_check"] = "api_status_online_official_url"
        playable.append(item)

    playable.sort(key=lambda item: str(item.get("name") or "").casefold())
    checked_at = datetime.now(timezone.utc).isoformat()
    return {
        "total_channels": len(playable),
        "channels": playable,
        "catalog_check": {
            "source": "CDN Live TV API status and official player URL",
            "online_candidates": len(playable),
            "playable_channels": len(playable),
            "excluded_offline": excluded_offline,
            "excluded_invalid_player_url": excluded_url,
            "checked_at": checked_at,
            "note": (
                "Se incluyen los canales que la API marca online/live y que tienen "
                "una URL oficial válida. No se verifica la reproducción del vídeo."
            ),
        },
    }
