"""
Dashboard interactivo — capa de presentación (como el notebook: SOLO lee outputs/, no calcula
nada). Genera un .html autocontenido (Plotly vía CDN, sin servidor) con el resultado completo
del experimento: decisión, efecto primario, guardrails, balance, segmentos, MDE de costes,
validación multi-semilla y demo de p-hacking.

Salida: docs/dashboard.html
Regenerar tras `python run_all.py`:  python src/build_dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import config

TABLES = config.OUT_TABLES
OUT_HTML = config.PROJECT_ROOT / "docs" / "dashboard.html"

# --- paleta validada (skill dataviz / references/palette.md) — modo claro ------------------
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def rj(name: str) -> dict:
    return json.loads((TABLES / name).read_text(encoding="utf-8"))


def load() -> dict:
    return {
        "f2": rj("fase2_resumen.json"),
        "f4": rj("fase4_resumen.json"),
        "f5": rj("fase5_resumen.json"),
        "bal": pd.read_csv(TABLES / "fase3_balance.csv"),
        "srm": pd.read_csv(TABLES / "fase3_srm.csv").iloc[0],
        "seg": pd.read_csv(TABLES / "fase5_segmentos.csv"),
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
# 1. Forest plot — efecto primario, varios estimadores
# ============================================================================
def fig_primary_forest(d: dict) -> str:
    p = d["f4"]["4_ab_test"]["primario"]
    anc = d["f5"]["3_ancova"]["con_ajuste"]
    rows = [
        ("Welch · crudo", p["Welch_crudo"]["lift_rel_pct"], *p["Welch_crudo"]["IC95_lift_pct"]),
        ("Welch · winsor p99,5 (primario)", p["Welch_winsor_p99.5"]["lift_rel_pct"], *p["Welch_winsor_p99.5"]["IC95_lift_pct"]),
        ("log (medias geométricas)", p["log_geom_ratio"]["lift_geom_pct"], None, None),
        ("bootstrap (10k, sin supuestos)", sum(p["bootstrap_ratio"]["IC95_lift_pct"]) / 2, *p["bootstrap_ratio"]["IC95_lift_pct"]),
        ("ANCOVA (ajustado por covariables)", anc["lift_pct"], *anc["ci95_pct"]),
    ]
    fig = go.Figure()
    mde = config.MDE_RELEVANCIA
    ate = config.ATE * 100
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    fig.add_vline(x=mde, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_vline(x=ate, line_color=CAT[2], line_width=1.5, line_dash="dash")
    for i, (name, lift, lo, hi) in enumerate(rows):
        color = CAT[1] if "primario" in name else CAT[0]
        if lo is not None:
            fig.add_trace(go.Scatter(x=[lo, hi], y=[i, i], mode="lines",
                                     line=dict(color=color, width=2), hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=[lift], y=[i], mode="markers", marker=dict(color=color, size=10),
            hovertemplate=f"<b>{name}</b><br>lift = {lift:+.2f}%<br>"
                          + (f"IC95 [{lo:+.2f}%, {hi:+.2f}%]<extra></extra>" if lo is not None else "sin IC<extra></extra>")))
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(rows))), ticktext=[r[0] for r in rows],
                     autorange="reversed")
    fig.update_xaxes(ticksuffix="%")
    fig = _base_layout(fig, height=260, x_title="lift del AOV (%)")
    breakeven_real = d["f5"]["2_impacto_negocio"]["consistencia_MDE_vs_volumen"][
        "MDE_break_even_AL_VOLUMEN_REAL_del_dataset_pct"]
    fig.add_annotation(x=1, y=1.12, xref="paper", yref="paper", xanchor="right",
                       text=f"break-even real (+{breakeven_real:.1f}%) queda fuera de este rango →",
                       showarrow=False, font=dict(color=STATUS["critical"], size=10))
    return div(fig)


# ============================================================================
# 2. Guardrails — tabla con estado (regla de dos puertas)
# ============================================================================
def guardrails_table(d: dict) -> str:
    g = d["f4"]["4_ab_test"]["guardrails"]
    labels = {"G1_review_score": "G1 · satisfacción (review_score)",
              "G2_cancelacion": "G2 · cancelación",
              "G3_freight_value": "G3 · flete asumido",
              "G4_n_items": "G4 · ítems por pedido"}
    rows = []
    for k, v in g.items():
        bloquea = v["bloquea"]
        badge = ("serious", "⚠ bloquea") if bloquea else ("good", "✓ no bloquea")
        diff_key = "diff_pp" if "diff_pp" in v else "diff"
        c_key = "control_pct" if "control_pct" in v else "control"
        t_key = "treatment_pct" if "treatment_pct" in v else "treatment"
        rows.append(f"""
        <tr>
          <td>{labels.get(k, k)}</td>
          <td class="num">{v[c_key]}</td>
          <td class="num">{v[t_key]}</td>
          <td class="num">{v[diff_key]:+.4f}</td>
          <td class="num">{v['p_ajustado_BH']:.3f}</td>
          <td><span class="badge badge-{badge[0]}">{badge[1]}</span></td>
        </tr>""")
    return f"""
    <table class="gtable">
      <thead><tr><th>Guardrail</th><th>Control</th><th>Treatment</th><th>Δ</th><th>p (BH)</th><th>Estado</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class="footnote">Regla de dos puertas: bloquea solo si es significativo tras Benjamini-Hochberg
    <b>y</b> la magnitud supera el umbral de negocio declarado en <code>params.yaml</code>.</p>
    """


# ============================================================================
# 3. Balance de covariables (love plot) + SRM
# ============================================================================
def fig_balance(d: dict) -> str:
    bal = d["bal"].sort_values("SMD", key=lambda s: s.abs())
    fig = go.Figure()
    fig.add_vline(x=0.10, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_trace(go.Scatter(
        x=bal["SMD"].abs(), y=bal["covariable"], mode="markers",
        marker=dict(color=CAT[0], size=10),
        customdata=bal[["tipo", "p_value"]].values,
        hovertemplate="<b>%{y}</b><br>|SMD| = %{x:.4f}<br>tipo: %{customdata[0]}<br>p = %{customdata[1]:.3f}<extra></extra>"))
    fig.update_xaxes(range=[0, max(0.12, bal["SMD"].abs().max() * 1.3)])
    fig.add_annotation(x=0.10, y=1.08, yref="paper", text="umbral 0,10", showarrow=False,
                       font=dict(color=STATUS["serious"], size=10), xanchor="left")
    fig = _base_layout(fig, height=260, x_title="|SMD| (standardized mean difference)")
    return div(fig)


# ============================================================================
# 4. Segmentos pre-especificados (forest plot, color por familia)
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
                          f"IC95 [{r['ci_lo']:+.2f}%, {r['ci_hi']:+.2f}%]<br>n = {r['n_c']}+{r['n_t']}<extra></extra>"))
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(seg))),
                     ticktext=[f"{r.nivel}" for r in seg.itertuples()])
    fig.update_xaxes(ticksuffix="%")
    fig = _base_layout(fig, height=480, x_title="lift relativo del AOV (%)")
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 5. MDE de relevancia — break-even derivado de costes
# ============================================================================
def fig_mde_breakeven(d: dict) -> str:
    mde = d["mde"]
    imp = d["f5"]["2_impacto_negocio"]
    fig = go.Figure()
    for i, yrs in enumerate(sorted(mde["horizonte_payback_anios"].unique())):
        sub = mde[mde["horizonte_payback_anios"] == yrs].sort_values("pedidos_anio")
        fig.add_trace(go.Scatter(x=sub["pedidos_anio"], y=sub["MDE_breakeven_pct"], mode="lines",
                                 line=dict(color=CAT[i], width=2), name=f"payback {yrs} año(s)",
                                 hovertemplate=f"payback {yrs}a<br>%{{x:,.0f}} pedidos/año<br>break-even %{{y:.1f}}%<extra></extra>"))
    fig.add_hline(y=config.MDE_RELEVANCIA, line_color=STATUS["serious"], line_width=1.5, line_dash="dot")
    fig.add_vline(x=imp["pedidos_por_anio_estimado"], line_color=MUTED, line_width=1.5, line_dash="dash")
    fig.update_xaxes(type="log", title="pedidos / año")
    fig.update_yaxes(type="log", title="MDE break-even (%)", ticksuffix="%")
    fig.add_annotation(x=imp["pedidos_por_anio_estimado"], y=0.02, yref="paper", xanchor="left",
                       text=f"volumen real (~{imp['pedidos_por_anio_estimado']:,})", showarrow=False,
                       font=dict(color=MUTED, size=10))
    fig = _base_layout(fig, height=300)
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 6. Validación multi-semilla — tasa de decisión (500 re-aleatorizaciones)
# ============================================================================
def fig_multiseed(d: dict) -> str:
    ms = d["f4"]["8_ab_multiseed"]
    cats = ["LANZAR", "ITERAR", "NO LANZAR"]
    colors = {"LANZAR": STATUS["good"], "ITERAR": STATUS["warning"], "NO LANZAR": STATUS["critical"]}
    fig = go.Figure()
    for cat in cats:
        fig.add_trace(go.Bar(
            x=["crudo", "winsor p99,5"], y=[ms["crudo"]["tasa_decision"][cat], ms["winsor_p99.5"]["tasa_decision"][cat]],
            name=cat, marker_color=colors[cat],
            hovertemplate=f"<b>{cat}</b><br>%{{x}}<br>%{{y:.0%}} de 500 réplicas<extra></extra>",
            text=[f"{ms['crudo']['tasa_decision'][cat]:.0%}", f"{ms['winsor_p99.5']['tasa_decision'][cat]:.0%}"],
            textposition="inside", textfont=dict(color="#ffffff", size=11)))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig = _base_layout(fig, height=280)
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# 7. Demo de p-hacking — nivel vs log, antes/después de corrección
# ============================================================================
def fig_phacking(d: dict) -> str:
    ph = d["f5"]["5_p_hacking"]
    stages = ["nominal (p<0,05)", "tras BH", "tras Bonferroni"]
    nivel = [ph["test_en_NIVEL_(mv_w)"]["nominales_p<0.05"]["n"], ph["test_en_NIVEL_(mv_w)"]["tras_BH"]["n"],
             ph["test_en_NIVEL_(mv_w)"]["tras_Bonferroni"]]
    log = [ph["test_en_LOG_(efecto_relativo)"]["nominales_p<0.05"]["n"], ph["test_en_LOG_(efecto_relativo)"]["tras_BH"]["n"],
           ph["test_en_LOG_(efecto_relativo)"]["tras_Bonferroni"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stages, y=nivel, name="escala equivocada (nivel, R$)", marker_color=CAT[7],
                         hovertemplate="%{x}<br>%{y} \"hallazgos\" en NIVEL<extra></extra>"))
    fig.add_trace(go.Bar(x=stages, y=log, name="escala correcta (log, %)", marker_color=CAT[0],
                         hovertemplate="%{x}<br>%{y} hallazgos en LOG<extra></extra>"))
    fig.add_hline(y=ph["esperados_por_azar_a_0.05"], line_color=MUTED, line_width=1.5, line_dash="dash")
    fig.add_annotation(x=0, y=ph["esperados_por_azar_a_0.05"], xanchor="left", yanchor="bottom",
                       text=f"esperado por azar ≈ {ph['esperados_por_azar_a_0.05']}", showarrow=False,
                       font=dict(color=MUTED, size=10))
    fig = _base_layout(fig, height=280, y_title=f"nº de cortes \"significativos\" (de {ph['n_cortes_exploratorios']})")
    fig.update_layout(barmode="group", showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)))
    return div(fig)


# ============================================================================
# Página
# ============================================================================
def stat_tile(label: str, value: str, sub: str = "", status: str | None = None) -> str:
    cls = f" tile-{status}" if status else ""
    return f"""<div class="tile{cls}"><div class="tile-label">{label}</div>
    <div class="tile-value">{value}</div><div class="tile-sub">{sub}</div></div>"""


def build_html(d: dict) -> str:
    prim = d["f5"]["1_resultado_primario"]
    imp = d["f5"]["2_impacto_negocio"]
    dec = d["f5"]["6_decision"]
    aa = d["f4"]["3_aa_calibracion"]["merch_value"]
    srm = d["srm"]

    dec_status = {"LANZAR": "good", "ITERAR": "warning", "NO LANZAR": "critical"}[dec["decision"]]
    hero = f"""
    <div class="hero">
      <div class="hero-badge badge-{dec_status}">{dec['decision']}</div>
      <div class="hero-stats">
        {stat_tile("Efecto primario (AOV)", f"+{prim['lift_pct']}%", f"IC95 [{prim['IC95_lift_pct'][0]:+.2f}%, {prim['IC95_lift_pct'][1]:+.2f}%]")}
        {stat_tile("Significancia", f"log₁₀(p) = {prim['log10_p']}", "p < 0,0001", status="good")}
        {stat_tile("Impacto GMV anual", f"+R$ {imp['uplift_GMV_anual_R$']:,.0f}", f"IC [{imp['uplift_GMV_anual_IC95_R$'][0]:,.0f}, {imp['uplift_GMV_anual_IC95_R$'][1]:,.0f}]")}
        {stat_tile("Break-even real", f"+{imp['consistencia_MDE_vs_volumen']['MDE_break_even_AL_VOLUMEN_REAL_del_dataset_pct']:.1f}%", f"vs. +{imp['consistencia_MDE_vs_volumen']['MDE_declarado_pct']:.0f}% declarado", status="serious")}
      </div>
    </div>"""

    calib = f"""
    <div class="hero-stats">
      {stat_tile("A/A falsos positivos", f"{aa['tasa_falsos_positivos_alpha_0.05']:.1%}", "nominal 5% · 2.000 particiones", status="good")}
      {stat_tile("SRM (sample ratio mismatch)", srm["veredicto"], f"χ² p = {srm['p_value']:.2f}", status="good")}
      {stat_tile("Balance de covariables", "todas |SMD| < 0,10" if bool(d['bal']['balanceada'].all()) else "revisar", "", status="good" if bool(d['bal']['balanceada'].all()) else "serious")}
      {stat_tile("Potencia de la regla YA SUPERADA", f"{d['f4']['8_ab_multiseed']['winsor_p99.5']['tasa_decision']['LANZAR']:.0%}", "LANZAR bajo el MDE declarado (no la regla real, ver abajo)", status="warning")}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
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
    <h1>A/B testing en un marketplace (Olist) — dashboard</h1>
    <p>Proyecto de portfolio · metodología CRISP-DM ·
      <a href="../README.md">ver README completo</a> ·
      <a href="informe_completo.md">informe de referencia</a></p>
  </header>

  <div class="note">⚠️ <b>Nota de honestidad metodológica.</b> El dataset de Olist no contiene un
    experimento real. La asignación se simula (50/50 por cliente) y el efecto del rediseño se
    inyecta de forma declarada (ATE = +5%). El objetivo no es descubrir si el rediseño funciona
    —lo sabemos, porque el efecto lo ponemos nosotros— sino demostrar que el diseño y el análisis
    estadístico controlan los falsos positivos, recuperan sin sesgo un efecto de tamaño conocido,
    y distinguen significancia de relevancia de negocio.</p>
  </div>

  {hero}

  <div class="card">
    <h2>Calibración del diseño</h2>
    <div class="desc">Controles previos a interpretar cualquier resultado: ¿el test detecta ruido como si fuera efecto? ¿la asignación quedó desbalanceada?</div>
    {calib}
  </div>

  <div class="card">
    <h2>Efecto primario — robustez entre estimadores</h2>
    <div class="desc">Mismo efecto, cinco formas de estimarlo (crudo, winsorizado, log, bootstrap, ajustado por covariables). La línea punteada roja es el MDE declarado (+3%); la verde discontinua, el ATE verdadero inyectado (+5%). El umbral que realmente decide (break-even al volumen real, tarjeta de arriba) queda muy por encima de todos estos estimadores — por eso la decisión es ITERAR aunque todos superen el +3% declarado. <i>Nota: el ANCOVA ajusta por n_items/categoría, atributos del pedido ya realizado, no basales — inocuo aquí por construcción, ver <code>docs/05_evaluation.md §5.3</code>.</i></div>
    {fig_primary_forest(d)}
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Balance de covariables (Fase 3)</h2>
      <div class="desc">¿Control y treatment son intercambiables antes de inyectar el efecto? Umbral |SMD| &lt; 0,10.</div>
      {fig_balance(d)}
    </div>
    <div class="card">
      <h2>Guardrails (Fase 4)</h2>
      <div class="desc">Ninguna métrica de control debería degradarse (no se inyecta efecto en guardrails).</div>
      {guardrails_table(d)}
    </div>
  </div>

  <div class="card">
    <h2>Efecto por segmento pre-especificado</h2>
    <div class="desc">Test de interacción treat×segmento (Wald HC3 + Benjamini-Hochberg). Sin heterogeneidad significativa → el efecto relativo es homogéneo, coherente con el diseño.</div>
    {fig_segments(d)}
  </div>

  <div class="grid2">
    <div class="card">
      <h2>MDE de relevancia — break-even derivado de costes</h2>
      <div class="desc">El +3% declarado solo es break-even a partir de ~415k pedidos/año; el dataset real tiene ~59k.</div>
      {fig_mde_breakeven(d)}
    </div>
    <div class="card">
      <h2>Validación multi-semilla (500 réplicas)</h2>
      <div class="desc">Potencia de la <b>regla de decisión completa</b> (no solo de rechazar H0) bajo el MDE declarado.</div>
      {fig_multiseed(d)}
    </div>
  </div>

  <div class="card">
    <h2>Demostración de p-hacking</h2>
    <div class="desc">38 cortes exploratorios sin pre-especificar. En la escala equivocada (R$ nivel), artefactos del efecto multiplicativo sobreviven incluso a Bonferroni. En la escala correcta (log, %), no queda nada.</div>
    {fig_phacking(d)}
  </div>

  <footer>
    Generado automáticamente desde <code>outputs/</code> por <code>src/build_dashboard.py</code> — no calcula nada, solo presenta.
    Código completo y reproducible: <a href="https://github.com/luciaparvaz/ab-testing-marketplace-olist">repositorio</a>.
  </footer>
</div>
</body>
</html>"""


def main():
    d = load()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(d), encoding="utf-8")
    print(f"Dashboard escrito en {OUT_HTML}")


if __name__ == "__main__":
    main()
