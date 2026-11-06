#!/usr/bin/env python3
"""Actualiza los JSON estáticos que consume Mi TV en GitHub Pages.

Cada fuente se actualiza de forma independiente. Si una fuente falla, se
conserva el último JSON válido para no borrar datos por un fallo temporal.
"""
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


def load_previous(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def main() -> int:
    from server import fetch_json
    from agenda_futbolenlatv import get_agenda_payload

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
            changed |= write_if_changed(path, {"ok": True, "data": data})
        except Exception as exc:  # una fuente no debe impedir actualizar las demás
            message = f"CDN Live TV ({endpoint}): {exc}"
            failures.append(message)
            print(f"AVISO: {message}", file=sys.stderr)
            if not path.exists():
                write_if_changed(path, {"ok": False, "error": "Todavía no hay datos disponibles." , "data": empty_data})

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

    # La configuración de reproducción se publica como JSON estático separado.
    config_path = ROOT / "config" / "channels.json"
    playback_path = DATA_DIR / "playback.json"
    config = load_previous(config_path, {"version": 1, "channels": []})
    changed |= write_if_changed(playback_path, config)

    print(f"\nActualización terminada. Cambios: {'sí' if changed else 'no'}.")
    if failures:
        print(f"Fuentes con errores: {len(failures)}. Se conservan los últimos datos válidos cuando existen.")
        # Fallos parciales no hacen fallar el workflow: las otras fuentes siguen actualizándose.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
