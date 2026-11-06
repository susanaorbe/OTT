#!/usr/bin/env python3
"""Servidor local de Mi TV con CDN Live TV y agenda personalizada."""
from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "docs"
API_BASE = "https://api.cdnlivetv.tv/api/v1"
API_QUERY = "?user=cdnlivetv&plan=free"
TIMEOUT = 15


def fetch_json(path: str):
    url = f"{API_BASE}/{path}/{API_QUERY}"
    request = Request(url, headers={"User-Agent": "MiTV/0.2 (personal project)", "Accept": "application/json"})
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"La API respondió con HTTP {response.status}")
        payload = response.read()
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("La API no devolvió un objeto JSON")
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def _json(self, status: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        routes = {"/api/channels": "channels", "/api/events": "events/sports"}
        if self.path in routes:
            try:
                data = fetch_json(routes[self.path])
                self._json(200, {"ok": True, "data": data})
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                self._json(502, {"ok": False, "error": f"No se pudo consultar CDN Live TV: {exc}"})
            except Exception as exc:
                self._json(500, {"ok": False, "error": f"Error inesperado: {exc}"})
            return

        if self.path == "/api/futbolenlatv":
            try:
                from agenda_futbolenlatv import get_agenda_payload
                data = get_agenda_payload()
                self._json(200, {"ok": True, "data": data})
            except Exception as exc:
                self._json(502, {"ok": False, "error": f"No se pudo consultar Futbolenlatv: {exc}"})
            return

        if self.path == "/config/channels.json":
            try:
                raw = (ROOT / "config" / "channels.json").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            except OSError as exc:
                self._json(500, {"ok": False, "error": f"No se pudo leer la configuración: {exc}"})
            return

        if self.path == "/" or self.path.startswith("/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        print("[Mi TV] " + (fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Servidor local de Mi TV")
    parser.add_argument("--host", default="127.0.0.1", help="127.0.0.1 (solo este equipo) o 0.0.0.0 (red local)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Mi TV disponible en http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print("Acceso desde otros dispositivos de tu red local: http://IP-DEL-ORDENADOR:%s" % args.port)
    print("Pulsa Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando Mi TV...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
