"""
The project's single reproducible entrypoint.

    python run_all.py

Runs the CRISP-DM phases in dependency order, verifies that each one generates its outputs
and finishes with a REPRODUCIBILITY REPORT: checks key invariants (decision == LAUNCH,
A/A false-positive rate ~5%, no SRM, guardrails intact, ...) and exits with code != 0
if any of them fails.

All parameters live in params.yaml. All seeds are fixed -> deterministic result.
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
    ("Phase 2 · profiling", "profiling_phase2", [config.OUT_TABLES / "phase2_summary.json"]),
    ("Phase 2 · figures", "figures_phase2", [config.OUT_FIGURES / "f2_02_aov_distribution.png"]),
    ("Phase 3 · preparation", "prepare_data",
     [config.ANALYTICAL_TABLE, config.OUT_TABLES / "phase3_transformations.csv"]),
    ("Phase 3 · balance + SRM", "balance_check",
     [config.OUT_TABLES / "phase3_balance.csv", config.OUT_TABLES / "phase3_srm.csv"]),
    ("Phase 4 · MDE break-even", "mde_cost_model", [config.OUT_TABLES / "mde_cost_model.csv"]),
    ("Phase 4 · modeling", "modeling", [config.OUT_TABLES / "phase4_summary.json"]),
    ("Phase 5 · evaluation", "evaluation", [config.OUT_TABLES / "phase5_summary.json"]),
]


def _load_csv_dict(path: Path) -> dict:
    import csv
    with open(path, encoding="utf-8") as f:
        return next(csv.DictReader(f))


def reproducibility_report() -> bool:
    f4 = json.loads((config.OUT_TABLES / "phase4_summary.json").read_text(encoding="utf-8"))
    f5 = json.loads((config.OUT_TABLES / "phase5_summary.json").read_text(encoding="utf-8"))
    srm = _load_csv_dict(config.OUT_TABLES / "phase3_srm.csv")
    bal = pd.read_csv(config.OUT_TABLES / "phase3_balance.csv")

    aa = f4["3_aa_calibration"]["merch_value"]["false_positive_rate_alpha_0.05"]
    prim = f5["1_primary_result"]
    # two-gate rule (significant after BH AND magnitude >= threshold) — see modeling.py::run_ab_test
    guard_ok = all(not g["blocks"] for g in f4["4_ab_test"]["guardrails"].values())
    ms = f4["8_ab_multiseed"]["raw"]

    checks = [
        ("decision == LAUNCH", f5["6_decision"]["decision"] == "LAUNCH"),
        ("A/A: false positives in [0.035, 0.065]", 0.035 <= aa <= 0.065),
        ("A/B primary: significant", prim["significant"]),
        ("A/B primary: 95% CI above the MDE", prim["relevant"]),
        ("A/B multi-seed (raw): |bias| < 0.3 pp", abs(ms["bias_pp"]) < 0.3),
        ("A/B multi-seed (raw): CI coverage in [0.90, 0.98]", 0.90 <= ms["CI95_coverage_of_+5pct"] <= 0.98),
        ("no SRM (p > 0.01)", float(srm["p_value"]) > 0.01),
        ("all covariates balanced", bool(bal["balanceada"].all())),
        ("guardrails: none blocks the launch (two-gate rule)", guard_ok),
        ("homogeneous effect across segments (no interaction after BH)",
         all(not v["heterogeneity_significant_after_BH"]
             for v in f5["4_segments"]["interaction_test"].values())),
    ]

    print("\n" + "=" * 64)
    print("REPRODUCIBILITY REPORT")
    print("=" * 64)
    for label, ok in checks:
        print(f"  [{'OK   ' if ok else 'FAIL '}] {label}")
    print("-" * 64)
    print(f"  A/B effect (winsor): +{f5['1_primary_result']['lift_pct']}%  "
          f"95% CI {f5['1_primary_result']['CI95_lift_pct']}  ·  decision: {f5['6_decision']['decision']}")
    print(f"  A/A false positives: {aa:.3f}  ·  SRM p: {srm['p_value']}  ·  "
          f"multi-seed raw bias: {ms['bias_pp']} pp")
    return all(ok for _, ok in checks)


def main() -> int:
    if not config.RAW.exists() or not list(config.RAW.glob("olist_*.csv")):
        print(f"ERROR: the Olist CSVs are missing from {config.RAW}\n"
              f"       download them with:  python -m kaggle datasets download "
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
            print(f"ERROR: {name} did not generate: {missing}", file=sys.stderr)
            return 3
        print(f"  OK ({time.time() - ts:.0f}s)")

    ok = reproducibility_report()
    print(f"\n  total time: {time.time() - t0:.0f}s")
    if not ok:
        print("\n  ✗ SOME CHECK FAILED — the results do not match what was expected.",
              file=sys.stderr)
        return 1
    print("\n  ✓ complete and reproducible pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
