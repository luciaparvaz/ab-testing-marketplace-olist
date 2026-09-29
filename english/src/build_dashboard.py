"""
Interactive dashboard — presentation layer (like the notebook: ONLY reads outputs/, computes
nothing). Generates a self-contained .html (Plotly via CDN, no server) with the full experiment
result: decision, primary effect, guardrails, balance, segments, cost-model MDE, multi-seed
validation and the p-hacking demo.

Output: docs/dashboard.html
Regenerate after `python run_all.py`:  python src/build_dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import config

TABLES = config.OUT_TABLES
OUT_HTML = config.PROJECT_ROOT / "docs" / "dashboard.html"

# --- validated palette (dataviz skill / references/palette.md) — light mode -----------------
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def rj(name: str) -> dict:
    return json.loads((TABLES / name).read_text(encoding="utf-8"))


def load() -> dict:
    return {
        "f2": rj("phase2_summary.json"),
        "f4": rj("phase4_summary.json"),
        "f5": rj("phase5_summary.json"),
        "bal": pd.read_csv(TABLES / "phase3_balance.csv"),
        "srm": pd.read_csv(TABLES / "phase3_srm.csv").iloc[0],
        "seg": pd.read_csv(TABLES / "phase5_segments.csv"),
        "mde": pd.read_csv(TABLES / "mde_cost_model.csv"),
    }


def _base_layout(fig: go.Figure, height: int = 320, x_title: str = "", y_title: str = "") -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=20, t=44, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK2, size=12),
        hoverlabel=dict(bgcolor=SURFACE, font_color=INK, bordercolor=GRID),
        showlegend=False,
    )
    fig.update_xaxes(title=x_title, gridcolor=GRID, zerolinecolor=GRID, linecolor=MUTED, tickfont=dict(color=MUTED))
    fig.update_yaxes(title=y_title, gridcolor=GRID, zerolinecolor=GRID, linecolor=MUTED, tickfont=dict(color=MUTED))
    return fig


def div(fig: go.Figure) -> str:
    fig.update_layout(autosize=True)
    return fig.to_html(include_plotlyjs=False, full_html=False,
                       config={"displayModeBar": False, "responsive": True},
                       default_width="100%", default_height=None)


# ============================================================================
# 1. Forest plot — primary effect, several estimators
# ============================================================================
def fig_primary_forest(d: dict) -> str:
    p = d["f4"]["4_ab_test"]["primary"]
    anc = d["f5"]["3_ancova"]["adjusted"]
    rows = [
        ("Welch · raw", p["Welch_raw"]["lift_rel_pct"], *p["Welch_raw"]["CI95_lift_pct"]),
        ("Welch · winsor p99.5 (primary)", p["Welch_winsor_p99.5"]["lift_rel_pct"], *p["Welch_winsor_p99.5"]["CI95_lift_pct"]),
        ("log (geometric means)", p["log_geom_ratio"]["lift_geom_pct"], None, None),
        ("bootstrap (10k, no assumptions)", sum(p["bootstrap_ratio"]["CI95_lift_pct"]) / 2, *p["bootstrap_ratio"]["CI95_lift_pct"]),
        ("ANCOVA (covariate-adjusted)", anc["lift_pct"], *anc["ci95_pct"]),
    ]
    fig = go.Figure()
    mde = config.MDE_RELEVANCIA
    ate = config.ATE * 100
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    fig.add_vline(x=mde, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_vline(x=ate, line_color=CAT[2], line_width=1.5, line_dash="dash")
    for i, (name, lift, lo, hi) in enumerate(rows):
        color = CAT[1] if "primary" in name else CAT[0]
        if lo is not None:
            fig.add_trace(go.Scatter(x=[lo, hi], y=[i, i], mode="lines",
                                     line=dict(color=color, width=2), hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=[lift], y=[i], mode="markers", marker=dict(color=color, size=10),
            hovertemplate=f"<b>{name}</b><br>lift = {lift:+.2f}%<br>"
                          + (f"95% CI [{lo:+.2f}%, {hi:+.2f}%]<extra></extra>" if lo is not None else "no CI<extra></extra>")))
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(rows))), ticktext=[r[0] for r in rows],
                     autorange="reversed")
    fig.update_xaxes(ticksuffix="%")
    fig = _base_layout(fig, height=260, x_title="AOV lift (%)")
    breakeven_real = d["f5"]["2_business_impact"]["MDE_vs_volume_consistency"][
        "MDE_break_even_AT_REAL_dataset_volume_pct"]
    fig.add_annotation(x=1, y=1.12, xref="paper", yref="paper", xanchor="right",
                       text=f"real break-even (+{breakeven_real:.1f}%) is off this range →",
                       showarrow=False, font=dict(color=STATUS["critical"], size=10))
    return div(fig)


# ============================================================================
# 2. Guardrails — table with status (two-gate rule)
# ============================================================================
def guardrails_table(d: dict) -> str:
    g = d["f4"]["4_ab_test"]["guardrails"]
    labels = {"G1_review_score": "G1 · satisfaction (review_score)",
              "G2_cancellation": "G2 · cancellation",
              "G3_freight_value": "G3 · freight cost",
              "G4_n_items": "G4 · items per order"}
    rows = []
    for k, v in g.items():
        blocks = v["blocks"]
        badge = ("serious", "⚠ blocks") if blocks else ("good", "✓ no block")
        diff_key = "diff_pp" if "diff_pp" in v else "diff"
        c_key = "control_pct" if "control_pct" in v else "control"
        t_key = "treatment_pct" if "treatment_pct" in v else "treatment"
        rows.append(f"""
        <tr>
          <td>{labels.get(k, k)}</td>
          <td class="num">{v[c_key]}</td>
          <td class="num">{v[t_key]}</td>
          <td class="num">{v[diff_key]:+.4f}</td>
          <td class="num">{v['p_adjusted_BH']:.3f}</td>
          <td><span class="badge badge-{badge[0]}">{badge[1]}</span></td>
        </tr>""")
    return f"""
    <table class="gtable">
      <thead><tr><th>Guardrail</th><th>Control</th><th>Treatment</th><th>Δ</th><th>p (BH)</th><th>Status</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="footnote">Two-gate rule: blocks only if significant after Benjamini-Hochberg
    <b>and</b> the magnitude exceeds the business threshold declared in <code>params.yaml</code>.</p>
    """


# ============================================================================
# 3. Covariate balance (love plot) + SRM
# ============================================================================
def fig_balance(d: dict) -> str:
    bal = d["bal"].sort_values("SMD", key=lambda s: s.abs())
    fig = go.Figure()
    fig.add_vline(x=0.10, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_trace(go.Scatter(
        x=bal["SMD"].abs(), y=bal["covariate"], mode="markers",
        marker=dict(color=CAT[0], size=10),
        customdata=bal[["type", "p_value"]].values,
        hovertemplate="<b>%{y}</b><br>|SMD| = %{x:.4f}<br>type: %{customdata[0]}<br>p = %{customdata[1]:.3f}<extra></extra>"))
    fig.update_xaxes(range=[0, max(0.12, bal["SMD"].abs().max() * 1.3)])
    fig.add_annotation(x=0.10, y=1.08, yref="paper", text="threshold 0.10", showarrow=False,
                       font=dict(color=STATUS["serious"], size=10), xanchor="left")
    fig = _base_layout(fig, height=260, x_title="|SMD| (standardized mean difference)")
    return div(fig)


# ============================================================================
# 4. Pre-specified segments (forest plot, color by family)
# ============================================================================
def fig_segments(d: dict) -> str:
    seg = d["seg"]
    families = list(dict.fromkeys(seg["segmento"]))
    fam_color = {f: CAT[i % len(CAT)] for i, f in enumerate(families)}
    seg = seg.iloc[::-1].reset_index(drop=True)
    fig = go.Figure()
    mde = config.MDE_RELEVANCIA
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    fig.add_vline(x=mde, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    seen = set()
    for i, r in seg.iterrows():
        color = fam_color[r["segmento"]]
        showlegend = r["segmento"] not in seen
        seen.add(r["segmento"])
        fig.add_trace(go.Scatter(x=[r["ci_lo"], r["ci_hi"]], y=[i, i], mode="lines",
                                 line=dict(color=color, width=2), hoverinfo="skip",
                                 legendgroup=r["segmento"], showlegend=False))
        fig.add_trace(go.Scatter(
            x=[r["lift_pct"]], y=[i], mode="markers", marker=dict(color=color, size=8),
            legendgroup=r["segmento"], name=r["segmento"], showlegend=showlegend,
            hovertemplate=f"<b>{r['segmento']}: {r['nivel']}</b><br>lift = {r['lift_pct']:+.2f}%<br>"
                          f"95% CI [{r['ci_lo']:+.2f}%, {r['ci_hi']:+.2f}%]<br>n = {r['n_c']}+{r['n_t']}<extra></extra>"))
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(seg))),
                     ticktext=[f"{r.nivel}" for r in seg.itertuples()])
    fig.update_xaxes(ticksuffix="%")
    fig = _base_layout(fig, height=480, x_title="relative AOV lift (%)")
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 5. Relevance MDE — cost-derived break-even
# ============================================================================
def fig_mde_breakeven(d: dict) -> str:
    mde = d["mde"]
    imp = d["f5"]["2_business_impact"]
    fig = go.Figure()
    for i, yrs in enumerate(sorted(mde["horizonte_payback_anios"].unique())):
        sub = mde[mde["horizonte_payback_anios"] == yrs].sort_values("pedidos_anio")
        fig.add_trace(go.Scatter(x=sub["pedidos_anio"], y=sub["MDE_breakeven_pct"], mode="lines",
                                 line=dict(color=CAT[i], width=2), name=f"payback {yrs} year(s)",
                                 hovertemplate=f"payback {yrs}y<br>%{{x:,.0f}} orders/year<br>break-even %{{y:.1f}}%<extra></extra>"))
    fig.add_hline(y=config.MDE_RELEVANCIA, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_vline(x=imp["estimated_orders_per_year"], line_color=MUTED, line_width=1.5, line_dash="dash")
    fig.update_xaxes(type="log", title="orders / year")
    fig.update_yaxes(type="log", title="MDE break-even (%)", ticksuffix="%")
    fig.add_annotation(x=imp["estimated_orders_per_year"], y=0.02, yref="paper", xanchor="left",
                       text=f"real volume (~{imp['estimated_orders_per_year']:,})", showarrow=False,
                       font=dict(color=MUTED, size=10))
    fig = _base_layout(fig, height=300)
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 6. Multi-seed validation — decision rate (500 re-randomizations)
# ============================================================================
def fig_multiseed(d: dict) -> str:
    ms = d["f4"]["8_ab_multiseed"]
    cats = ["LAUNCH", "ITERATE", "DO NOT LAUNCH"]
    colors = {"LAUNCH": STATUS["good"], "ITERATE": STATUS["warning"], "DO NOT LAUNCH": STATUS["critical"]}
    fig = go.Figure()
    for cat in cats:
        fig.add_trace(go.Bar(
            x=["raw", "winsor p99.5"], y=[ms["raw"]["decision_rate"][cat], ms["winsor_p99.5"]["decision_rate"][cat]],
            name=cat, marker_color=colors[cat],
            hovertemplate=f"<b>{cat}</b><br>%{{x}}<br>%{{y:.0%}} of 500 replicates<extra></extra>",
            text=[f"{ms['raw']['decision_rate'][cat]:.0%}", f"{ms['winsor_p99.5']['decision_rate'][cat]:.0%}"],
            textposition="inside", textfont=dict(color="#ffffff", size=11)))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig = _base_layout(fig, height=280)
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 7. p-hacking demo — level vs log, before/after correction
# ============================================================================
def fig_phacking(d: dict) -> str:
    ph = d["f5"]["5_p_hacking"]
    stages = ["nominal (p<0.05)", "after BH", "after Bonferroni"]
    level = [ph["test_at_LEVEL_(mv_w)"]["nominal_p<0.05"]["n"], ph["test_at_LEVEL_(mv_w)"]["after_BH"]["n"],
             ph["test_at_LEVEL_(mv_w)"]["after_Bonferroni"]]
    log = [ph["test_at_LOG_(relative_effect)"]["nominal_p<0.05"]["n"], ph["test_at_LOG_(relative_effect)"]["after_BH"]["n"],
           ph["test_at_LOG_(relative_effect)"]["after_Bonferroni"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stages, y=level, name="wrong scale (level, R$)", marker_color=CAT[7],
                         hovertemplate="%{x}<br>%{y} \"findings\" at LEVEL<extra></extra>"))
    fig.add_trace(go.Bar(x=stages, y=log, name="correct scale (log, %)", marker_color=CAT[0],
                         hovertemplate="%{x}<br>%{y} findings at LOG<extra></extra>"))
    fig.add_hline(y=ph["expected_by_chance_at_0.05"], line_color=MUTED, line_width=1.5, line_dash="dash")
    fig.add_annotation(x=0, y=ph["expected_by_chance_at_0.05"], xanchor="left", yanchor="bottom",
                       text=f"expected by chance ≈ {ph['expected_by_chance_at_0.05']}", showarrow=False,
                       font=dict(color=MUTED, size=10))
    fig = _base_layout(fig, height=280, y_title=f"# of \"significant\" cuts (of {ph['n_exploratory_cuts']})")
    fig.update_layout(barmode="group", showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# Page
# ============================================================================
def stat_tile(label: str, value: str, sub: str = "", status: str | None = None) -> str:
    cls = f" tile-{status}" if status else ""
    return f"""<div class="tile{cls}"><div class="tile-label">{label}</div>
    <div class="tile-value">{value}</div><div class="tile-sub">{sub}</div></div>"""


def build_html(d: dict) -> str:
    prim = d["f5"]["1_primary_result"]
    imp = d["f5"]["2_business_impact"]
    dec = d["f5"]["6_decision"]
    aa = d["f4"]["3_aa_calibration"]["merch_value"]
    srm = d["srm"]

    dec_status = {"LAUNCH": "good", "ITERATE": "warning", "DO NOT LAUNCH": "critical"}[dec["decision"]]
    hero = f"""
    <div class="hero">
      <div class="hero-badge badge-{dec_status}">{dec['decision']}</div>
      <div class="hero-stats">
        {stat_tile("Primary effect (AOV)", f"+{prim['lift_pct']}%", f"95% CI [{prim['CI95_lift_pct'][0]:+.2f}%, {prim['CI95_lift_pct'][1]:+.2f}%]")}
        {stat_tile("Significance", f"log₁₀(p) = {prim['log10_p']}", "p < 0.0001", status="good")}
        {stat_tile("Annual GMV impact", f"+R$ {imp['uplift_GMV_annual_R$']:,.0f}", f"CI [{imp['uplift_GMV_annual_CI95_R$'][0]:,.0f}, {imp['uplift_GMV_annual_CI95_R$'][1]:,.0f}]")}
        {stat_tile("Real break-even", f"+{imp['MDE_vs_volume_consistency']['MDE_break_even_AT_REAL_dataset_volume_pct']:.1f}%", f"vs. +{imp['MDE_vs_volume_consistency']['declared_MDE_pct']:.0f}% declared", status="serious")}
      </div>
    </div>"""

    calib = f"""
    <div class="hero-stats">
      {stat_tile("A/A false positives", f"{aa['false_positive_rate_alpha_0.05']:.1%}", "nominal 5% · 2,000 partitions", status="good")}
      {stat_tile("SRM (sample ratio mismatch)", srm["verdict"], f"χ² p = {srm['p_value']:.2f}", status="good")}
      {stat_tile("Covariate balance", "all |SMD| < 0.10" if bool(d['bal']['balanced'].all()) else "review", "", status="good" if bool(d['bal']['balanced'].all()) else "serious")}
      {stat_tile("Power of the SUPERSEDED rule", f"{d['f4']['8_ab_multiseed']['winsor_p99.5']['decision_rate']['LAUNCH']:.0%}", "LAUNCH under the declared MDE (not the real rule, see below)", status="warning")}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard — A/B testing marketplace (Olist)</title>
