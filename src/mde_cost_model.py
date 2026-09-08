"""
Mejora nº 4 de la auditoría global — derivar el MDE de relevancia de un modelo de costes,
en vez de asertarlo.

El "MDE de relevancia" es el lift de AOV por debajo del cual el margen incremental anual NO cubre
el coste total de propiedad del rediseño (construir + mantener). Todo son asunciones DECLARADAS y
a efectos ilustrativos; el dataset de Olist no trae costes ni take rate.

Salida: outputs/tables/mde_cost_model.csv  +  outputs/figures/f_mde_breakeven.png
"""

from __future__ import annotations

try:
    import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

OUT_T = Path("outputs/tables")
FIG = Path("outputs/figures")

# ---- asunciones declaradas (ilustrativas) ---------------------------------
AOV_BASE = 137.0                 # R$, de la Fase 2
COMMISSION = 0.15                # take rate del marketplace sobre el GMV
NET_MARGIN_ON_COMMISSION = 0.80  # tras procesamiento de pago y soporte -> margen neto sobre la comisión
BUILD_COST = 250_000             # R$, coste único de construir (motor de reco + UI + QA)
MAINT_COST_YEAR = 80_000         # R$/año, infraestructura + reentrenamiento + mantenimiento
PAYBACK_YEARS = 2                # horizonte en el que el cambio debe amortizarse

# volumen anual de pedidos: rango. El dataset da ~58.700; un marketplace mediano-grande, mucho más.
VOLUME_GRID = [58_700, 250_000, 1_000_000, 5_000_000, 20_000_000]


def breakeven_lift(volume: float,
                   build=BUILD_COST, maint=MAINT_COST_YEAR, years=PAYBACK_YEARS) -> float:
    """Lift relativo de AOV (fracción) que iguala margen incremental acumulado y coste total."""
    margin_per_lift_year = AOV_BASE * volume * COMMISSION * NET_MARGIN_ON_COMMISSION
    total_cost = build + maint * years
    total_margin_per_lift = margin_per_lift_year * years
    return total_cost / total_margin_per_lift


def main():
    rows = []
    for v in VOLUME_GRID:
        for yrs in (1, 2, 3):
            bl = breakeven_lift(v, years=yrs)
            rows.append({"pedidos_anio": v, "horizonte_payback_anios": yrs,
                         "MDE_breakeven_pct": round(bl * 100, 3)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT_T / "mde_cost_model.csv", index=False)

    print("=== MDE de relevancia derivado de costes ===")
    print(f"asunciones: AOV R$ {AOV_BASE:.0f} · comisión {COMMISSION:.0%} · margen neto sobre comisión "
          f"{NET_MARGIN_ON_COMMISSION:.0%}")
    print(f"            construir R$ {BUILD_COST:,} · mantener R$ {MAINT_COST_YEAR:,}/año\n")
    piv = df.pivot(index="pedidos_anio", columns="horizonte_payback_anios", values="MDE_breakeven_pct")
    piv.columns = [f"payback {c}a  (MDE %)" for c in piv.columns]
    print(piv.to_string())

    v_data = 58_700
    v_mid = 1_000_000
    print(f"\nLectura:")
    print(f"  · Al volumen del propio dataset (~{v_data:,} pedidos/año) el break-even es "
          f"~+{breakeven_lift(v_data)*100:.1f}%  ->  el MDE de +3% NO estaría justificado a esa escala.")
    print(f"  · A escala de marketplace mediano (~{v_mid:,} pedidos/año) el break-even es "
          f"~+{breakeven_lift(v_mid)*100:.2f}%  ->  +3% es CONSERVADOR (deja margen).")
    print(f"  · El proyecto asume implícitamente esa segunda escala. El +3% se mantiene como umbral "
          f"pero queda condicionado a volumen >= ~{ (BUILD_COST+MAINT_COST_YEAR*PAYBACK_YEARS)/(AOV_BASE*COMMISSION*NET_MARGIN_ON_COMMISSION*PAYBACK_YEARS*0.03):,.0f} pedidos/año.")

    fig, ax = plt.subplots(figsize=(7, 3.8))
    vols = np.logspace(np.log10(40_000), np.log10(20_000_000), 60)
    for yrs, col in zip((1, 2, 3), ("#c1121f", "#3b6ea5", "#2a9d8f")):
        ax.plot(vols, [breakeven_lift(v, years=yrs) * 100 for v in vols], color=col,
                label=f"payback {yrs} año(s)")
    ax.axhline(3.0, color="#666", ls="--", lw=1, label="MDE asumido (+3%)")
    ax.axvline(58_700, color="#999", ls=":", lw=1)
    ax.annotate("volumen del dataset", (58_700, 40), fontsize=7, rotation=90, va="bottom")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("pedidos / año"); ax.set_ylabel("MDE break-even (%)")
    ax.set_title("MDE de relevancia derivado de costes: cae con el volumen de pedidos")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "f_mde_breakeven.png", dpi=130)
    print(f"\nfigura -> {FIG / 'f_mde_breakeven.png'}")


if __name__ == "__main__":
    main()
