"""
Integration tests on the pipeline results.

REQUIRE having run beforehand:  python run_all.py
Verify the project's key invariants (the same ones run_all.py checks, here as a
pytest suite for CI).
"""
import json

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def f4(outputs_dir):
    p = outputs_dir / "phase4_summary.json"
    if not p.exists():
        pytest.skip("run `python run_all.py` first")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def f5(outputs_dir):
    p = outputs_dir / "phase5_summary.json"
    if not p.exists():
        pytest.skip("run `python run_all.py` first")
    return json.loads(p.read_text(encoding="utf-8"))


# ---- Phase 3 -----------------------------------------------------------------
def test_analytical_table_shape(outputs_dir):
    from config import ANALYTICAL_TABLE
    if not ANALYTICAL_TABLE.exists():
        pytest.skip("run `python run_all.py` first")
    df = pd.read_parquet(ANALYTICAL_TABLE)
    assert 90_000 < len(df) < 100_000
    assert df["customer_unique_id"].is_unique
    assert set(df["group"].unique()) == {"control", "treatment"}
    assert df.drop(columns=["review_score"]).notna().all().all()


def test_no_srm(outputs_dir):
    srm = pd.read_csv(outputs_dir / "phase3_srm.csv").iloc[0]
    assert srm["p_value"] > 0.01
    assert srm["verdict"] == "no SRM"


def test_covariates_balanced(outputs_dir):
    bal = pd.read_csv(outputs_dir / "phase3_balance.csv")
    assert bal["balanced"].all()
    assert bal["SMD"].abs().max() < 0.10


# ---- Phase 4 -----------------------------------------------------------------
def test_aa_calibration_false_positive_rate(f4):
    for metric in ("merch_value", "merch_value_w", "log_merch"):
        fpr = f4["3_aa_calibration"][metric]["false_positive_rate_alpha_0.05"]
        assert 0.035 <= fpr <= 0.065, f"{metric}: FPR={fpr}"


def test_assumptions_lead_to_welch(f4):
    a = f4["2_assumptions"]
    assert a["normality_bootstrap_mean"]["p"] > 0.05      # normal mean (CLT)
    assert float(a["homoscedasticity_diluted_effect"]["p"]) < 0.05  # variances != under H1


def test_power_dilution_penalty_is_small(f4):
    pen = f4["1_power_analysis"]["raw"]["power_penalty_from_dilution_pp"]
    assert abs(pen) < 2.0


def test_multiseed_raw_unbiased(f4):
    ms = f4["8_ab_multiseed"]["raw"]
    assert abs(ms["bias_pp"]) < 0.3
    assert 0.90 <= ms["CI95_coverage_of_+5pct"] <= 0.98


def test_guardrails_not_degraded(f4):
    """'blocks' applies the two-gate rule (significant after BH AND magnitude >= threshold) and is
    the real field that run_all.py uses to decide; significant_after_BH alone must NOT
    govern the decision (see implementation audit, finding 2)."""
    for g in f4["4_ab_test"]["guardrails"].values():
        assert not g["blocks"]


def test_g2_uses_same_assignment_as_analytical_table():
    """g2_cancellation_guardrail() must aggregate over the SAME control/treatment assignment
    persisted in analytical_table.parquet, not one recomputed by row position (implementation
    audit, finding 1). Verified by independently recomputing the control/treatment counts
    (direct customer->group merge) and comparing against what the real function returns."""
    from config import ANALYTICAL_TABLE, RAW, WINDOW_START, WINDOW_END
    if not ANALYTICAL_TABLE.exists():
        pytest.skip("run `python run_all.py` first")
    import modeling

    at = pd.read_parquet(ANALYTICAL_TABLE)[["customer_unique_id", "group"]]
    orders = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    m = (orders["order_purchase_timestamp"] >= WINDOW_START) & (orders["order_purchase_timestamp"] < WINDOW_END)
    o = orders[m].merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
    o = o.sort_values("order_purchase_timestamp").drop_duplicates("customer_unique_id", keep="first")
    o = o.merge(at, on="customer_unique_id", how="inner")
    o["canceled"] = (o["order_status"] == "canceled").astype(int)
    expected = o.groupby("group")["canceled"].agg(["sum", "count"])

    g2 = modeling.g2_cancellation_guardrail()
    assert g2["control"]["n"] == int(expected.loc["control", "count"])
    assert g2["treatment"]["n"] == int(expected.loc["treatment", "count"])
    assert g2["control"]["canceled"] == int(expected.loc["control", "sum"])
    assert g2["treatment"]["canceled"] == int(expected.loc["treatment", "sum"])


