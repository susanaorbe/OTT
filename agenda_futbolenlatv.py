from datetime import datetime, date
import zoneinfo
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zoneinfo import ZoneInfoNotFoundError
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURACIÓN Y UTILIDADES DE FUTBOLENLATV
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
        raise RuntimeError(f"No se pudo obtener la agenda de Futbolenlatv: {e}") from e

    results.sort(key=lambda x: (x["date_obj"], x["hora"]))
    return results


def get_agenda_payload():
    """Obtiene la agenda personalizada y la convierte a JSON serializable."""
    events = fetch_and_parse_agenda()
    return {
        "source": "futbolenlatv",
        "count": len(events),
        "events": [
            {
                "id": "ftv:{}:{}:{}:{}".format(
                    item["date_obj"].isoformat(), item["hora"],
                    normalize_search_text(item["competicion"]),
                    normalize_search_text(item["evento"]),
                ),
                "date": item["date_obj"].isoformat(),
                "time": item["hora"],
                "sport": item["deporte"],
                "icon": item["icono"],
                "competition": item["competicion"],
                "event": item["evento"],
                "channels": item["tv_list"],
                "featured": bool(item["is_filtered"]),
                "competition_key": item.get("comp_key", ""),
            }
            for item in events
        ],
    }

