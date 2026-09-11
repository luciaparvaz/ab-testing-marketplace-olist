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
    p = outputs_dir / "fase4_resumen.json"
    if not p.exists():
        pytest.skip("run `python run_all.py` first")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def f5(outputs_dir):
    p = outputs_dir / "fase5_resumen.json"
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
    srm = pd.read_csv(outputs_dir / "fase3_srm.csv").iloc[0]
    assert srm["p_value"] > 0.01
    assert srm["veredicto"] == "no SRM"


def test_covariates_balanced(outputs_dir):
    bal = pd.read_csv(outputs_dir / "fase3_balance.csv")
    assert bal["balanceada"].all()
    assert bal["SMD"].abs().max() < 0.10


# ---- Phase 4 -----------------------------------------------------------------
def test_aa_calibration_false_positive_rate(f4):
    for metric in ("merch_value", "merch_value_w", "log_merch"):
        fpr = f4["3_aa_calibracion"][metric]["tasa_falsos_positivos_alpha_0.05"]
        assert 0.035 <= fpr <= 0.065, f"{metric}: FPR={fpr}"


def test_assumptions_lead_to_welch(f4):
    a = f4["2_supuestos"]
    assert a["normalidad_de_la_media_bootstrap"]["p"] > 0.05      # normal mean (CLT)
    assert float(a["homocedasticidad_con_efecto_diluido"]["p"]) < 0.05  # variances != under H1


def test_power_dilution_penalty_is_small(f4):
    pen = f4["1_power_analysis"]["crudo"]["penalizacion_potencia_por_dilucion_pp"]
    assert abs(pen) < 2.0


def test_multiseed_crudo_unbiased(f4):
    ms = f4["8_ab_multiseed"]["crudo"]
    assert abs(ms["sesgo_pp"]) < 0.3
    assert 0.90 <= ms["cobertura_IC95_del_+5pct"] <= 0.98


def test_guardrails_not_degraded(f4):
    """'bloquea' applies the two-gate rule (significant after BH AND magnitude >= threshold) and is
    the real field that run_all.py uses to decide; significativo_tras_BH alone must NOT
    govern the decision (see implementation audit, finding 2)."""
    for g in f4["4_ab_test"]["guardrails"].values():
        assert not g["bloquea"]


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
    assert g2["control"]["cancelados"] == int(expected.loc["control", "sum"])
    assert g2["treatment"]["cancelados"] == int(expected.loc["treatment", "sum"])


def test_guardrail_bloquea_is_two_gate_and(f4):
    """'bloquea' in the real guardrail (run_ab_test) must be exactly significativo_tras_BH AND
    magnitud_supera_umbral (True if there is no quantified threshold, e.g. G4) — the two-gate
    rule must live in the decision code, not only in the isolated demonstration function."""
    for g in f4["4_ab_test"]["guardrails"].values():
        mag = g["magnitud_supera_umbral"]
        expected = g["significativo_tras_BH"] and (True if mag is None else mag)
        assert g["bloquea"] == expected


def test_guardrail_thresholds_configured():
    from config import GUARDRAIL_THRESHOLDS
    assert GUARDRAIL_THRESHOLDS["g1_review_score_pts"] == 0.05
    assert GUARDRAIL_THRESHOLDS["g2_cancelacion_pp"] == 0.2
    assert GUARDRAIL_THRESHOLDS["g3_freight_share_of_aov_rise_pct"] == 20.0


def test_guardrail_regression_two_gate_rule(f4):
    escenarios = {s["regresion_inyectada_pts"]: s for s in f4["6_guardrail_regression"]["escenarios"]}
    assert escenarios[-0.03]["regla_AND_(significativo Y magnitud)"] is False   # does not block
    assert escenarios[-0.08]["regla_AND_(significativo Y magnitud)"] is True    # does block


def test_heterogeneous_effect_is_detected(f4):
    het = f4["7_efecto_heterogeneo"]
    assert het["heterogeneidad_detectada"] is True
    assert het["lift_en_banda_pct"] > het["lift_fuera_de_banda_pct"]


# ---- Phase 5 ---------------------------------------------------------------
def test_primary_result_significant_and_relevant(f5):
    prim = f5["1_resultado_primario"]
    assert prim["significativo"] is True
    assert prim["ci_entero_sobre_MDE"] is True
    assert prim["relevante"] is True
    assert 4.0 < prim["lift_pct"] < 8.0


def test_no_segment_heterogeneity(f5):
    for v in f5["4_segmentos"]["test_interaccion"].values():
        assert v["heterogeneidad_significativa_tras_BH"] is False


def test_p_hacking_log_scale_is_clean(f5):
    log = f5["5_p_hacking"]["test_en_LOG_(efecto_relativo)"]
    assert log["tras_BH"]["n"] == 0
    assert log["tras_Bonferroni"] == 0


def test_decision_is_lanzar(f5):
    assert f5["6_decision"]["decision"] == "LAUNCH"
