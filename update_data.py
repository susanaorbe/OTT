#!/usr/bin/env python3
"""Actualiza los JSON estáticos de Mi TV sin filtrar el catálogo ni la agenda CDN."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "docs" / "data"


def serialize(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_if_changed(path: Path, payload: Any) -> bool:
    content = serialize(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        print(f"Sin cambios: {path.relative_to(ROOT)}")
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    print(f"Actualizado: {path.relative_to(ROOT)}")
    return True


def main() -> int:
    from server import fetch_json
    from agenda_futbolenlatv import get_agenda_payload
    from channel_catalog import filter_playable_channels
    from cdn_event_filter import filter_cdn_sports_payload

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    changed = False
    sources = (
        ("channels.json", "channels", {"channels": []}),
        ("events_cdn.json", "events/sports", {}),
    )
    for filename, endpoint, empty_data in sources:
        path = DATA_DIR / filename
        try:
            data = fetch_json(endpoint)
            if not isinstance(data, dict):
                raise ValueError("la API no devolvió un objeto JSON")
            if filename == "events_cdn.json":
                data, stats = filter_cdn_sports_payload(data)
                print(f"Agenda CDN completa: {stats['total_kept']} eventos conservados; 0 descartados.")
            elif filename == "channels.json":
                data = filter_playable_channels(data)
                check = data.get("catalog_check", {})
                print(
                    f"Catálogo CDN completo: {check.get('total_channels', len(data.get('channels', [])))} canales; "
                    f"{check.get('channels_with_official_player_url', 0)} con reproductor oficial y "
                    f"{check.get('channels_without_valid_player_url', 0)} sin URL oficial válida."
                )
            changed |= write_if_changed(path, {"ok": True, "data": data})
        except Exception as exc:
            message = f"CDN Live TV ({endpoint}): {exc}"
            failures.append(message)
            print(f"AVISO: {message}", file=sys.stderr)
            if not path.exists():
                write_if_changed(path, {"ok": False, "error": "Todavía no hay datos disponibles.", "data": empty_data})

    # Se sigue actualizando el JSON de Futbolenlatv para no tocar ni romper
    # el proyecto de agenda personalizada; Mi TV ya no lo consulta.
    ftv_path = DATA_DIR / "events_futbolenlatv.json"
    try:
        data = get_agenda_payload()
        if not isinstance(data, dict):
            raise ValueError("el parser no devolvió un objeto JSON")
        changed |= write_if_changed(ftv_path, {"ok": True, "data": data})
    except Exception as exc:
        message = f"Futbolenlatv: {exc}"
        failures.append(message)
        print(f"AVISO: {message}", file=sys.stderr)
        if not ftv_path.exists():
            write_if_changed(ftv_path, {"ok": False, "error": "Todavía no hay datos disponibles.", "data": {"events": []}})

    print(f"\nActualización terminada. Cambios: {'sí' if changed else 'no'}.")
    if failures:
        print(f"Fuentes con errores: {len(failures)}. Se conservan los últimos datos válidos cuando existen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
