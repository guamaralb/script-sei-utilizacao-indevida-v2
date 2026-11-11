"""Fluxo de cancelar os memos DEPROC antigos (main_geacs_canc_memo_deproc_ant.py),
com o SEI simulado."""

from datetime import datetime

import main_geacs_canc_memo_deproc_ant as fluxo
import planilha_controle
import pytest
from constantes import UNIDADE_APIS, UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral
from selenium.common.exceptions import TimeoutException

from tests.sei_falso import DriverFalso, SEIFalso


def texto_memo(data='18 de setembro de 2026', para='IPSEMG/DEPROC', assunto='Levantamento de coparticipação - utilização indevida da assistência à saúde', corpo=None):
    corpo = corpo or 'Solicitamos o levantamento dos valores de coparticipação referentes aos atendimentos efetivamente realizados.'
    linha_data = f'Belo Horizonte, {data}.' if data else ''
    return f'Memorando nº 1/2026\n{linha_data}\nPara: {para}\nAssunto: {assunto}\n{corpo}'


class SEICancelamento(SEIFalso):
    def __init__(self):
        super().__init__()
        self.selecionados: list[str] = []
        self.cancelados: list[tuple[str, str]] = []
        self.sem_opcao: set[str] = set()

    def _cancelar(self, driver, motivo):
        if self.selecionados[-1] in self.sem_opcao:
            raise TimeoutException()
        self.cancelados.append((self.selecionados[-1], motivo))

    def memo_antigo(self, **kwargs) -> str:
        return self.novo_doc('Memorando 9', UNIDADE_GEACS, texto_memo(**kwargs))

    def instalar(self, monkeypatch) -> None:
        super().instalar(monkeypatch)
        monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(fluxo, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in self.docs])
        monkeypatch.setattr(fluxo, 'ler_texto_doc', lambda driver, doc: self.textos[doc['numero_sei']])
        monkeypatch.setattr(fluxo, 'selecionar_doc', lambda driver, doc: self.selecionados.append(doc['numero_sei']))
        monkeypatch.setattr(fluxo, 'cancelar_doc', self._cancelar)


@pytest.fixture
def sei(monkeypatch):
    sei = SEICancelamento()
    sei.instalar(monkeypatch)
    sei.novo_processo()
    return sei


def _passar():
    return fluxo._processar_linha(DriverFalso(), 'PROC')


def _cancelados(sei):
    return [numero for numero, _ in sei.cancelados]


def test_cancela_todos_os_memos_deproc_antigos(sei):
    primeiro = sei.memo_antigo()
    segundo = sei.memo_antigo(data='14 de outubro de 2026', para='IPSEMG/DEPROC-Utilização', assunto='Levantamento de coparticipação – utilização indevida da assistência à saúde')

    registro = _passar()

    assert registro.erro is None
    assert _cancelados(sei) == [primeiro, segundo]
    assert {motivo for _, motivo in sei.cancelados} == {'Documento será ou já foi substituído por uma nova versão'}
    assert registro.canc_memo_deproc_ant_cancelado
    assert registro.canc_memo_deproc_ant_sei == [primeiro, segundo]
    assert registro.to_dict()['canc_memo_deproc_ant_sei'] == f'{primeiro}; {segundo}'
    assert registro.canc_memo_deproc_ant_em == registro.ultima_passagem


@pytest.mark.parametrize(
    'kwargs',
    [
        pytest.param({'data': '15 de outubro de 2026'}, id='no dia do corte'),
        pytest.param({'data': '3 de novembro de 2026'}, id='depois do corte'),
        pytest.param({'para': 'IPSEMG/DISA-UTI-INDEV'}, id='outro destinatario'),
        pytest.param({'assunto': 'Coparticipação apurada – utilização indevida da assistência à saúde'}, id='outro assunto'),
        pytest.param({'corpo': 'Encaminhamos os relatórios da rede credenciada.'}, id='sem o trecho do levantamento'),
    ],
)
def test_memo_que_nao_e_o_antigo_nao_e_cancelado(sei, kwargs):
    sei.memo_antigo(**kwargs)
    registro = _passar()

    assert registro.erro is None
    assert sei.cancelados == []
    assert not registro.canc_memo_deproc_ant_cancelado
    assert _passar().para_log()['prox_acao'] == 'Nenhum memo DEPROC antigo cancelado'


