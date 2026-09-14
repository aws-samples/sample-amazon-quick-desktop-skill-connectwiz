# ConnectWiz Dashboard Style Reference — Graphite Dark

## Aesthetic: Graphite (Dark)

The dashboard uses the **Graphite** design language: calm, precise, monospace-native. A single monospace typeface throughout (the local stack `'SF Mono','JetBrains Mono','Fira Code',Consolas,monospace` — no webfont, see § No external references), pure grayscale with ONE restrained blue accent (`#2563EB`), and a command-palette/CLI-inspired layout.

This is the explicit **opposite** of cyberpunk: no neon, no glow, no glitch, no scanlines. The beauty comes from precision, alignment, and typographic discipline.

### Hard Constraints

- ONE monospace typeface everywhere: headings, numbers, labels, body, metric cards, charts.
- Pure **grayscale** surface/text palette + exactly ONE accent (`#2563EB`), used only for active/positive state: active tab, links, primary series, and the "good" semantic threshold.
- **Threshold colors are functional, not decorative.** Green/amber/red are permitted ONLY on metric values and chart segments that carry KPI threshold meaning. They must be muted, not neon: `#22c55e` (green), `#ca8a04` (muted gold), `#dc2626` (muted red).
- Tabular numerals with perfectly aligned columns, 1px hairline rules, generous letter-tracking on small uppercase labels.
- A command-palette-first feel: a subtle `⌘K` affordance, keyboard-hint chips, a top command bar.
- Sparklines and bars built from monospace block characters (▁▂▃▄▅▆▇█) are encouraged.
- NO neon, NO glow, NO glitch, NO scanlines. This is calm, quiet, precise.

## Template

See `dashboard_template.html` in this folder. It is the AUTHORITATIVE layout for the **entire artifact** — one HTML file with a four-tab bar (IVR Observability · IVR Flow Visibility · Queue Wait Analysis · Cost Analysis), one shared header, and all 11 pinned charts wired up.

The skill emits **one tabbed file, not four separate dashboards.** See SKILL.md § Dashboard Registry for the tab-by-tab chart assignment and the two implementation rules (explicit chart heights, and passing the clicked element to `switchTab`) that the tabs depend on.

## All Four Tabs Always Render (REQUIRED)

Never drop a tab because its data source is unavailable. Render the tab with a callout naming what is missing, which AWS API supplies it, and what the tab would have shown.

## No Customer Identifiers in the Template (REQUIRED)

`dashboard_template.html` is shipped inside the skill zip and read on every run, so anything hardcoded in it travels to every future customer.

| Placeholder | Filled from |
| --- | --- |
| `{{INSTANCE_ALIAS}}` | Step 2.5 instance selection (badge only — NOT in `<h1>` or `<title>`) |
| `{{INSTANCE_ID}}` | Step 2.5 |
| `{{DATE_RANGE}}` | the `date_range` input |
| `{{CONTACT_COUNT}}` | CTR query result count |
| `{{FLOW_EVENT_COUNT}}` | CloudWatch flow-log event count |
| `{{TRACED_COUNT}}` | distinct ContactIDs in the flow logs |
| `{{FLOW_NAMES}}` | contact flow names found in the logs |
| `{{VERSION}}` | SKILL.md frontmatter `version:` |

Never hardcode quoted IVR prompt text, flow names, queue names, contact IDs, or agency/department/organization names.

## No external references (REQUIRED)

A generated dashboard must contain **zero** `http(s)://` references that the browser would
fetch. Verify with a grep before shipping one — the only URLs that may remain are license
text and XML namespaces inside the inlined library, which are never requested.

| Was | Now |
| --- | --- |
| 6 × `cdn.jsdelivr.net` Highcharts `<script src>` | Apache ECharts 5.5.1 minified and inlined in `dashboard_template.html` before `</head>` (~1 MB) |
| `fonts.googleapis.com` + `fonts.gstatic.com` (JetBrains Mono) | Local stack `'SF Mono','JetBrains Mono','Fira Code',Consolas,monospace` |

Three reasons, each of which has actually bitten:

