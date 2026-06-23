// Variables used by Scriptable.
// icon-color: blue; icon-glyph: clock;
//
// Clock Widget — orologio, % giornata, batteria
// Dimensioni: Medium (default), Large, Lock Screen Rectangular
//
// Installazione:
//   1. Copia questo file in Scriptable (app o iCloud/Scriptable/)
//   2. Esegui nell'app per vedere l'anteprima
//   3. Aggiungi widget Scriptable alla home → scegli questo script

const REFRESH_S = 30

// ── Dati ────────────────────────────────────────────────────────────

const now      = new Date()
const startDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
const dayPct   = (now - startDay) / 864e5 * 100
const battPct  = Device.batteryLevel() * 100
const charging = Device.isCharging()

const timeStr = now.toLocaleTimeString("it-IT", {
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
})
const dateStr = now.toLocaleDateString("it-IT", {
  weekday: "long", day: "numeric", month: "long",
}).replace(/^\w/, c => c.toUpperCase())

// ── Colori ──────────────────────────────────────────────────────────

const BATT_CLR = charging   ? "#4ade80"
               : battPct > 50 ? "#4ade80"
               : battPct > 20 ? "#facc15"
               : "#f87171"

const CLR = {
  bg1:  "#0d0d1a",
  bg2:  "#091525",
  time: "#38bdf8",
  date: "#94a3b8",
  day:  "#facc15",
  batt: BATT_CLR,
}

// ── Helpers ─────────────────────────────────────────────────────────

const hex = h => new Color(h)

function bar(pct, width) {
  const n = Math.round(Math.min(100, Math.max(0, pct)) / 100 * width)
  return "█".repeat(n) + "░".repeat(width - n)
}

function addText(parent, str, font, color, align) {
  const t = parent.addText(str)
  t.font      = font
  t.textColor = color instanceof Color ? color : hex(color)
  if (align === "center") t.centerAlignText()
  if (align === "right")  t.rightAlignText()
  return t
}

function addRow(container, icon, label, pct, color, size) {
  const row = container.addStack()
  row.layoutHorizontally()
  row.centerAlignContent()
  addText(row, `${icon}  ${label}`, Font.boldSystemFont(size), hex(color))
  row.addSpacer()
  addText(row, `${pct.toFixed(1)}%`, Font.boldMonospacedSystemFont(size), hex(color))
}

// ── Schermata di blocco (Rectangular) ───────────────────────────────

function buildLockScreen(w) {
  w.setPadding(2, 4, 2, 4)
  addText(w, timeStr, Font.boldMonospacedSystemFont(20), Color.white())
  w.addSpacer(2)
  addText(w, `☀  Giorno  ${dayPct.toFixed(1)}%`, Font.boldSystemFont(10), hex(CLR.day))
  addText(w, bar(dayPct, 22), Font.regularMonospacedSystemFont(8), hex(CLR.day))
  w.addSpacer(2)
  addText(w, `${charging ? "⚡" : "🔋"}  Batteria  ${battPct.toFixed(0)}%`,
    Font.boldSystemFont(10), hex(CLR.batt))
  addText(w, bar(battPct, 22), Font.regularMonospacedSystemFont(8), hex(CLR.batt))
}

// ── Widget principale (Medium / Large) ──────────────────────────────

function buildMain(w, large) {
  const PAD      = large ? 16 : 14
  const timeSize = large ? 52 : 38
  const bodySize = large ? 13 : 11
  const barWidth = large ? 34 : 26

  w.setPadding(PAD, PAD, PAD, PAD)

  // ── Orologio ──
  w.addSpacer(large ? 8 : 2)
  addText(w, timeStr, Font.boldMonospacedSystemFont(timeSize), hex(CLR.time), "center")

  // ── Data ──
  w.addSpacer(4)
  addText(w, dateStr, Font.systemFont(bodySize - 1), hex(CLR.date), "center")

  w.addSpacer(large ? 16 : 8)

  // ── % giornata ──
  addRow(w, "☀", "Giorno", dayPct, CLR.day, bodySize)
  w.addSpacer(3)
  addText(w, bar(dayPct, barWidth), Font.regularMonospacedSystemFont(bodySize), hex(CLR.day), "center")

  w.addSpacer(large ? 12 : 6)

  // ── Batteria ──
  addRow(w, charging ? "⚡" : "🔋", "Batteria", battPct, CLR.batt, bodySize)
  w.addSpacer(3)
  addText(w, bar(battPct, barWidth), Font.regularMonospacedSystemFont(bodySize), hex(CLR.batt), "center")

  w.addSpacer(large ? 8 : 2)
}

// ── Costruisci il widget ─────────────────────────────────────────────

const widget = new ListWidget()
widget.refreshAfterDate = new Date(Date.now() + REFRESH_S * 1000)

const grad = new LinearGradient()
grad.colors    = [hex(CLR.bg1), hex(CLR.bg2)]
grad.locations = [0, 1]
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
