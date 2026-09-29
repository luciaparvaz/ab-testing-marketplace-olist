"""Pytest configuration: puts src/ on the path and defines a `slow` marker."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUTPUTS = ROOT / "outputs" / "tables"


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: tests that re-run simulations (several minutes)")


@pytest.fixture(scope="session")
def outputs_dir() -> Path:
    """Results directory. The tests in `test_outputs.py` require having run
    `python run_all.py` beforehand."""
    return OUTPUTS