1. **Licensing** — ECharts is Apache-2.0 and may be redistributed in a customer deliverable. Highcharts is proprietary; embedding it in a delivered product needs a paid OEM license. Do not reintroduce it.
2. **No network** — these files are opened off a filesystem and emailed around. A CDN tag means blank charts wherever the CDN is blocked or the machine is offline.
3. **Supply chain** — a CDN `<script>` tag is a runtime trust decision: whatever that host serves at open time executes in the reader's browser. Inlining a pinned, checksummed copy removes that decision entirely.

The webfont is dropped rather than embedded: `SF Mono` (macOS) and `Consolas` (Windows) are
both ubiquitous, so the monospace intent survives without shipping font bytes. If the exact
JetBrains Mono face becomes a requirement, embed it as a base64 `woff2` (it is OFL, so that
is permitted) — **never** re-add the Google Fonts link.

## Header Brand Mark (REQUIRED)

The artifact has **one** `<h1>`, above the tab bar, and it **opens with the animated ConnectWiz character mark** — the SVG face wearing a headset that blinks, glances, idles, and pulses its mic tip. In Graphite dark, the mic tip pulses the accent blue (`#2563EB`) instead of green, reinforcing the single-accent constraint.

Copy both the `<span class="cw-mark-slot">` + `<svg class="cw-face">…</svg>` and the full CSS block verbatim from `dashboard_template.html`.

Rules:

- The mark stands beside the word, not inside it.
- Pure SVG + CSS. No JS, no Lottie, no external asset.
- Keep the `cw-` prefix and the `cw-face-grad` gradient id.
- Sizes are in `em` — resize by changing `--cw-mark` only.
- The mark must not add height to the header (absolute positioning in the slot).
- Motion suppressed under `prefers-reduced-motion: reduce`.

## Splash Screen (REQUIRED)

Same rules as before — CSS-only dismissal, never JavaScript. The Graphite splash uses the grayscale background with the character mark and "ConnectWiz" in the monospace stack.

## Color System

### Graphite Dark Palette (CSS variables)

```css
:root {
  --bg: #09090b;           /* near-black canvas */
  --surface: #111113;      /* card/panel background */
  --surface-2: #18181b;    /* elevated surface, hover states */
  --border: #27272a;       /* 1px hairline rules */
  --border-light: #1c1c1f; /* subtle dividers */
  --text: #e4e4e7;         /* primary text */
  --text-secondary: #a1a1aa; /* secondary/label text */
  --text-muted: #52525b;   /* muted/placeholder text */
  --accent: #2563EB;       /* THE one accent — active/positive only */
  --accent-dim: #1d4ed8;   /* accent hover state */
  --accent-bg: rgba(37, 99, 235, 0.08); /* accent wash for active tab bg */

  /* Threshold colors — functional only, never decorative */
  --green: #22c55e;        /* meets/exceeds target */
  --yellow: #ca8a04;       /* near threshold (muted gold) */
  --red: #dc2626;          /* critical / below target */

  --font-mono: 'SF Mono', 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  --radius: 6px;           /* tighter radius for CLI feel */
}

```

### Threshold-Based Color Coding (REQUIRED)

All metric values MUST be color-coded based on performance against thresholds:

| Color | CSS | When to use |
| --- | --- | --- |
| 🟢 Green (`#22c55e`) | `color: var(--green)` | Metric meets or exceeds target |
| 🟡 Gold (`#ca8a04`) | `color: var(--yellow)` | Metric is close to threshold |
| 🔴 Red (`#dc2626`) | `color: var(--red)` | Metric exceeds threshold in bad direction |
| ⚪ Neutral (`#e4e4e7`) | `color: var(--text)` | Informational only |
| 🔵 Accent (`#2563EB`) | `color: var(--accent)` | Positive/active/featured value |

### Chart Palette

Charts use a **grayscale-first palette** with the accent blue as the primary/featured series. All other series are shades of gray. Threshold colors appear only on threshold-coded segments.