def test_espacos_e_maiusculas_sao_ignorados(sei):
    numero = sei.novo_doc(
        'Memorando 9',
        UNIDADE_GEACS,
        'BELO HORIZONTE, 2 de Outubro de 2026.\nPara:  IPSEMG/DEPROC\n'
        'ASSUNTO: Levantamento de\ncoparticipação -  utilização indevida da assistência à saúde\n'
        'levantamento dos valores\nde coparticipação referentes aos atendimentos efetivamente realizados',
    )
    _passar()

    assert _cancelados(sei) == [numero]


def test_so_memorandos_da_geacs(sei):
    sei.novo_doc('Memorando 9', UNIDADE_APIS, texto_memo())
    sei.novo_doc('Despacho 9', UNIDADE_GEACS, texto_memo())
    registro = _passar()

    assert sei.cancelados == []
    assert registro.erro is None


def test_sem_data_legivel_nao_cancela_e_vira_erro(sei):
    sem_data = sei.memo_antigo(data=None)
    antigo = sei.memo_antigo()
    registro = _passar()

    assert _cancelados(sei) == [antigo]
    assert registro.canc_memo_deproc_ant_nao_cancelados == [sem_data]
    assert registro.tipo_erro == 'ErroAvaliacao'
    assert 'sem data legível' in registro.erro


def test_cancelamento_indisponivel_nao_impede_os_outros(sei):
    sem_opcao = sei.memo_antigo()
    antigo = sei.memo_antigo()
    sei.sem_opcao = {sem_opcao}
    registro = _passar()

    assert _cancelados(sei) == [antigo]
    assert registro.canc_memo_deproc_ant_sei == [antigo]
    assert registro.canc_memo_deproc_ant_nao_cancelados == [sem_opcao]
    assert registro.tipo_erro == 'ErroAvaliacao'
    assert 'Cancelar Documento' in registro.erro
    assert registro.para_log()['prox_acao'] == '1 memo(s) DEPROC antigo(s) cancelado(s)'


def test_processo_fechado_nao_e_reaberto(sei):
    sei.memo_antigo()
    sei.processo_fechado = True
    registro = _passar()

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert sei.cancelados == []
    assert sei.reaberturas == 0


def test_planilha_de_controle_mantem_prox_acao_fluxo_e_erro_dos_outros_fluxos(sei, tmp_path, monkeypatch):
    monkeypatch.setattr(planilha_controle, 'DIR_BACKUP_CONTROLE', tmp_path / 'backup')
    arquivo = tmp_path / 'controle.xlsx'
    anterior = {
        'num_processo': 'PROC',
        'data_execucao': 'exec1',
        'ultima_passagem': datetime(2026, 11, 1, 9),
        'fluxo': 'NOVO',
        'prox_acao': 'Assinar memo DEPROC e encaminhar',
        'tipo_erro': None,
        'erro': None,
        'tag_processo_novo': True,
    }
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(anterior)

    sei.memo_antigo()
    PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo).registrar(_passar().to_dict())

    processos = load_workbook(arquivo)['processos']
    linha = {cabecalho.value: valor.value for cabecalho, valor in zip(processos[1], processos[2], strict=True)}
    assert linha['prox_acao'] == 'Assinar memo DEPROC e encaminhar'
    assert linha['fluxo'] == 'NOVO'
    assert linha['tag_processo_novo'] is True
    assert linha['script'] == fluxo.SCRIPT
    assert linha['canc_memo_deproc_ant_cancelado'] is True
    assert linha['canc_memo_deproc_ant_em'] is not None
    resumo = [tuple(c.value for c in r) for r in load_workbook(arquivo)['resumo'].iter_rows()]
    assert ('Assinar memo DEPROC e encaminhar', 1) in resumo


def test_erro_vai_para_colunas_proprias(sei):
    sei.memo_antigo(data=None)
    dados = _passar().to_dict()

    assert 'erro' not in dados
    assert 'prox_acao' not in dados
    assert 'sem data legível' in dados['canc_memo_deproc_ant_erro']
