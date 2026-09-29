"""
Single project configuration.

Loads `params.yaml` (single source of truth for scientific parameters) and adds the paths
and derived values. **All other modules import from here; none defines constants.**

Paths are absolute (derived from this file's location), so the scripts, the
notebook and the tests work from any working directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows opens stdout as cp1252 by default
except Exception:
    pass

# --- paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAMS_FILE = PROJECT_ROOT / "params.yaml"
RAW = PROJECT_ROOT / "data" / "raw"
PROC = PROJECT_ROOT / "data" / "processed"
OUT_TABLES = PROJECT_ROOT / "outputs" / "tables"
OUT_FIGURES = PROJECT_ROOT / "outputs" / "figures"
ANALYTICAL_TABLE = PROC / "analytical_table.parquet"
for _d in (PROC, OUT_TABLES, OUT_FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

# --- parameters (from params.yaml) --------------------------------------
_P = yaml.safe_load(PARAMS_FILE.read_text(encoding="utf-8"))

SEED: int = _P["seed"]
ALPHA: float = _P["alpha"]

P_RESP: float = _P["effect"]["p_resp"]
DELTA_RESP: float = _P["effect"]["delta_resp"]
EPS_SD: float = _P["effect"]["eps_sd"]
ATE: float = P_RESP * DELTA_RESP                     # derived: mean effect (+5%)

MDE_RELEVANCIA: float = _P["mde_relevancia_pct"]     # in %
TARGET_POWER: float = _P["target_power"]

GUARDRAIL_THRESHOLDS: dict = _P["guardrail_thresholds"]

WINDOW_START: str = _P["window_start"]
WINDOW_END: str = _P["window_end"]
VALID_STATUS: set[str] = set(_P["valid_status"])
WINSOR_Q: float = _P["winsor_q"]

N_SIM_AA: int = _P["n_sim_aa"]
N_SIM_POWER: int = _P["n_sim_power"]
N_SIM_MULTISEED: int = _P["n_sim_multiseed"]
N_BOOT: int = _P["n_bootstrap"]

COST_MODEL: dict = _P["cost_model"]

# --- figure style (shared) ---------------------------------------------
PLOT_RC = {"figure.dpi": 110, "savefig.dpi": 130, "font.size": 10,
           "axes.spines.top": False, "axes.spines.right": False}


def apply_plot_style() -> None:
    import matplotlib.pyplot as plt
    plt.rcParams.update(PLOT_RC)


def summary() -> str:
    return (f"SEED={SEED} ALPHA={ALPHA} | diluted effect p_resp={P_RESP} delta_resp={DELTA_RESP} "
            f"-> ATE={ATE:.2%} | MDE={MDE_RELEVANCIA}% | window {WINDOW_START}..{WINDOW_END} | "
            f"winsor q={WINSOR_Q} | n_sim_aa={N_SIM_AA}")


if __name__ == "__main__":
    print(summary())
    print("PROJECT_ROOT:", PROJECT_ROOT)
