"""
Slow test: re-runs parts of the pipeline and checks that the result is identical
(same SEED -> same numbers). Skipped by default:

    pytest                     # fast, without this test
    pytest -m slow             # only the slow ones
    pytest -m ""               # all
"""
import numpy as np
import pandas as pd
import pytest

import config
from effect_model import compute_winsor_cap, inject_diluted_effect, winsorize_outcome

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def analytical_df():
    if not config.ANALYTICAL_TABLE.exists():
        pytest.skip("run `python run_all.py` first")
    return pd.read_parquet(config.ANALYTICAL_TABLE)


def _primary_lift(df):
    from scipy import stats
    is_t = (df.group == "treatment").values
    rng = np.random.default_rng(config.SEED)
    mv = inject_diluted_effect(df["merch_value"].values, is_t, rng)
    cap = compute_winsor_cap(df["merch_value"].values, config.WINSOR_Q)
    mvw = winsorize_outcome(mv, cap)
    t, c = mvw[is_t], mvw[~is_t]
    lift = t.mean() / c.mean() - 1
    p = stats.ttest_ind(t, c, equal_var=False)[1]
    return lift, p


def test_primary_is_bit_reproducible(analytical_df):
    a = _primary_lift(analytical_df)
    b = _primary_lift(analytical_df)
    assert a[0] == b[0]
    assert a[1] == b[1]


def test_primary_matches_committed_result(analytical_df, outputs_dir):
    import json
    lift, p = _primary_lift(analytical_df)
    f5 = json.loads((outputs_dir / "phase5_summary.json").read_text(encoding="utf-8"))
    committed = f5["1_primary_result"]["lift_pct"]
    assert abs(lift * 100 - committed) < 0.01
    assert p < 1e-6


def test_modeling_main_is_idempotent():
    """Running modeling.main() twice produces the same JSON (numbers)."""
    import json
    import modeling
    modeling.main()
    r1 = json.loads((config.OUT_TABLES / "phase4_summary.json").read_text(encoding="utf-8"))
    modeling.main()
    r2 = json.loads((config.OUT_TABLES / "phase4_summary.json").read_text(encoding="utf-8"))
    assert r1["4_ab_test"]["primary"] == r2["4_ab_test"]["primary"]
    assert r1["3_aa_calibration"] == r2["3_aa_calibration"]