def test_guardrail_blocks_is_two_gate_and(f4):
    """'blocks' in the real guardrail (run_ab_test) must be exactly significant_after_BH AND
    magnitude_exceeds_threshold (True if there is no quantified threshold, e.g. G4) — the two-gate
    rule must live in the decision code, not only in the isolated demonstration function."""
    for g in f4["4_ab_test"]["guardrails"].values():
        mag = g["magnitude_exceeds_threshold"]
        expected = g["significant_after_BH"] and (True if mag is None else mag)
        assert g["blocks"] == expected


def test_guardrail_thresholds_configured():
    from config import GUARDRAIL_THRESHOLDS
    assert GUARDRAIL_THRESHOLDS["g1_review_score_pts"] == 0.05
    assert GUARDRAIL_THRESHOLDS["g2_cancelacion_pp"] == 0.2
    assert GUARDRAIL_THRESHOLDS["g3_freight_share_of_aov_rise_pct"] == 20.0
    # previously absent (G4 used to block on significance alone, no magnitude threshold --
    # portfolio review, priority 4): now quantified as a relative drop in control n_items.
    assert GUARDRAIL_THRESHOLDS["g4_n_items_relative_drop_pct"] == 5.0


def test_g4_magnitude_threshold_is_quantified(f4):
    """G4 no longer blocks on significance alone (mag=None) -- it must now carry a real
    threshold computed from GUARDRAIL_THRESHOLDS['g4_n_items_relative_drop_pct']
    (portfolio review, priority 4)."""
    g4 = f4["4_ab_test"]["guardrails"]["G4_n_items"]
    assert g4["magnitude_exceeds_threshold"] is not None
    assert isinstance(g4["magnitude_exceeds_threshold"], bool)
    assert g4["magnitude_threshold_items"] > 0


def test_guardrail_regression_two_gate_rule(f4):
    escenarios = {s["regression_injected_pts"]: s for s in f4["6_guardrail_regression"]["scenarios"]}
    assert escenarios[-0.03]["rule_AND_(significant_AND_magnitude)"] is False   # does not block
    assert escenarios[-0.08]["rule_AND_(significant_AND_magnitude)"] is True    # does block


def test_heterogeneous_effect_is_detected(f4):
    het = f4["7_heterogeneous_effect"]
    assert het["heterogeneity_detected"] is True
    assert het["lift_in_band_pct"] > het["lift_outside_band_pct"]


# ---- Phase 5 ---------------------------------------------------------------
def test_primary_result_significant_and_relevant(f5):
    prim = f5["1_primary_result"]
    assert prim["significant"] is True
    assert prim["ci_entirely_above_MDE"] is True
    assert prim["relevant"] is True
    assert 4.0 < prim["lift_pct"] < 8.0


def test_no_segment_heterogeneity(f5):
    for v in f5["4_segments"]["interaction_test"].values():
        assert v["heterogeneity_significant_after_BH"] is False


def test_p_hacking_log_scale_is_clean(f5):
    log = f5["5_p_hacking"]["test_at_LOG_(relative_effect)"]
    assert log["after_BH"]["n"] == 0
    assert log["after_Bonferroni"] == 0


def test_decision_is_valid_and_justified(f5):
    """Before: `decision == "LAUNCH"` hardcoded -- an acceptance criterion fixed on the result,
    not on the structure (audit §5.4). Now verifies the decision is one of the rule's three valid
    branches (§1.5) and comes with its justification and the MDE-vs-volume comparison that
    conditions it (portfolio review, priority 2) -- not that it has to be "LAUNCH" specifically."""
    dec = f5["6_decision"]
    assert dec["decision"] in {"LAUNCH", "ITERATE", "DO NOT LAUNCH"}
    assert len(dec["justification"]) > 0
    assert "MDE_vs_volume_consistency" in f5["2_business_impact"]


def test_decision_consistent_with_real_volume_breakeven(f5):
    """The headline decision must be self-consistent with the project's own cost model at the
    REAL volume used for the R$ impact -- not with an MDE calibrated for a ~7x larger marketplace
    scale (portfolio review, priority 2: before, 'LAUNCH' and the real ~+21% break-even coexisted
    without being reconciled)."""
    prim = f5["1_primary_result"]
    ci_lo = prim["CI95_lift_pct"][0]
    mde_real = f5["2_business_impact"]["MDE_vs_volume_consistency"][
        "MDE_break_even_AT_REAL_dataset_volume_pct"]
    if not prim["significant"] or prim["lift_pct"] <= 0:
        assert f5["6_decision"]["decision"] == "DO NOT LAUNCH"
    elif ci_lo > mde_real:
        assert f5["6_decision"]["decision"] == "LAUNCH"
    else:
        assert f5["6_decision"]["decision"] == "ITERATE"
