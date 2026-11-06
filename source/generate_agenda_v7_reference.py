from collections import Counter
from datetime import datetime, date
from html import escape
import zoneinfo
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zoneinfo import ZoneInfoNotFoundError
from bs4 import BeautifulSoup
from urllib.parse import urlparse


# ============================================================================
# CONFIGURACIÓN Y DICCIONARIO DE CANALES Y APLICACIONES
# ============================================================================

WIDGET_URL = "https://www.futbolenlatv.es/deporte"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15


def get_spain_timezone():
    """Devuelve Europe/Madrid; usa la zona local como último recurso."""
    try:
        return zoneinfo.ZoneInfo("Europe/Madrid")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo


def create_http_session() -> requests.Session:
    """Sesión HTTP con reintentos limitados ante errores transitorios."""
    session = requests.Session()
    retry_options = {
        "total": 3,
        "connect": 3,
        "read": 2,
        "status": 2,
        "backoff_factor": 0.5,
        "status_forcelist": (429, 500, 502, 503, 504),
        "raise_on_status": False,
    }
    try:
        retry = Retry(**retry_options, allowed_methods=frozenset({"GET"}))
    except TypeError:  # Compatibilidad con versiones antiguas de urllib3.
        retry = Retry(**retry_options, method_whitelist=frozenset({"GET"}))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_dynamic_domain() -> str:
    """Obtiene dinámicamente el dominio actual siguiendo fctvlink y fclink."""
    default_domain = "www.fctv33go.pics"
    try:
        with create_http_session() as session:
            resp1 = session.get("https://hubu.ru/fctvlink", headers=REQUEST_HEADERS, timeout=10)
            soup1 = BeautifulSoup(resp1.content, "html.parser")
            
            fclink_url = "https://hubu.ru/fclink"
            for a in soup1.find_all("a", href=True):
                if "fctv33" in a.get_text(strip=True).lower() or "page" in a.get_text(strip=True).lower():
                    fclink_url = a["href"]
                    break
            
            resp2 = session.get(fclink_url, headers=REQUEST_HEADERS, timeout=10)
            soup2 = BeautifulSoup(resp2.content, "html.parser")
            
            target_url = None
            for a in soup2.find_all("a", href=True):
                txt = a.get_text(strip=True).lower()
                if "link - fctv33" in txt or ("link" in txt and "fctv33" in txt):
                    target_url = a["href"]
                    break
            
            if not target_url:
                for a in soup2.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and "hubu.ru" not in href:
                        target_url = href
                        break
                        
            if target_url:
                parsed = urlparse(target_url)
                if parsed.netloc:
                    return parsed.netloc
    except Exception as e:
        print(f"Error obteniendo dominio dinámico: {e}")
    return default_domain


def get_time_slot(time_str: str) -> str:
    """Clasifica una hora en su franja horaria correspondiente (en minúsculas sin ñ)."""
    try:
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        total_mins = h * 60 + m
        if total_mins <= 419:  # 00:00 - 06:59
            return "madrugada"
        elif total_mins <= 839:  # 07:00 - 13:59
            return "manana"
        elif total_mins <= 1229:  # 14:00 - 20:29
            return "tarde"
        else:  # 20:30 - 23:59
            return "noche"
    except Exception:
        return "noche"

# Aplicaciones instaladas en Fire TV
FIRETV_APP_PACKAGES = {
    "movistar": "com.movistarplus.androidtv",
    "dazn": "com.dazn",
    "prime": "com.amazon.firebat",
    "kodi": "org.xbmc.kodi",
}

CHANNEL_APP_MAP = {
    "la 1": "movistar",
    "la 2": "movistar",
    "antena 3": "movistar",
    "cuatro": "movistar",
    "telecinco": "movistar",
    "la sexta": "movistar",
    "movistar plus+": "movistar",
    "m+ vamos": "movistar",
    "m+ vamos 2": "movistar",
    "m+ vamos 3": "movistar",
    "primera federacion": "movistar",
    "eurosport 1": "movistar",
    "eurosport 2": "movistar",
    "real madrid tv": "movistar",
    "teledeporte": "movistar",
    "replay": "movistar",
    "dazn": "dazn",
    "dazn laliga": "dazn",
    "dazn 1": "dazn",
    "dazn 2": "dazn",
    "tennis channel": "prime",
    "tennis channel - orange tv": "prime",
    "amazon prime video": "prime",
    "dazn 3": "kodi",
    "dazn 4": "kodi",
    "dazn f1": "kodi",
    "dazn motogp": "kodi",
    "dazn baloncesto": "kodi",
    "dazn baloncesto 2": "kodi",
    "dazn baloncesto 3": "kodi",
}


