"""Fluxo de cancelar o memo DEPROC antigo (main_geacs_canc_memo_deproc_ant.py),
com o SEI simulado."""

import re
from datetime import datetime

import main_geacs_canc_memo_deproc_ant as fluxo
import planilha_controle
import pytest
from constantes import UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral
from selenium.common.exceptions import TimeoutException

from tests.sei_falso import DriverFalso, SEIFalso

ASSUNTO_ANTIGO = 'Assunto: Levantamento ANTIGO'


class SEICancelamento(SEIFalso):
    def __init__(self):
        super().__init__()
        self.selecionados: list[str] = []
        self.cancelados: list[tuple[str, str]] = []
        self.cancelamento_disponivel = True

    def _cancelar(self, driver, motivo):
        if not self.cancelamento_disponivel:
            raise TimeoutException()
        self.cancelados.append((self.selecionados[-1], motivo))

    def instalar(self, monkeypatch) -> None:
        super().instalar(monkeypatch)
        monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(fluxo, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in self.docs])
        monkeypatch.setattr(fluxo, 'ler_texto_doc', lambda driver, doc: self.textos[doc['numero_sei']])
        monkeypatch.setattr(fluxo, 'selecionar_doc', lambda driver, doc: self.selecionados.append(doc['numero_sei']))
        monkeypatch.setattr(fluxo, 'cancelar_doc', self._cancelar)
        monkeypatch.setattr(fluxo, 'PADRAO_MEMO_DEPROC_ANTIGO', re.compile('Levantamento ANTIGO'))


@pytest.fixture
def sei(monkeypatch):
    sei = SEICancelamento()
    sei.instalar(monkeypatch)
    sei.novo_processo()
    return sei


def _passar():
    return fluxo._processar_linha(DriverFalso(), 'PROC')


def test_cancela_o_memo_que_casa_com_o_padrao(sei):
    sei.memo_geacs('Levantamento NOVO')
    antigo = sei.novo_doc('Memorando 9', UNIDADE_GEACS, ASSUNTO_ANTIGO)

    registro = _passar()

    assert registro.erro is None
    assert sei.cancelados == [(antigo, 'Documento será ou já foi substituído por uma nova versão')]
    assert registro.canc_memo_deproc_ant_cancelado
    assert registro.canc_memo_deproc_ant_sei == antigo
    assert registro.canc_memo_deproc_ant_em == registro.ultima_passagem


@pytest.mark.parametrize(
    ('preparar', 'mensagem'),
    [
        (lambda sei: sei.memo_geacs('Levantamento NOVO'), 'não encontrado'),
        (lambda sei: [sei.novo_doc('Memorando 8', UNIDADE_GEACS, ASSUNTO_ANTIGO) for _ in range(2)], 'Mais de um'),
    ],
)
def test_nenhum_ou_mais_de_um_memo_nao_cancela(sei, preparar, mensagem):
    preparar(sei)
    registro = _passar()

    assert mensagem in registro.erro
    assert sei.cancelados == []


def test_sem_padrao_definido_nao_cancela(sei, monkeypatch):
    sei.novo_doc('Memorando 9', UNIDADE_GEACS, ASSUNTO_ANTIGO)
    monkeypatch.setattr(fluxo, 'PADRAO_MEMO_DEPROC_ANTIGO', None)
    registro = _passar()

    assert 'Padrão do memo DEPROC antigo não definido' in registro.erro
    assert sei.cancelados == []


def test_memo_da_apis_com_o_padrao_nao_e_cancelado(sei):
    # Só os memorandos da GEACS: o da APIS (sei_falso.MEMO_APIS) não entra
    sei.textos[sei.docs[-1]['numero_sei']] += f'\n{ASSUNTO_ANTIGO}'
    registro = _passar()

    assert 'não encontrado' in registro.erro
    assert sei.cancelados == []


def test_cancelamento_indisponivel_vira_erro_sem_traceback(sei):
    sei.novo_doc('Memorando 9', UNIDADE_GEACS, ASSUNTO_ANTIGO)
    sei.cancelamento_disponivel = False
    registro = _passar()

    assert registro.tipo_erro == 'ErroAvaliacao'
    assert 'Cancelar Documento' in registro.erro
    assert not registro.canc_memo_deproc_ant_cancelado


def test_processo_fechado_nao_e_reaberto(sei):
    sei.novo_doc('Memorando 9', UNIDADE_GEACS, ASSUNTO_ANTIGO)
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
    PlanilhaControleGeral('geacs', 'exec1', arquivo).registrar(anterior)

    sei.novo_doc('Memorando 9', UNIDADE_GEACS, ASSUNTO_ANTIGO)
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
    dados = _passar().to_dict()

    assert 'erro' not in dados
    assert 'prox_acao' not in dados
    assert 'não encontrado' in dados['canc_memo_deproc_ant_erro']
