import pytest

from tests.sei_falso import SEIFalso


@pytest.fixture
def sei(monkeypatch):
    falso = SEIFalso()
    falso.instalar(monkeypatch)
    return falso
