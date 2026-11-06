#!/usr/bin/env python3
"""Filtra el catálogo a canales online con página oficial de reproductor accesible.

La comprobación verifica que la URL de reproductor publicada por CDN Live TV
responde con una página HTML HTTPS. No puede demostrar que el vídeo se reproduzca
en todos los dispositivos ni que esté disponible desde todas las regiones.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
import json
import time

import requests

ALLOWED_PLAYER_HOSTS = {"cdnlivetv.tv", "www.cdnlivetv.tv"}
PLAYER_PATH = "/api/v1/channels/player/"
CHECK_TIMEOUT = 8
MAX_WORKERS = 12
POSITIVE_TTL = 6 * 60 * 60
NEGATIVE_TTL = 60 * 60
USER_AGENT = "Mozilla/5.0 (compatible; MiTV-CatalogCheck/1.0)"


def channel_key(channel: dict[str, Any]) -> str:
    name = str(channel.get("name") or "").strip().casefold()
    code = str(channel.get("code") or "").strip().casefold()
    return f"{name}|{code}"


def valid_player_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
        query = parse_qs(parsed.query)
        return (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_PLAYER_HOSTS
            and parsed.path == PLAYER_PATH
            and all(query.get(key) for key in ("name", "code", "user", "plan"))
            and query.get("user", [""])[0] == "cdnlivetv"
            and query.get("plan", [""])[0] == "free"
        )
    except (TypeError, ValueError):
        return False


def probe_player_url(url: str) -> tuple[bool, str]:
    """Comprueba la página del reproductor, sin extraer ni descargar el stream."""
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=CHECK_TIMEOUT,
            allow_redirects=True,
            stream=True,
        ) as response:
            final = urlparse(response.url)
            content_type = response.headers.get("Content-Type", "").lower()
            if final.scheme != "https" or final.hostname not in ALLOWED_PLAYER_HOSTS:
                return False, "redirección fuera del dominio oficial"
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return False, "la URL no devuelve una página HTML de reproductor"
            first_chunk = next(response.iter_content(chunk_size=8192), b"")
            if not first_chunk.strip():
                return False, "la página de reproductor está vacía"
            return True, "página oficial accesible (HTTP 200)"
    except requests.RequestException as exc:
        return False, f"no se pudo comprobar la página: {type(exc).__name__}"


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        checks = value.get("checks", {}) if isinstance(value, dict) else {}
        return checks if isinstance(checks, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, checks: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "checks": checks}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _cache_fresh(entry: dict[str, Any], url: str, now: float) -> bool:
    if entry.get("url") != url:
        return False
    try:
        checked = datetime.fromisoformat(str(entry["checked_at"]).replace("Z", "+00:00")).timestamp()
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    ttl = POSITIVE_TTL if entry.get("ok") is True else NEGATIVE_TTL
    return 0 <= now - checked < ttl


def filter_playable_channels(payload: dict[str, Any], cache_path: Path) -> dict[str, Any]:
    """Devuelve solo canales online con URL oficial válida y página accesible."""
    raw = payload.get("channels", [])
    if not isinstance(raw, list):
        raw = []

    cache = load_cache(cache_path)
    now = time.time()
    candidates: list[tuple[str, dict[str, Any], str]] = []
    excluded_offline = 0
    excluded_url = 0

    for channel in raw:
        if not isinstance(channel, dict) or not str(channel.get("name") or "").strip():
            excluded_url += 1
            continue
        if str(channel.get("status") or "").strip().casefold() not in {"online", "live"}:
            excluded_offline += 1
            continue
        url = channel.get("url")
        if not valid_player_url(url):
            excluded_url += 1
            continue
        key = channel_key(channel)
        candidates.append((key, channel, url))

    to_probe: list[tuple[str, dict[str, Any], str]] = []
    results: dict[str, dict[str, Any]] = {}
    for key, channel, url in candidates:
        old = cache.get(key, {})
        if _cache_fresh(old, url, now):
            results[key] = old
        else:
            to_probe.append((key, channel, url))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(probe_player_url, url): (key, url) for key, _channel, url in to_probe}
        for future in as_completed(futures):
            key, url = futures[future]
            try:
                ok, reason = future.result()
            except Exception as exc:  # una comprobación aislada no debe abortar el catálogo
                ok, reason = False, f"error de comprobación: {type(exc).__name__}"
            results[key] = {
                "url": url,
                "ok": ok,
                "reason": reason,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

    playable: list[dict[str, Any]] = []
    for key, channel, url in candidates:
        check = results.get(key, {})
        if check.get("ok") is not True:
            continue
        item = dict(channel)
        item["player_url"] = url
        item["playback_allowed"] = True
        item["player_checked_at"] = check.get("checked_at")
        item["player_check"] = "official_player_page_http_200"
        playable.append(item)

    playable.sort(key=lambda item: str(item.get("name") or "").casefold())
    save_cache(cache_path, results)
    return {
        "total_channels": len(playable),
        "channels": playable,
        "catalog_check": {
            "source": "CDN Live TV official player page",
            "online_candidates": len(candidates),
            "playable_channels": len(playable),
            "excluded_offline": excluded_offline,
            "excluded_invalid_player_url": excluded_url,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "note": "HTTP 200 verifies the player page, not successful video playback or regional availability.",
        },
    }
