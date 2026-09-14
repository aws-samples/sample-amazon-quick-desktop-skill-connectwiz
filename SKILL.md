---
name: connectwiz
display_name: ConnectWiz
description: "Activate when the user asks about Amazon Connect contact center metrics, data lake queries, abandonment rates, queue performance, disconnect reasons, agent stats, handle times, or says 'connectwiz', 'connect analytics', 'contact center metrics', 'connect data lake'. Also activate for natural language questions about contact center data that could be answered via Athena queries against a Connect data lake."
icon: "📞"
version: "4.0.0"
trigger: connectwiz, connect analytics, contact center metrics, abandonment rate, queue performance, disconnect reasons, connect data lake, handle time, agent performance, contact volume, flow analysis, cost optimization, IVR analysis, callback optimization, IVR containment, IVR drop-off
inputs:
  - name: query
    description: "Natural language question or KPI name (e.g. 'abandonment rate by queue', 'IVR containment', 'contact volume by week'). If omitted, produce the full 4-tab dashboard."
    type: string
    required: false
  - name: date_range
    description: "Date range for the query. Format: 'YYYY-MM-DD to YYYY-MM-DD' or relative like 'last 30 days', 'last 7 days', 'this month'. Default: last 30 days."
    type: string
    required: false
    default: "last 30 days"
  - name: instance
    description: "Connect instance name or ID. If not specified and multiple instances exist, prompt the user to select one. Once selected, cached for the session."
    type: string
    required: false
tools: [run_python, open_in_session_tab]
depends-on: [user_mcp__aws_mcp, html_design]
scripts: [references/dashboard_style.md, references/dashboard_template.html, scripts/connectwiz_render.py]
id: 5ad41f27b8ba4c9eb7e0be7fa15b2ef6
---

## The single data plane: `aws-mcp`

Every AWS call this skill makes goes through **one** MCP server — the AWS API MCP proxy:

```json
{
  "mcpServers": {
    "aws-mcp": {
      "command": "uvx",
      "transport": "stdio",
      "timeout": 100000,
      "args": [
        "mcp-proxy-for-aws-cli@latest",
        "https://aws-mcp.us-east-1.api.aws/mcp",
        "--metadata",
        "AWS_REGION=us-west-2"
      ]
    }
  }
}

```

This config block is documentation only — the MCP server is already connected via Quick Suite. This is the **only** MCP server this skill uses. It exposes eight tools, named **unprefixed** — call them exactly as written here.

| Tool | Use in this skill |
| --- | --- |
| `aws___run_script` | **The workhorse.** Python sandbox with `call_boto3(service_name=…, operation_name=…, region_name=…, params={…})` — how Athena, Glue, CloudWatch Logs and the Connect API are all reached. Results auto-paginate; call each API once. |
| `aws___search_documentation` | Metric-formula and schema lookups (Step 4c). |
| `aws___read_documentation` | Fetch a full doc page as markdown, once search has identified it. |
| `aws___get_presigned_url` | Optional: hand the user a download link for an Athena result set. Every query already writes CSV to the output location, so this costs no extra query — useful when an analyst wants to verify a metric card's numbers themselves. |
| `aws___get_tasks` | Poll long-running async tasks. Relevant only if a polling loop hits a sandbox time limit — see the note in Steps 5–6. |
| `aws___list_regions` / `aws___get_regional_availability` | Rarely needed. `list_regions` can help when CTR data holds instance_ids not returned by a single-region `connect:ListInstances`. |
| `aws___retrieve_skill` | Not used by ConnectWiz. |

Sandbox constraints, all load-bearing:

- Top-level `await` and `asyncio.gather(...)` only. `asyncio.get_event_loop`** is blocked** and will fail code validation — never wrap calls in a `run_until_complete`.
- Assign `result = {...}`, then `result` alone as the final expression.
- Use `asyncio.gather(..., return_exceptions=True)` for read fan-out so one `AccessDenied` doesn't abort the batch. Let mutations raise.
- Check the returned `api_calls` list to confirm each call actually ran before trusting `return_value`.
- No network beyond `call_boto3`.

**Athena result rows come back from **`GetQueryResults`** directly.** No flag or setting gates access to them — if a query succeeds and returns no rows, the table genuinely has no matching data. Do not suggest the user enable anything to unlock results.

**Degradation is per-API-permission, not per-server.** One credential does not mean uniform access: a scoped role can pass `connect:ListInstances` and fail `connect:DescribeContactFlow`, so instance selection succeeds while architecture detection goes dark. Preflight the specific APIs (Step 1) and report the specific ones that were denied.

- **Dashboard mode**: When user asks for a full dashboard or multiple KPIs, use the IVR Observability Dashboard style (see Dashboard Style Guide below)

## Dashboard Registry (Canonical — ONE tabbed artifact, 4 tabs)

The skill emits **one** HTML artifact containing **four tabs** — not four separate files. `references/dashboard_template.html` is the authoritative implementation of the whole thing: same tab bar, same chart IDs, same structure. Build from it rather than assembling a layout from prose.

Tab labels are fixed and **must never begin with a digit** — leading numbers sort badly and read like drafts:

| Tab | Label | Data source |
| --- | --- | --- |
| 1 | `IVR Observability` | Athena CTR |
| 2 | `IVR Flow Visibility` | **CloudWatch** contact flow logs |
| 3 | `Queue Wait Analysis` | Athena CTR |
| 4 | `Cost Analysis` | **Cost Explorer** (`ce:GetCostAndUsage`); CUR 2.0 optionally enriches it per Step 2.6 |

One shared header above the tab bar: `<h1>` opens with the animated ConnectWiz character mark copied verbatim from the template — a headset-wearing SVG face, never an emoji and never a logo image — followed by `ConnectWiz Dashboard` as plain text, with the version badge top-right carrying the instance/date/contact-count scope inline. No separate subtitle line. See `references/dashboard_style.md`.

Chart element IDs are **pinned**. Use these exact IDs so runs are reproducible and comparable, and never invent variants — shipped output once drifted to `sankey-chart`/`abandon-chart` against a spec requiring `chart-sankey`/`chart-abandon`, which is what this registry exists to stop.

**Tab 1 — IVR Observability** (`#tab-ivr`)

| Section | Chart ID | Type |
| --- | --- | --- |
| Contact journey | `chart-sankey` | sankey |
| Disconnect reasons | `chart-disconnect-reasons` | pie |
| Call disposition | `chart-disposition` | donut |
| Abandonment segmentation | `chart-abandon` | column, pre-queue vs in-queue |
| Transfers by queue | `chart-transfers-by-queue` | horizontal bar, one color per bar |

Metric cards: IVR Containment · Abandonment · IVR→Agent Transfer Rate · Net Deflection · Drop-Off / Never Arrived.

**No Auth/Verification Success card.** Removed deliberately — see § Auth metrics are not reported.

**Tab 2 — IVR Flow Visibility** (`#tab-flow`)

| Section | Chart ID | Type |
| --- | --- | --- |
| Block-level funnel | `chart-block-funnel` | sankey |
| Time-to-drop distribution | `chart-time-to-drop` | column histogram |

Plus the stats grid and the contact-level trace table (`#trace-table`). This is the only tab CTR data cannot produce: it needs CloudWatch flow logs (`logs:StartQuery` on `/aws/connect/<alias>`). **If those are unavailable, still render the tab** — see the rule below.

**Tab 3 — Queue Wait Analysis** (`#tab-queue`)

| Section | Chart ID | Type |
| --- | --- | --- |
| Queue wait / duration | `chart-queue-wait` | column |

Plus recommended actions ordered by impact. Note this reverses an earlier decision that folded queue wait into Observability: as a tab it costs no extra artifact and no extra navigation, so the duplication argument that motivated the fold no longer applies.

**Tab 4 — Cost Analysis** (`#tab-cost`)

| Section | Chart ID | Type |
| --- | --- | --- |
| Cost by service | `chart-cost-by-service` | pie |
| Daily cost trend | `chart-cost-daily` | area |
| Connect & telecom breakdown | `chart-cost-connect` | bar |

Plus optimization opportunities. Sourced from Cost Explorer; read § Cost figures carry their scope
before presenting any cost figure, and the CUR 2.0 Interpretation Reference as well if you took the
optional CUR path.

### All four tabs ALWAYS render — never drop one

The artifact contains all four tabs on every run, without exception. A tab whose data source is unavailable **still renders**, containing an explicit callout that names what is missing, which AWS API would supply it, and what the tab would have shown. Do not omit the tab. Do not silently reduce the tab bar to three.

This is the same rule the skill already applies one level down: a metric that cannot be computed is shown as **N/A with the reason**, never hidden. A dropped tab is that same failure at a larger scale — the reader cannot distinguish "we looked and there was nothing to report" from "we never looked". A director shown three tabs has no way to know a fourth was possible.

Tab 2 is where this bites, because it is the only tab with a hard dependency. Pattern for an unavailable tab:

```html
<div id="tab-flow" class="tab-content">
<h2>IVR Flow Visibility — Block-Level Caller Journey</h2>
<div class="action-card critical">
  <div class="action-title">⚠️ NOT AVAILABLE — CloudWatch contact flow logs required</div>
  <div class="action-desc">This tab traces each caller block by block through the contact flow to
  show the exact step they abandon at. It reads CloudWatch log group
  <code>/aws/connect/&lt;instance-name&gt;</code>, which is not available: <em>state the actual
  cause — the log group does not exist because contact flow logging is off for this instance, or
  <code>logs:StartQuery</code> was denied for this credential.</em> Contact-record data cannot
  substitute: CTRs record that a caller dropped, never which IVR step they dropped at. Enable flow
  logging on the contact flow (or grant the permission) and re-run to populate this tab.</div>
</div>
</div>

```

