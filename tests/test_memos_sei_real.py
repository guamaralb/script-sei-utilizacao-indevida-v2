"""Cria no SEI real, no processo de teste, os memos escolhidos, com o texto
como está hoje (inclusive os com TEXTO_DEFINIDO = False). Serve para
conferir a formatação dos memos no SEI.

Os memos só são criados: não entram em bloco de assinatura e não recebem
marcador. Os dados (titular, matrículas, memo da APIS e relatórios) são
fictícios.

Desligado por padrão. Exige as duas variáveis com o valor 1 (no .env ou no
ambiente), e cada execução cria um documento novo por memo escolhido:
- SEI_TESTE_REAL: execução real (sozinha, não cria nada);
- SEI_TESTE_REAL_<MEMO>: inclui o memo, uma variável por memo:
    SEI_TESTE_REAL_APIS_SEM_MEMO
    SEI_TESTE_REAL_APIS_FORMATO_INVALIDO
    SEI_TESTE_REAL_APIS_MAT_NAO_ENCONTRADAS
    SEI_TESTE_REAL_PERIODO_DEPS
    SEI_TESTE_REAL_DISA_VALIDAR_CONSTA
    SEI_TESTE_REAL_DISA_VALIDAR_NAO_CONSTA
    SEI_TESTE_REAL_DISA_SEM_MANTIS_RELATORIO
    SEI_TESTE_REAL_DEPROC
    SEI_TESTE_REAL_APIS_SEM_USO
    SEI_TESTE_REAL_APIS_COM_TODAS_AS_INFORMACOES

Para rodar: poetry run pytest tests/test_memos_sei_real.py
"""

import os

import pytest
from constantes import CARGO_SIGNATARIO, NOME_SIGNATARIO, UNIDADE_GEACS
from sei_automacao.processo import incluir_doc_sei_memo
from sei_automacao.ubiquo.busca import acessar_processo
from sessao_sei import abrir_sei

from script_sei_utilizacao_indevida_v2.memorandos import MemoApisPeriodoDependentes, MemoApisSemUso
from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import MemoApisComTodasAsInformacoes, ValoresBeneficiario
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisFormatoInvalido import MemoApisFormatoInvalido
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import MemoApisMatNaoEncontradas
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import MemoApisSemMemo
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    MemoDisaSemMantisSolicitaRelatorio,
    MemoDisaValidarConsta,
    MemoDisaValidarNaoConsta,
)
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import UsoRedeBeneficiarios

pytestmark = pytest.mark.skipif(os.getenv('SEI_TESTE_REAL') != '1', reason='cria memos no SEI real; rode com SEI_TESTE_REAL=1')

PROCESSO_TESTE = '2010.01.0096589/2026-12'

MEMO_APIS = {'numero_sei': '150644870', 'nome_arvore': 'Memorando 2627', 'unidade': 'IPSEMG/APIS-Utilização'}
DADOS = DadosUI(
    nome_titular='José da Silva Teste',
    matricula_titular='1234567-8',
    periodo_titular='(01/05/2019 a 31/12/2019) e (01/02/2020 a 12/06/2024)',
    periodo_dependentes=False,
    matriculas_dependentes='1234567001; 1234567002',
)
DOCS_RELATORIO_RP = ('111111111', '222222222')
ASSINATURA = {'nome_signatario': NOME_SIGNATARIO, 'cargo_signatario': CARGO_SIGNATARIO}
BENEFICIARIOS = (
    ValoresBeneficiario('Titular – 1234567-8', 1500.5, 320, 180.25, '555555551', '555555552'),
    ValoresBeneficiario('Dependente – 1234567001', 250, 0, 37.5, '555555553'),
    ValoresBeneficiario('Dependente – 1234567002', 0, 1040.9, 0, None, '555555554'),
)


