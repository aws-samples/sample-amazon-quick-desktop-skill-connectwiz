#!/usr/bin/env python3
"""
connectwiz_render.py — Template-fill renderer for ConnectWiz dashboards.

Reads references/dashboard_template.html, replaces markers with live data,
writes the final dashboard to artifacts/connectwiz_dashboard.html.

Usage from SKILL.md Step 7:
    from connectwiz_render import render_dashboard
    html = render_dashboard(data)
    # data is the dict assembled from Steps 1-6

Data contract (the `data` dict):
    {
        "instance_alias": str,
        "instance_id": str,
        "date_range": str,
        "version": str,
        "contact_count": int,

        # Tab 1 — IVR Observability
        "metrics_ivr": [
            {"title": "IVR Containment Rate", "value": "37.1%", "status": "bad",
             "formula": "= 53 / 143 × 100",
             "interpretation": "Contacts resolved entirely in IVR without agent",
             "benchmark": "Benchmark: 40–60%"},
            ...
        ],
        "chart_sankey": {...},          # ECharts option (series/data only)
        "chart_disconnect_reasons": {...},
        "chart_disposition": {...},
        "chart_abandon": {...},
        "chart_transfers_by_queue": {...},

        # Tab 2 — IVR Flow Visibility
        "flow_available": bool,         # False → N/A callout
        "flow_unavailable_reason": str, # Why CW logs are missing
        "flow_event_count": int,
        "traced_count": int,
        "flow_names": str,
        "metrics_flow": [...],
        "chart_block_funnel": {...},
        "chart_time_to_drop": {...},
        "flow_blocks": [...],           # Block-level flow diagram data
        "trace_table": [...],           # Contact-level trace rows

        # Tab 3 — Queue Wait Analysis
        "metrics_queue": [...],
        "chart_queue_wait": {...},
        "actions_queue": [              # Recommended actions
            {"severity": "critical|warn|good", "title": str, "desc": str},
            ...
        ],

        # Tab 4 — Cost Analysis
        "cost_available": bool,
        "cost_unavailable_reason": str,
        "metrics_cost": [...],
        "chart_cost_by_service": {...},
        "chart_cost_daily": {...},
        "chart_cost_connect": {...},
        "actions_cost": [...],
    }
"""

import json
import re
import os


def _metric_card_html(m):
    """Generate a single metric card HTML block."""
    status_class = {
        "good": "status-good",
        "warn": "status-warn",
        "bad": "status-bad",
        "neutral": "",
        "accent": "status-accent",
    }.get(m.get("status", "neutral"), "")

    parts = [
        '<div class="metric-card">',
        f'  <div class="metric-title">{m["title"]}</div>',
        f'  <div class="metric-value {status_class}">{m["value"]}</div>',
    ]
    if m.get("formula"):
        parts.append(f'  <div class="metric-formula">{m["formula"]}</div>')
    if m.get("interpretation"):
        parts.append(f'  <div class="metric-interpretation">{m["interpretation"]}</div>')
    if m.get("benchmark"):
        parts.append(f'  <div class="metric-benchmark">{m["benchmark"]}</div>')
    parts.append('</div>')
    return '\n'.join(parts)


def _metrics_grid_html(metrics):
    """Generate a full metrics grid from a list of metric dicts."""
    if not metrics:
        return '<div class="metrics-grid"><div class="metric-card"><div class="metric-title">NO DATA</div><div class="metric-value">N/A</div></div></div>'
    cards = '\n'.join(_metric_card_html(m) for m in metrics)
    return f'<div class="metrics-grid">\n{cards}\n</div>'


def _action_cards_html(actions):
    """Generate action card HTML blocks."""
    if not actions:
        return ''
    parts = []
    for a in actions:
        severity = a.get("severity", "warn")
        css_class = {"critical": "critical", "good": "good"}.get(severity, "")
        parts.append(
            f'<div class="action-card {css_class}">\n'
            f'  <div class="action-title">{a["title"]}</div>\n'
            f'  <div class="action-desc">{a["desc"]}</div>\n'
            f'</div>'
        )
    return '\n'.join(parts)


