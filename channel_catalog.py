#!/usr/bin/env python3
"""Prepara el catálogo completo de canales de CDN Live TV.

No se filtra por país, estado, actividad ni emisión. Cada entrada con nombre
se conserva. Solo se marca como reproducible si contiene la URL HTTPS oficial
del reproductor; no se extraen streams ni se eluden restricciones.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

ALLOWED_PLAYER_HOSTS = {"cdnlivetv.tv", "www.cdnlivetv.tv"}
PLAYER_PATH = "/api/v1/channels/player/"


def channel_key(channel: dict[str, Any]) -> str:
    name = str(channel.get("name") or "").strip().casefold()
    code = str(channel.get("code") or "").strip().casefold()
    return f"{name}|{code}"


def valid_player_url(value: Any) -> bool:
    """Valida únicamente el enlace público al reproductor oficial de CDN."""
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
    payload: dict[str, Any], cache_path: Any = None
) -> dict[str, Any]:
    """Compatibilidad con el actualizador: devuelve todos los canales del catálogo."""
    if not isinstance(payload, dict):
        raise ValueError("La respuesta de CDN Live TV no es un objeto JSON")
    raw = payload.get("channels", [])
    if not isinstance(raw, list):
        raw = []

    channels: list[dict[str, Any]] = []
    playable = 0
    without_player = 0
    for channel in raw:
        if not isinstance(channel, dict):
            continue
        channel_name = str(channel.get("name") or "").strip()
        if not channel_name:
            continue
        # Se respetan las clasificaciones explícitas de contenido restringido
        # que pudiera proporcionar la API; no se infieren por el nombre.
        categories = {
            str(channel.get(key) or "").strip().casefold()
            for key in ("category", "genre", "content_category")
        }
        restricted_categories = {
            "adult", "age-restricted", "gambling", "betting", "casino",
            "weapons", "firearms", "drugs", "intoxicants", "controlled-substances",
        }
        if (
            channel.get("age_restricted") is True
            or channel.get("adult_content") is True
            or channel.get("restricted_content") is True
            or categories.intersection(restricted_categories)
        ):
            continue
        item = dict(channel)
        official_url = item.get("url") or item.get("player_url")
        if valid_player_url(official_url):
            item["player_url"] = str(official_url).strip()
            item["playback_allowed"] = True
            item["player_check"] = "official_player_url_format"
            playable += 1
        else:
            # El canal sigue en el catálogo, pero no se convierte en un enlace inseguro.
            item.pop("player_url", None)
            item["playback_allowed"] = False
            item["player_check"] = "no_valid_official_player_url"
            without_player += 1
        channels.append(item)

    channels.sort(key=lambda item: str(item.get("name") or "").casefold())
    checked_at = datetime.now(timezone.utc).isoformat()
    return {
        **{key: value for key, value in payload.items() if key not in {"channels", "total_channels", "catalog_check"}},
        "total_channels": len(channels),
        "channels": channels,
        "catalog_check": {
            "source": "CDN Live TV API complete channel catalog",
            "total_channels": len(channels),
            "channels_with_official_player_url": playable,
            "channels_without_valid_player_url": without_player,
            "status_filter_applied": False,
            "checked_at": checked_at,
            "note": "Se conservan todos los canales con nombre, independientemente de su estado. La URL oficial se valida por formato; no se verifica la reproducción del vídeo.",
        },
    }
