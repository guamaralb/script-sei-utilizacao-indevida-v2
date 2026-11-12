import planilha_controle
import pytest

from tests.sei_falso import SEIFalso


@pytest.fixture(autouse=True)
def _backup_controle_temporario(tmp_path, monkeypatch):
    """Nenhum teste grava em dados/controle/backup: a rotação dos backups (30
    mais recentes) apagaria os backups reais da planilha de controle."""
    monkeypatch.setattr(planilha_controle, 'DIR_BACKUP_CONTROLE', tmp_path / 'backup_controle')


@pytest.fixture
def sei(monkeypatch):
    falso = SEIFalso()
    falso.instalar(monkeypatch)
    return falso