Phrase the callout as *what the reader is missing out on*, not as an internal error. "Flow logs unavailable" tells a supervisor nothing; "this would show you the exact IVR step callers abandon at" tells them whether it is worth chasing.

The same applies to tab 4, but it should now be rare: Cost Explorer needs no export, so the only
reason this tab goes dark is **`ce:GetCostAndUsage` being denied**. Say that, and name the API — do
not tell the user cost data does not exist when what happened is a permissions failure. If CUR
enrichment was attempted and no CUR table was found, that is *not* grounds for a callout; the tab
still renders from Cost Explorer.

### Sankey charts are always full width

`chart-sankey` and `chart-block-funnel` each get their own full-width `.chart-container`. Never place a sankey inside a `.charts-grid` two-column layout, and never pair `chart-block-funnel` with `chart-time-to-drop` side by side.

A sankey renders node labels beside the nodes rather than below them, so it needs horizontal room in a way a pie or a column chart does not. At half width the labels overlap each other, the node columns compress into slivers, and the flow — the entire point of the chart — becomes unreadable. The histogram, by contrast, is perfectly legible at half width, which is why the tempting side-by-side pairing is the wrong way round.

Everything else may share a two-column `.charts-grid`.

### Charting: Apache ECharts, bundled

Charts are **Apache ECharts 5.5.1**, and the minified library is **inlined in
`references/dashboard_template.html`** — roughly 1 MB of `<script>` before `</head>`.

Three reasons it is bundled rather than loaded from a CDN, all of which have bitten:

1. **Licensing.** ECharts is Apache-2.0, so it can be redistributed inside an artifact handed to a customer. Highcharts (used through v3.x) is proprietary — Highsoft's agreement reserves embedding-in-a-delivered-product to a paid OEM license. Do not reintroduce it.
2. **No network.** These dashboards get opened off a filesystem and emailed around. A CDN `<script>` tag means every chart is blank wherever the CDN is blocked or the machine is offline.
3. **Supply chain.** A CDN `<script>` tag is a runtime trust decision: whatever that host serves at open time executes in the reader's browser. Inlining a pinned, checksummed copy removes that decision entirely.

So: **never replace the inlined library with a `<script src>` tag**, and carry the whole
block when copying the template. There must be no external URL in a generated dashboard.

The template registers an ECharts theme named `connectwiz` and creates every chart through
its own `mk(id, option)` helper. Always use `mk()` — it applies the theme and records the
instance for the tab-switch `resize()`. A bare `echarts.init` gets neither.

**Do not style charts by merging a theme object per chart with `Object.assign`.** That was
tried and produced near-invisible titles: `Object.assign` is shallow, so a chart passing
`title: {text: …}` replaced the themed `title` wholesale and the text color fell back to
ECharts' default `#333` on a near-black canvas. `registerTheme` merges at the correct
precedence.

**Chart text uses `--text` / `--text-secondary`, never `--text-muted`.** `#52525b` is
legible as a 10px CSS label but reads as dim gray once rasterized into a canvas.

### Sankey data must be acyclic (ECharts throws otherwise)

ECharts' sankey requires a **DAG** and fails the whole chart with
`Sankey is a DAG, the original data has cycle!` if any loop exists. Highcharts tolerated
cycles, so this is a real behavior change and it bites on **real** data, not just samples:
contact flows genuinely loop — a caller who fails a prompt returns to `GetUserInput`, and a
Wisdom/recording pair can bounce back and forth.

When building `chart-block-funnel` (and any sankey) from block-transition counts:

1. **Detect cycles before rendering.** A depth-first walk over the `source → target` pairs is enough.
2. **Split revisits into distinctly named nodes** rather than dropping the back-edge — e.g. `GetUserInput` and `GetUserInput (loop)`, `PlayPrompt` and `PlayPrompt (final)`. This preserves the volume, which dropping an edge would silently lose, and reads correctly as flow progression.
3. **Never silently discard links to force a DAG.** If a loop is significant, its own node makes the loop visible, which is usually the finding the reader wants.

### Two implementation rules that are load-bearing

**1. Every chart div needs an explicit inline pixel height.** e.g. `<div id="chart-sankey" style="height:350px;"></div>`. Charts in tabs 2–4 are created while their panel is `display:none`, so they have no measurable container. Without an explicit height, ECharts cannot measure the container at `init` (it logs a zero-size warning) and the chart has nothing to lay out against. `resize()` on tab switch restores width, but only if the element has a height to begin with. Verified across all 11 charts: each reaches full size the moment its tab is shown, and reports zero width while hidden.

**2. **`switchTab`** must receive the clicked element, not read the global **`event`**.** Wire tabs as `data-tab="ivr" onclick="switchTab('ivr', this)"`. The tempting version reads `event.target`, which works on a real click in Chrome but **throws** when called programmatically — an auto-rotating kiosk loop, or deep-linking to a tab. When it throws, the panel has already switched but the tab highlight never applies and the `resize()` after it never runs, leaving every chart mis-sized.

## Dashboard Style Guide (Preferred: "Observability" Pattern)

When generating HTML dashboard artifacts, ALWAYS follow this design pattern:

### Required Elements

1. **Header brand mark** — the artifact's single `<h1>`, above the tab bar, opens with the animated ConnectWiz character mark: an SVG face in a headset that blinks, glances, idles and pulses its mic tip green, followed by `ConnectWiz Dashboard` as plain text. The mark stands beside the word, never substituted for a letter inside it. Copy both the `<span class="cw-mark-slot">`-wrapped `<svg class="cw-face">…</svg>` and the `/* Animated ConnectWiz character mark */` CSS block (the `--cw-mark` variable, four `@keyframes`, and the `prefers-reduced-motion` rule) verbatim out of `references/dashboard_template.html`. The mark is drawn about twice the height of the old logo but adds **zero** height to the header, because the svg is absolutely positioned inside the slot — keep it that way. Pure SVG + CSS — no JS, no external asset. See `references/dashboard_style.md` § Header Brand Mark. The Amazon Quick base64 PNG that previously served as the mark is retired, as are the old `📞` / `🔬` / `💰` per-dashboard icons — do not reintroduce either.
2. **Splash screen** — the artifact opens on a brief branded loading screen: the character mark centered with `ConnectWiz` beneath it, filling the viewport, fading out after 2.15s to reveal the dashboard. Copy the `#cw-splash` div and its CSS block verbatim from `references/dashboard_template.html`. It dismisses itself with a **CSS animation and no JavaScript** — never rewrite it to wait on `window.load` or a chart callback, because a blocked CDN or a thrown script would then strand the whole dashboard behind an opaque overlay. See `references/dashboard_style.md` § Splash Screen.
3. **Version badge** — top-right, and it carries the run's scope inline: `ConnectWiz v<version> — Instance: <instance_id> · Data: <date_range> · <count> contacts`, where `<version>` is read from this file's frontmatter `version:` field. Never hardcode a version number here or in the template. There is **no separate subtitle line** under the `<h1>` any more — the instance/date/count used to live there and now belongs in this badge. Do not re-add it in both places.
4. **Metric cards** — each metric gets a plain-language title + value + formula + interpretation + benchmark
5. **Formula transparency** — show the calculation: `= numerator / denominator × 100`
6. **Explicit N/A handling** — if a metric CANNOT be computed, show it with explanation ("requires containment > 0 to compute"). **This applies to whole tabs as well:** a tab whose data source is unavailable still renders, carrying a callout explaining what is missing. Never drop a tab.
7. **Missing capability callouts** — if a data source is unavailable, name the specific AWS API that was denied or the resource that does not exist, rather than hiding the gap. State what you *checked* — never assert that infrastructure is absent when what you actually observed is that you could not see it.
8. **Industry benchmarks** — include where known (e.g., "Benchmark: 40–60%", "Target: <10%")
9. **Flow visualization** — Sankey chart showing call disposition flow (IVR → Queue → Agent/Dropped)
10. **Dark theme** — use Quick Desktop CSS variables (--color-bg, --color-surface, --color-text, etc.)

### Metric Card HTML Pattern

**Never render internal metric IDs (M1, M2, …) in output.** They are spec-internal shorthand; the audience is contact-center staff and executives to whom those codes are meaningless. Use the plain-language metric name as the card title.

```html
<div class="metric-card">
  <div class="metric-title">IVR Containment</div>
  <div class="metric-value">0%</div>
  <div class="metric-formula">= 0 / 4 × 100</div>
  <div class="metric-interpretation">No contacts resolved in IVR</div>
  <div class="metric-benchmark">Benchmark: 40–60%</div>
</div>

```

### Chart Types by Metric