<script src="{PLOTLY_CDN}"></script>
<style>
  :root {{
    --surface: {SURFACE}; --page: {PAGE}; --ink: {INK}; --ink2: {INK2}; --muted: {MUTED}; --grid: {GRID};
    --good: {STATUS['good']}; --warning: {STATUS['warning']}; --serious: {STATUS['serious']}; --critical: {STATUS['critical']};
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--page); color: var(--ink);
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 24px 16px 64px; }}
  header {{ margin-bottom: 24px; }}
  header h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  header p {{ color: var(--ink2); margin: 0; font-size: 0.92rem; }}
  header a {{ color: var(--ink2); }}
  .note {{ background: #fff8e8; border: 1px solid #f0dca0; border-radius: 8px; padding: 12px 16px;
          font-size: 0.85rem; color: var(--ink2); margin: 16px 0 24px; }}
  .card {{ background: var(--surface); border: 1px solid var(--grid); border-radius: 12px;
          padding: 20px; margin-bottom: 20px; min-width: 0; }}
  .card .js-plotly-plot {{ width: 100% !important; }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 4px; }}
  .card .desc {{ color: var(--ink2); font-size: 0.85rem; margin: 0 0 14px; }}
  .hero {{ background: var(--surface); border: 1px solid var(--grid); border-radius: 12px;
          padding: 20px; margin-bottom: 12px; }}
  .hero-badge {{ display: inline-block; font-weight: 700; font-size: 1.1rem; padding: 6px 16px;
                border-radius: 999px; color: #fff; margin-bottom: 16px; }}
  .hero-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }}
  .tile {{ border: 1px solid var(--grid); border-radius: 10px; padding: 12px 14px; }}
  .tile-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.02em; }}
  .tile-value {{ font-size: 1.35rem; font-weight: 600; margin: 2px 0; }}
  .tile-sub {{ font-size: 0.78rem; color: var(--ink2); }}
  .tile-good {{ border-left: 3px solid var(--good); }}
  .tile-warning {{ border-left: 3px solid var(--warning); }}
  .tile-serious {{ border-left: 3px solid var(--serious); }}
  .badge-good {{ background: var(--good); }}
  .badge-warning {{ background: var(--warning); color: #3a2b00 !important; }}
  .badge-critical {{ background: var(--critical); }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; color: #fff; font-size: 0.8rem; font-weight: 600; }}
  .gtable {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  .gtable th {{ text-align: left; color: var(--muted); font-weight: 600; font-size: 0.75rem;
               text-transform: uppercase; padding: 6px 10px; border-bottom: 1px solid var(--grid); }}
  .gtable td {{ padding: 8px 10px; border-bottom: 1px solid var(--grid); }}
  .gtable .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .footnote {{ font-size: 0.78rem; color: var(--muted); margin-top: 10px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  footer {{ color: var(--muted); font-size: 0.8rem; text-align: center; margin-top: 32px; }}
  footer a {{ color: var(--ink2); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>A/B testing in a marketplace (Olist) — dashboard</h1>
    <p>Portfolio project · CRISP-DM methodology ·
      <a href="../README.md">full README</a> ·
      <a href="full_report.md">reference report</a></p>
  </header>

  <div class="note">⚠️ <b>Note on methodological honesty.</b> The Olist dataset does not contain a
    real experiment. The assignment is simulated (50/50 per customer) and the redesign's effect is
    injected in a declared way (ATE = +5%). The goal is not to discover whether the redesign
    works — we know it does, because we are the ones who put the effect there — but to demonstrate
    that the experimental design and statistical analysis control false positives, recover an
    effect of known size without bias, and distinguish statistical significance from business
    relevance.</p>
  </div>

  {hero}

  <div class="card">
    <h2>Design calibration</h2>
    <div class="desc">Checks before interpreting any result: does the test detect noise as if it were an effect? did the assignment end up imbalanced?</div>
    {calib}
  </div>

  <div class="card">
    <h2>Primary effect — robustness across estimators</h2>
    <div class="desc">Same effect, five ways to estimate it (raw, winsorized, log, bootstrap, covariate-adjusted). The dotted red line is the declared MDE (+3%); the dashed green one, the true injected ATE (+5%). The threshold that actually decides (real-volume break-even, card above) sits far above every estimator here — that's why the decision is ITERATE even though all of them clear the declared +3%. <i>Note: the ANCOVA adjusts for n_items/category, attributes of the order as already placed, not baseline — harmless here by construction, see <code>docs/05_evaluation.md §5.3</code>.</i></div>
    {fig_primary_forest(d)}
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Covariate balance (Phase 3)</h2>
      <div class="desc">Are control and treatment interchangeable before the effect is injected? Threshold |SMD| &lt; 0.10.</div>
      {fig_balance(d)}
    </div>
    <div class="card">
      <h2>Guardrails (Phase 4)</h2>
      <div class="desc">No control metric should degrade (no effect is injected into guardrails).</div>
      {guardrails_table(d)}
    </div>
  </div>

  <div class="card">
    <h2>Effect by pre-specified segment</h2>
    <div class="desc">treat×segment interaction test (Wald HC3 + Benjamini-Hochberg). No significant heterogeneity → the relative effect is homogeneous, consistent with the design.</div>
    {fig_segments(d)}
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Relevance MDE — cost-derived break-even</h2>
      <div class="desc">The declared +3% is only break-even from ~415k orders/year; the real dataset has ~59k.</div>
      {fig_mde_breakeven(d)}
    </div>
    <div class="card">
      <h2>Multi-seed validation (500 replicates)</h2>
      <div class="desc">Power of the <b>full decision rule</b> (not just rejecting H0) under the declared MDE.</div>
      {fig_multiseed(d)}
    </div>
  </div>

  <div class="card">
    <h2>p-hacking demonstration</h2>
    <div class="desc">38 exploratory cuts without pre-specification. On the wrong scale (R$ level), artifacts of the multiplicative effect survive even Bonferroni. On the correct scale (log, %), nothing survives.</div>
    {fig_phacking(d)}
  </div>

  <footer>
    Automatically generated from <code>outputs/</code> by <code>src/build_dashboard.py</code> — computes nothing, only presents.
    Full, reproducible code: <a href="https://github.com/luciaparvaz/ab-testing-marketplace-olist">repository</a>.
  </footer>
</div>
</body>
</html>"""


def main():
    d = load()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(d), encoding="utf-8")
    print(f"Dashboard written to {OUT_HTML}")


if __name__ == "__main__":
    main()
