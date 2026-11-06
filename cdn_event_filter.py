
#!/usr/bin/env python3
"""Filtra los eventos de CDN Live TV.

De esta fuente solo se conservan las competiciones:
- Formula 1
- MotoGP

Todas las demás categorías y competiciones se excluyen.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


ROOT_KEY = "cdn-live-tv"

ALLOWED_MOTORSPORT_COMPETITIONS = {
    "formula 1",
    "motogp",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _event_is_allowed(event: dict[str, Any]) -> bool:
    """Comprueba si el evento pertenece a Formula 1 o MotoGP."""
    tournament = (
        _text(event.get("tournament"))
        or _text(event.get("competition"))
        or _text(event.get("league"))
    )

    return tournament.casefold() in ALLOWED_MOTORSPORT_COMPETITIONS


def filter_cdn_sports_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Conserva exclusivamente Formula 1 y MotoGP en la respuesta de CDN."""
    if not isinstance(payload, dict):
        raise ValueError(
            "La respuesta de CDN Live TV no es un objeto JSON"
        )

    result = deepcopy(payload)

    if isinstance(result.get(ROOT_KEY), dict):
        root = result[ROOT_KEY]
    elif (
        isinstance(result.get("data"), dict)
        and isinstance(result["data"].get(ROOT_KEY), dict)
    ):
        root = result["data"][ROOT_KEY]
    elif isinstance(result.get("Motorsport"), list):
        root = result
    else:
        raise ValueError(
            "La respuesta de CDN Live TV no contiene "
            "la estructura esperada: cdn-live-tv"
        )

    if not isinstance(root.get("Motorsport"), list):
        raise ValueError(
            "La respuesta de CDN Live TV no contiene "
            "la categoría Motorsport como lista"
        )

    stats: dict[str, Any] = {
        "kept": {},
        "removed": {},
        "total_kept": 0,
        "total_removed": 0,
    }

    # Procesa todas las categorías que contienen listas de eventos.
    for category, events in list(root.items()):
        if not isinstance(events, list):
            continue

        if category == "Motorsport":
            kept = [
                event
                for event in events
                if isinstance(event, dict)
                and _event_is_allowed(event)
            ]
        else:
            kept = []

        removed_count = len(events) - len(kept)
        root[category] = kept

        stats["kept"][category] = len(kept)
        stats["removed"][category] = removed_count
        stats["total_kept"] += len(kept)
        stats["total_removed"] += removed_count

    # Actualiza el contador general.
    if "total_events" in root:
        root["total_events"] = sum(
            len(value)
            for value in root.values()
            if isinstance(value, list)
        )

    # Actualiza los contadores individuales existentes.
    for category in list(stats["kept"]):
        count_key = f"total_events_{category.casefold()}"
        if count_key in root:
            root[count_key] = stats["kept"][category]

    return result, stats