def _unavailable_callout(tab_name, reason):
    """Generate an N/A callout for an unavailable tab."""
    return (
        f'<div class="action-card critical">\n'
        f'  <div class="action-title">⚠️ NOT AVAILABLE — {tab_name}</div>\n'
        f'  <div class="action-desc">{reason}</div>\n'
        f'</div>'
    )


def _chart_config_js(chart_id, config):
    """Generate an mk() call from a config dict.

    `mk(id, option)` is the template's own helper: it runs echarts.init with the
    registered 'connectwiz' theme and records the instance so a tab switch can
    resize it. Emitting echarts.init directly would skip both.

    `config` should be a full ECharts option object (title, tooltip, xAxis, yAxis,
    series, ...) as a Python dict. It is serialized to JSON.

    ECharts option shape differs from Highcharts in ways that matter here:
      - pie/bar per-point colors are `itemStyle.color` on each datum, not `color`
      - sankey takes `data` (nodes) + `links` (source/target/value), and the graph
        MUST be acyclic -- see SKILL.md § Sankey data must be acyclic
      - categories live on `xAxis.data` / `yAxis.data`, not `xAxis.categories`
    """
    if not config:
        return f"// {chart_id}: no data available"
    config_json = json.dumps(config, indent=2, default=str)
    return f"mk('{chart_id}', {config_json});"


def render_dashboard(data, template_path=None, output_path=None):
    """Render the ConnectWiz dashboard from template + data.
    
    Args:
        data: Dict matching the data contract above.
        template_path: Path to dashboard_template.html. 
                       Auto-detected from skill references/ folder if None.
        output_path: Where to write the final HTML.
                     Defaults to artifacts/connectwiz_dashboard.html.
    
    Returns:
        str: Path to the written HTML file.
    """
    # --- Locate template ---
    if template_path is None:
        # Try common locations
        candidates = [
            os.path.join(os.environ.get('WORKSPACE_DIR', '.'), 
                        'references', 'dashboard_template.html'),
            'references/dashboard_template.html',
        ]
        for c in candidates:
            if os.path.exists(c):
                template_path = c
                break
        if template_path is None:
            raise FileNotFoundError("Cannot find dashboard_template.html")

    if output_path is None:
        output_path = os.path.join(
            os.environ.get('WORKSPACE_DIR', '.'),
            'artifacts', 'connectwiz_dashboard.html'
        )

    with open(template_path, 'r') as f:
        html = f.read()

    # --- 1. Text placeholder replacement ---
    replacements = {
        '{{INSTANCE_ALIAS}}': data.get('instance_alias', 'Unknown'),
        '{{INSTANCE_ID}}': data.get('instance_id', ''),
        '{{DATE_RANGE}}': data.get('date_range', 'last 30 days'),
        # No hardcoded version fallback: the version is read from SKILL.md's
        # frontmatter and passed in. A literal here silently ships a stale number
        # whenever the caller forgets the key, which is exactly the drift the
        # single-source-of-truth rule exists to prevent.
        '{{VERSION}}': data['version'],
        '{{CONTACT_COUNT}}': str(data.get('contact_count', 0)),
        '{{FLOW_EVENT_COUNT}}': str(data.get('flow_event_count', 0)),
        '{{TRACED_COUNT}}': str(data.get('traced_count', 0)),
        '{{FLOW_NAMES}}': data.get('flow_names', 'N/A'),
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    # --- 2. Metric card injection ---
    # Replace each metrics-grid block with generated cards
    tab_metrics_map = {
        'tab-ivr': 'metrics_ivr',
        'tab-flow': 'metrics_flow',
        'tab-queue': 'metrics_queue',
        'tab-cost': 'metrics_cost',
    }

    for tab_id, data_key in tab_metrics_map.items():
        # Find the metrics-grid inside this tab
        tab_start = html.index(f'id="{tab_id}"')
        # Find the next metrics-grid after this tab start
        grid_start = html.index('<div class="metrics-grid">', tab_start)
        # Find the closing </div> of the metrics-grid
        # Count nested divs
        depth = 0
        pos = grid_start
        grid_end = None
        while pos < len(html):
            if html[pos:pos+4] == '<div':
                depth += 1
            elif html[pos:pos+6] == '</div>':
                depth -= 1
                if depth == 0:
                    grid_end = pos + 6
                    break
            pos += 1

        if grid_end:
            metrics = data.get(data_key, [])
            new_grid = _metrics_grid_html(metrics)
            html = html[:grid_start] + new_grid + html[grid_end:]

    # --- 3. Action card injection (tabs 3 & 4) ---
    tab_actions_map = {
        'tab-queue': 'actions_queue',
        'tab-cost': 'actions_cost',
    }

    for tab_id, data_key in tab_actions_map.items():
        marker = f'<!-- ACTIONS:{tab_id} -->'
        if marker in html:
            actions = data.get(data_key, [])
            html = html.replace(marker, _action_cards_html(actions))

    # --- 4. N/A fallbacks for unavailable tabs ---
    if not data.get('flow_available', True):
        # Replace tab-flow content with N/A callout (keep the tab)
        tab_start = html.index('id="tab-flow"')
        h2_end = html.index('</h2>', tab_start) + 5
        next_tab = html.index('id="tab-queue"')
        tab_end = html.rindex('</div>', h2_end, next_tab) + 6
        callout = _unavailable_callout(
            'CloudWatch contact flow logs required',
            data.get('flow_unavailable_reason', 'Flow logs not available.')
        )
        html = html[:h2_end] + '\n' + callout + '\n' + html[tab_end:]

    if not data.get('cost_available', True):
        tab_start = html.index('id="tab-cost"')
        h2_end = html.index('</h2>', tab_start) + 5
        script_start = html.index('<script>', h2_end)
        tab_end = html.rindex('</div>', h2_end, script_start) + 6
        callout = _unavailable_callout(
            'CUR 2.0 table not found',
            data.get('cost_unavailable_reason', 'No CUR 2.0 table discovered.')
        )
        html = html[:h2_end] + '\n' + callout + '\n' + html[tab_end:]

    # --- 5. Chart data injection ---
    # Replace the sample ECharts configs in the <script> block with real data.
    # Each chart config is: mk('chart-id', { ... });
    # We replace the entire config object.
    chart_ids = [
        'chart-sankey', 'chart-disconnect-reasons', 'chart-disposition',
        'chart-abandon', 'chart-transfers-by-queue', 'chart-block-funnel',
        'chart-time-to-drop', 'chart-queue-wait', 'chart-cost-by-service',
        'chart-cost-daily', 'chart-cost-connect',
    ]

    for chart_id in chart_ids:
        data_key = chart_id.replace('-', '_')  # chart-sankey → chart_sankey
        config = data.get(data_key)
        if config:
            # Find the existing mk('chart-id', { ... }); block.
            # Non-greedy to the first `});` -- the sample configs are written so
            # that sequence appears only at the end of each call.
            pattern = rf"mk\('{re.escape(chart_id)}',\s*\{{.*?\}}\);"
            match = re.search(pattern, html, re.DOTALL)
            if match:
                new_call = _chart_config_js(chart_id, config)
                html = html[:match.start()] + new_call + html[match.end():]

    # --- 6. Write output ---
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)

    return output_path


