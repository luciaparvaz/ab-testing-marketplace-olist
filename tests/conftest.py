"""Configuración de pytest: pone src/ en el path y define un marcador `slow`."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUTPUTS = ROOT / "outputs" / "tables"


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: tests que re-ejecutan simulaciones (varios minutos)")


@pytest.fixture(scope="session")
def outputs_dir() -> Path:
    """Directorio de resultados. Los tests de `test_outputs.py` requieren haber corrido
    `python run_all.py` antes."""
    return OUTPUTS