def normalize_search_text(text: str) -> str:
    value = (text or "").lower()
    value = (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ç", "c")
        .replace("ñ", "n").replace("º", "ª")
    )
    value = re.sub(r"[|,;:/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_time(time_str: str) -> str:
    if not time_str:
        return ""
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", str(time_str))
    if not match:
        return ""
    hours, minutes = map(int, match.groups())
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return ""
    return f"{hours:02d}:{minutes:02d}"


def normalize_channel_name(channel_name: str) -> str:
    normalized = normalize_search_text(channel_name)
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def clean_channel_display_name(channel_name: str) -> str:
    cleaned = str(channel_name or "").strip()
    cleaned = re.sub(
        r"\s*[-–—]\s*orange\s+tv\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if normalize_search_text(cleaned) == "tennis channel":
        return "Tennis Channel"
    return cleaned


def get_channel_app(channel_name: str) -> str:
    normalized = normalize_channel_name(channel_name)
    aliases = {
        "movistar plus": "movistar plus+",
        "movistar+": "movistar plus+",
        "tdp": "teledeporte",
        "tennis channel orange tv": "tennis channel - orange tv",
        "m+ #vamos": "m+ vamos",
        "#vamos": "m+ vamos",
        "#vamos spain": "m+ vamos",
        "m+ vamos 8 y 50": "m+ vamos",
    }
    normalized = aliases.get(normalized, normalized)
    return CHANNEL_APP_MAP.get(normalized, "kodi")


def get_firetv_intent(channel_name: str) -> str:
    app_key = get_channel_app(channel_name)
    if app_key == "kodi":
        return ""
    package_name = FIRETV_APP_PACKAGES.get(app_key)
    if not package_name:
        return ""
    return (
        "intent:#Intent;"
        "action=android.intent.action.MAIN;"
        "category=android.intent.category.LEANBACK_LAUNCHER;"
        f"package={package_name};end"
    )


EXCLUDED_CHANNELS = {
    "* sin tv en directo *", "antel tv internacional", "aragón play", "aragón tv",
    "asobal tv", "atp tennis tv", "athletic-club.eus", "baloncesto tv",
    "baloncesto tv ppv", "barclays women's super league youtube", "be mad", "betevé web",
    "beisbolplay", "canal 9 soria youtube", "cayotv youtube", "cmmplay",
    "concacaf youtube", "conmebol libertadores youtube", "dazn 1 bar(m148)", "dazn 1 bar", "dazn 2 bar(m149)",
    "dazn 2 bar", "deportes tvcanaria youtube", "eleventv youtube", "esport3 web",
    "esport3(cataluña)", "esport3", "etb1", "etb1(país vasco)", "f1 academy youtube", "fanatiz", "fanplay",
    "fanplay tv", "fanseat", "fc barcelona ppv youtube", "fff tv youtube", "fiba youtube",
    "flamengo tv youtube", "hbo max", "j.league international youtube", "la 7", "la 7 tv",
    "la ocho mediterráneo", "la xarxa+", "laliga tv bar", "laliga tv m2",
    "laliga tv m3", "laliga tv m4", "laliga tv m5", "laliga+ plus",
    "liga futve youtube", "ligafutve app", "lleida televisió", "m+ #vamos bar", "m+ #vamos bar 2",
    "m+ #vamos bar 2(308)", "m+ #vamos bar(307)", "m+ laliga hdr", "m+ laliga hdr(m440 o111)",
    "mediaset infinity", "motogp videopass", "movistar+ lite",
    "nwsl+", "onefootball", "onefootball ppv", "orange fútbol 1(107)",
    "orange fútbol 2(108)", "orange fútbol 3(109)", "popular tv murcia", "prosieben maxx(m+ astra)", "rcd deportivo tv youtube",
    "rcdeportivo tv youtube", "rcn nuestra tele", "red bull tv", "rfef tv youtube",
    "rfef.es", "rtve play", "sefutbol youtube", "sevilla fc +",
    "siroko tv", "tv 3", "tv footballclub(acceder)", "tv footballclub", "tv canaria",
    "tv galicia", "tv3(cataluña)", "tvg(galicia)", "tv footballclub ▾",
    "tvg", "tv5monde", "uefa tv", "uefa youtube",
    "win sports tv youtube", "wta tv", "web directo", "zapping internacional",
    "a-leagues youtube", "liga u youtube", "marca youtube", "german football youtube", "l1 max youtube",
    "the afc hub youtube", "hc eivissa youtube", "vinxtv youtube",
    "valencia cf youtube", "valencia cf app", "à punt", "à punt mèdia",
    "fip - international padel federation youtube", "fip youtube"
}

def channel_exclusion_key(channel: str) -> str:
    """Clave de comparación sin acentos, puntuación ni identificadores entre paréntesis."""
    base = re.sub(r"\([^)]*\)", "", normalize_search_text(channel))
    return re.sub(r"[^a-z0-9]+", "", base)


EXCLUDED_CHANNEL_KEYS = {channel_exclusion_key(c) for c in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = channel_exclusion_key(channel)
    if not key:
        return True
    return key in EXCLUDED_CHANNEL_KEYS


def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r" real madrid ", r" rm castilla ", r" r\.?\s*madrid ")
CASTILLA_RE = rx(r" real madrid castilla ", r" rm castilla ", r" castilla ")
YOUTH_BASKET_RE = rx(r" sub\s*[-]?\d+ ", r" junior ", r" cadete ", r" infantil ")

EXCLUDED_SPORTS_RE = rx(
    r" hockey ", r" patines ", r" nfl ", r" cowboys ", r" packers ",
    r" balonmano ", r" asobal ", r" handball ", r" waterpolo ", r" rugby ", r" rutby ", r" rucby ", r" rubgy ",
    r" ehf ", r" ihf ", r" futsal ", r" futbol sala ", r" golf ", r" beisbol ",
    r" padel ", r" padell "
)

EXCLUDED_COMPETITIONS_RE = rx(
    r" national league ", r" vanarama national league ", r" liga u ",
    r" tercera ", r" 3ª ", r" 3a ", r" grupo 8 ", r" tercera federacion ",
    r" basketball champions league ", r" futsal champions ",
    r" 2\.?\s*bundesliga ", r" serie a fem+inile ", r" serie a femminile ",
    r" laliga hypermotion ", r" segunda division ", r" hypermotion ",
    r" brasil\s*[-–—]?\s*serie\s+a ",
    r" argentina ", r" torneo clausura ", r" torneo apertura ",
    r" liga profesional ", r" primera division argentina ",
    r" international cup ", r" eurocup "
)

SPANISH_TENNIS_PLAYERS_RE = rx(
    r" carlos alcaraz ", r" alcaraz ", r" alejandro davidovich ", r" davidovich ",
    r" cristina bucsa ", r" bucsa ", r" paula badosa ", r" badosa ",
    r" jaume munar ", r" munar ", r" rafael jodar ", r" jodar ",
    r" dani merida ", r" merida "
)

WTA_RE = re.compile(r" wta ", re.IGNORECASE)
WOMEN_RE = rx(r" femenina ", r" femenino ", r" frauen ", r" women ", r"\(f\) ", r"\(w\) ")

PRIMERA_RFEF_RE = rx(
    r" primera federacion ", r" primera rfef ", r" 1[ªa]\s*federacion ",
)

LALIGA_RE = rx(
    r" liga ea sports ", r" liga ea ", r" primera division ", 
    r" españa - la liga ", r" laliga(?![\s\-]*(?:hypermotion|smartbank|tv hypermotion|123)) "
)

BASKET_ALLOWED_COMPETITIONS_RE = rx(
    r" liga endesa ", r" acb ", r" euroliga ", r" euroleague ", r" euro league ",
    r" copa acb ", r" supercopa endesa ", r" supercopa de espana ",
    r" nba "
)

WOMEN_FOOTBALL_COMPETITIONS = (
    (rx(r" liga f ", r" primera division femenina "), "Liga F"),
    (rx(r" copa de la reina "), "Copa de la Reina"),
    (rx(r" supercopa de espana femenina ", r" supercopa femenina "), "Supercopa de España Femenina"),
    (rx(r" women'?s champions league ", r" champions league femenina "), "UEFA Women's Champions League"),
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder", 
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|videopass|prime video|amazon|à punt)"
)

CHANNEL_LINE_RE = rx(
    r" tennis channel ", r" orange tv ", r" channel\s*[-–—]\s*orange tv ", r" prime video ", r" à punt mèdia ", r" à punt "
)

JUNK_RESIDUES_RE = rx(
    r"\(\s*(?:cataluña|catalunya|país vasco|pais vasco|galicia|andalucía|andalucia)\s*\)",
    r"\(\s*(?:ver gratis|ver en directo|acceder|ver)\s*\)",
    r"\(\s*\d+\s*\)"
)

EVENT_CLEANUP_TRAIL_RE = re.compile(
    r"\s*-\s*(?:orange\s*f[uú]tbol\s*\d*|movistar[^\-]*|dazn[^\-]*|nba\s+league\s+pass|primera\s+federaci[oó]n(?:\s*\(\s*[mo]\d+(?:\s+[mo]\d+)*\s*\))?|\(\s*\d+(?:\s*y\s*\d+)?\s*\))\s*$",
    re.IGNORECASE
)

# Patrones compilados reutilizados durante la clasificación de cada evento.
TENNIS_EVENT_RE = rx(r" tenis ", r" atp ", r" wta ", r" masters ", r" open ", r" challenger ", r" itf ", r" torneo de ")
GOLF_RE = rx(r" golf ")
NBA_RE = rx(r" nba ")
EUROLIGA_RE = rx(r" euroliga ", r" euroleague ")
BASKET_WOMEN_RE = rx(r"\(f\) ", r"\(w\) ")
COPA_DEL_REY_RE = rx(r" copa del rey ")
BASKET_CONTEXT_RE = rx(r" basket ", r" baloncesto ", r" acb ")
CHAMPIONS_RE = rx(r" champions league ", r" champions ")
CHAMPIONS_NON_FOOTBALL_RE = rx(r" basketball ", r" cl ", r" afc ", r" asia ")
PREMIER_RE = rx(r" premier league ", r" premier ", r" inglaterra - premier league ")
SERIE_A_RE = rx(r" serie a ")
BUNDESLIGA_RE = rx(r" bundesliga ", r" alemania - bundesliga ")
BUNDESLIGA_2_RE = rx(r"2\.?\s*bundesliga ")
LIGUE1_RE = rx(r" ligue 1 ", r" francia - ligue 1 ")
EREDIVISIE_RE = rx(r" eredivisie ")
LIGA_PORTUGAL_RE = rx(r" liga portugal ", r" portugal ", r" betclic ")
WORLD_CUP_RE = rx(r" copa mundial ", r" mundial de la fifa ", r" world cup ")
EUROCUP_RE = rx(r" eurocup ")
EURO_FINAL_RE = rx(r" eurocopa ", r" euro\s*20\d{2} ", r" euro\s*cup ")
NATIONS_LEAGUE_RE = rx(r" nations league ")


def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)
    if any(forbidden in blob_lower for forbidden in ["academy", "moto2", "moto 2", "moto3", "moto 3", "rookies", "supercars"]):
        return ("", "", False)
    if any(junk in blob_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje"]):
        return ("", "", False)

    comp_name = ""
    if "formula 1" in blob_lower or "f1" in blob_lower:
        comp_name = "Fórmula 1"
    elif "motogp" in blob_lower:
        comp_name = "MotoGP"
    elif "formula e" in blob_lower or "fórmula e" in blob_lower:
        comp_name = "Fórmula E"
    elif "indycar" in blob_lower or "indy car" in blob_lower:
        comp_name = "Indycar"

    if not comp_name:
        return ("", "", False)

    valid_lines = [l for l in text_lines if normalize_search_text(l) not in {normalize_search_text(comp_name), "motor", "automovilismo", "motociclismo"}]
    clean_desc = " - ".join(valid_lines).strip()
    clean_desc = EVENT_CLEANUP_TRAIL_RE.sub("", clean_desc).strip()
    
    if not clean_desc or clean_desc == "-":
        clean_desc = "Carrera"
    
    event_title = f"{comp_name} - {clean_desc}"
    clean_norm = normalize_search_text(event_title)

    is_fav = False
    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
    else:
        is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])

    return (comp_name, event_title, is_fav)


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:
    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob or "movistar golf" in tv_blob:
        return ("", "", "", False, False, "", "")
    if EXCLUDED_COMPETITIONS_RE.search(blob):
        return ("", "", "", False, False, "", "")

    if TENNIS_EVENT_RE.search(blob):
        if GOLF_RE.search(tv_blob) or "movistar golf" in blob:
            return ("", "", "", False, False, "", "")
        tour = "WTA" if WTA_RE.search(blob) else "ATP"
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"tenis", "atp", "wta", ""} else f"{tour} Tour"
        is_fav = bool(SPANISH_TENNIS_PLAYERS_RE.search(blob))
        return ("Tenis", "🎾", comp, is_fav, True, "", "tenis")

    if BASKET_ALLOWED_COMPETITIONS_RE.search(blob):
        if WOMEN_RE.search(blob) or BASKET_WOMEN_RE.search(blob):
            return ("", "", "", False, False, "", "")
        if NBA_RE.search(blob):
            comp_name = "NBA"
            comp_key = "nba"
        elif EUROLIGA_RE.search(blob):
            comp_name = "Euroliga"
            comp_key = "euroliga"
        else:
            comp_name = "Liga Endesa / ACB"
            comp_key = "ligaendesa"
        is_fav = bool(REAL_MADRID_RE.search(blob) and not YOUTH_BASKET_RE.search(blob))
        return ("Baloncesto", "🏀", comp_name, is_fav, True, "", comp_key)

    if WOMEN_RE.search(blob) or any(p.search(blob) for p, _ in WOMEN_FOOTBALL_COMPETITIONS):
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(blob) or ("femenina" in blob and name.lower() in blob):
                comp_match = name
                break
        if comp_match and REAL_MADRID_RE.search(blob):
            return ("Fútbol", "⚽", comp_match, True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    if COPA_DEL_REY_RE.search(blob) and not WOMEN_RE.search(blob) and not BASKET_CONTEXT_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob))
        return ("Fútbol", "⚽", "Copa del Rey", is_fav, True, "", "copadelrey")

    if CHAMPIONS_RE.search(blob) and not WOMEN_RE.search(blob) and not CHAMPIONS_NON_FOOTBALL_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob))
        return ("Fútbol", "⚽", "UEFA Champions League", is_fav, True, "", "champions")

    if LALIGA_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob))
        return ("Fútbol", "⚽", "LaLiga EA Sports", is_fav, True, "", "laliga")

    if PREMIER_RE.search(blob):
        return ("Fútbol", "⚽", "Premier League", False, True, "", "premier")

    if SERIE_A_RE.search(blob) and not ("brasil" in blob or "serie a brasil" in blob):
        return ("Fútbol", "⚽", "Serie A", False, True, "", "seriea")

    if BUNDESLIGA_RE.search(blob) and not BUNDESLIGA_2_RE.search(blob):
        return ("Fútbol", "⚽", "Bundesliga", False, True, "", "bundesliga")

    if LIGUE1_RE.search(blob):
        return ("Fútbol", "⚽", "Ligue 1", False, True, "", "ligue1")

    if EREDIVISIE_RE.search(blob):
        return ("Fútbol", "⚽", "Eredivisie", False, True, "", "eredivisie")

    if LIGA_PORTUGAL_RE.search(blob):
        return ("Fútbol", "⚽", "Liga Portugal Betclic", False, True, "", "ligaportugal")

    if WORLD_CUP_RE.search(blob):
        return ("Fútbol", "⚽", "Copa Mundial de la FIFA", False, True, "", "mundial")

    if EURO_FINAL_RE.search(blob) and not EUROCUP_RE.search(blob):
        return ("Fútbol", "⚽", "Eurocopa", False, True, "", "eurocopa")

    if NATIONS_LEAGUE_RE.search(blob):
        return ("Fútbol", "⚽", "UEFA Nations League", False, True, "", "nationsleague")

    if PRIMERA_RFEF_RE.search(blob) or "primera federacion" in blob or "primera rfef" in blob:
        if CASTILLA_RE.search(blob):
            return ("Fútbol", "⚽", "España - Primera Federación", True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    return ("", "", "", False, False, "", "")


def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:
    if item is None or not hasattr(item, "get_text"):
        return "", "", [], "", []

    raw_parts = [
        part.strip()
        for part in item.get_text("\n", strip=True).split("\n")
        if part.strip()
    ]
    if not 3 <= len(raw_parts) <= 30:
        return "", "", [], "", []

    text_full = " | ".join(raw_parts)
    time_match = TIME_RE.search(text_full)
    time_clean = clean_time(time_match.group(0)) if time_match else ""

    if not time_clean:
        return "", "", [], "", []

    channels: list[str] = []
    channel_keys = set()
    text_lines = []

    competition_terms = (
        "liga", "primera", "segunda", "tercera", "federacion", "division", "grupo", "torneo", "serie a",
        "endesa", "bundesliga", "atp", "wta", "masters", "copa", "champions", "superbike", "eredivisie", "euroliga", "euroleague", "nba", "portugal"
    )

    for part in raw_parts:
        part = JUNK_RESIDUES_RE.sub("", part).strip()
        if not part:
            continue

        part_lower = normalize_search_text(part)
        if TIME_RE.fullmatch(part) or part_lower in {
            "ver partido", "directo", "(ver en directo)", "ver gratis",
            "(ver)", "acceder", "(acceder)"
        }:
            continue
        if re.fullmatch(r"[\s,.|;:/-]*", part):
            continue
        if re.fullmatch(r"\(?[mo]\+?\d+.*\)?", part_lower):
            continue

        is_primera_federacion_channel = part_lower == "primera federacion"

        # "LaLiga EA Sports" es una competición, no un canal. Solo tratamos
        # una línea que contenga LaLiga como canal cuando incluye un indicador
        # inequívoco de emisión (TV, M+, Movistar o DAZN).
        is_laliga_competition = (
            "laliga" in part_lower
            and not any(token in part_lower for token in (" tv", "m+", "movistar", "dazn"))
        )

        looks_like_channel = (
            is_primera_federacion_channel
            or (TV_IDENTIFIERS_RE.search(part) and not is_laliga_competition)
            or CHANNEL_LINE_RE.search(part_lower)
            or any(term in part_lower for term in (
                "m+", "dazn", "youtube", "fanatiz", "onefootball",
                "siroko", "tv footballclub", "aragon tv", "aragon play",
                "cmmplay", "etb1", "tvg", "tv3", "esport3", "hbo max", "ehf tv", "videopass", "prime video", "amazon", "à punt", "rcn", "beisbolplay", "app"
            ))
        )
        if looks_like_channel:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            clean_part = JUNK_RESIDUES_RE.sub("", clean_part).strip()
            clean_part = re.sub(r"\(m\d+[^)]*\)", "", clean_part, flags=re.IGNORECASE).strip()
            clean_part = re.sub(r"\s*\([^)]*\)", "", clean_part).strip()

            sub_parts = re.split(r"[,|\n]+", clean_part)
            for channel in sub_parts:
                channel = channel.strip().rstrip(":").strip()
                channel = clean_channel_display_name(channel)
                channel_lower = normalize_search_text(channel)

                if (
                    channel
                    and not is_excluded_channel(channel)
                    and normalize_search_text(channel) not in channel_keys
                    and not re.fullmatch(r"\(?[mo]\+?\d+.*\)?", channel_lower)
                    and channel_lower not in {"acceder", "(acceder)", "ver en directo"}
                ):
                    channels.append(channel)
                    channel_keys.add(normalize_search_text(channel))
            continue

        text_lines.append(part)

    if not text_lines or not channels:
        return "", "", [], "", []

    tournament_candidates = []
    matchup_candidates = []
    for part in text_lines:
        part_lower = normalize_search_text(part)
        is_competition_line = any(term in part_lower for term in competition_terms)
        has_match_separator = bool(
            re.search(r"\s+-\s+|\s+vs\.?\s+|\s+v\.\s+", part, re.IGNORECASE)
            or re.search(r"\s\(f\)\s*-\s*", part, re.IGNORECASE)
        )
        is_primera_federacion_group = bool(
            re.search(r"primera\s+federaci[oó]n", part_lower)
            and re.search(r"\bgrupo\s*\d+\b", part_lower)
            and not re.search(r"\bvs\.?\b|\bv\.\b", part_lower)
        )
        if is_primera_federacion_group or (is_competition_line and not has_match_separator):
            tournament_candidates.append(part)
        else:
            matchup_candidates.append(part)

    if tournament_candidates:
        tournament = tournament_candidates[0]
        event_lines = [part for part in matchup_candidates if part != tournament]
    else:
        # Cuando no hay una línea que identifique claramente la competición,
        # mantenemos la primera como competición por compatibilidad con el origen.
        tournament = text_lines[0]
        event_lines = text_lines[1:]

    matchup = " - ".join(event_lines) if event_lines else tournament

    matchup = EVENT_CLEANUP_TRAIL_RE.sub("", matchup).strip()

    return time_clean, matchup, channels, tournament, text_lines


def fetch_and_parse_agenda() -> list[dict]:
    results = []
    seen_events = set()
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    current_date_obj = today_date

    try:
        with create_http_session() as session:
            response = session.get(WIDGET_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Si la agenda usa filas de tabla, son la unidad de evento más fiable.
        # Solo recurrimos a contenedores genéricos cuando no existen filas.
        elements = soup.find_all("tr")
        if not elements:
            elements = soup.find_all(["article", "li", "div", "section", "p"])
        if not elements:
            elements = [node for node in soup.descendants if getattr(node, "name", None)]

        for element in elements:
            if not hasattr(element, "get_text"):
                continue

            el_text = element.get_text(" ", strip=True)
            date_match = DATE_RE.search(el_text)
            if date_match:
                try:
                    d, m, y = map(int, date_match.groups())
                    current_date_obj = date(y, m, d)
                except ValueError:
                    pass

            time_clean, event_str, channels, tournament, text_lines = parse_row_elements(element)
            if not time_clean or not channels:
                continue

            tv_blob = " ".join(channels).lower()
            blob = normalize_search_text(f"{' '.join(text_lines)} {tournament} {tv_blob}")

            comp_name, motor_event_title, is_fav = parse_motor_event(blob, tournament, text_lines)
            if comp_name:
                event_key = (current_date_obj, time_clean, comp_name, normalize_search_text(motor_event_title))
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                results.append({
                    "date_obj": current_date_obj,
                    "hora": time_clean,
                    "deporte": "Motor",
                    "icono": "🏆",
                    "competicion": comp_name,
                    "evento": motor_event_title,
                    "tv_list": channels,
                    "is_filtered": is_fav,
                    "is_configured": True,
                    "comp_key": "motor"
                })
                continue

            sport, icon, competition, is_favorite, is_configured, custom_event, comp_key = get_sport_and_competition(
                blob, tournament, tv_blob, text_lines
            )
            if not sport:
                continue

            normalized_competition = normalize_search_text(competition)
            if (
                normalized_competition == "brasil serie a"
                or ("brasil" in normalized_competition and "serie a" in normalized_competition)
            ):
                continue

            final_event = custom_event if custom_event else event_str
            final_event = EVENT_CLEANUP_TRAIL_RE.sub("", final_event).strip()

            if not EVENT_TEXT_RE.search(final_event):
                continue

            event_key = (current_date_obj, time_clean, normalize_search_text(competition), normalize_search_text(final_event))
            if event_key in seen_events: 
                continue
            seen_events.add(event_key)

            results.append({
                "date_obj": current_date_obj,
                "hora": time_clean,
                "deporte": sport,
                "icono": icon,
                "competicion": competition,
                "evento": final_event,
                "tv_list": channels,
                "is_filtered": is_favorite,
                "is_configured": is_configured,
                "comp_key": comp_key
            })

    except Exception as e:
        print(f"Error cargando la agenda general: {e}")

    results.sort(key=lambda x: (x["date_obj"], x["hora"]))
    return results


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agenda Deportiva</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg-color: #0f172a; --card-bg: #1e293b; --border-color: #334155; --text-main: #f8fafc; --text-muted: #94a3b8; --accent-blue: #3b82f6; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 16px 12px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 1150px; }
        .sticky-panel { position: sticky; top: 0; z-index: 1000; background: var(--bg-color); padding-top: 8px; margin-top: -8px; box-shadow: 0 8px 14px -12px rgba(0,0,0,.9); }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 8px; }
        h1 { font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 6px; }
        .icon-link { text-decoration: none; display: inline-flex; align-items: center; cursor: pointer; transition: transform 0.2s; }
        .icon-link:hover { transform: scale(1.15); }
        .header-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .btn-update { background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
        .btn-alt { background: #6366f1; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; text-decoration: none; transition: all 0.2s; display: inline-flex; align-items: center; }
        .btn-alt:hover { background: #4f46e5; }
        .last-update { font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; display: flex; justify-content: space-between; align-items: center; }
        .btn-toggle-chk { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 2px 8px; border-radius: 5px; font-size: 0.75rem; cursor: pointer; font-weight: 600; transition: all 0.2s; }
        .btn-toggle-chk:hover { background: rgba(59, 130, 246, 0.4); color: #ffffff; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-bottom: 12px; }
        .stat-card { background: var(--card-bg); padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }
        .stat-card.active-card { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }
        .stat-card .val { font-size: 1.1rem; font-weight: 700; color: var(--accent-blue); }
        .stat-card .lbl { font-size: 0.72rem; color: var(--text-muted); }

        .comp-filter-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 12px; font-size: 0.85rem; overflow: hidden; }
        .comp-filter-header { padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.05); user-select: none; }
        .comp-filter-header:hover { background: rgba(56, 189, 248, 0.1); }
        .comp-filter-content {
            padding: 10px 12px;
            border-top: 1px solid var(--border-color);
            display: grid;
            grid-template-columns: minmax(0, 4fr) minmax(145px, 1.1fr) minmax(105px, 0.8fr) minmax(115px, 0.8fr);
            align-items: start;
            gap: 14px;
        }
        .comp-group { min-width: 0; }
        .comp-section-title {
            font-weight: 700;
            color: #cbd5e1;
            font-size: 0.80rem;
            text-transform: uppercase;
            margin: 4px 0 8px;
        }
        .comp-checkboxes {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 7px 12px;
        }
        .comp-group:not(.football-group) .comp-checkboxes {
            grid-template-columns: 1fr;
        }
        .football-group .comp-checkboxes {
            grid-auto-flow: column;
            grid-template-rows: repeat(3, minmax(0, auto));
        }
        .comp-checkboxes label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            color: var(--text-main);
            font-size: 0.82rem;
            white-space: nowrap;
            min-width: 0;
        }
        .comp-checkboxes input[type="checkbox"] {
            accent-color: var(--accent-blue);
            width: 16px;
            height: 16px;
            cursor: pointer;
            flex: 0 0 16px;
            margin: 0;
        }
        @media (max-width: 900px) {
            .comp-filter-content {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px 16px;
            }
            .football-group { grid-column: 1 / -1; }
            .football-group .comp-checkboxes {
                grid-auto-flow: row;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                grid-template-rows: none;
            }
        }
        @media (max-width: 520px) {
            .comp-filter-content {
                grid-template-columns: 1fr;
                gap: 12px;
            }
            .football-group { grid-column: auto; }
            .football-group .comp-checkboxes {
                grid-auto-flow: row;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                grid-template-rows: none;
                gap: 8px 6px;
            }
            .comp-group:not(.football-group) .comp-checkboxes {
                grid-template-columns: 1fr;
            }
            .comp-section-title { font-size: 0.76rem; }
            .comp-checkboxes label { font-size: 0.80rem; }
        }
        
        .table-card { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: visible !important; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); margin-bottom: 80px; }
        table { width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }
        th { position: sticky; top: var(--sticky-panel-height, 0px); z-index: 900; background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; }
        tr.event-row:hover { background-color: #243146; }
        /* Identificación discreta del último horario anterior a la hora actual. */
        tr.event-row.previous-event td {
            background: rgba(56, 189, 248, 0.075);
            border-top: 1px solid rgba(56, 189, 248, 0.42);
            border-bottom: 1px solid rgba(56, 189, 248, 0.42);
        }
        tr.event-row.previous-event td:first-child {
            border-left: 3px solid #38bdf8;
        }
        tr.event-row.previous-event .time-badge {
            background: #0369a1;
            box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.35);
        }
        tr.event-row.previous-event .event-title::before {
            content: "EN JUEGO";
            display: block;
            color: #38bdf8;
            font-size: 0.62rem;
            font-weight: 800;
            letter-spacing: 0.65px;
            margin-bottom: 4px;
        }
        
        .sport-col { width: 155px !important; min-width: 155px !important; white-space: nowrap; }
        .time-col, .date-col { white-space: nowrap; }
        .sport-tag { font-weight: 600; white-space: nowrap; }
        .favorite-pin {
            display: inline-block;
            margin-right: 6px;
            color: #c4b5fd;
            font-size: 0.88rem;
            line-height: 1;
            vertical-align: 1px;
            filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.28));
        }
        body.favorites-view .favorite-pin { display: none; }
        .date-badge { display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
        .date-badge.today { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }
        .time-badge { background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }
        .comp-title { font-weight: 600; color: #38bdf8; font-size: 0.85rem; }
        .event-title { font-weight: 700; color: #ffffff; font-size: 0.9rem; }
        .tv-container { display: flex; flex-direction: column; gap: 4px; }
        
        .tv-badge { display: inline-block; background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; text-decoration: none; transition: all 0.2s ease; cursor: pointer; }
        .tv-badge:hover { background: rgba(99, 102, 241, 0.35); color: #a5b4fc; border-color: #818cf8; transform: translateY(-1px); }
        .tv-badge-no-link { cursor: default; }
        .tv-badge-no-link:hover { transform: none; background: rgba(99, 102, 241, 0.15); color: #818cf8; border-color: rgba(99, 102, 241, 0.3); }

        .empty-state { text-align: center; padding: 30px; color: var(--text-muted); font-size: 1rem; }

        @media screen and (max-width: 768px) and (orientation: portrait) and (pointer: coarse) {
            body { padding: 8px 6px; }
            h1 { font-size: 1.25rem; }
            .stats-grid { grid-template-columns: repeat(3, 1fr); gap: 6px; }
            .stat-card { padding: 6px 8px; }
            .football-group .comp-checkboxes { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
            .comp-group:not(.football-group) .comp-checkboxes { grid-template-columns: 1fr !important; }
            
            thead { display: none; }
            table, tbody { display: block; width: 100%; }
            .table-card { background: transparent; border: none; box-shadow: none; }
            
            tr.event-row {
                display: flex;
                flex-direction: column;
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 10px;
                gap: 6px;
            }
            tr.event-row.previous-event {
                border-color: rgba(56, 189, 248, 0.75);
                box-shadow: inset 3px 0 0 #38bdf8, 0 0 0 1px rgba(56, 189, 248, 0.12);
            }
            
            td { padding: 0; border: none; width: auto !important; white-space: normal; }
            .date-col { display: inline-block; order: 0; }
            .time-col { order: 1; display: inline-block; }
            .sport-col { order: 2; margin-left: 8px; display: inline-block; font-size: 0.95rem; width: auto !important; min-width: 0 !important; }
            .comp-col { order: 3; margin-top: 4px; }
            .comp-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }
            .event-col { order: 4; margin: 2px 0 4px 0; }
            .event-title { font-size: 1rem; line-height: 1.35; }
            .tv-col { order: 5; margin-top: 4px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px; }
            .tv-badge { font-size: 0.72rem; padding: 4px 8px; white-space: nowrap; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="sticky-panel" id="stickyPanel">
    <header>
        <div><h1><a href="https://daddylive.pk/" target="_blank" class="icon-link" title="Abrir DaddyLive HD">⚡</a> Agenda Deportiva</h1></div>
        <div class="header-controls">
            <a href="https://{DOMAIN}/es/football.html" target="_blank" class="btn-alt">⚽ Fútbol</a>
            <a href="https://{DOMAIN}/es/basketball.html" target="_blank" class="btn-alt">🏀 Baloncesto</a>
            <a href="https://{DOMAIN}/es/tennis.html" target="_blank" class="btn-alt">🎾 Tenis</a>
            <a href="https://{DOMAIN}/es/motorsport.html" target="_blank" class="btn-alt">🏆 Motor</a>
            <button class="btn-update" onclick="location.reload()">🔄 Actualizar</button>
        </div>
        <div class="last-update">
            <span>Hora actual: <strong id="liveClock">--:--:--</strong></span>
            <span>Última actualización: <strong>{FECHA_ACT}</strong></span>
        </div>
    </header>
    <div class="stats-grid">
        <div class="stat-card" id="card-favoritos" onclick="setFilter('favoritos')">
            <div><div class="lbl">Favoritos</div><div class="val" style="color:#a78bfa">{FILTERED_CNT}</div></div><div style="font-size:1.1rem">📌</div>
        </div>
        <div class="stat-card" id="card-madrugada" onclick="setFilter('madrugada')">
            <div><div class="lbl">Madrugada</div><div class="val" style="color:#60a5fa">{MADRUGADA_CNT}</div></div><div style="font-size:1.1rem">💤</div>
        </div>
        <div class="stat-card" id="card-manana" onclick="setFilter('manana')">
            <div><div class="lbl">Mañana</div><div class="val" style="color:#fbbf24">{MANANA_CNT}</div></div><div style="font-size:1.1rem">☀️</div>
        </div>
        <div class="stat-card" id="card-tarde" onclick="setFilter('tarde')">
            <div><div class="lbl">Tarde</div><div class="val" style="color:#f97316">{TARDE_CNT}</div></div><div style="font-size:1.1rem">🌇</div>
        </div>
        <div class="stat-card" id="card-noche" onclick="setFilter('noche')">
            <div><div class="lbl">Noche</div><div class="val" style="color:#a78bfa">{NOCHE_CNT}</div></div><div style="font-size:1.1rem">🌙</div>
        </div>
        <div class="stat-card" id="card-proximamente" onclick="setFilter('proximamente')">
            <div><div class="lbl">Próximamente</div><div class="val">{TOTAL_CNT}</div></div><div style="font-size:1.1rem">📅</div>
        </div>
    </div>
    
    <div class="comp-filter-panel">
        <div class="comp-filter-header" onclick="toggleCompPanel()">
            <span>⚙️ Deportes y Competiciones</span>
            <div style="display: flex; align-items: center; gap: 10px;">
                <button class="btn-toggle-chk" onclick="toggleAllCheckboxes(event)">Desmarcar todo / Marcar todo</button>
                <span id="compToggleIcon">▼</span>
            </div>
        </div>
        <div class="comp-filter-content" id="compFilterContent" style="display: none;">
            <section class="comp-group football-group">
                <div class="comp-section-title">⚽ FÚTBOL</div>
                <div class="comp-checkboxes">
                    <label><input type="checkbox" class="comp-chk" value="laliga" checked onchange="applyFilters()"> LaLiga</label>
                    <label><input type="checkbox" class="comp-chk" value="champions" checked onchange="applyFilters()"> Champions League</label>
                    <label><input type="checkbox" class="comp-chk" value="copadelrey" checked onchange="applyFilters()"> Copa del Rey</label>
                    <label><input type="checkbox" class="comp-chk" value="premier" checked onchange="applyFilters()"> Premier League</label>
                    <label><input type="checkbox" class="comp-chk" value="bundesliga" checked onchange="applyFilters()"> Bundesliga</label>
                    <label><input type="checkbox" class="comp-chk" value="seriea" checked onchange="applyFilters()"> Serie A</label>
                    <label><input type="checkbox" class="comp-chk" value="ligue1" checked onchange="applyFilters()"> Ligue 1</label>
                    <label><input type="checkbox" class="comp-chk" value="ligaportugal" checked onchange="applyFilters()"> Liga Portugal</label>
                    <label><input type="checkbox" class="comp-chk" value="eredivisie" checked onchange="applyFilters()"> Eredivisie</label>
                    <label><input type="checkbox" class="comp-chk" value="mundial" checked onchange="applyFilters()"> Copa Mundial</label>
                    <label><input type="checkbox" class="comp-chk" value="eurocopa" checked onchange="applyFilters()"> Eurocopa</label>
                    <label><input type="checkbox" class="comp-chk" value="nationsleague" checked onchange="applyFilters()"> Nations League</label>
                </div>
            </section>
            <section class="comp-group">
                <div class="comp-section-title">🏀 BALONCESTO</div>
                <div class="comp-checkboxes">
                    <label><input type="checkbox" class="comp-chk" value="ligaendesa" checked onchange="applyFilters()"> ACB</label>
                    <label><input type="checkbox" class="comp-chk" value="euroliga" checked onchange="applyFilters()"> Euroliga</label>
                    <label><input type="checkbox" class="comp-chk" value="nba" checked onchange="applyFilters()"> NBA</label>
                </div>
            </section>
            <section class="comp-group">
                <div class="comp-section-title">🎾 TENIS</div>
                <div class="comp-checkboxes">
                    <label><input type="checkbox" class="comp-chk" value="tenis" checked onchange="applyFilters()"> ATP / WTA</label>
                </div>
            </section>
            <section class="comp-group">
                <div class="comp-section-title">🏆 MOTOR</div>
                <div class="comp-checkboxes">
                    <label><input type="checkbox" class="comp-chk" value="motor" checked onchange="applyFilters()"> F1 / MotoGP</label>
                </div>
            </section>
        </div>
    </div>
    </div>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th class="date-col" style="width: 70px;">Fecha</th>
                    <th class="time-col" style="width: 70px;">Hora</th>
                    <th class="sport-col" style="width: 155px;">Deporte</th>
                    <th class="comp-col" style="width: 140px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 250px;">Canal TV</th>
                </tr>
            </thead>
            <tbody id="agendaTable">
                {ROWS_HTML}
            </tbody>
        </table>
    </div>
</div>
<script>
const TODAY_DATE_STR = "{TODAY_DATE_STR}";
let currentFilter = 'favoritos';

function updateLiveClock() {
    const now = new Date();
    const options = { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    const timeStr = new Intl.DateTimeFormat('es-ES', options).format(now);
    const clockElem = document.getElementById('liveClock');
    if (clockElem) clockElem.textContent = timeStr;
}
setInterval(updateLiveClock, 1000);
updateLiveClock();

function cleanStr(str) {
    return (str || '')
        .toLowerCase()
        .replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i')
        .replace(/ó/g, 'o').replace(/ú/g, 'u').replace(/ç/g, 'c')
        .replace(/ñ/g, 'n')
        .replace(new RegExp('[|,;:/]+', 'g'), ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function toggleCompPanel() {
    if (currentFilter === 'favoritos') return;
    const content = document.getElementById('compFilterContent');
    const icon = document.getElementById('compToggleIcon');
    if (content.style.display === 'none') {
        content.style.display = 'grid';
        icon.textContent = '▲';
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
    }
    updateStickyHeadingOffset();
}

function toggleAllCheckboxes(event) {
    if (event) event.stopPropagation();
    const checkboxes = document.querySelectorAll('.comp-chk');
    const anyChecked = Array.from(checkboxes).some(chk => chk.checked);
    checkboxes.forEach(chk => chk.checked = !anyChecked);
    applyFilters();
}

function updateStickyHeadingOffset() {
    const panel = document.getElementById('stickyPanel');
    if (!panel) return;
    document.documentElement.style.setProperty('--sticky-panel-height', panel.getBoundingClientRect().height + 'px');
}

function setFilter(filterType) {
    currentFilter = cleanStr(filterType);
    document.body.classList.toggle('favorites-view', currentFilter === 'favoritos');
    document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active-card'));
    const activeCard = document.getElementById('card-' + currentFilter);
    if (activeCard) activeCard.classList.add('active-card');

    const content = document.getElementById('compFilterContent');
    const icon = document.getElementById('compToggleIcon');

    content.style.display = 'none';
    icon.textContent = '▼';

    if (currentFilter !== 'favoritos') {
        document.querySelectorAll('.comp-chk').forEach(chk => chk.checked = true);
    }

    applyFilters();
}

function filterTable() { applyFilters(); }

function highlightPreviousEvents() {
    const rows = Array.from(document.querySelectorAll('#agendaTable tr.event-row[data-ts]'));
    rows.forEach(row => row.classList.remove('previous-event'));

    // La agenda trabaja con precisión de minuto: solo cuentan inicios
    // anteriores al minuto actual, no los que empiezan en este mismo minuto.
    const currentMinuteTimestamp = Math.floor(Date.now() / 60000) * 60000;
    let previousTimestamp = null;

    rows.forEach(row => {
        if (row.getAttribute('data-date') !== TODAY_DATE_STR) return;

        const timestamp = Number(row.getAttribute('data-ts'));
        if (!Number.isFinite(timestamp) || timestamp >= currentMinuteTimestamp) return;

        if (previousTimestamp === null || timestamp > previousTimestamp) {
            previousTimestamp = timestamp;
        }
    });

    if (previousTimestamp === null) return;

    // Se resaltan todos los eventos que comparten el último horario anterior.
    rows.forEach(row => {
        if (
            row.getAttribute('data-date') === TODAY_DATE_STR &&
            Number(row.getAttribute('data-ts')) === previousTimestamp
        ) {
            row.classList.add('previous-event');
        }
    });
}

window.addEventListener('load', () => {
    const nowMadrid = new Date(new Date().toLocaleString("en-US", {timeZone: "Europe/Madrid"}));
    const h = nowMadrid.getHours();
    const m = nowMadrid.getMinutes();
    const totalMins = h * 60 + m;
    let initialSlot = 'noche';
    if (totalMins <= 419) initialSlot = 'madrugada';
    else if (totalMins <= 839) initialSlot = 'manana';
    else if (totalMins <= 1229) initialSlot = 'tarde';
    else initialSlot = 'noche';

    highlightPreviousEvents();
    setFilter(initialSlot);
    updateStickyHeadingOffset();
});

window.addEventListener('resize', () => {
    updateStickyHeadingOffset();
});

// Recalcula el desplazamiento si cambia la altura del panel fijo (p. ej. al
// abrir/cerrar filtros o al cambiar de orientación en móvil/Fire TV).
if ('ResizeObserver' in window) {
    const stickyPanel = document.getElementById('stickyPanel');
    if (stickyPanel) {
        const stickyObserver = new ResizeObserver(updateStickyHeadingOffset);
        stickyObserver.observe(stickyPanel);
    }
}

function applyFilters() {
    const checkedComps = new Set();
    document.querySelectorAll('.comp-chk:checked').forEach(chk => {
        checkedComps.add(chk.value);
    });

    const table = document.getElementById('agendaTable');
    if (!table) return;
    const trs = table.getElementsByClassName('event-row');
    let visibleCount = 0;
    for (let i = 0; i < trs.length; i++) {
        const tr = trs[i];
        if (tr.id === 'dynamicEmptyState') continue;

        const rowSlot = cleanStr(tr.getAttribute('data-slot'));
        const isFiltered = tr.getAttribute('data-filtered') === 'true';
        const sport = cleanStr(tr.getAttribute('data-sport')); 
        const compKey = tr.getAttribute('data-comp-key') || '';
        const rowDate = tr.getAttribute('data-date');

        let matchesFilter = false;
        let matchesComp = true;

        if (currentFilter === 'proximamente') {
            matchesFilter = (rowDate > TODAY_DATE_STR);
            if (sport === 'tenis') {
                matchesComp = checkedComps.has('tenis');
            } else if (sport === 'motor') {
                matchesComp = checkedComps.has('motor');
            } else if (sport === 'futbol' || sport === 'baloncesto') {
                matchesComp = compKey ? checkedComps.has(compKey) : false;
            } else {
                matchesComp = false;
            }
        } else if (currentFilter === 'favoritos') {
            matchesFilter = isFiltered;
            matchesComp = true;
        } else {
            const isToday = (rowDate === TODAY_DATE_STR);
            matchesFilter = isToday && (rowSlot === currentFilter);

            if (sport === 'tenis') {
                matchesComp = checkedComps.has('tenis');
            } else if (sport === 'motor') {
                matchesComp = checkedComps.has('motor');
            } else if (sport === 'futbol' || sport === 'baloncesto') {
                matchesComp = compKey ? checkedComps.has(compKey) : false;
            } else {
                matchesComp = false;
            }
        }

        if (matchesFilter && matchesComp) {
            tr.style.display = '';
            visibleCount++;
        } else {
            tr.style.display = 'none';
        }
    }

    let emptyRow = document.getElementById('dynamicEmptyState');
    if (visibleCount === 0) {
        if (!emptyRow) {
            emptyRow = document.createElement('tr');
            emptyRow.id = 'dynamicEmptyState';
            emptyRow.innerHTML = '<td colspan="6" class="empty-state">😴 No hay eventos que coincidan con la selección.</td>';
            table.appendChild(emptyRow);
        } else { emptyRow.style.display = ''; }
    } else { if (emptyRow) emptyRow.style.display = 'none'; }
}
</script>
</body>
</html>"""


def generate_html(events):
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")
    
    filtered_cnt = sum(1 for event in events if event["is_filtered"])
    slot_counts = Counter(get_time_slot(event["hora"]) for event in events if event["date_obj"] == today_date)
    total_cnt = sum(1 for event in events if event["date_obj"] > today_date)
    domain = get_dynamic_domain()

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
    else:
        for ev in events:
            tv_badges_list = []
            for channel in ev["tv_list"]:
                safe_channel = escape(str(channel), quote=True)
                app_key = get_channel_app(channel)
                app_intent = escape(get_firetv_intent(channel), quote=True)
                app_label = {
                    "movistar": "Movistar Plus+",
                    "dazn": "DAZN",
                    "prime": "Prime Video",
                    "kodi": "Kodi",
                }[app_key]

                if app_key == "kodi":
                    tv_badges_list.append(
                        f'<span class="tv-badge tv-badge-no-link" title="Canal {safe_channel}">{safe_channel}</span>'
                    )
                else:
                    tv_badges_list.append(
                        f'<a href="{app_intent}" class="tv-badge" title="Abrir {app_label} en Fire TV para el canal {safe_channel}">{safe_channel} 🔗</a>'
                    )

            tv_badges = "".join(tv_badges_list)
            
            ev_date = ev["date_obj"]
            if ev_date == today_date:
                date_badge_html = '<span class="date-badge today">Hoy</span>'
            else:
                date_badge_html = f'<span class="date-badge">{ev_date.strftime("%d/%m")}</span>'

            slot = get_time_slot(ev["hora"])
            safe_slot = escape(clean_key(slot), quote=True)

            search_text = normalize_search_text(" ".join(
                [str(ev_date), ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
            ))
            safe_search = escape(search_text, quote=True)
            event_datetime = datetime.combine(ev_date, datetime.strptime(ev["hora"], "%H:%M").time()).replace(tzinfo=spain_tz)
            event_timestamp = int(event_datetime.timestamp() * 1000)
            safe_timestamp = str(event_timestamp)
            safe_date_str = escape(ev_date.isoformat(), quote=True)
            safe_sport_key = escape(clean_key(ev["deporte"]), quote=True)
            safe_comp_key = escape(str(ev.get("comp_key", "")), quote=True)
            safe_time = escape(str(ev["hora"]))
            safe_icon = escape(str(ev["icono"]))
            safe_sport = escape(str(ev["deporte"]))
            safe_competition = escape(str(ev["competicion"]))
            safe_event = escape(str(ev["evento"]))

            is_filtered_str = str(ev["is_filtered"]).lower()
            is_configured_str = str(ev["is_configured"]).lower()
            favorite_pin_html = (
                '<span class="favorite-pin" title="Favorito" aria-label="Favorito">📌</span>'
                if ev["is_filtered"] else ""
            )
            rows_list.append(
                f'<tr class="event-row" data-date="{safe_date_str}" data-ts="{safe_timestamp}" data-time="{safe_time}" data-slot="{safe_slot}" data-sport="{safe_sport_key}" data-comp-key="{safe_comp_key}" data-filtered="{is_filtered_str}" data-configured="{is_configured_str}" data-search="{safe_search}">'
                f'<td class="date-col">{date_badge_html}</td>'
                f'<td class="time-col"><span class="time-badge">{safe_time}</span></td>'
                f'<td class="sport-col"><span class="sport-tag">{safe_icon} {safe_sport}</span></td>'
                f'<td class="comp-col"><div class="comp-title">{favorite_pin_html}{safe_competition}</div></td>'
                f'<td class="event-col"><div class="event-title">{safe_event}</div></td>'
                f'<td class="tv-col"><div class="tv-container">{tv_badges}</div></td>'
                f'</tr>'
            )

    rows_html = "".join(rows_list)

    html = HTML_TEMPLATE.replace("{DOMAIN}", domain)
    html = html.replace("{FECHA_ACT}", fecha_act)
    html = html.replace("{FILTERED_CNT}", str(filtered_cnt))
    html = html.replace("{MADRUGADA_CNT}", str(slot_counts["madrugada"]))
    html = html.replace("{MANANA_CNT}", str(slot_counts["manana"]))
    html = html.replace("{TARDE_CNT}", str(slot_counts["tarde"]))
    html = html.replace("{NOCHE_CNT}", str(slot_counts["noche"]))
    html = html.replace("{TOTAL_CNT}", str(total_cnt))
    html = html.replace("{TODAY_DATE_STR}", today_date.isoformat())
    html = html.replace("{ROWS_HTML}", rows_html)
    return html


if __name__ == "__main__":
    events = fetch_and_parse_agenda()
    html_content = generate_html(events)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(
        "Archivo index.html generado con éxito. "
        f"Eventos totales ordenados cronológicamente: {len(events)}"
    )
