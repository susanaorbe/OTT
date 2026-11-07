#!/usr/bin/env python3
"""Conserva íntegra la agenda de eventos de CDN Live TV.

Se mantiene el nombre de la función pública por compatibilidad con update_data.py
y server.py, pero ya no se aplican reglas de Futbolenlatv ni exclusiones.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any


def _find_root(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("cdn-live-tv", "cdnlivetv.tv"):
        root = payload.get(key)
        if isinstance(root, dict):
            return root
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("cdn-live-tv", "cdnlivetv.tv"):
            root = data.get(key)
            if isinstance(root, dict):
                return root
    return payload


def filter_cdn_sports_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devuelve una copia sin filtrar: ningún evento se descarta ni se reescribe."""
    if not isinstance(payload, dict):
        raise ValueError("La respuesta de CDN Live TV no es un objeto JSON")
    result = deepcopy(payload)
    root = _find_root(result)
    kept: dict[str, int] = {}
    total = 0
    removed: dict[str, int] = {}
    restricted_categories = {
        "adult", "age-restricted", "gambling", "betting", "casino",
        "weapons", "firearms", "drugs", "intoxicants", "controlled-substances",
    }
    for category, events in list(root.items()):
        if not isinstance(events, list):
            continue
        if category.strip().casefold() in restricted_categories:
            removed[category] = len(events)
            root[category] = []
            continue
        safe_events = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_categories = {
                str(event.get(key) or "").strip().casefold()
                for key in ("category", "genre", "content_category")
            }
            if (
                event.get("age_restricted") is True
                or event.get("adult_content") is True
                or event.get("restricted_content") is True
                or event_categories.intersection(restricted_categories)
            ):
                continue
            safe_events.append(event)
        root[category] = safe_events
        kept[category] = len(safe_events)
        removed[category] = len(events) - len(safe_events)
        total += len(safe_events)
    return result, {
        "kept": kept,
        "removed": removed,
        "total_kept": total,
        "total_removed": sum(removed.values()),
    }