def _memos() -> dict:
    """Um memo de cada tipo. Montados dentro do teste, depois de liberar o
    texto pendente. A chave dá o nome da variável (_variavel)."""
    return {
        'apis_sem_memo': lambda: MemoApisSemMemo(**ASSINATURA),
        'apis_formato_invalido': lambda: MemoApisFormatoInvalido(memo_apis=MEMO_APIS, **ASSINATURA),
        'apis_mat_nao_encontradas': lambda: MemoApisMatNaoEncontradas(titular='1234567-8', dependentes=('1234567001',), memo_apis=MEMO_APIS, **ASSINATURA),
        'periodo_deps': lambda: MemoApisPeriodoDependentes.MemoApisPeriodoDependentes(dependentes=('1234567001', '1234567002'), memo_apis=MEMO_APIS, **ASSINATURA),
        'disa_validar_consta': lambda: MemoDisaValidarConsta(
            dados=DADOS,
            memo_apis=MEMO_APIS,
            uso_disa=UsoRedeBeneficiarios('12345678', True),
            tit_usou_mantis=True,
            deps_que_usaram_mantis=(),
            docs_relatorio_rp=DOCS_RELATORIO_RP,
            **ASSINATURA,
        ),
        'disa_validar_nao_consta': lambda: MemoDisaValidarNaoConsta(
            dados=DADOS,
            memo_apis=MEMO_APIS,
            uso_disa=UsoRedeBeneficiarios('12345678', False),
            tit_usou_mantis=True,
            deps_que_usaram_mantis=(),
            docs_relatorio_rp=DOCS_RELATORIO_RP[:1],
            **ASSINATURA,
        ),
        'disa_sem_mantis_relatorio': lambda: MemoDisaSemMantisSolicitaRelatorio(
            dados=DADOS,
            memo_apis=MEMO_APIS,
            uso_disa=UsoRedeBeneficiarios('12345678', True),
            tit_usou_mantis=False,
            deps_que_usaram_mantis=(),
            **ASSINATURA,
        ),
        'deproc': lambda: MemoDeproc(dados=DADOS, docs_relatorio_rc=DOCS_RELATORIO_RP, doc_relatorio_disa='333333333', doc_manifestacao_disa='444444444', memo_apis=MEMO_APIS, **ASSINATURA),
        'apis_sem_uso': lambda: MemoApisSemUso.MemoApisSemUso(dados=DADOS, memo_apis=MEMO_APIS, **ASSINATURA),
        'apis_com_todas_as_informacoes': lambda: MemoApisComTodasAsInformacoes(
            dados=DADOS, memo_apis=MEMO_APIS, beneficiarios=BENEFICIARIOS, doc_coparticipacao='666666666', doc_levantamento_disa='777777777', **ASSINATURA
        ),
    }


def _variavel(tipo: str) -> str:
    return f'SEI_TESTE_REAL_{tipo.upper()}'


def _param(tipo: str):
    """O memo só roda com a sua variável; sem ela, o teste é pulado."""
    variavel = _variavel(tipo)
    return pytest.param(tipo, marks=pytest.mark.skipif(os.getenv(variavel) != '1', reason=f'memo não incluído; rode com {variavel}=1'))


@pytest.fixture(scope='module')
def driver():
    driver = abrir_sei(UNIDADE_GEACS)
    yield driver
    driver.quit()


@pytest.mark.parametrize('tipo', [_param(tipo) for tipo in _memos()])
def test_criar_memo_no_processo_de_teste(driver, monkeypatch, tipo):
    # Cria como está hoje, mesmo com o texto pendente (placeholders)
    monkeypatch.setattr(MemoApisPeriodoDependentes, 'TEXTO_DEFINIDO', True)
    monkeypatch.setattr(MemoApisSemUso, 'TEXTO_DEFINIDO', True)
    memo = _memos()[tipo]()

    acessar_processo(driver, PROCESSO_TESTE)
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc(), nome=type(memo).__name__)
