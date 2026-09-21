"""
Único entrypoint reproducible del proyecto.

    python run_all.py

Ejecuta las fases de CRISP-DM en orden de dependencia, verifica que cada una genera sus salidas
y termina con un INFORME DE REPRODUCIBILIDAD: comprueba invariantes clave (decisión == LANZAR,
tasa de falsos positivos del A/A ~5 %, sin SRM, guardrails intactos, …) y sale con código != 0
si alguna falla.

Todos los parámetros están en params.yaml. Todas las semillas son fijas -> resultado determinista.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config  # noqa: E402

STEPS = [
    ("Fase 2 · perfilado", "profiling_fase2", [config.OUT_TABLES / "fase2_resumen.json"]),
    ("Fase 2 · figuras", "figures_fase2", [config.OUT_FIGURES / "f2_02_distribucion_aov.png"]),
    ("Fase 3 · preparación", "prepare_data",
     [config.ANALYTICAL_TABLE, config.OUT_TABLES / "fase3_transformaciones.csv"]),
    ("Fase 3 · balance + SRM", "balance_check",
     [config.OUT_TABLES / "fase3_balance.csv", config.OUT_TABLES / "fase3_srm.csv"]),
    ("Fase 4 · MDE break-even", "mde_cost_model", [config.OUT_TABLES / "mde_cost_model.csv"]),
    ("Fase 4 · modeling", "modeling", [config.OUT_TABLES / "fase4_resumen.json"]),
    ("Fase 5 · evaluación", "evaluation", [config.OUT_TABLES / "fase5_resumen.json"]),
]


def _load_csv_dict(path: Path) -> dict:
    import csv
    with open(path, encoding="utf-8") as f:
        return next(csv.DictReader(f))


def reproducibility_report() -> bool:
    f4 = json.loads((config.OUT_TABLES / "fase4_resumen.json").read_text(encoding="utf-8"))
    f5 = json.loads((config.OUT_TABLES / "fase5_resumen.json").read_text(encoding="utf-8"))
    srm = _load_csv_dict(config.OUT_TABLES / "fase3_srm.csv")
    bal = pd.read_csv(config.OUT_TABLES / "fase3_balance.csv")

    aa = f4["3_aa_calibracion"]["merch_value"]["tasa_falsos_positivos_alpha_0.05"]
    prim = f5["1_resultado_primario"]
    # regla de dos puertas (significativo tras BH Y magnitud >= umbral) — ver modeling.py::run_ab_test
    guard_ok = all(not g["bloquea"] for g in f4["4_ab_test"]["guardrails"].values())
    ms = f4["8_ab_multiseed"]["crudo"]

    checks = [
        # Antes: `decision == "LANZAR"` -- un criterio de aceptación fijado sobre el RESULTADO en
        # vez de sobre la estructura del pipeline (auditoría §5.4: "el pipeline falla si el
        # análisis cambia de conclusión, el resultado deja de ser falsable"). Se sustituye por un
        # invariante estructural: la decisión debe ser una de las tres ramas válidas de la regla
        # §1.5 y venir acompañada de su justificación -- no que tenga que ser una en concreto.
        ("decisión es una de LANZAR/ITERAR/NO LANZAR, con justificación",
         f5["6_decision"]["decision"] in {"LANZAR", "ITERAR", "NO LANZAR"}
         and len(f5["6_decision"]["justificacion"]) > 0),
        ("A/A: falsos positivos en [0.035, 0.065]", 0.035 <= aa <= 0.065),
        ("A/B primario: significativo", prim["significativo"]),
        ("A/B primario: IC 95 % por encima del MDE", prim["relevante"]),
        ("A/B multi-semilla (crudo): |sesgo| < 0.3 pp", abs(ms["sesgo_pp"]) < 0.3),
        ("A/B multi-semilla (crudo): cobertura IC en [0.90, 0.98]", 0.90 <= ms["cobertura_IC95_del_+5pct"] <= 0.98),
        ("sin SRM (p > 0.01)", float(srm["p_value"]) > 0.01),
        ("todas las covariables balanceadas", bool(bal["balanceada"].all())),
        ("guardrails: ninguno bloquea el lanzamiento (regla de dos puertas)", guard_ok),
        ("efecto homogéneo entre segmentos (sin interacción tras BH)",
         all(not v["heterogeneidad_significativa_tras_BH"]
             for v in f5["4_segmentos"]["test_interaccion"].values())),
    ]

    print("\n" + "=" * 64)
    print("INFORME DE REPRODUCIBILIDAD")
    print("=" * 64)
    for label, ok in checks:
        print(f"  [{'OK   ' if ok else 'FALLO'}] {label}")
    print("-" * 64)
    print(f"  Efecto A/B (winsor): +{f5['1_resultado_primario']['lift_pct']}%  "
          f"IC95 {f5['1_resultado_primario']['IC95_lift_pct']}  ·  decisión: {f5['6_decision']['decision']}")
    print(f"  A/A falsos positivos: {aa:.3f}  ·  SRM p: {srm['p_value']}  ·  "
          f"multi-semilla sesgo crudo: {ms['sesgo_pp']} pp")
    return all(ok for _, ok in checks)


def main() -> int:
    if not config.RAW.exists() or not list(config.RAW.glob("olist_*.csv")):
        print(f"ERROR: faltan los CSV de Olist en {config.RAW}\n"
              f"       descárgalos con:  python -m kaggle datasets download "
              f"-d olistbr/brazilian-ecommerce -p data/raw --unzip", file=sys.stderr)
        return 2

    print(config.summary())
    t0 = time.time()
    for name, mod_name, outputs in STEPS:
        print(f"\n=== {name} ===")
        ts = time.time()
        mod = importlib.import_module(mod_name)
        mod.main()
        missing = [str(o) for o in outputs if not o.exists()]
        if missing:
            print(f"ERROR: {name} no generó: {missing}", file=sys.stderr)
            return 3
        print(f"  OK ({time.time() - ts:.0f}s)")

    ok = reproducibility_report()
    print(f"\n  tiempo total: {time.time() - t0:.0f}s")
    if not ok:
        print("\n  ✗ ALGUNA COMPROBACIÓN FALLÓ — los resultados no coinciden con lo esperado.",
              file=sys.stderr)
        return 1
    print("\n  ✓ pipeline completo y reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
