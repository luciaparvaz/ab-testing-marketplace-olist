"""Tests unitarios del efecto de tratamiento sintético (modelo diluido)."""
import numpy as np
import pytest

import config
from effect_model import inject_diluted_effect


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    values = rng.lognormal(mean=4.5, sigma=0.9, size=200_000)   # ~ como el AOV
    is_treat = rng.random(200_000) < 0.5
    return values, is_treat


def test_control_group_is_untouched(data):
    values, is_treat = data
    out = inject_diluted_effect(values, is_treat, np.random.default_rng(config.SEED))
    assert np.array_equal(out[~is_treat], values[~is_treat])


def test_average_treatment_effect_matches_ate(data):
    values, is_treat = data
    out = inject_diluted_effect(values, is_treat, np.random.default_rng(config.SEED))
    lift = out[is_treat].mean() / values[is_treat].mean() - 1
    # ATE declarado = 5 %; margen amplio por el ruido de muestreo
    assert abs(lift - config.ATE) < 0.01


def test_responder_share_is_p_resp(data):
    values, is_treat = data
    rng = np.random.default_rng(config.SEED)
    out = inject_diluted_effect(values, is_treat, rng)
    changed = out[is_treat] != values[is_treat]
    assert abs(changed.mean() - config.P_RESP) < 0.01


def test_deterministic_with_same_seed(data):
    values, is_treat = data
    a = inject_diluted_effect(values, is_treat, np.random.default_rng(123))
    b = inject_diluted_effect(values, is_treat, np.random.default_rng(123))
    assert np.array_equal(a, b)


def test_different_seed_gives_different_result(data):
    values, is_treat = data
    a = inject_diluted_effect(values, is_treat, np.random.default_rng(1))
    b = inject_diluted_effect(values, is_treat, np.random.default_rng(2))
    assert not np.array_equal(a, b)


def test_effect_is_multiplicative_and_positive_on_responders(data):
    values, is_treat = data
    out = inject_diluted_effect(values, is_treat, np.random.default_rng(config.SEED))
    ratio = out[is_treat] / values[is_treat]
    responders = ratio != 1.0
    # entre respondedores el factor medio ~ 1 + delta_resp
    assert abs(ratio[responders].mean() - (1 + config.DELTA_RESP)) < 0.01
