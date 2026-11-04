import pytest

from script_sei_utilizacao_indevida_v2.memorandos import MemoApisPeriodoDependentes
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisPeriodoDependentes import PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

MEMO_APIS = {'numero_sei': '150644870', 'nome_arvore': 'Memorando 2627', 'unidade': 'IPSEMG/APIS-Utilização'}
ARGS = {'nome_signatario': 'x', 'cargo_signatario': 'y', 'memo_apis': MEMO_APIS}


def _texto(dependentes: tuple[str, ...]) -> str:
    return ' '.join(MemoApisPeriodoDependentes.MemoApisPeriodoDependentes(dependentes=dependentes, **ARGS).paragrafos)


@pytest.fixture
def texto_liberado(monkeypatch):
    monkeypatch.setattr(MemoApisPeriodoDependentes, 'TEXTO_DEFINIDO', True)


def test_texto_pendente_nao_cria_memo():
    with pytest.raises(TextoMemoPendente):
        _texto(('555',))


@pytest.mark.usefixtures('texto_liberado')
@pytest.mark.parametrize(
    ('dependentes', 'esperado'),
    [
        (('555',), 'Matrícula do dependente</strong>: 555.'),
        (('555', '666'), 'Matrículas dos dependentes</strong>: 555; 666.'),
    ],
)
def test_cita_o_memo_da_apis_e_os_dependentes(dependentes, esperado):
    texto = _texto(dependentes)
    assert 'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)' in texto
    assert esperado in texto
    assert 'TODO' not in texto


@pytest.mark.usefixtures('texto_liberado')
def test_sem_matricula_de_dependente():
    assert 'Matrícula' not in _texto(())


@pytest.mark.usefixtures('texto_liberado')
def test_assunto_e_encontrado_pelo_padrao():
    memo = MemoApisPeriodoDependentes.MemoApisPeriodoDependentes(dependentes=('555',), **ARGS)
    assert PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES.search(memo.assunto)
