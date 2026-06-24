"""
Clock Widget per Pyto — v3
Layout:  [meteo]  [OROLOGIO GRANDE]  [data]
         [☀ giorno ████]  [🔋 batt. ████]
"""

import widgets as wd
from datetime import datetime, timedelta
import urllib.request
import json

# ── Batteria ─────────────────────────────────────────────────────────

try:
    import battery as _batt
    def get_battery():
        return _batt.level * 100, _batt.charging
except Exception:
    def get_battery():
        return None, False

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

# ── Meteo via IP + Open-Meteo ────────────────────────────────────────

def fetch(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())

def fetch_weather():
    try:
        geo = fetch("https://ipapi.co/json/", timeout=4)
        lat, lon = geo["latitude"], geo["longitude"]
        wx = fetch(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&current=temperature_2m,weather_code"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto&forecast_days=1",
            timeout=5,
        )
        return {
            "temp":     round(wx["current"]["temperature_2m"]),
            "code":     wx["current"]["weather_code"],
            "max_temp": round(wx["daily"]["temperature_2m_max"][0]),
            "min_temp": round(wx["daily"]["temperature_2m_min"][0]),
        }
    except Exception:
        return None

# ── Helpers ──────────────────────────────────────────────────────────

def c(h):
    h = h.lstrip("#")
    return wd.Color.rgb(int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)

def bar(pct, width=13):
    n = max(0, min(width, round((pct or 0) / 100 * width)))
    return "█" * n + "░" * (width - n)

def t(text, font_name, size, color_hex):
    return wd.Text(text=text, font=wd.Font(font_name, size), color=c(color_hex))

MONTHS_IT = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]

# ── Widget ────────────────────────────────────────────────────────────

def build_widget(now: datetime, wx, batt_pct, batt_chrg) -> wd.Widget:
    elapsed = now.hour * 3600 + now.minute * 60 + now.second
    day_pct = elapsed / 86400 * 100

    CLR_BG   = "#0d0d1a"
    CLR_TIME = "#b5273f"
    CLR_DATE = "#94a3b8"
    CLR_DAY  = "#facc15"
    CLR_WX   = "#e2e8f0"
    CLR_BATT = (
        "#4ade80" if (batt_chrg or batt_pct is None or batt_pct > 50)
        else "#facc15" if batt_pct > 20
        else "#f87171"
    )

    time_s = now.strftime("%H:%M")

    # Meteo sinistra — due righe con \n
    if wx:
        wx_icon, wx_label = wmo_info(wx["code"])
        wx_cell = f"{wx_icon} {wx['temp']}°C\n{wx_label}"
    else:
        wx_cell = "—\nMeteo n/d"

    # Data destra — giorno / mese in lettere / anno
    date_cell = f"{now.day}\n{MONTHS_IT[now.month - 1]}\n{now.year}"

    # Batteria
    batt_icon = "⚡" if batt_chrg else "🔋"
    batt_val  = f"{batt_pct:.0f}%" if batt_pct is not None else "n/d"

    widget = wd.Widget()
    layout = widget.medium_layout
    layout.set_background_color(c(CLR_BG))

    # ── Riga unica: [meteo | orologio | data] ────────────────────────
    layout.add_row([
        t(wx_cell,   "HelveticaNeue",      11, CLR_WX),
        t(time_s,    "HelveticaNeue-Thin", 64, CLR_TIME),
        t(date_cell, "HelveticaNeue",      13, CLR_DATE),
    ])

    layout.add_vertical_spacer()

    # ── Barre affiancate in basso ─────────────────────────────────────
    layout.add_row([
        t(f"☀  Giorno  {day_pct:.0f}%\n{bar(day_pct)}", "Menlo", 9, CLR_DAY),
        t(f"{batt_icon}  Batt.  {batt_val}\n{bar(batt_pct)}",  "Menlo", 9, CLR_BATT),
    ])

    return widget

# ── Fallback (schermo verde → mostra almeno l'ora) ───────────────────

def fallback_widget(err=""):
    widget = wd.Widget()
    layout = widget.medium_layout
    layout.set_background_color(c("#0d0d1a"))
    now = datetime.now()
    layout.add_row([t(now.strftime("%H:%M"), "HelveticaNeue-Thin", 64, "#b5273f")])
    layout.add_vertical_spacer()
    if err:
        layout.add_row([t(str(err)[:60], "HelveticaNeue", 8, "#64748b")])
    return widget

# ── Timeline provider ─────────────────────────────────────────────────

_wx              = fetch_weather()
_batt_pct, _batt_chrg = get_battery()

class ClockProvider(wd.TimelineProvider):
    def timeline(self):
        base = datetime.now().replace(second=0, microsecond=0)
        return [base + timedelta(minutes=i * 15) for i in range(9)]

    def widget(self, date):
        try:
            return build_widget(date, _wx, _batt_pct, _batt_chrg)
        except Exception as e:
            return fallback_widget(e)

try:
    wd.provide_timeline(ClockProvider())
except Exception as e:
    wd.show_widget(fallback_widget(e))
