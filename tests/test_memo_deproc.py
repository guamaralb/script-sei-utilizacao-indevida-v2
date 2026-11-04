import pytest

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import (
    ASSUNTO_MEMO_DEPROC,
    ASSUNTO_MEMO_DEPROC_DUAS_REDES,
    PADRAO_ASSUNTO_MEMO_DEPROC,
    MemoDeproc,
)

MEMO_APIS = {'numero_sei': '150644870', 'nome_arvore': 'Memorando 2627', 'unidade': 'IPSEMG/APIS-Utilização'}
DADOS = DadosUI(nome_titular='José da Silva', matricula_titular='1234567', periodo_titular='01/2024 a 06/2024', periodo_dependentes=False, matriculas_dependentes='555; 666')
ARGS = {'dados': DADOS, 'memo_apis': MEMO_APIS, 'nome_signatario': 'x', 'cargo_signatario': 'y'}


def _texto(memo) -> str:
    return ' '.join(memo.paragrafos).replace('<strong>', '').replace('</strong>', '')


def test_duas_redes_cita_relatorios_e_manifestacao():
    memo = MemoDeproc(docs_relatorio_rc=('111', '222'), doc_relatorio_disa='333', doc_manifestacao_disa='444', **ARGS)
    texto = _texto(memo)
    assert memo.assunto == ASSUNTO_MEMO_DEPROC_DUAS_REDES
    assert 'realizados nas redes credenciada e própria pelo titular' in texto
    assert 'extraídos do SADS, constantes dos documentos 111 e 222.' in texto
    assert 'constante do documento 333, conforme manifestação no documento 444.' in texto
    assert 'atendimentos de ambas as redes' in texto


def test_so_rede_credenciada_nao_cita_a_rede_propria():
    memo = MemoDeproc(docs_relatorio_rc=('111',), **ARGS)
    texto = _texto(memo)
    assert memo.assunto == ASSUNTO_MEMO_DEPROC
    assert 'constantes do documento 111.' in texto
    assert 'atendimentos da rede credenciada' in texto
    assert 'própria' not in texto
    assert 'DISA' not in texto


def test_periodo_dos_dependentes_e_o_do_titular():
    texto = _texto(MemoDeproc(docs_relatorio_rc=('111',), **ARGS))
    assert 'Período de apuração dos dependentes: 01/2024 a 06/2024' in texto


def test_sem_dependentes_nao_mostra_periodo_dos_dependentes():
    dados = DadosUI(nome_titular='José da Silva', matricula_titular='1234567', periodo_titular='01/2024 a 06/2024', periodo_dependentes=False)
    texto = _texto(MemoDeproc(docs_relatorio_rc=('111',), **{**ARGS, 'dados': dados}))
    assert 'Período de apuração dos dependentes' not in texto


def test_exige_relatorios_da_rede_credenciada():
    with pytest.raises(ValueError, match='rede credenciada'):
        MemoDeproc(docs_relatorio_rc=(), **ARGS)


def test_exige_relatorio_e_manifestacao_da_disa_juntos():
    with pytest.raises(ValueError, match='manifestação'):
        MemoDeproc(docs_relatorio_rc=('111',), doc_relatorio_disa='333', **ARGS)


@pytest.mark.parametrize('assunto', [ASSUNTO_MEMO_DEPROC, ASSUNTO_MEMO_DEPROC_DUAS_REDES, 'Levantamento de coparticipação - utilização indevida da assistência à saúde'])
def test_padrao_encontra_os_assuntos(assunto):
    assert PADRAO_ASSUNTO_MEMO_DEPROC.search(assunto)
