#!/usr/bin/env python3
# Aplica el ajuste de clasificación de Pádel/Liga Portugal de Mi TV v0.7.2.
# Ejecutar desde la raíz del repositorio: python apply_agenda_parser_v072.py
# Crea una copia .bak antes de modificar agenda_futbolenlatv.py.
from pathlib import Path
import re

path = Path("agenda_futbolenlatv.py")
if not path.exists():
    raise SystemExit("No se encuentra agenda_futbolenlatv.py en la carpeta actual.")
s = path.read_text(encoding="utf-8")
original = s

def replace_once(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f"No se pudo aplicar '{label}': no coincide el código esperado. No se ha modificado el archivo.")
    s = s.replace(old, new, 1)

# Bare 'Portugal' in a participant name must never imply Liga Portugal.
replace_once('LIGA_PORTUGAL_RE = rx(r" liga portugal ", r" portugal ", r" betclic ")',
             'LIGA_PORTUGAL_RE = rx(r" liga portugal ")', 'regex Liga Portugal')
replace_once('"euroliga", "euroleague", "nba", "portugal"',
             '"euroliga", "euroleague", "nba"', 'detección de competición')

# Preserve a category explicitly exposed by Futbolenlatv's /deporte/<slug>/ link.
marker = 'def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:\n'
helper = '''def detect_explicit_sport(item) -> str:\n    \"\"\"Lee el deporte desde el enlace de categoría de la fila, si existe.\"\"\"\n    if item is None or not hasattr(item, "find_all"):\n        return ""\n    slug_map = {\n        "padel": "padel", "pádel": "padel", "tenis": "tenis",\n        "tennis": "tenis", "futbol": "futbol", "fútbol": "futbol",\n        "baloncesto": "baloncesto", "basketball": "baloncesto",\n        "motor": "motor", "motociclismo": "motor", "automovilismo": "motor",\n    }\n    for anchor in item.find_all("a", href=True):\n        match = re.search(r"/deporte/([^/?#]+)/?", str(anchor.get("href", "")), re.IGNORECASE)\n        if match:\n            slug = normalize_search_text(match.group(1))\n            if slug in slug_map:\n                return slug_map[slug]\n    for image in item.find_all("img"):\n        alt = normalize_search_text(image.get("alt", ""))\n        for label, slug in (("padel", "padel"), ("pádel", "padel"), ("tenis", "tenis"),\n                            ("futbol", "futbol"), ("fútbol", "futbol"),\n                            ("baloncesto", "baloncesto"), ("motor", "motor")):\n            if alt == normalize_search_text(label):\n                return slug\n    return ""\n\n\n'''
replace_once(marker, helper + marker, 'lector de categoría explícita')
replace_once('def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:',
             'def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str], str]:', 'firma parse_row_elements')
# Extend all empty returns in this function only.
start = s.index('def parse_row_elements(')
end = s.index('\ndef fetch_and_parse_agenda()', start)
block = s[start:end]
block = block.replace('return "", "", [], "", []', 'return "", "", [], "", [], explicit_sport')
block = block.replace('if item is None or not hasattr(item, "get_text"):\n        return "", "", [], "", [], explicit_sport', 'if item is None or not hasattr(item, "get_text"):\n        return "", "", [], "", [], ""')
block = block.replace('    raw_parts = [', '    explicit_sport = detect_explicit_sport(item)\n\n    raw_parts = [', 1)
block = block.replace('return time_clean, matchup, channels, tournament, text_lines',
                      'return time_clean, matchup, channels, tournament, text_lines, explicit_sport')
s = s[:start] + block + s[end:]

# Explicit category takes precedence; other exclusions remain in force.
replace_once('def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:\n    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob or "movistar golf" in tv_blob:',
'''def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str], explicit_sport: str = "") -> tuple[str, str, str, bool, bool, str, str]:
    if explicit_sport == "padel":
        # La categoría de origen confirma Pádel; no se confunde con el país de un participante.
        return ("Pádel", "🎾", raw_tournament or "Pádel", False, True, "", "padel")
    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob or "movistar golf" in tv_blob:''',
             'prioridad de categoría explícita')
# Restrict Liga Portugal recognition to the actual competition label, not the whole event blob.
replace_once('    if LIGA_PORTUGAL_RE.search(blob):',
             '    if LIGA_PORTUGAL_RE.search(" " + normalize_search_text(raw_tournament) + " "):',
             'contexto de Liga Portugal')
# Adapt the caller and unpacking.
replace_once('time_clean, event_str, channels, tournament, text_lines = parse_row_elements(element)',
             'time_clean, event_str, channels, tournament, text_lines, explicit_sport = parse_row_elements(element)',
             'resultado de parse_row_elements')
replace_once('blob, tournament, tv_blob, text_lines\n            )',
             'blob, tournament, tv_blob, text_lines, explicit_sport\n            )',
             'paso de categoría explícita')

if s == original:
    raise SystemExit("No había cambios que aplicar.")
backup = path.with_suffix(path.suffix + ".v072.bak")
if backup.exists():
    raise SystemExit(f"Ya existe {backup}; no se sobrescribirá por seguridad.")
backup.write_text(original, encoding="utf-8")
path.write_text(s, encoding="utf-8")
print("Correcto: agenda_futbolenlatv.py actualizado. Copia de seguridad:", backup)
