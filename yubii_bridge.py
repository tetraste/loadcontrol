#!/usr/bin/env python3
"""Ponte HTTP fra widget telefono e Yubii Home (Nice / Fibaro Home Center).

Espone URL semplici e GET-friendly che un widget della schermata home del
telefono (iOS Scorciatoie, Android HTTP Shortcuts/Tasker, o un semplice
collegamento browser) può chiamare per:

  * accendere / spegnere un dispositivo (relè, luce, presa)
  * impostare la temperatura di un termostato (accensione riscaldamento)
  * cambiare la modalità di un termostato (Heat / Off / Auto / Cool)
  * lanciare una scena Yubii
  * elencare dispositivi e scene (per scoprire gli ID)

Il ponte tiene le credenziali del Home Center al suo interno: il widget chiama
solo questo ponte (protetto da un token condiviso), mai direttamente Yubii.

Perché serve un ponte?  La REST API di Fibaro/Yubii usa azioni con POST e body
JSON e autenticazione Basic: scomoda da chiamare da un widget telefono.  Il
ponte la traduce in URL «puliti» come:

    http://<host-ponte>:8770/thermostat/12?temp=21&token=SEGRETO

Esempio di avvio (variabili d'ambiente, consigliato per systemd):

    export YUBII_HOST=192.168.1.20          # IP del Yubii Home / Home Center
    export YUBII_USER=admin
    export YUBII_PASSWORD=la-mia-password
    export BRIDGE_TOKEN=un-token-lungo-a-caso
    python yubii_bridge.py

Oppure tutto da riga di comando:

    python yubii_bridge.py --yubii-host 192.168.1.20 \
        --yubii-user admin --yubii-password segreta \
        --token un-token-lungo-a-caso --port 8770

Endpoint disponibili (tutti accettano GET così il widget funziona con un URL):

    /                                 stato del ponte (no token)
    /devices                          elenco dispositivi (id, nome, tipo)
    /scenes                           elenco scene (id, nome)
    /device/<id>/on                   accende il dispositivo (turnOn)
    /device/<id>/off                  spegne il dispositivo (turnOff)
    /device/<id>/level/<n>            imposta livello/dimmer 0-99 (setValue)
    /thermostat/<id>?temp=21          imposta setpoint riscaldamento a 21°
    /thermostat/<id>/mode/<mode>      imposta modalità (Heat/Off/Auto/Cool…)
    /scene/<id>/run                   esegue la scena
    /device/<id>/action/<name>?args=21,Heat   azione generica (escape hatch)

Tutti gli endpoint (tranne `/`) richiedono il token, passato come
`?token=...` nell'URL oppure come header `X-Bridge-Token`.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit


# --------------------------------------------------------------------------- #
# Client Yubii / Fibaro Home Center
# --------------------------------------------------------------------------- #
class YubiiClient:
    """Wrapper minimale sulla REST API di Fibaro Home Center (Yubii Home)."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        scheme: str = "http",
        timeout: float = 10.0,
    ) -> None:
        self.base = f"{scheme}://{host}/api"
        self.timeout = timeout
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._auth = f"Basic {token}"

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self._auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        # X-Fibaro-Version richiesto da alcune azioni su HC3.
        req.add_header("X-Fibaro-Version", "2")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode(errors="replace")

    # --- letture ---------------------------------------------------------- #
    def list_devices(self) -> list:
        data = self._request("GET", "/devices")
        out = []
        for d in data or []:
            out.append(
                {
                    "id": d.get("id"),
                    "name": d.get("name"),
                    "type": d.get("type"),
                    "room": d.get("roomID"),
                    "enabled": d.get("enabled"),
                }
            )
        return out

    def list_scenes(self) -> list:
        data = self._request("GET", "/scenes")
        return [{"id": s.get("id"), "name": s.get("name")} for s in (data or [])]

    # --- azioni ----------------------------------------------------------- #
    def call_action(self, device_id: int, action: str, args: Optional[list] = None) -> Any:
        body = {"args": args or []}
        return self._request("POST", f"/devices/{device_id}/action/{action}", body)

    def run_scene(self, scene_id: int) -> Any:
        return self._request("POST", f"/scenes/{scene_id}/execute", {})


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #
def _coerce(value: str) -> Any:
    """Converte una stringa argomento in int/float se possibile, altrimenti str."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
class BridgeHandler(BaseHTTPRequestHandler):
    # iniettati dal server
    client: YubiiClient
    token: str

    server_version = "YubiiBridge/1.0"

    def log_message(self, fmt: str, *fmt_args: Any) -> None:  # noqa: A003
        sys.stderr.write(
            "%s - %s\n" % (self.address_string(), fmt % fmt_args)
        )

    # --- utilità di risposta --------------------------------------------- #
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, **payload: Any) -> None:
        payload.setdefault("ok", True)
        self._send(200, payload)

    def _err(self, code: int, message: str) -> None:
        self._send(code, {"ok": False, "error": message})

    # --- autenticazione --------------------------------------------------- #
    def _authorized(self, query: dict) -> bool:
        if not self.token:
            return True  # token non configurato: ponte aperto (sconsigliato)
        supplied = self.headers.get("X-Bridge-Token")
        if not supplied:
            vals = query.get("token")
            supplied = vals[0] if vals else None
        return supplied == self.token

    # --- routing ---------------------------------------------------------- #
    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        parts = urlsplit(self.path)
        segments = [s for s in parts.path.split("/") if s]
        query = parse_qs(parts.query)

        # health check, nessun token richiesto
        if not segments:
            self._ok(service="yubii-bridge", endpoints_require_token=bool(self.token))
            return

        if not self._authorized(query):
            self._err(401, "token mancante o errato")
            return

        try:
            self._route(segments, query)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace") if exc.fp else ""
            self._err(502, f"Yubii ha risposto {exc.code}: {detail[:300]}")
        except urllib.error.URLError as exc:
            self._err(502, f"impossibile raggiungere Yubii: {exc.reason}")
        except Exception as exc:  # pragma: no cover - difensivo
            self._err(500, f"{type(exc).__name__}: {exc}")

    def _route(self, segments: list, query: dict) -> None:
        head = segments[0]

        if head == "devices" and len(segments) == 1:
            self._ok(devices=self.client.list_devices())
            return

        if head == "scenes" and len(segments) == 1:
            self._ok(scenes=self.client.list_scenes())
            return

        if head == "scene" and len(segments) == 3 and segments[2] == "run":
            sid = self._as_int(segments[1])
            result = self.client.run_scene(sid)
            self._ok(action="scene.run", scene=sid, result=result)
            return

        if head == "thermostat" and len(segments) == 2:
            # /thermostat/<id>?temp=21   (opzionale &mode=Heat)
            did = self._as_int(segments[1])
            temp = query.get("temp")
            mode = query.get("mode")
            if not temp and not mode:
                self._err(400, "specificare ?temp=<gradi> e/o &mode=<modo>")
                return
            done = []
            if mode:
                self.client.call_action(did, "setThermostatMode", [mode[0]])
                done.append(f"mode={mode[0]}")
            if temp:
                self.client.call_action(
                    did, "setHeatingThermostatSetpoint", [_coerce(temp[0])]
                )
                done.append(f"temp={temp[0]}")
            self._ok(action="thermostat", device=did, applied=done)
            return

        if head == "thermostat" and len(segments) == 4 and segments[2] == "mode":
            did = self._as_int(segments[1])
            mode = segments[3]
            self.client.call_action(did, "setThermostatMode", [mode])
            self._ok(action="thermostat.mode", device=did, mode=mode)
            return

        if head == "device" and len(segments) == 3:
            did = self._as_int(segments[1])
            verb = segments[2]
            if verb == "on":
                self.client.call_action(did, "turnOn")
                self._ok(action="device.on", device=did)
                return
            if verb == "off":
                self.client.call_action(did, "turnOff")
                self._ok(action="device.off", device=did)
                return

        if head == "device" and len(segments) == 4 and segments[2] == "level":
            did = self._as_int(segments[1])
            level = self._as_int(segments[3])
            self.client.call_action(did, "setValue", [level])
            self._ok(action="device.level", device=did, level=level)
            return

        if head == "device" and len(segments) == 4 and segments[2] == "action":
            # escape hatch: /device/<id>/action/<name>?args=21,Heat
            did = self._as_int(segments[1])
            name = segments[3]
            raw_args = query.get("args", [""])[0]
            args = [_coerce(a) for a in raw_args.split(",")] if raw_args else []
            result = self.client.call_action(did, name, args)
            self._ok(action=name, device=did, args=args, result=result)
            return

        self._err(404, f"endpoint sconosciuto: /{'/'.join(segments)}")

    def _as_int(self, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"id non valido: {value!r}")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def _env_default(name: str, fallback: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, fallback)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ponte HTTP fra widget telefono e Yubii Home (Fibaro HC).",
    )
    parser.add_argument(
        "--yubii-host",
        default=_env_default("YUBII_HOST"),
        help="IP/hostname del Yubii Home / Home Center (env YUBII_HOST)",
    )
    parser.add_argument(
        "--yubii-user",
        default=_env_default("YUBII_USER"),
        help="utente Yubii/Fibaro (env YUBII_USER)",
    )
    parser.add_argument(
        "--yubii-password",
        default=_env_default("YUBII_PASSWORD"),
        help="password Yubii/Fibaro (env YUBII_PASSWORD)",
    )
    parser.add_argument(
        "--yubii-scheme",
        default=_env_default("YUBII_SCHEME", "http"),
        choices=["http", "https"],
        help="schema per raggiungere Yubii (default http)",
    )
    parser.add_argument(
        "--token",
        default=_env_default("BRIDGE_TOKEN"),
        help="token condiviso che il widget deve presentare (env BRIDGE_TOKEN)",
    )
    parser.add_argument(
        "--host",
        default=_env_default("BRIDGE_BIND", "0.0.0.0"),
        help="indirizzo su cui il ponte ascolta (default 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_env_default("BRIDGE_PORT", "8770")),
        help="porta del ponte (default 8770)",
    )
    args = parser.parse_args()

    missing = [
        n
        for n, v in (
            ("--yubii-host/YUBII_HOST", args.yubii_host),
            ("--yubii-user/YUBII_USER", args.yubii_user),
            ("--yubii-password/YUBII_PASSWORD", args.yubii_password),
        )
        if not v
    ]
    if missing:
        parser.error("parametri mancanti: " + ", ".join(missing))

    if not args.token:
        print(
            "ATTENZIONE: nessun token impostato — il ponte è APERTO a chiunque "
            "sulla rete. Imposta --token / BRIDGE_TOKEN.",
            file=sys.stderr,
        )

    client = YubiiClient(
        host=args.yubii_host,
        user=args.yubii_user,
        password=args.yubii_password,
        scheme=args.yubii_scheme,
    )

    # inietta le dipendenze nell'handler
    BridgeHandler.client = client
    BridgeHandler.token = args.token or ""

    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print(
        f"Ponte Yubii in ascolto su http://{args.host}:{args.port}  "
        f"→ Yubii {args.yubii_scheme}://{args.yubii_host}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto del ponte.", file=sys.stderr)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
