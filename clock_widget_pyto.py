"""
Clock Widget per Pyto
Orologio bordeaux, % giornata, batteria, meteo

Installazione:
  1. Copia in Pyto (incolla o importa da iCloud)
  2. Aggiungi widget "Run Script" alla home → scegli questo script
  3. Prima esecuzione: concedi i permessi Posizione
"""

import widgets as wd
from datetime import datetime, timedelta
import requests

# ── Moduli iOS opzionali ─────────────────────────────────────────────

try:
    import battery as _batt
    def get_battery():
        return _batt.level * 100, _batt.charging
except ImportError:
    def get_battery():
        return None, False

try:
    import location as _loc
    _has_location = True
except ImportError:
    _has_location = False

# ── WMO weather codes ────────────────────────────────────────────────

def wmo_info(code):
    if code == 0:   return "☀️", "Sereno"
    if code == 1:   return "🌤️", "Poco nuvoloso"
    if code == 2:   return "⛅", "Parz. nuvoloso"
    if code == 3:   return "☁️", "Nuvoloso"
    if code <= 48:  return "🌫️", "Nebbia"
    if code <= 55:  return "🌦️", "Pioggerella"
    if code <= 65:  return "🌧️", "Pioggia"
    if code <= 77:  return "❄️", "Neve"
    if code <= 82:  return "🌧️", "Rovesci"
    if code <= 86:  return "🌨️", "Neve a rovesci"
    return "⛈️", "Temporale"

# ── Meteo via Open-Meteo (gratuito, no API key) ──────────────────────

def fetch_weather():
    if not _has_location:
        return None
    try:
        _loc.start_updating()
        loc = _loc.get_location()
        _loc.stop_updating()
        lat = round(loc.latitude, 4)
        lon = round(loc.longitude, 4)
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=auto&forecast_days=1"
        )
        data = requests.get(url, timeout=5).json()
        return {
            "temp":     round(data["current"]["temperature_2m"]),
            "code":     data["current"]["weather_code"],
            "max_temp": round(data["daily"]["temperature_2m_max"][0]),
            "min_temp": round(data["daily"]["temperature_2m_min"][0]),
        }
    except Exception:
        return None

# ── Helpers ──────────────────────────────────────────────────────────

def c(h):
    h = h.lstrip("#")
    return wd.Color.rgb(int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)

def bar(pct, width=26):
    n = max(0, min(width, round((pct or 0) / 100 * width)))
    return "█" * n + "░" * (width - n)

def t(text, font_name, size, color_hex):
    return wd.Text(text=text, font=wd.Font(font_name, size), color=c(color_hex))

DAYS_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
MONTHS_IT = ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"]

# ── Costruzione widget ────────────────────────────────────────────────

def build_widget(now: datetime, wx, batt_pct, batt_chrg) -> wd.Widget:
    elapsed = now.hour * 3600 + now.minute * 60 + now.second
    day_pct = elapsed / 86400 * 100

    # Colori
    CLR_BG   = "#0d0d1a"
    CLR_TIME = "#b5273f"   # bordeaux
    CLR_DATE = "#94a3b8"
    CLR_DAY  = "#facc15"
    CLR_WX   = "#e2e8f0"
    CLR_DIM  = "#64748b"
    CLR_BATT = (
        "#4ade80" if (batt_chrg or batt_pct is None or batt_pct > 50)
        else "#facc15" if batt_pct > 20
        else "#f87171"
    )

    # Stringhe data in italiano
    day_it  = DAYS_IT[now.weekday()]
    mon_it  = MONTHS_IT[now.month - 1]
    date_s  = f"{day_it} {now.day} {mon_it}"
    time_s  = now.strftime("%H:%M")

    # Meteo
    if wx:
        wx_icon, wx_label = wmo_info(wx["code"])
        wx_line = f"{wx_icon} {wx['temp']}°C · {wx_label}"
    else:
        wx_line = "Meteo non disponibile"

    # Batteria
    batt_icon = "⚡" if batt_chrg else "🔋"
    batt_val  = f"{batt_pct:.0f}%" if batt_pct is not None else "n/d"

    widget = wd.Widget()
    layout = widget.medium_layout
    layout.set_background_color(c(CLR_BG))

    # ── Riga 1: orologio sx · data dx ────────────────────────────────
    layout.add_row([
        t(time_s,  "HelveticaNeue-Thin", 42, CLR_TIME),
        t(date_s,  "HelveticaNeue",       9, CLR_DATE),
    ])

    # ── Riga 2: meteo ─────────────────────────────────────────────────
    layout.add_row([
        t(wx_line, "HelveticaNeue",  10, CLR_WX),
    ])

    layout.add_vertical_spacer()

    # ── Riga 3: % giornata ────────────────────────────────────────────
    layout.add_row([
        t("☀  Giorno",  "HelveticaNeue-Bold", 10, CLR_DAY),
        t(f"{day_pct:.1f}%", "Menlo",         10, CLR_DAY),
    ])
    layout.add_row([
        t(bar(day_pct), "Menlo", 9, CLR_DAY),
    ])

    # ── Riga 4: batteria ──────────────────────────────────────────────
    layout.add_row([
        t(f"{batt_icon}  Batteria", "HelveticaNeue-Bold", 10, CLR_BATT),
        t(batt_val,                 "Menlo",              10, CLR_BATT),
    ])
    layout.add_row([
        t(bar(batt_pct), "Menlo", 9, CLR_BATT),
    ])

    return widget

# ── Timeline: aggiorna ogni 15 minuti ────────────────────────────────

_wx        = fetch_weather()
_batt_pct, _batt_chrg = get_battery()

class ClockProvider(wd.TimelineProvider):
    def timeline(self):
        base = datetime.now().replace(second=0, microsecond=0)
        return [base + timedelta(minutes=i * 15) for i in range(9)]

    def widget(self, date):
        return build_widget(date, _wx, _batt_pct, _batt_chrg)

wd.provide_timeline(ClockProvider())