- **Containment** + **Abandonment** + **Transfer Rate**: Gauge or bold metric cards
- **Drop-Off Points**: Use the **IVR Flow Visibility** style (see section below) — block-flow diagram + Sankey funnel + time-to-drop histogram + contact-level trace table. Do NOT use a simple card.
- **Net Deflection**: Conditional — show if data available, N/A with reason if not
- **Abandonment segmentation**: Stacked bar (pre-queue vs. in-queue)
- **Disconnect Reasons**: Pie chart showing ALL disconnect_reason values and counts — never filter these silently
- **Queue Wait**: Horizontal bar of average wait per queue, plus a per-queue detail table
- **Color coding**: ALL metric values must be color-coded — green (#4ade80) if meets target, yellow (#fbbf24) if near threshold, red (#ff6b6b) if critical. See references/dashboard_style.md for thresholds per metric.
- **Time trends**: Line charts (`type: 'line'` with `areaStyle` for filled trends)
- **Queue comparisons**: Horizontal bar charts

### DO NOT

- Hide metrics that can't be computed — always show with explanation
- Omit formulas — analysts need to verify the math
- Render internal metric IDs (M1, M2, …) as visible badges — use plain-language titles
- Invent chart element IDs — use the pinned IDs from the Dashboard Registry below
- Skip the version badge

## Overview

ConnectWiz is a comprehensive Amazon Connect analytics and optimization skill. It discovers a customer's Connect environment, queries their contact center data lake, and produces an interactive 4-tab HTML dashboard with Apache ECharts visualizations covering IVR performance, caller flow tracing, queue health, and AWS cost analysis.

It draws on four kinds of data, all reached through the single `aws-mcp` server via `call_boto3`:

| Data | AWS APIs | Required? |
| --- | --- | --- |
| **Data lake (Athena)** — historical CTRs, abandonment, handle times, queue metrics | `athena`, `glue`, `s3` | **Required** |
| **CloudWatch contact flow logs** — block-level IVR tracing, drop-off analysis | `logs` | Optional — tab 2 only |
| **Connect API** — flow definitions, queue/user/phone config, real-time metrics | `connect` | Optional — architecture detection, cost verification |
| **AWS documentation** — official metric definitions and schema lookups | `aws___search_documentation` | Optional — falls back to the references in this file |

It supports pre-built KPI templates (see § KPI Catalog), natural language → SQL generation, CloudWatch Logs Insights queries, and flow analysis with cost optimization recommendations. Results are presented as tables and Apache ECharts visualizations in a single tabbed HTML artifact.

Only the Athena path is required. Everything else degrades per the rule in Step 1 — less detail, never less structure.

## Auth metrics are not reported

**Never render an Auth/Verification Success card or a "NO AUTH FLOW EXISTS" callout.** Both were removed deliberately because: (1) detecting an authentication block requires heuristics over customer-specific flow JSON and contact attributes that vary per account, and (2) the "NO AUTH FLOW EXISTS" callout asserted infrastructure absence when the evidence only supported "this skill did not find one" — on an account where `connect:DescribeContactFlow` was denied, that callout was false.

Auth is out of scope. If a user asks for authentication metrics, say the skill does not measure them and why, rather than approximating.

## Known limitation: containment cannot distinguish resolution from abandonment

Read this before presenting IVR Containment or Net Deflection to anyone.

The formula — `disconnect_reason = 'CONTACT_FLOW_DISCONNECT' AND agent_connected IS NULL` — counts a caller who self-served and hung up **identically** to one who gave up in frustration and hung up. CTR data carries no field that separates them. Two consequences:

1. **Containment is an upper bound, not a measurement.** Label it as such in the interpretation line. Never present it as "contacts resolved" without qualification.
2. **Net Deflection is currently the same number as containment**, not an independent corroboration of it. If both cards appear, say so on the card rather than implying two measurements agree.

Always include `queue_enqueue_timestamp IS NULL` — without it, after-hours calls that never reached a queue inflate containment (see Lessons Learned).

Two things that would make containment a real measurement, neither implemented:

- Joining `contact_flow_events.flow_outcome` — `ENDED_FLOW_EXECUTION` (flow completed) versus `DISCONNECTED_PARTICIPANT` / `DROPPED` (caller left mid-flow) is exactly the completion-vs-abandonment distinction the formula lacks. The skill already discovers this table and never joins it.
- A duration floor, so instant hang-ups cannot count as containment.

Architecture detection (Step 2.8) exists to vary this formula and currently does not — all four architecture types resolve to the same expression. Until that is resolved, architecture classification should inform the **benchmark and the interpretation** you write on the card, not the arithmetic: a `conversational_router` cannot resolve contacts by definition, so a high containment number there is a misrouting signal rather than a success.

## Date Range Handling

Every KPI query MUST include a date range filter. The `{{date_range}}` input defaults to "last 30 days" and is used silently — the skill does not prompt for a range unless the user explicitly asks to change it.

1. If explicit dates (e.g., "2026-06-01 to 2026-06-12"):```sql WHERE initiation_timestamp >= TIMESTAMP '2026-06-01 00:00:00' AND initiation_timestamp < TIMESTAMP '2026-06-13 00:00:00'

```
2. If relative (e.g., "last 30 days"):```sql
WHERE initiation_timestamp >= current_date - interval '30' day

```

Always show the date range used in the output header so results are reproducible.

## KPI Catalog

Pre-built KPI templates for Step 4a. Each entry names the metric, provides the SQL template (with `{TABLE}`, `{DATE_FILTER}`, and `{INSTANCE_FILTER}` placeholders), the columns it produces, and which dashboard element it populates.

### Tab 1 — IVR Observability KPIs

**IVR Containment** (metric card)

```sql
SELECT
  COUNT(CASE WHEN disconnect_reason = 'CONTACT_FLOW_DISCONNECT'
              AND agent_connected_to_agent_timestamp IS NULL
              AND queue_enqueue_timestamp IS NULL THEN 1 END) AS contained,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(CASE WHEN disconnect_reason = 'CONTACT_FLOW_DISCONNECT'
              AND agent_connected_to_agent_timestamp IS NULL
              AND queue_enqueue_timestamp IS NULL THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS containment_pct
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'

```

Benchmark: 40–60%. Below 40% = 🔴, 40–60% = 🟡, above 60% = 🟢. **Upper bound only** — see § Known limitation.

**Abandonment Rate** (metric card + `chart-abandon`)

```sql
SELECT
  COUNT(CASE WHEN disconnect_reason IN ('CONTACT_FLOW_DISCONNECT', 'THIRD_PARTY_DISCONNECT')
              AND agent_connected_to_agent_timestamp IS NULL
              AND queue_enqueue_timestamp IS NOT NULL THEN 1 END) AS in_queue_abandon,
  COUNT(CASE WHEN disconnect_reason IN ('CONTACT_FLOW_DISCONNECT', 'THIRD_PARTY_DISCONNECT')
              AND agent_connected_to_agent_timestamp IS NULL
              AND queue_enqueue_timestamp IS NULL THEN 1 END) AS pre_queue_abandon,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(CASE WHEN disconnect_reason IN ('CONTACT_FLOW_DISCONNECT', 'THIRD_PARTY_DISCONNECT')
              AND agent_connected_to_agent_timestamp IS NULL THEN 1 END) / NULLIF(COUNT(*), 0), 1) AS abandon_pct
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'

```

Benchmark: <10%. Above 20% = 🔴, 10–20% = 🟡, below 10% = 🟢.

**IVR→Agent Transfer Rate** (metric card)

```sql
SELECT
  COUNT(CASE WHEN agent_connected_to_agent_timestamp IS NOT NULL THEN 1 END) AS transferred,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(CASE WHEN agent_connected_to_agent_timestamp IS NOT NULL THEN 1 END)
        / NULLIF(COUNT(*), 0), 1) AS transfer_pct
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'

```

**Disconnect Reasons** (`chart-disconnect-reasons`)

```sql
SELECT disconnect_reason, COUNT(*) AS cnt
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'
GROUP BY disconnect_reason
ORDER BY cnt DESC

```

Show ALL disconnect_reason values — never filter silently.

**Contact Journey Sankey** (`chart-sankey`)

```sql
SELECT
  CASE
    WHEN agent_connected_to_agent_timestamp IS NOT NULL THEN 'Agent Connected'
    WHEN queue_enqueue_timestamp IS NOT NULL AND agent_connected_to_agent_timestamp IS NULL THEN 'Abandoned in Queue'
    WHEN disconnect_reason = 'CONTACT_FLOW_DISCONNECT' AND queue_enqueue_timestamp IS NULL THEN 'IVR Contained'
    ELSE 'Other'
  END AS disposition,
  COALESCE(queue_name, 'No Queue') AS queue_name,
  disconnect_reason,
  COUNT(*) AS cnt
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'
GROUP BY 1, 2, 3

```

**Transfers by Queue** (`chart-transfers-by-queue`)

```sql
SELECT queue_name, COUNT(*) AS transfers
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'
  AND agent_connected_to_agent_timestamp IS NOT NULL
  AND queue_name IS NOT NULL
GROUP BY queue_name
ORDER BY transfers DESC
LIMIT 15

```

### Tab 3 — Queue Wait Analysis KPIs

**Queue Wait by Queue** (`chart-queue-wait`)

```sql
SELECT
  queue_name,
  COUNT(*) AS contacts,
  ROUND(AVG(queue_duration), 0) AS avg_wait_sec,
  ROUND(MAX(queue_duration), 0) AS max_wait_sec,
  ROUND(APPROX_PERCENTILE(queue_duration, 0.9), 0) AS p90_wait_sec,
  COUNT(CASE WHEN agent_connected_to_agent_timestamp IS NULL THEN 1 END) AS abandoned
FROM {TABLE}
WHERE {DATE_FILTER} AND {INSTANCE_FILTER} AND channel = 'VOICE'
  AND queue_enqueue_timestamp IS NOT NULL
GROUP BY queue_name
ORDER BY avg_wait_sec DESC

```

### Tab 4 — Cost Analysis KPIs

**Cost Explorer is the primary source.** It needs no export, so this tab works on every account.
All three charts come from **one** `ce:GetCostAndUsage` shape with different `GroupBy` / `Filter`.
CUR 2.0 is an optional enrichment for line-item depth — see Step 2.6 and the CUR 2.0
Interpretation Reference, and read § Cost figures carry their scope before presenting any number.

Cost Explorer is a **global endpoint**: always call it with `region_name="us-east-1"`, regardless
of where the Connect instance lives.

```python
CE = dict(service_name="ce", operation_name="GetCostAndUsage", region_name="us-east-1")
period = {"Start": START_DATE, "End": END_DATE}   # End is EXCLUSIVE, unlike Athena BETWEEN

# Cost by Service (chart-cost-by-service) + Daily Cost Trend (chart-cost-daily)
# One call answers both: group by service at daily granularity, then aggregate either axis.
by_service = await call_boto3(**CE, params={
    "TimePeriod": period, "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
    "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}]})

# Connect & Telecom Breakdown (chart-cost-connect)
connect_usage = await call_boto3(**CE, params={
    "TimePeriod": period, "Granularity": "MONTHLY", "Metrics": ["UnblendedCost"],
    "Filter": {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Connect"]}},
    "GroupBy": [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}]})

result = {"by_service": by_service["ResultsByTime"],
          "connect_usage": connect_usage["ResultsByTime"]}
result
```

Four things that will bite:

- **`End` is exclusive.** To cover through the 30th, pass `"End": "2026-07-01"`. Off-by-one here silently drops the last day from every cost chart.
- **Amounts are strings.** `Groups[].Metrics.UnblendedCost.Amount` is `"12.3456"`, not a float. Cast before summing, and read `Unit` rather than assuming USD.
- **Each call costs $0.01.** Trivial, but it means don't loop CE per-day when one `Granularity=DAILY` call returns the whole series.
- **Daily is the finest free granularity.** `HOURLY` requires opting in to paid hourly data. If a user asks for hourly spend, say CE cannot supply it here rather than silently returning daily.

Group keys arrive as `"Amazon Connect"` (display names), **not** the CUR `line_item_product_code`
values like `AmazonConnect`. Do not port CUR's product-code filters across.

## Workflow

### Step 1: Preflight — one script, all capabilities

- **Mode**: `deterministic`
- **Tool**: `aws___run_script`
- **Purpose**: learn in one round trip what this account and credential can actually answer, so failures surface here rather than four steps later mid-dashboard.

Run every probe concurrently and tolerate individual failures:

```python
probes = {
    "identity":   call_boto3(service_name="sts",    operation_name="GetCallerIdentity", region_name=REGION),
    "databases":  call_boto3(service_name="glue",   operation_name="GetDatabases",      region_name=REGION),
    "workgroups": call_boto3(service_name="athena", operation_name="ListWorkGroups",    region_name=REGION),
    "instances":  call_boto3(service_name="connect", operation_name="ListInstances",    region_name=REGION),
    "loggroups":  call_boto3(service_name="logs",   operation_name="DescribeLogGroups", region_name=REGION,
                             params={"logGroupNamePrefix": "/aws/connect"}),
    # Cost Explorer is a global endpoint -- us-east-1 regardless of REGION. A one-day probe
    # is enough to prove the permission without pulling a real series.
    "cost":       call_boto3(service_name="ce", operation_name="GetCostAndUsage",
                             region_name="us-east-1",
                             params={"TimePeriod": {"Start": PROBE_START, "End": PROBE_END},
                                     "Granularity": "DAILY", "Metrics": ["UnblendedCost"]}),
}
res = await asyncio.gather(*probes.values(), return_exceptions=True)
result = dict(zip(probes.keys(), [r if not isinstance(r, Exception) else {"error": str(r)} for r in res]))
result

```

**Required to proceed:** `glue:GetDatabases` and `athena:ListWorkGroups`. Anything else may fail; record which and carry it into the dashboard callouts.

Resolve the Athena output location — do this here, not at query time

Pick the workgroup (Step 2), then call `athena:GetWorkGroup` on it and read `Configuration.ResultConfiguration.OutputLocation` and `Configuration.ManagedQueryResultsConfiguration.Enabled`.

- Either one set → queries will run; use the workgroup's own configuration.
- **Neither set** → `StartQueryExecution` fails with *"No output location provided"* on every query. Ask the user for an S3 path and pass it explicitly as `ResultConfiguration={"OutputLocation": "s3://…/"}` on each `StartQueryExecution`:```

Specify an S3 output location Choose another workgroup

```

Nothing supplies an output location on your behalf — if the workgroup lacks one, you must pass it. Workgroup configuration varies per customer: many have it set and this check passes silently, which is exactly why it must not be skipped for the ones that don't. Resolving it here costs one API call; skipping it fails every query in Step 5 instead.

"Gracefully degrade" means show less detail, never show less structure

If a capability is unavailable, the artifact still has all four tabs and every metric card still appears; the ones that cannot be computed carry an explicit reason instead of a value. Do not drop a tab, a card or a chart because its input is missing — a reader cannot tell the difference between "nothing to report" and "never checked".

Name the **specific API** that failed, not "the MCP is down". `connect:DescribeContactFlow` denied while `connect:ListInstances` succeeds is a permissions finding the user can act on; "Connect unavailable" is not.

### Step 2: Discover Connect Environment

- **Mode**: `agentic`
- **Tool**: `aws___run_script` — `glue:GetDatabases`, `glue:GetTables`, `athena:ListWorkGroups`
- **Output**: Connect database name, table names, workgroup, output location

Discovery logic:

1. Scan database names from the Step 1 `databases` probe for keywords: `connect`, `cxa`, `contact`
2. For each candidate, call `glue:GetTables` and look for `connect_contact_record`
3. Also look for `contact_flow_events` in the same database.
4. Pick a workgroup with `State=ENABLED` (prefer one with "connect" or "cxa" in the name), then resolve its output location per Step 1.
5. Cache discovered config for session reuse — database, CTR table, flow-events table, workgroup, output location

**Cost data does not come from this catalog by default.** Tab 4 reads Cost Explorer
(`ce:GetCostAndUsage`), a separate AWS API on the same credential — no export, no table, no
workgroup. It is reached through the same `aws-mcp` server as everything else.

**CUR 2.0 is the optional enrichment, and it *is* in this catalog** — another table alongside the
CTR tables, reached with the same credential and workgroup. Look for it only when line-item detail
is actually wanted (per-number telecom charges, hourly spend); identify it per Step 2.6. Not finding
one is a normal outcome and costs the user nothing, because Cost Explorer already populated the tab.

### Step 2.5: Instance Selection (P0 — CRITICAL)

- **Mode**: `deterministic` if multiple instances, skip if only one
- **Purpose**: Prevent data contamination across instances

**Why this matters:** Real AWS accounts often have multiple Connect instances (production, staging, DR, different business units). Without filtering by instance_id, queries return mixed data from ALL instances, producing incorrect metrics.

**Logic:**

1. Query: `SELECT DISTINCT instance_id, count(*) as contacts FROM {table} WHERE {date_filter} GROUP BY instance_id`
2. If only 1 instance_id → use it automatically, no prompt needed
3. If multiple instance_ids found: a. Cross-reference against the Step 1 `instances` probe (`connect:ListInstances` → `InstanceSummaryList[].Id` / `.InstanceAlias`) to get human-readable aliases. If that call was denied, present the raw instance_ids with their contact counts and say the aliases could not be resolved — do not skip the prompt. b. Present decision card
4. Store selected `instance_id` as session variable
5. ALL subsequent queries include: `AND instance_id = '{selected_instance_id}'`

Note `connect:ListInstances` returns instances in **one region**. If the CTR table holds instance_ids that the call did not return, the missing ones most likely live in another region — say so rather than treating them as unknown.

### Step 2.6: CUR Table Identification (OPTIONAL enrichment — identify by SCHEMA, never by name)

- **Mode**: `deterministic`
- **Purpose**: find the cost table whatever the customer called it, without guessing
- **Skip by default.** Tab 4 is already populated from Cost Explorer. Run this step only when
  line-item depth is genuinely needed — per-phone-number telecom charges, hourly spend, or
  reconciling against a CUR figure the customer already has. Not finding a CUR table is a
  non-event; it does not reduce the tab and does not warrant a callout.

**Never match on the table name.** CUR export names are chosen per customer and vary freely — `connect_cur_2_0`, `cur_2_0`, `cost_and_usage_report`, `cur2`, `billing_hourly`, `aws_costs`, or something with no recognizable token at all. Substring matching is also actively dangerous: `cur` appears inside `security_events`, `recurring_charges`, `accuracy_report`, `current_state`, `procurement` and `curated_contacts`. Selecting one of those and then presenting its numbers as spend is worse than reporting no cost data, because it looks like an answer.

**Identify by column signature instead.** CUR 2.0's schema is standardized by AWS regardless of export name. `glue:GetTables` already returns every column (Step 2.7), so this costs no extra calls. A table is CUR 2.0 when it carries essentially all of:

| Column | Purpose |
| --- | --- |
| `line_item_usage_amount` | quantity — see the CUR 2.0 Interpretation Reference before using |
| `line_item_unblended_cost` | the dollar figure to sum |
| `line_item_product_code` | which service |
| `line_item_usage_start_date` | for date filtering |
| `bill_billing_period_start_date` | billing period |
| `product_servicecode` | service grouping |
| `pricing_unit` | units — do NOT read `Count` as a resource count |

Require at least `line_item_unblended_cost` **and** `line_item_usage_amount` before treating a table as CUR. Both present is conclusive; either alone is not.

**Logic:**

1. Enumerate databases with `glue:GetDatabases` — **all of them, not only the Connect ones.** CUR is frequently exported to a dedicated billing database (`athenacurcfn_*`, `cur`, `billing`) that has no `connect` token in its name. It may also be the same database as the CTR tables; both are normal.
2. For each candidate table, read its columns from `glue:GetTables` (`StorageDescriptor.Columns` plus `PartitionKeys`). Fan out across databases with one `asyncio.gather`.
3. Select tables matching the signature above. Table names may be used only to *rank* multiple schema-confirmed matches, never to find them.
4. If exactly one match → use it.
5. If several match (hourly and daily exports, or several accounts/payers), prefer the one whose `line_item_usage_start_date` range covers the requested period. If still ambiguous, present a decision card listing database, table and row count, the same way Step 2.5 handles instances.
6. If none match → cost data genuinely is unavailable. Render tab 4 with the callout, and name the databases actually searched so the user can see where you looked.
7. Cache the resolved database and table for the session.

**Legacy CUR (v1) is not the same thing.** v1 exports use camelCase-derived columns (`lineitem_unblendedcost`, `lineitem_usageamount`). If only a v1 table is present, say so explicitly rather than treating it as CUR 2.0 — the column semantics and the resource-count trap differ, and the Interpretation Reference below is written against 2.0.

**Never report cost data unavailable.** With Cost Explorer as the primary source there is almost no
case where this is true — only a denied `ce:GetCostAndUsage`, which you name as a permissions
finding. And never conflate the two sources: "no CUR table" is not "no cost data", it just means no
line-item enrichment. Saying the latter when you mean the former hands the user a false limitation.

### Step 2.7: Schema Discovery

- **Mode**: `deterministic`
- **Purpose**: Get the actual table schema instead of relying on hardcoded column lists

**Logic:**

1. Call `glue:GetTables` on the discovered database → returns ALL columns + types for every table at once, including `connect_contact_record`
2. Note the sibling tables in the same database from the same response
3. Store the CTR schema (column names + types) for use in NL→SQL generation (Step 4b)

### Step 2.8: Architecture Discovery (P1 — Critical for Correct Containment)

- **Mode**: `agentic`
- **Tool**: `aws___run_script` — `connect:ListContactFlows`, `connect:DescribeContactFlow`
- **Depends on**: those two APIs being permitted. If `DescribeContactFlow` is denied, say which API was denied and assume `architecture_type = "basic_ivr"` — do not silently default.
- **Purpose**: Understand how the contact center works BEFORE calculating any metrics.

**Architecture types to detect:**

1. `basic_ivr` — DTMF-only menu, no AI
2. `conversational_router` — Lex bot for routing only (no self-service)
3. `ai_self_service` — Amazon Q / Lex with fulfillment (can resolve contacts without agent)
4. `hybrid` — Mix of DTMF + AI paths

**Containment formula** is currently the same for all types: `disconnect_reason = 'CONTACT_FLOW_DISCONNECT' AND agent_connected IS NULL AND queue_enqueue_timestamp IS NULL`

See § Known limitation before relying on this to differentiate anything.

**Per-architecture benchmarks and interpretation** — this is where architecture type matters today, even though the formula does not vary:

| Architecture | Containment Benchmark | Interpretation guidance |
| --- | --- | --- |
| `basic_ivr` | 15–30% | Modest self-service; high containment here likely means callers hanging up in frustration, not resolution. Qualify heavily. |
| `conversational_router` | 5–15% | Router cannot resolve contacts by definition. High containment = misrouting signal, not success. Flag for investigation. |
| `ai_self_service` | 40–70% | Designed for resolution. Containment here is the most credible, though still an upper bound. |
| `hybrid` | 25–50% | Blend. Break out by flow path if possible (DTMF vs AI) for more actionable numbers. |

Write these benchmarks on the metric card's interpretation line, and call out when a number is suspiciously high for the architecture type (e.g., 60% containment on a `conversational_router` strongly suggests misclassification or data issues).

### Step 3.5: Architecture Presentation (BEFORE any KPI queries)

Present discovered architecture to user for confirmation before running queries.

### Step 3: Route Request

Route to Step 4a (pre-built KPI), Step 4b (NL→SQL), or Step 4c (knowledge lookup).

### Step 4a: Pre-built KPI Query

- **Mode**: `deterministic`
- **Tool**: `aws___run_script` (Athena queries)
- **Input**: KPI name from § KPI Catalog, discovered schema from Step 2.7, instance from Step 2.5
- **Output**: Athena query results for the requested KPI(s)
- **Validate**: Query returns rows; column names match expected output
- **On failure**: Check `StateChangeReason` for column name mismatches — fall back to discovered schema

**Logic:**

1. Match the user's `{{query}}` to a KPI in the § KPI Catalog (fuzzy match on name/alias)
2. If no `{{query}}` provided, run ALL Tab 1 + Tab 3 KPIs for the full dashboard
3. Fill the SQL template placeholders:- `{TABLE}` → discovered CTR table (Step 2)
- `{DATE_FILTER}` → `initiation_timestamp` clause from `{{date_range}}`
- `{INSTANCE_FILTER}` → `instance_id = '{selected_instance_id}'` from Step 2.5
- `{CUR_TABLE}` → discovered CUR table (Step 2.6). Only set on the optional CUR enrichment path; the cost tab does not need it, since Cost Explorer is queried by API rather than by SQL.
- `{CUR_DATE_FILTER}` → `line_item_usage_start_date` clause from `{{date_range}}`
4. Validate column names in the SQL against the discovered schema (Step 2.7). If a column doesn't exist (e.g., `queue_name` might be `queue` on some schemas), substitute the actual column name. Never run a query with an unverified column name.
5. Run via the Steps 5–6 pattern (start → poll → fetch in one `aws___run_script` call)

For dashboard mode, batch KPIs into as few queries as possible to minimize Athena scans. Combine compatible metrics into a single query with multiple aggregations.

### Step 4b: Natural Language → SQL

- **Mode**: `agentic`
- **Tool**: `aws___run_script` (Athena)
- **Input**: User's natural language question, discovered schema from Step 2.7
- **Output**: Generated SQL + Athena query results
- **Validate**: SQL is syntactically valid Presto/Trino; results answer the question
- **On failure**: Surface `StateChangeReason` which names the bad column/function; adjust and retry once

**NL→SQL generation guidelines:**

1. **Schema-first**: Only reference columns that exist in the discovered schema (Step 2.7). Print the available columns before generating SQL if uncertain.
2. **Date filter always**: Every query includes `WHERE initiation_timestamp >= ...` per § Date Range.
3. **Instance filter always**: Every query includes `AND instance_id = '{selected_instance_id}'`.
4. **Safe defaults**:- Use `COALESCE(column, 'Unknown')` for nullable GROUP BY columns
- Use `NULLIF(denominator, 0)` in any division to avoid divide-by-zero
- Use `ROUND(value, 1)` for percentages
- Timestamp columns: cast with `CAST(col AS TIMESTAMP)` if comparing
5. **Presto/Trino SQL dialect** — Athena v3 uses Trino:- String literals: single quotes only
- Date intervals: `interval '30' day` (not `interval 30 day`)
- Approximate percentiles: `APPROX_PERCENTILE(col, 0.9)`
- No `ILIKE` — use `LOWER(col) LIKE lower('pattern')`
6. **LIMIT by default**: Add `LIMIT 100` unless the user explicitly wants all rows or the query is an aggregation
7. **Explain the SQL**: Before running, briefly tell the user what the generated query does so they can course-correct

**Common NL→SQL mappings:**

| User says | Maps to |
| --- | --- |
| "calls", "contacts", "volume" | `COUNT(*)` from CTR table |
| "average handle time", "AHT" | `AVG(agent_interaction_duration)` |
| "longest wait" | `MAX(queue_duration)` |
| "by queue", "per queue" | `GROUP BY queue_name` |
| "by day", "daily" | `GROUP BY DATE(initiation_timestamp)` |
| "by hour" | `GROUP BY HOUR(initiation_timestamp)` |
| "agent performance" | `GROUP BY agent_username` with handle time + contacts |
| "callback", "callbacks" | `WHERE initiation_method = 'CALLBACK'` |

### Step 4c: AWS Documentation Lookup

- **Mode**: `agentic`
- **Tool**: `aws___search_documentation`, then optionally `aws___read_documentation`
- **Input**: Metric name or schema question the user needs clarified
- **Output**: Official AWS definition, formula, or schema reference
- **Validate**: The returned context answers the question
- **On failure**: Fall back to the definitions in this file (§ KPI Catalog, § CUR 2.0 Reference) and say you are using the skill's built-in reference rather than live docs

Use `aws___search_documentation` with `topics: ["reference_documentation"]` for schema/column questions, and `topics: ["general"]` for metric definitions and best practices. Only follow up with `aws___read_documentation` when the search result's `context` field genuinely lacks the needed detail — the context is a verbatim page chunk and usually already contains the answer.

### Steps 5–6: Run the query, poll, fetch results

Do all three inside **one** `aws___run_script` call. Splitting them across calls loses the execution id and wastes round trips.

```python
start = {"QueryString": sql, "WorkGroup": WORKGROUP,
         "QueryExecutionContext": {"Catalog": "AwsDataCatalog", "Database": DATABASE}}
if OUTPUT_LOCATION:                     # only when the workgroup has none — see Step 1
    start["ResultConfiguration"] = {"OutputLocation": OUTPUT_LOCATION}

q = await call_boto3(service_name="athena", operation_name="StartQueryExecution",
                     region_name=REGION, params=start)
qid = q["QueryExecutionId"]

for _ in range(60):                     # ~2 min ceiling
    ex = await call_boto3(service_name="athena", operation_name="GetQueryExecution",
                          region_name=REGION, params={"QueryExecutionId": qid})
    status = ex["QueryExecution"]["Status"]
    if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
        break
    await asyncio.sleep(2)

if status["State"] != "SUCCEEDED":
    result = {"state": status["State"], "reason": status.get("StateChangeReason")}
else:
    r = await call_boto3(service_name="athena", operation_name="GetQueryResults",
                         region_name=REGION, params={"QueryExecutionId": qid})
    result = {"state": "SUCCEEDED", "rows": r["ResultSet"]["Rows"]}
result

```

Three things to hold onto:

- `asyncio.sleep`**, never **`time.sleep` — and never `asyncio.get_event_loop`, which the sandbox blocks.
- **Row 0 of **`ResultSet.Rows`** is the header**, and every value arrives as a string under `VarCharValue`. Cast before arithmetic. A missing key means SQL `NULL`, not zero.
- **On **`FAILED`**, surface **`StateChangeReason`** verbatim.** It names the missing column or bad cast; paraphrasing it into "the query failed" throws away the only actionable detail.

**If the sandbox times out mid-poll**, do not silently retry from scratch — a fresh `StartQueryExecution` re-scans and re-bills the same data. The `QueryExecutionId` is the recovery handle: return it in `result`, then resume with `GetQueryExecution` / `GetQueryResults` on that id in a second call. `aws___get_tasks` may offer a cleaner async path for this; verify its behavior before relying on it.

Narrow the date range or add `LIMIT` before reaching for either. A CTR scan wide enough to outlast the sandbox is usually a scan that should have been partition-filtered.

### Step 6.5: Analyze Results & Generate Dynamic Content
- **Mode**: `agentic`
- **Tool**: None (pure reasoning over data from Steps 5–6)
- **Input**: Raw query results, architecture type from Step 2.8, date range, instance alias
- **Output**: Complete `data` dict ready for `render_dashboard()`
- **Validate**: Every required key in the data contract is populated; no placeholder text remains
- **On failure**: Re-run the missing query (Steps 4–6) and retry

This is the **intelligence boundary** — the last step where the LLM exercises judgment.
Everything after this (Steps 7 and 7.5) is deterministic string replacement.

The LLM builds the full `data` dict by processing raw query results through three lenses:

**6.5a — Metric cards (per tab)**

For each metric:
1. **Calculate** the value from raw query results (e.g., `contained / total * 100`)
2. **Classify** against § KPI Catalog thresholds → `status` = `good` / `warn` / `bad`
3. **Write the formula** showing the actual numbers (e.g., `= 53 / 143 × 100`)
4. **Write the interpretation** considering:
   - The architecture type from Step 2.8 and its per-architecture benchmarks
   - Whether the number is surprising for this architecture (e.g., 60% containment
     on a `conversational_router` is a red flag, not a win)
   - The § Known limitation caveat for containment
5. **Write the benchmark line** with the per-architecture range

```python
# Example: one metric card dict
{
    "title": "IVR Containment Rate",
    "value": "37.1%",
    "status": "bad",
    "formula": "= 53 / 143 × 100",
    "interpretation": "Upper-bound containment for a basic_ivr architecture. "
                      "Benchmark is 15–30% — the elevated rate likely reflects "
                      "caller frustration (hangups) rather than successful "
                      "self-service resolution. See § Known limitation.",
    "benchmark": "Benchmark: 15–30% for basic_ivr"
}
```

**6.5b — Chart configurations**

For each of the 11 charts, build an ECharts option dict from query results:
1. Transform query rows into the chart's expected `series` / `data` format
2. Use the Graphite chart palette (§ Dashboard Style Guide → Chart Palette):
   - Accent blue `#2563EB` for primary/featured series
   - Grayscale `#d4d4d8` → `#3f3f46` for other series
   - Threshold colors (`#22c55e` / `#ca8a04` / `#dc2626`) only for threshold-coded segments
3. Set chart-specific options (type, tooltip format, axis labels)
4. Use the pinned chart ID from § Dashboard Registry — never invent a new one

Each config is a Python dict matching the ECharts option object. The render script
serializes it to JSON inside the `mk('{id}', ...)` call.

**6.5c — Recommendations (action cards)**

For Tabs 3 and 4, generate prioritized recommendations from the data:
1. **Queue recommendations** (Tab 3): Analyze queue wait times, abandonment by queue,
   transfer rates. Order by estimated impact (highest first). Each recommendation
   cites specific numbers from the query results.
2. **Cost recommendations** (Tab 4): Apply the patterns from § Cost Optimization Patterns.
   Cross-reference CUR data with Connect API results where available. Never assert
   exact resource counts from CUR alone (§ CUR 2.0 Interpretation Reference).

```python
# Example: one action card dict
{
    "severity": "critical",
    "title": "⚠️ High Abandonment at GetUserInput Block (33% of contacts)",
    "desc": "Callers are dropping during IVR/Lex interaction after a median "
            "18s dwell time. Consider: (1) simplify the menu tree to reduce "
            "decision fatigue, (2) add an early escape-to-agent option at the "
            "first prompt, (3) enable callback to reduce queue pressure."
}
```

**6.5d — N/A explanations**

For any unavailable data source, generate a specific explanation:
- **Name the exact API** that was denied or the resource that doesn't exist
- **Explain what the tab/card would have shown** if the data were available
- **Suggest how to enable it** (e.g., "Enable contact flow logging in the Connect
  console under Contact Flows → Logging")

```python
# Example: flow tab unavailable
data["flow_available"] = False
data["flow_unavailable_reason"] = (
    "CloudWatch log group /aws/connect/state-benefits does not exist — "
    "contact flow logging is not enabled for this instance. Enable it in "
    "the Connect console under Contact Flows → Logging to unlock block-level "
    "caller tracing, drop-off analysis, and time-to-drop histograms."
)
```

**6.5e — Assemble the complete data dict**

Combine all outputs into a single dict matching the data contract in Step 7.
Every key must be populated — use empty lists `[]` for sections with no data,
never `None` or missing keys.


### Step 7: Assemble Dashboard Artifact (Template-Fill)
- **Mode**: `deterministic`
- **Tool**: `run_python` (calls `scripts/connectwiz_render.py`)
- **Input**: All query results from Steps 4a/4b/5–6 assembled into a data dict
- **Output**: Single HTML file opened in session tab
- **Validate**: `validate_dashboard()` returns all checks passing
- **On failure**: Check which validation check failed; fix the data dict and re-render

This step is **deterministic** — it calls the `render_dashboard()` function from
`scripts/connectwiz_render.py`, which reads `references/dashboard_template.html` and
fills it with live data. The LLM does NOT generate any HTML. The template is the
single source of truth for layout, CSS, tabs, brand mark, splash, and chart structure.

**Step 7a: Build the data dict**

Assemble all query results from Steps 1–6 into the data contract expected by
`render_dashboard()`:

```python
data = {
    # Text placeholders
    "instance_alias": instance_alias,       # from Step 2.5
    "instance_id": instance_id,             # from Step 2.5
    "date_range": date_range,               # from input or default "last 30 days"
    "version": "3.1.3",                     # from SKILL.md frontmatter
    "contact_count": total_contacts,        # from CTR query

    # Tab 1 — IVR Observability
    "metrics_ivr": [
        {
            "title": "IVR Containment Rate",
            "value": f"{containment_pct:.1f}%",
            "status": "bad" if containment_pct < 40 else "warn" if containment_pct < 60 else "good",
            "formula": f"= {contained} / {total} × 100",
            "interpretation": "Contacts resolved entirely in IVR without agent",
            "benchmark": "Benchmark: 40–60% (upper bound — see § Known limitation)"
        },
        # ... one dict per metric card, in display order
    ],
    "chart_sankey": { ... },                # Full ECharts option object
    "chart_disconnect_reasons": { ... },
    "chart_disposition": { ... },
    "chart_abandon": { ... },
    "chart_transfers_by_queue": { ... },

    # Tab 2 — IVR Flow Visibility
    "flow_available": True,                 # False → N/A callout replaces tab content
    "flow_unavailable_reason": "",          # Why CW logs are missing (if unavailable)
    "flow_event_count": flow_events,
    "traced_count": traced_contacts,
    "flow_names": "MainFlow, TransferFlow",
    "metrics_flow": [ ... ],
    "chart_block_funnel": { ... },
    "chart_time_to_drop": { ... },

    # Tab 3 — Queue Wait Analysis
    "metrics_queue": [ ... ],
    "chart_queue_wait": { ... },
    "actions_queue": [
        {"severity": "critical", "title": "⚠️ High wait in Support Queue",
         "desc": "P90 wait time is 245s. Consider adding agents during peak hours."},
        ...
    ],

    # Tab 4 — Cost Analysis
    "cost_available": True,                 # False → N/A callout
    "cost_unavailable_reason": "",
    "metrics_cost": [ ... ],
    "chart_cost_by_service": { ... },
    "chart_cost_daily": { ... },
    "chart_cost_connect": { ... },
    "actions_cost": [ ... ],
}
```

Each metric dict has: `title`, `value`, `status` (`good`/`warn`/`bad`/`neutral`),
`formula`, `interpretation`, `benchmark`. Apply thresholds from § KPI Catalog.

Each chart config is a full ECharts option object (the argument to `mk()`).
Build it as a Python dict — the render script serializes it to JSON.

**Step 7b: Call render_dashboard()**

```python
# Read the render script (bundled with the skill)
exec(open("scripts/connectwiz_render.py").read())

output_path = render_dashboard(
    data=data,
    template_path="references/dashboard_template.html",
    output_path=f"{WORKSPACE_DIR}/artifacts/connectwiz_dashboard.html"
)
```

This produces a single HTML file with all 4 tabs, all 11 charts, all metric cards,
and the brand mark — identical layout every run.

**Step 7c: Open in session tab**

```python
open_in_session_tab(output_path)
```

### Step 7.5: Dashboard Validation
- **Mode**: `deterministic`
- **Tool**: `run_python` (calls `validate_dashboard()` from `scripts/connectwiz_render.py`)
- **Input**: Path to the generated HTML from Step 7
- **Output**: Pass/fail with specific issues listed
- **Validate**: All checks return True
- **On failure**: Fix the data dict (not the template) and re-run Step 7b

```python
checks = validate_dashboard(output_path)
for check, passed in checks.items():
    print(f"{'✅' if passed else '❌'} {check}")

if not all(checks.values()):
    raise RuntimeError("Dashboard validation failed — fix data dict and re-render")
```

The validator checks:
- All 4 tab IDs present
- All 11 chart IDs present
- No raw `{{PLACEHOLDER}}` text remaining
- Splash screen present
- Character mark present
- No hardcoded instance IDs
- Metric cards rendered

**Key principle**: If validation fails, fix the **data**, not the **template**.
The template is locked. The only moving part is the data dict from Steps 1–6.
## IVR-Specific Metrics (Contact Flow Events + CloudWatch + Connect API)

### Contact Flow Events Table (Athena)

Table: `contact_flow_events` Key columns: `contact_id`, `flow_resource_id`, `flow_type`, `flow_outcome`, `start_timestamp`, `end_timestamp`, `next_flow_resource_id`, `next_queue_resource_id` Use for: flow-level disposition (DROPPED, TRANSFERRED_TO_QUEUE, DISCONNECTED_PARTICIPANT, ENDED_FLOW_EXECUTION)

### CloudWatch Contact Flow Logs

Log group: `/aws/connect/<instance-name>` Key fields: `ContactId`, `ContactFlowName`, `ContactFlowModuleType`, `Parameters`, `Results` Use for: block-level tracing — exact step where caller drops.

**Query pattern:**

```
fields @timestamp, ContactId, ContactFlowName, ContactFlowModuleType, @message
| filter ContactFlowName like /FLOW_NAME/
| sort ContactId, @timestamp asc
| limit 500

```

**Running it via **`call_boto3` — Logs Insights is start-then-poll, same shape as Athena, and again belongs in one script:

```python
q = await call_boto3(service_name="logs", operation_name="StartQuery", region_name=REGION,
                     params={"logGroupNames": [f"/aws/connect/{instance_alias}"],
                             "startTime": start_epoch, "endTime": end_epoch,   # seconds, not ms
                             "queryString": query, "limit": 500})
for _ in range(60):
    r = await call_boto3(service_name="logs", operation_name="GetQueryResults",
                         region_name=REGION, params={"queryId": q["queryId"]})
    if r["status"] in ("Complete", "Failed", "Cancelled"):
        break
    await asyncio.sleep(2)
result = {"status": r["status"], "results": r.get("results", [])}
result

```

Two differences from Athena worth remembering: `startTime`/`endTime` are **epoch seconds** (millis silently return nothing), and results come back as a list of `[{"field": …, "value": …}]` pairs per row rather than positional columns — build a dict per row before analyzing.

The log group is named for the instance **alias**, not the instance id. Get it from `connect:ListInstances`; if that was denied, match against the `/aws/connect` prefix list from the Step 1 `loggroups` probe instead.

**Analysis workflow:**

1. Group events by `ContactId` → build per-contact block sequences
2. Parse `@message` JSON for `Parameters.Text` (prompt text) and `Results` (success/error)
3. Identify last block before disconnect = drop-off point
4. Calculate time deltas between first and last event per contact
5. Classify outcomes: `transferred_to_queue`, `dropped_at_prompt`, `dropped_early`

**Rendering:** Use the IVR Flow Visibility Style Guide (see below).

### IVR Flow Visibility Style Guide (Drop-Off Deep-Dive)

When generating block-level IVR flow analysis (drop-off points, flow visibility, caller journey), use this EXACT layout pattern:

**This is tab 2 of the single tabbed artifact** (`#tab-flow`), not a standalone file, and `references/dashboard_template.html` implements it — build from the template rather than from this prose. The prose below records *why* the layout is shaped this way.

**Layout (top to bottom):**

1. **Stats Grid** — 5 cards: Contacts Traced, Drop-Off Point (block name), Median Time to Drop, Successful Engagement %, Avg Time (Successful)
2. **Block Flow Diagram** — horizontal scrollable visualization showing each flow block as a node
3. **Callout** — critical finding with root cause explanation
4. **Sankey Funnel Chart** — block-level flow using the ECharts sankey series, id `chart-block-funnel`
5. **Time-to-Drop Distribution** — histogram (ECharts bar series) with Dropped vs Transferred series, id `chart-time-to-drop`
6. **Contact-Level Trace Table** — per-contact: ID (truncated), Duration, Blocks count, Last Block, Outcome tag

**Block Flow Diagram CSS Pattern:**

```html
<div class="flow-container">
  <div class="flow-title"><span class="badge">FLOW</span> Flow Name — Block-by-Block Caller Journey</div>
  <div class="block-flow">
    <div class="block">
      <div class="block-node active">📞</div>
      <div class="block-label">Call Arrives</div>
      <div class="block-count">20/20</div>
    </div>
    <div class="arrow"></div>
    <div class="block">
      <div class="block-node danger">💬</div>
      <div class="block-label">GetUserInput (Lex + AI)</div>
      <div class="block-count">19/20</div>
      <div class="block-count drop">−14 drop!</div>
    </div>
  </div>
  <div class="callout"><strong>⚠️ Critical drop-off zone:</strong> explanation...</div>
</div>

```

**Block node states:**

- `.active` — green border: `border-color: var(--color-success); background: color-mix(in srgb, var(--color-success) 10%, var(--color-bg));`
- `.danger` — red border: `border-color: var(--color-error); background: color-mix(in srgb, var(--color-error) 10%, var(--color-bg));`
- `.warning` — orange border: `border-color: var(--color-warning); background: color-mix(in srgb, var(--color-warning) 10%, var(--color-bg));`

**Block node sizing:** 64×64px, border-radius: 8px, emoji icon centered, 18px font

**Arrow connector:** 32px wide, 2px solid `var(--color-border)`, with `›` character at end

**Required CSS classes:**

```css
.flow-container { background: var(--color-surface); border: 1px solid var(--color-border-light); border-radius: var(--radius-md); padding: 24px; margin-bottom: 20px; overflow-x: auto; }
.flow-title { font-size: 14px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.flow-title .badge { background: var(--color-primary); color: white; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: var(--radius-sm); font-family: var(--font-mono); }
.block-flow { display: flex; align-items: flex-start; gap: 0; padding: 16px 0; min-width: 1200px; }
.block { display: flex; flex-direction: column; align-items: center; min-width: 100px; }
.block-node { width: 64px; height: 64px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 2px solid var(--color-border); background: var(--color-bg); }
.block-label { font-size: 10px; color: var(--color-text-muted); text-align: center; margin-top: 8px; max-width: 90px; line-height: 1.3; }
.block-count { font-size: 11px; font-family: var(--font-mono); font-weight: 600; color: var(--color-text); margin-top: 4px; }
.block-count.drop { color: var(--color-error); }
.arrow { width: 32px; height: 2px; background: var(--color-border); margin-top: 32px; position: relative; }
.arrow::after { content: '›'; position: absolute; right: -4px; top: -8px; font-size: 14px; color: var(--color-text-muted); }

```

**Stats Grid pattern:**

```css
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
.stat-card { background: var(--color-surface); border: 1px solid var(--color-border-light); border-radius: var(--radius-md); padding: 16px; }
.stat-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); }
.stat-value { font-size: 24px; font-weight: 700; font-family: var(--font-mono); margin-top: 4px; }
.stat-detail { font-size: 11px; color: var(--color-text-secondary); margin-top: 4px; }

```

**Outcome tags in trace table:**

- `.tag-ok` — green: TRANSFERRED
- `.tag-drop` — red: DROPPED
- `.tag-warn` — yellow: DROPPED EARLY

**Emoji mapping for common blocks:**

| Block Type | Emoji |
| --- | --- |
| Call Arrives | 📞 |
| SetLoggingBehavior | 📝 |
| SetVoice | 🗣️ |
| SetContactData (language) | 🌐 |
| SetRecordingBehavior | 🎙️ |
| SetWisdomAssistant / CreateWisdomSession | 🤖 |
| InvokeExternalResource (Lambda) | ⚡ |
| GetUserInput (Lex/Bot prompt) | 💬 |
| CheckAttribute | 📋 |
| SetQueue / TransferToQueue | 🔀 |
| DisconnectParticipant | ❌ |
| MessageParticipant | 💬 |

**Time-to-Drop histogram buckets:** 0–1s, 1–2s, 2–3s, 3–4s, 4–5s, 5–10s, 10–30s, 30s–1m, 1–3m, 3m+ Use two series: Dropped (red) and Transferred/Successful (green).

### Connect API (Flow JSON)

Use `connect:DescribeContactFlow` to get the full flow definition. Parse the `Content` JSON to:

- Map block identifiers to human-readable names
- Determine the intended routing logic
- Identify prompt text, Lambda ARNs, queue targets

## CUR 2.0 Interpretation Reference (CRITICAL — Read Before Presenting Cost Data)

**Finding the table:** identify it by column signature, never by name — see Step 2.6. Customer export names vary (`connect_cur_2_0`, `cur_2_0`, `billing_hourly`, …) and a substring match on `cur` false-positives on `security_events`, `recurring_charges` and `procurement`.

### Prorated Usage Amounts — DO NOT Interpret as Discrete Counts

CUR 2.0 `line_item_usage_amount` for recurring charges (phone numbers, subscriptions, keys) represents **quantity × prorated billing fraction**, NOT a simple count of resources.

**Phone Number Trap (most common mistake):**

| CUR Line Item | Usage Amount | Pricing Unit | WRONG Interpretation | CORRECT Interpretation |
| --- | --- | --- | --- | --- |
| `USE1-US-did-numbers` | 17.1667 | Count | ❌ "17 DID numbers" | ✅ Could be 1 DID × 17.2 days, or 2 DIDs × 8.6 days |
| `USE1-US-tollfree-numbers` | 8.1618 | count | ❌ "8 toll-free numbers" | ✅ Could be 1 TFN × 8.2 days |
| `us-east-1-KMS-Keys` | 1.1306 | Keys | ❌ "1 KMS key" | ✅ 1 key × 1.13 billing months (prorated) |

**Rule: ALWAYS cross-reference with the Connect API for discrete resource counts:**

- Phone numbers → `connect:ListPhoneNumbersV2` (`TargetArn` = the instance ARN)
- Queues → `connect:ListQueues`
- Users → `connect:ListUsers`

**Never state "you have N phone numbers" based solely on CUR usage_amount.**

### Cost Explorer vs CUR 2.0 Differences

| Aspect | Cost Explorer | CUR 2.0 |
| --- | --- | --- |
| Credits/adjustments | Gross (credits applied to total, not per-service) | Net (credits as negative line items per-service) |
| Granularity | Service-level, daily minimum | Line-item level, hourly possible |
| Typical delta | ~0.1–0.5% higher than CUR | Authoritative net cost |
| Use case | Quick overview | Detailed analysis |

When reconciling: a small delta (< 1%) between CE and CUR is normal and usually due to credit netting differences. Report both if the user asks.

**This table is now load-bearing, not trivia.** Tab 4 reads Cost Explorer, so its figures are the
*gross* ones. If a customer compares them against a CUR-derived number they already have, they will
not match exactly. Say why — credit netting — rather than re-running the query looking for a bug.

### Cost figures carry their scope (REQUIRED)

Never present a spend number without saying whose spend it is. Cost Explorer returns the calling
account's view, and in an AWS Organization that depends on where you are standing:

- From the **management (payer) account**, CE returns consolidated spend for the whole organization — which may be far more than the Connect workload the user asked about.
- From a **member account**, CE returns that account's costs only, unless the payer has enabled member access to cost data.

So state the account and the period alongside the total, and use the Step 1 `identity` probe
(`sts:GetCallerIdentity`) for the account id rather than assuming. A Connect cost figure that is
silently organization-wide is the cost equivalent of the mixed-instance bug that Step 2.5 exists to
prevent: it looks like an answer and is wrong by an unknowable multiple.

The prorated-quantity trap survives the switch to Cost Explorer. CE's `UsageQuantity` on recurring
items is prorated exactly as CUR's `line_item_usage_amount` is, so a `USAGE_TYPE` group for
`did-numbers` reading `17.1667` still is **not** 17 phone numbers. Discrete counts come from the
Connect API, per § Assumptions Requiring API Verification below — that rule is unchanged.

### Safe Patterns for CUR Cost Analysis

**DO:**

- Sum `line_item_unblended_cost` for totals (already prorated correctly)
- Use `line_item_usage_type` to identify WHAT was consumed
- Cross-reference discrete counts via Connect API
- Note that `pricing_unit = "Count"` or `"count"` on recurring items means prorated-days, not resources

**DO NOT:**

- Interpret `line_item_usage_amount` as resource count for subscriptions/numbers
- Say "release X unused numbers" without verifying via API
- Assume Cost Explorer and CUR will match exactly (credit netting)
- Present hourly-chart overlays (like business hours) without querying actual Hours of Operation from Connect API

### Assumptions Requiring API Verification

Before presenting any of these in a dashboard, VERIFY via Connect API:

- Number of phone numbers → `connect:ListPhoneNumbersV2`
- Hours of operation → `connect:ListHoursOfOperations` + `connect:DescribeHoursOfOperation`
- Number of queues/agents → `connect:ListQueues`, `connect:ListUsers`
- Queue-to-agent mapping → `connect:ListRoutingProfiles` + `connect:ListRoutingProfileQueues`

If the relevant `connect:*` call is denied, explicitly state the limitation and name the API: "Phone number count cannot be verified — `connect:ListPhoneNumbersV2` was denied, and CUR shows prorated billing units, not discrete numbers."

## Cost Optimization Patterns (Tab 4 Recommendations)

When presenting Tab 4, include actionable optimization recommendations based on CUR data and Connect API verification. Order by estimated impact (highest first).

### Patterns to Check

**1. Unused Phone Numbers** (High Impact)

- Query CUR for DID/TFN line items with zero or near-zero `line_item_unblended_cost` per number
- Cross-reference with `connect:ListPhoneNumbersV2` for actual count
- Look for numbers with no associated contacts in the CTR table for the date range
- Recommendation: "Release unused phone numbers — each DID costs ~$0.03/day, each TFN ~$0.06/day"
- **Never state a count from CUR alone** — see § CUR 2.0 Interpretation Reference

**2. Off-Hours Queue Staffing** (Medium Impact)

- Query CTR for contact volume by hour-of-day: `GROUP BY HOUR(initiation_timestamp)`
- Cross-reference with `connect:DescribeHoursOfOperation` for configured hours
- If contacts arrive outside configured hours, they incur queue time with no agents
- Recommendation: "Align hours of operation with actual contact volume patterns"

**3. High Transfer Rates** (Medium Impact — indirect cost)

- From Tab 1/3 data: queues with >30% transfer rate
- Each transfer doubles handle time (two agents touch the same contact)
- Recommendation: "Reduce transfers from [queue] — current rate [X%] means [N] contacts handled twice. Review routing rules and agent skill assignments."

**4. Long IVR Dwell Time** (Medium Impact — telecom cost)

- From Tab 2 data: median time-to-drop in IVR
- Telecom charges accrue per-minute while callers are in the IVR
- Recommendation: "Callers spend median [X]s in IVR before reaching an agent. Streamlining prompts could reduce per-contact telecom cost by ~$0.01–0.03"

**5. Callback Optimization** (Low-Medium Impact)

- Query: `WHERE initiation_method = 'CALLBACK'` — compare callback volume to queue abandonment
- If abandonment is high but callbacks are low, the callback feature may not be enabled
- Recommendation: "Enable/promote callback to reduce queue abandonment and improve CSAT"

Present each recommendation as an action card with estimated savings range where possible. Never assert exact dollar savings without Connect API verification of resource counts.

## Output

The skill produces **one** self-contained HTML file: `artifacts/connectwiz_dashboard.html`, opened in a session tab.

**Contents:**

- 4-tab dashboard (IVR Observability · IVR Flow Visibility · Queue Wait Analysis · Cost Analysis)
- Animated ConnectWiz character mark + splash screen
- All 11 ECharts visualizations with interactive tooltips
- Metric cards with values, formulas, interpretations, and benchmarks
- Color-coded thresholds (🟢 green / 🟡 yellow / 🔴 red)
- Action cards with prioritized optimization recommendations
- Version badge with instance/date/contact scope

**For ad-hoc queries** (single KPI or NL→SQL), the output is a focused table or chart in a smaller HTML artifact, not the full 4-tab dashboard.

**Downloadable data**: Offer `aws___get_presigned_url` for the Athena result CSV when the user wants to verify numbers or do their own analysis.

## Lessons Learned

### Do

- Always filter on `initiation_timestamp` — not `connected_to_system_timestamp` or `disconnect_timestamp`
- Always filter on `instance_id` after Step 2.5 — mixed-instance data produces meaningless metrics
- Always include `queue_enqueue_timestamp IS NULL` in containment queries to exclude after-hours calls
- Use discovered schema (Step 2.7) column names, never hardcoded ones
- Surface `StateChangeReason` verbatim on Athena failures — it names the exact bad column or cast
- Use `asyncio.sleep` and top-level `await` only — `time.sleep` and `asyncio.get_event_loop` are blocked
- Pass `startTime`/`endTime` as epoch **seconds** to CloudWatch Logs Insights (millis silently return nothing)
- Resolve the Athena output location in Step 1 — skipping it fails every query in Step 5
- Cross-reference CUR `line_item_usage_amount` with Connect API for discrete resource counts
- Identify CUR tables by column signature, never by table name

### Don't

- Don't drop a tab, card, or chart because its data source is missing — show N/A with reason
- Don't render internal metric IDs (M1, M2, …) as visible labels — use plain-language names
- Don't interpret CUR `line_item_usage_amount` as a resource count for subscriptions/phone numbers
- Don't state "you have N phone numbers" based solely on CUR data
- Don't assume Cost Explorer and CUR will match exactly (credit netting differences are normal)
- Don't invent chart element IDs — use the pinned IDs from § Dashboard Registry
- Don't use `asyncio.get_event_loop` — the sandbox blocks it
- Don't present containment as "contacts resolved" without qualification — it's an upper bound

### Common Failures

| Symptom | Root Cause | Fix |
| --- | --- | --- |
| Every query fails at Step 5 | Workgroup has no output location | Resolve in Step 1 via `athena:GetWorkGroup` |
| Logs Insights returns 0 results | `startTime`/`endTime` passed in milliseconds | Use epoch **seconds** |
| Sandbox rejects the script | Used `asyncio.get_event_loop` or `time.sleep` | Top-level `await` + `asyncio.sleep` only |
| Wrong contact counts | Missing `instance_id` filter | Run Step 2.5 first |
| False containment (after-hours inflation) | Missing `queue_enqueue_timestamp IS NULL` | Add the filter |
| Column not found | Hardcoded column name doesn't match schema | Use discovered schema from Step 2.7 |
| CUR phone number count wrong | Interpreted `usage_amount` as discrete count | Verify via `connect:ListPhoneNumbersV2` |
| Business hours overlay wrong | Assumed typical hours | Query `connect:ListHoursOfOperations` or omit |
| Cost Explorer vs CUR delta | Different credit netting | Expected <1% — report both if asked |
| Cost tab blank at a customer | Depended on a CUR export that was never configured | Cost Explorer is primary; CUR is optional enrichment only |
| Last day missing from cost charts | CE `TimePeriod.End` is **exclusive** | Pass the day *after* the range end |
| Cost totals wildly too high | Ran CE from the payer account, returning org-wide spend | State the account with every figure (§ Cost figures carry their scope) |
| CE amounts concatenating not summing | `UnblendedCost.Amount` is a **string** | Cast before arithmetic; read `Unit` rather than assuming USD |
| Sankey chart renders collapsed | Chart div has no explicit pixel height | Add `style="height:350px;"` |

### When to Ask the User

- **Multiple Connect instances**: Always prompt — never guess which one (Step 2.5)
- **Multiple CUR tables**: If schema signature matches several, present options (Step 2.6)
- **No Athena output location**: The workgroup has none configured — need an S3 path (Step 1)
- **Ambiguous KPI request**: If the natural language query could map to multiple metrics, clarify
- **Architecture type uncertain**: If `DescribeContactFlow` is denied, present the assumed type and ask the user to confirm before running containment queries
- **Unexpected zero results**: If the CTR table has data but a specific KPI returns zero, confirm the date range and instance before concluding "no data"

