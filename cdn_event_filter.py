#!/usr/bin/env python3
"""Filtra los eventos de CDN con el mismo clasificador que Futbolenlatv.

Cada evento se evalúa con las funciones de clasificación de la agenda
personalizada. Así, ambas fuentes comparten deportes, competiciones y
exclusiones, sin excepciones independientes para NHL o NFL.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenda_futbolenlatv import (
    get_sport_and_competition,
    normalize_search_text,
    parse_motor_event,
)

ROOT_KEYS = ("cdn-live-tv", "cdnlivetv.tv")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _channel_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = _text(item.get("channel_name") or item.get("name"))
        else:
            name = ""
        if name:
            names.append(name)
    return names


def _classify_event(category: str, event: dict[str, Any]) -> dict[str, Any] | None:
    """Devuelve los metadatos de la agenda si el evento está permitido."""
    tournament = (
        _text(event.get("tournament"))
        or _text(event.get("competition"))
        or _text(event.get("league"))
    )
    home = _text(event.get("homeTeam"))
    away = _text(event.get("awayTeam"))
    title = (
        _text(event.get("eventTitle"))
        or _text(event.get("title"))
        or _text(event.get("event"))
    )
    channels = _channel_names(event.get("channels"))
    tv_blob = " ".join(channels).lower()

    text_lines: list[str] = []
    if tournament:
        text_lines.append(tournament)
    if home and away:
        text_lines.append(f"{home} - {away}")
    if title and title not in text_lines:
        text_lines.append(title)
    if not text_lines:
        return None

    # La categoría solo ayuda a interpretar etiquetas explícitas de la API.
    category_key = category.strip().casefold()
    category_hints = {
        "nba": "NBA",
        "tennis": "tenis",
        "tenis": "tenis",
        "nhl": "hockey",
        "nfl": "nfl",
    }
    category_hint = category_hints.get(category_key, category)
    blob = normalize_search_text(
        " ".join([*text_lines, tournament, tv_blob, category_hint])
    )

    # El motor se clasifica antes que el resto, igual que en la agenda original.
    motor_competition, motor_title, motor_featured = parse_motor_event(
        blob, tournament, text_lines
    )
    if motor_competition:
        return {
            "sport": "Motor",
            "icon": "🏆",
            "competition": motor_competition,
            "event_title": motor_title,
            "competition_key": "motor",
            "featured": bool(motor_featured),
        }

    sport, icon, competition, featured, configured, _custom, comp_key = (
        get_sport_and_competition(blob, tournament, tv_blob, text_lines)
    )
    if not configured or not sport or not competition:
        return None

    return {
        "sport": sport,
        "icon": icon,
        "competition": competition,
        "event_title": title,
        "competition_key": comp_key,
        "featured": bool(featured),
    }


def _find_root(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ROOT_KEYS:
        root = payload.get(key)
        if isinstance(root, dict):
            return root
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ROOT_KEYS:
            root = data.get(key)
            if isinstance(root, dict):
                return root
    known_categories = {"soccer", "nba", "nhl", "nfl", "tennis", "motorsport", "motor", "basketball"}
    if any(
        isinstance(value, list)
        and (key.casefold() in known_categories or any(isinstance(item, dict) for item in value))
        for key, value in payload.items()
    ):
        return payload
    raise ValueError("La respuesta de CDN Live TV no contiene las categorías deportivas esperadas")


def _update_count_fields(root: dict[str, Any], category_counts: dict[str, int]) -> None:
    if "total_events" in root:
        root["total_events"] = sum(
            len(value) for value in root.values() if isinstance(value, list)
        )

    # Conserva las grafías originales de los contadores (por ejemplo NFL/NHL).
    for key in list(root):
        if not key.casefold().startswith("total_events_"):
            continue
        suffix = key[len("total_events_"):].casefold()
        for category, count in category_counts.items():
            if category.casefold() == suffix:
                root[key] = count
                break


def filter_cdn_sports_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Conserva exclusivamente los eventos aceptados por la agenda personalizada."""
    if not isinstance(payload, dict):
        raise ValueError("La respuesta de CDN Live TV no es un objeto JSON")

    result = deepcopy(payload)
    root = _find_root(result)
    stats: dict[str, Any] = {
        "kept": {},
        "removed": {},
        "total_kept": 0,
        "total_removed": 0,
    }
    kept_counts: dict[str, int] = {}

    for category, events in list(root.items()):
        if not isinstance(events, list):
            continue

        kept: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            classification = _classify_event(category, event)
            if classification is None:
                continue
            item = dict(event)
            item["agenda_sport"] = classification["sport"]
            item["agenda_icon"] = classification["icon"]
            item["agenda_competition"] = classification["competition"]
            item["agenda_event_title"] = classification["event_title"]
            item["agenda_competition_key"] = classification["competition_key"]
            item["agenda_featured"] = classification["featured"]
            kept.append(item)

        removed_count = len(events) - len(kept)
        root[category] = kept
        kept_counts[category] = len(kept)
        stats["kept"][category] = len(kept)
        stats["removed"][category] = removed_count
        stats["total_kept"] += len(kept)
        stats["total_removed"] += removed_count

    _update_count_fields(root, kept_counts)
    return result, stats
