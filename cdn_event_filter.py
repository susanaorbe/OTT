#!/usr/bin/env python3
"""Aplica a los eventos de CDN los mismos criterios de selección que Futbolenlatv.

La clasificación se delega en ``agenda_futbolenlatv.get_sport_and_competition``
para que las reglas de competiciones no se dupliquen ni diverjan entre fuentes.
NHL y NFL se conservan como excepción para la vista «Todos»; la interfaz no
les asigna una pestaña deportiva propia.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from agenda_futbolenlatv import get_sport_and_competition, normalize_search_text


ROOT_KEY = "cdnlivetv.tv"
FILTERED_CATEGORIES = {
    "Soccer": "Fútbol",
    "NBA": "Baloncesto",
}
PASSTHROUGH_CATEGORIES = ("NHL", "NFL")
ALL_CATEGORIES = ("Soccer", "NBA", "NHL", "NFL")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _event_is_allowed(category: str, event: dict[str, Any]) -> bool:
    """Devuelve True solo si el clasificador de Futbolenlatv acepta el evento."""
    tournament = (
        _text(event.get("tournament"))
        or _text(event.get("competition"))
        or _text(event.get("league"))
    )
    home = _text(event.get("homeTeam"))
    away = _text(event.get("awayTeam"))
    title = _text(event.get("eventTitle")) or _text(event.get("title"))

    # No incluimos el país del partido: «Portugal», por ejemplo, podría
    # confundirse con el nombre de la competición Liga Portugal.
    text_lines = [part for part in (tournament, home, away, title) if part]
    if not text_lines:
        return False

    # El nombre de categoría solo se añade para la categoría NBA, que la API
    # también utiliza como etiqueta explícita de la competición.
    if category == "NBA":
        text_lines.append("NBA")

    blob = normalize_search_text("x " + " ".join(text_lines) + " x")
    sport, _icon, _competition, _featured, configured, _custom, _key = (
        get_sport_and_competition(blob, tournament, "", text_lines)
    )
    return configured is True and sport == FILTERED_CATEGORIES[category]


def filter_cdn_sports_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Filtra Soccer y NBA con las reglas de Futbolenlatv.

    NHL y NFL se conservan deliberadamente para la vista «Todos». Se devuelve
    una copia del JSON para no mutar el objeto original.
    """
    if not isinstance(payload, dict):
        raise ValueError("La respuesta de CDN Live TV no es un objeto JSON")

    result = deepcopy(payload)
    if isinstance(result.get(ROOT_KEY), dict):
        root = result[ROOT_KEY]
    elif isinstance(result.get("data"), dict) and isinstance(result["data"].get(ROOT_KEY), dict):
        root = result["data"][ROOT_KEY]
    elif any(category in result for category in ALL_CATEGORIES):
        root = result
    else:
        raise ValueError("La respuesta de CDN Live TV no contiene las categorías deportivas esperadas")

    stats: dict[str, Any] = {"kept": {}, "removed": {}, "total_kept": 0, "total_removed": 0}

    for category in FILTERED_CATEGORIES:
        events = root.get(category, [])
        if not isinstance(events, list):
            raise ValueError(f"La categoría {category} de CDN Live TV no es una lista")

        kept = [
            event for event in events
            if isinstance(event, dict) and _event_is_allowed(category, event)
        ]
        removed_count = len(events) - len(kept)
        root[category] = kept
        stats["kept"][category] = len(kept)
        stats["removed"][category] = removed_count
        stats["total_kept"] += len(kept)
        stats["total_removed"] += removed_count

    # NHL/NFL siguen visibles únicamente en «Todos», como excepción acordada.
    for category in PASSTHROUGH_CATEGORIES:
        events = root.get(category, [])
        if not isinstance(events, list):
            raise ValueError(f"La categoría {category} de CDN Live TV no es una lista")
        stats["kept"][category] = len(events)
        stats["removed"][category] = 0
        stats["total_kept"] += len(events)

    # Actualiza los contadores que devuelve CDN para que coincidan con las listas.
    if "total_events" in root:
        root["total_events"] = sum(
            len(root.get(category, []))
            for category in ALL_CATEGORIES
            if isinstance(root.get(category, []), list)
        )
    for category, count_key in (
        ("Soccer", "total_events_soccer"),
        ("NBA", "total_events_nba"),
        ("NHL", "total_events_nhl"),
        ("NFL", "total_events_NFL"),
    ):
        if count_key in root:
            root[count_key] = len(root.get(category, []))

    return result, stats