```
Accent blue:  #2563EB  (primary series, positive/featured)
Light blue:   #3b82f6  (secondary blue when needed)
Zinc-300:     #d4d4d8  (high-contrast gray)
Zinc-400:     #a1a1aa  (medium gray)
Zinc-500:     #71717a  (dim gray)
Zinc-600:     #52525b  (muted gray)
Zinc-700:     #3f3f46  (background-ish gray)

```

For Sankey nodes, use the accent blue for the "good" outcome, muted red for bad outcomes, and gray tones for intermediate stages.

### Chart text is brighter than CSS text (REQUIRED)

`--text-muted` (`#52525b`) is fine for a 10px CSS label but reads as dim gray once
rasterized into a canvas. Chart text therefore steps up one level:

| Chart element | Color |
| --- | --- |
| Chart title | `#f4f4f5` |
| Subtitle, axis labels, axis names, legend | `#a1a1aa` – `#d4d4d8` |
| Data labels (pie slices, sankey nodes) | `#d4d4d8` – `#e4e4e7` |
| Gridlines | `#27272a` · axis lines `#3f3f46` |

These live in the ECharts theme registered as `connectwiz` in the template — set them there,
not per chart. **Never merge a theme per chart with `Object.assign`:** it is shallow, so a
chart passing `title: {text: …}` discards the themed `title.textStyle` and the title falls
back to ECharts' default `#333`, which is almost invisible on `--bg`. That was a real defect.

### One color per bar (REQUIRED)

Where each bar is an independent entity (queues, channels, usage types), give every bar its
own color via per-datum `itemStyle.color` — the ECharts equivalent of Highcharts'
`colorByPoint`. A single flat color across all bars was a past defect: it makes the chart
read as one continuous series.

## Typography

All text is monospace (see the stack above). Hierarchy comes from:

- **Scale**: 28px → 18px → 14px → 12px → 11px → 10px
- **Weight**: 700 (headings, metric values), 500 (labels), 400 (body)
- **Case + tracking**: uppercase with `letter-spacing: 0.08em` for small labels
- **Tabular numerals**: `font-variant-numeric: tabular-nums` on all numbers

Never mix typefaces. Never use a sans-serif.

## Layout Principles

- Dense but calm — a beautifully typeset terminal
- 1px `border: 1px solid var(--border)` on all cards — no shadows
- No box-shadow anywhere — depth comes from border contrast
- Metric cards: tight padding (12px 16px), aligned baselines
- Tab bar: pill-shaped active tab with accent background
- Tables: hairline row borders, monospace throughout, aligned right for numbers

## Metric Card Pattern (Graphite)

```html
<div class="metric-card">
  <div class="metric-title">IVR CONTAINMENT</div>
  <div class="metric-value status-bad">37.1%</div>
  <div class="metric-formula">= 53 / 143 × 100</div>
  <div class="metric-interpretation">Contacts resolved in IVR without agent</div>
  <div class="metric-benchmark">Benchmark: 40–60%</div>
</div>

```

All labels are uppercase + tracked. Values use tabular numerals. Formula is dimmed monospace.

## Metric Card Order

### Top Row (Tab 1):

1. IVR Containment Rate — 🔴 if <40%, 🟡 if 40-60%, 🟢 if >60%
2. Abandonment — 🔴 if >10%, 🟡 if 5-10%, 🟢 if <5%
3. IVR→Agent Transfer Rate — lower is better
4. Net Deflection — N/A if not measurable
5. Drop-Off / Never Arrived — target <5%

No auth card. See SKILL.md § Auth metrics are not reported.

### Charts Section:

- Sankey chart (`#chart-sankey`) — full width, never in a grid
- Disconnect reasons pie + Disposition donut — 2-column grid
- Abandonment segmentation + Transfers by queue — 2-column grid

## When generating:

1. Read `references/dashboard_template.html` for structure
2. Replace data values with actual query results
3. Keep the same CSS classes, card layout, and chart configurations
4. If a metric has no data, show it with the N/A pattern
5. All text is monospace — verify no sans-serif leaks into the output
6. Chart tooltips and axis labels are also monospace

