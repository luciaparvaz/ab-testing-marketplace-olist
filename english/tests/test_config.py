"""Sanity checks on the configuration (params.yaml -> config.py)."""
import config


def test_seed_is_fixed():
    assert config.SEED == 42


def test_ate_is_derived_correctly():
    assert config.ATE == config.P_RESP * config.DELTA_RESP
    assert abs(config.ATE - 0.05) < 1e-12


def test_alpha_and_mde():
    assert config.ALPHA == 0.05
    assert config.MDE_RELEVANCIA == 3.0


def test_window_is_20_months():
    start = config.WINDOW_START
    end = config.WINDOW_END
    assert start == "2017-01-01"
    # exclusive window at 2018-09-01 -> 20 months
    import pandas as pd
    months = (pd.Timestamp(end).to_period("M") - pd.Timestamp(start).to_period("M")).n
    assert months == 20


def test_paths_exist_and_are_absolute():
    for p in (config.RAW, config.PROC, config.OUT_TABLES, config.OUT_FIGURES):
        assert p.is_absolute()
    # PROC / OUT_* are created on importing config
    assert config.PROC.exists()
    assert config.OUT_TABLES.exists()


def test_valid_status_is_a_set():
    assert isinstance(config.VALID_STATUS, set)
    assert "delivered" in config.VALID_STATUS
    assert "canceled" not in config.VALID_STATUS


def test_no_module_redefines_constants():
    """No other module should redefine SEED/ALPHA/... at module level."""
    import ast
    from pathlib import Path
    src = Path(config.__file__).parent
    forbidden = {"SEED", "ALPHA", "P_RESP", "DELTA_RESP", "EPS_SD", "WINSOR_Q",
                 "WINDOW_START", "WINDOW_END", "MDE_RELEVANCIA"}
    offenders = []
    for py in src.glob("*.py"):
        if py.name in ("config.py",):
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:  # module-level assignments only
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id in forbidden:
                        offenders.append(f"{py.name}:{tgt.id}")
    assert not offenders, f"constants redefined outside config.py: {offenders}"
