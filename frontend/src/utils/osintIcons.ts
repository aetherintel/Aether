import L from "leaflet";

const makeIcon = (emoji: string): L.DivIcon =>
  L.divIcon({
    html: `<div style="font-size:18px;line-height:1;text-shadow:0 1px 3px rgba(0,0,0,0.5)">${emoji}</div>`,
    className: "",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });

export const OSINT_ICONS: Record<string, L.DivIcon> = {
  cameras:  makeIcon("📷"),
  atm:      makeIcon("🏧"),
  bank:     makeIcon("🏦"),
  police:   makeIcon("🚔"),
  military: makeIcon("🪖"),
  power:    makeIcon("⚡"),
  water:    makeIcon("💧"),
  alpr:     makeIcon("🚗"),
};

export const OSINT_LABELS: Record<string, string> = {
  cameras:  "📷 Kameras",
  atm:      "🏧 ATMs",
  bank:     "🏦 Banken",
  police:   "🚔 Polizei",
  military: "🪖 Militär",
  power:    "⚡ Strom-Infrastruktur",
  water:    "💧 Wasser-Infrastruktur",
  alpr:     "🚗 ALPR / Kennzeichenscanner",
};
