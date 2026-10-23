import pytest

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import identificar_doc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    MemoDisaSemMantisSolicitaRelatorio,
    MemoDisaValidarConsta,
    MemoDisaValidarNaoConsta,
)
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import UsoRedeBeneficiarios

MEMO_APIS = {'numero_sei': '150644870', 'nome_arvore': 'Memorando 2627', 'unidade': 'IPSEMG/APIS-Utilização'}
DADOS = DadosUI(nome_titular='José da Silva', matricula_titular='1234567', periodo_titular='01/2024 a 06/2024', periodo_dependentes=False)
ASSINATURA = {'nome_signatario': 'x', 'cargo_signatario': 'y'}


def _texto(memo) -> str:
    return ' '.join(memo.paragrafos)


def test_identificar_doc():
    assert identificar_doc(MEMO_APIS) == 'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)'
    assert identificar_doc({**MEMO_APIS, 'nome_arvore': 'Despacho'}) == 'Despacho IPSEMG/APIS-UTILIZAÇÃO (150644870)'


@pytest.mark.parametrize(
    ('docs', 'esperado'),
    [
        (('111',), ['no documento 111', 'constantes do documento 111', 'em substituição ao documento 111']),
        (('111', '222'), ['nos documentos 111 e 222', 'constantes dos documentos 111 e 222', 'em substituição aos documentos 111 e 222']),
    ],
)
def test_validar_consta_cita_os_relatorios(docs, esperado):
    memo = MemoDisaValidarConsta(
        dados=DADOS,
        memo_apis=MEMO_APIS,
        uso_disa=UsoRedeBeneficiarios('1234567', True),
        tit_usou_mantis=True,
        deps_que_usaram_mantis=(),
        docs_relatorio_rp=docs,
        **ASSINATURA,
    )
    texto = _texto(memo).replace('<strong>', '').replace('</strong>', '')
    for trecho in esperado:
        assert trecho in texto
    assert 'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)' in texto
    assert memo.destinatario_nome == 'Felippe Gonçalves Declie Fagioli<br>Diretor de Saúde - DISA'
    assert memo.vocativo == 'Prezado Diretor'


def test_validar_exige_os_relatorios():
    with pytest.raises(ValueError, match='número SEI dos relatórios'):
        MemoDisaValidarNaoConsta(
            dados=DADOS,
            memo_apis=MEMO_APIS,
            uso_disa=UsoRedeBeneficiarios('1234567', False),
            tit_usou_mantis=True,
            deps_que_usaram_mantis=(),
            docs_relatorio_rp=(),
            **ASSINATURA,
        )


def test_sem_mantis_cita_o_memo_da_apis_e_nao_cita_documento():
    memo = MemoDisaSemMantisSolicitaRelatorio(
        dados=DADOS,
        memo_apis=MEMO_APIS,
        uso_disa=UsoRedeBeneficiarios('1234567', True),
        tit_usou_mantis=False,
        deps_que_usaram_mantis=(),
        **ASSINATURA,
    )
    texto = _texto(memo)
    assert 'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)' in texto
    assert 'documento ' not in texto.replace('documentos anteriores', '')
    assert 'J.S.' in texto
    assert 'José' not in texto
