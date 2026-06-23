// Variables used by Scriptable.
// icon-color: red; icon-glyph: clock;
//
// Clock Widget v2 — orologio bordeaux, % giornata, batteria, meteo
// Dimensioni: Medium (default), Large, Lock Screen Rectangular
//
// Prima esecuzione: concedi i permessi Posizione quando richiesto

// ── WMO weather codes ────────────────────────────────────────────────

function wmoInfo(code) {
  if (code === 0)  return ["☀️", "Sereno"]
  if (code === 1)  return ["🌤️", "Poco nuvoloso"]
  if (code === 2)  return ["⛅", "Parz. nuvoloso"]
  if (code === 3)  return ["☁️", "Nuvoloso"]
  if (code <= 48)  return ["🌫️", "Nebbia"]
  if (code <= 55)  return ["🌦️", "Pioggerella"]
  if (code <= 65)  return ["🌧️", "Pioggia"]
  if (code <= 77)  return ["❄️", "Neve"]
  if (code <= 82)  return ["🌧️", "Rovesci"]
  if (code <= 86)  return ["🌨️", "Neve a rovesci"]
  return ["⛈️", "Temporale"]
}

// ── Meteo via Open-Meteo (gratuito, no API key) ──────────────────────

async function fetchWeather() {
  try {
    const loc  = await Location.current()
    const lat  = loc.latitude.toFixed(4)
    const lon  = loc.longitude.toFixed(4)
    const url  = `https://api.open-meteo.com/v1/forecast`
              + `?latitude=${lat}&longitude=${lon}`
              + `&current=temperature_2m,weather_code`
              + `&daily=temperature_2m_max,temperature_2m_min`
              + `&timezone=auto&forecast_days=1`
    const data = await new Request(url).loadJSON()
    return {
      temp:    Math.round(data.current.temperature_2m),
      code:    data.current.weather_code,
      maxTemp: Math.round(data.daily.temperature_2m_max[0]),
      minTemp: Math.round(data.daily.temperature_2m_min[0]),
    }
  } catch (_) {
    return null
  }
}

// ── Dati ─────────────────────────────────────────────────────────────

const weather  = await fetchWeather()

const now      = new Date()
const startDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
const dayPct   = (now - startDay) / 864e5 * 100
const battPct  = Device.batteryLevel() * 100
const charging = Device.isCharging()

const timeStr = now.toLocaleTimeString("it-IT", {
  hour: "2-digit", minute: "2-digit", hour12: false,
})
const dateStr = now.toLocaleDateString("it-IT", {
  weekday: "short", day: "numeric", month: "short",
}).replace(/^\w/, c => c.toUpperCase())

// ── Colori ───────────────────────────────────────────────────────────

const BATT_CLR = (charging || battPct > 50) ? "#4ade80"
               : battPct > 20               ? "#facc15"
               : "#f87171"

const CLR = {
  bg1:  "#0d0d1a",
  bg2:  "#0c111d",
  time: "#b5273f",   // bordeaux
  date: "#94a3b8",
  day:  "#facc15",
  batt: BATT_CLR,
  wx:   "#e2e8f0",
  dim:  "#64748b",
}

// ── Helpers ──────────────────────────────────────────────────────────

const hex = h => new Color(h)

function bar(pct, w) {
  const n = Math.round(Math.min(100, Math.max(0, pct)) / 100 * w)
  return "█".repeat(n) + "░".repeat(w - n)
}

function txt(parent, str, font, color, align) {
  const t = parent.addText(str)
  t.font      = font
  t.textColor = color instanceof Color ? color : hex(color)
  if (align === "center") t.centerAlignText()
  if (align === "right")  t.rightAlignText()
  return t
}

function addBarRow(w, icon, label, pct, color, size, barW) {
  const row = w.addStack()
  row.layoutHorizontally()
  row.centerAlignContent()
  txt(row, `${icon}  ${label}`, Font.boldSystemFont(size), hex(color))
  row.addSpacer()
  txt(row, `${pct.toFixed(1)}%`, Font.boldMonospacedSystemFont(size), hex(color))
  w.addSpacer(3)
  txt(w, bar(pct, barW), Font.regularMonospacedSystemFont(size), hex(color), "center")
}

// ── Lock Screen (Rectangular) ─────────────────────────────────────────

function buildLockScreen(w) {
  w.setPadding(2, 4, 2, 4)
  txt(w, timeStr, Font.thinSystemFont(22), hex(CLR.time))
  w.addSpacer(2)
  if (weather) {
    const [icon] = wmoInfo(weather.code)
    txt(w, `${icon} ${weather.temp}°  ↑${weather.maxTemp}° ↓${weather.minTemp}°`,
      Font.systemFont(10), hex(CLR.wx))
  }
  w.addSpacer(2)
  txt(w, `☀ ${dayPct.toFixed(1)}%  ${bar(dayPct, 14)}`,
    Font.regularMonospacedSystemFont(9), hex(CLR.day))
}

// ── Widget principale (Medium / Large) ────────────────────────────────

function buildMain(w, large) {
  const PAD      = large ? 16 : 12
  const timeSize = large ? 76 : 58
  const bodySize = large ? 13 : 11
  const barW     = large ? 34 : 26

  w.setPadding(PAD, PAD, PAD, PAD)

  // ── Riga superiore: orologio sx, data+meteo dx ──
  const topRow = w.addStack()
  topRow.layoutHorizontally()
  topRow.bottomAlignContent()

  // Orologio — grande, sottile, bordeaux, sinistra
  txt(topRow, timeStr, Font.thinSystemFont(timeSize), hex(CLR.time))

  topRow.addSpacer()

  // Data + meteo — destra
  const right = topRow.addStack()
  right.layoutVertically()
  right.bottomAlignContent()

  txt(right, dateStr, Font.systemFont(bodySize - 1), hex(CLR.date), "right")

  if (weather) {
    const [icon, label] = wmoInfo(weather.code)
    right.addSpacer(large ? 6 : 4)
    txt(right, `${icon} ${weather.temp}°C`, Font.boldSystemFont(bodySize + 2), hex(CLR.wx), "right")
    right.addSpacer(2)
    txt(right, label, Font.systemFont(bodySize - 1), hex(CLR.dim), "right")
    right.addSpacer(2)
    txt(right, `↑${weather.maxTemp}°  ↓${weather.minTemp}°`,
      Font.systemFont(bodySize - 1), hex(CLR.dim), "right")
  } else {
    right.addSpacer(4)
    txt(right, "Meteo n/d", Font.systemFont(bodySize - 1), hex(CLR.dim), "right")
  }

  w.addSpacer(large ? 14 : 7)

  // ── % giornata ──
  addBarRow(w, "☀", "Giorno", dayPct, CLR.day, bodySize, barW)

  w.addSpacer(large ? 10 : 5)

  // ── Batteria ──
  addBarRow(w, charging ? "⚡" : "🔋", "Batteria", battPct, CLR.batt, bodySize, barW)

  w.addSpacer(large ? 8 : 2)
}

// ── Costruzione widget ────────────────────────────────────────────────

const widget = new ListWidget()
widget.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)

const grad = new LinearGradient()
grad.colors     = [hex(CLR.bg1), hex(CLR.bg2)]
grad.locations  = [0, 1]
grad.startPoint = new Point(0, 0)
grad.endPoint   = new Point(0, 1)
widget.backgroundGradient = grad

const family = config.widgetFamily
if (family === "accessoryRectangular") {
  buildLockScreen(widget)
} else {
  buildMain(widget, family === "large")
}

Script.setWidget(widget)
if (config.runsInApp) widget.presentMedium()
Script.complete()