def validate_dashboard(html_path):
    """Run the standard validation checks on a generated dashboard.
    
    Returns dict of {check_name: bool}.
    """
    with open(html_path, 'r') as f:
        html = f.read()

    checks = {
        "4_tabs_present": all(t in html for t in ['tab-ivr', 'tab-flow', 'tab-queue', 'tab-cost']),
        "all_chart_ids": all(c in html for c in [
            'chart-sankey', 'chart-disconnect-reasons', 'chart-disposition',
            'chart-abandon', 'chart-transfers-by-queue', 'chart-block-funnel',
            'chart-time-to-drop', 'chart-queue-wait', 'chart-cost-by-service',
            'chart-cost-daily', 'chart-cost-connect']),
        "no_raw_placeholders": not re.search(r'\{\{[A-Z_]+\}\}', html),
        "splash_present": 'cw-splash' in html,
        "character_mark_present": 'cw-face' in html,
        "no_hardcoded_instance_ids": not re.search(r'i-[0-9a-f]{8,17}', html),
        "has_metric_cards": '<div class="metric-card">' in html,
    }
    return checks


if __name__ == '__main__':
    # Quick self-test with empty data
    print("ConnectWiz Renderer — self-test")
    print("Use: from connectwiz_render import render_dashboard, validate_dashboard")
