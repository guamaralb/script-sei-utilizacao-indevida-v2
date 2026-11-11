"""Fluxo de excluir os documentos da DEPROC (main_deproc_excluir_docs.py),
com a árvore simulada."""

from datetime import datetime

import main_deproc_excluir_docs as fluxo
import pytest
from constantes import UNIDADE_APIS, UNIDADE_DEPROC, UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral
from selenium.common.exceptions import InvalidSessionIdException, TimeoutException


class ArvoreFalsa:
    def __init__(self):
        self.docs: list[dict] = []
        self.selecionado: str | None = None
        self.excluidos: list[str] = []
        self.nao_excluiveis: set[str] = set()
        self.processo_fechado = False
        self.recarregamentos = 0
        self.fechar_navegador = False
        # Leituras da árvore que ainda mostram os excluídos (árvore atrasada)
        self.leituras_atrasadas = 0
        self.acessos = 0

    def doc(self, numero: str, unidade: str, nome: str = 'Memorando') -> None:
        self.docs.append({'numero_sei': numero, 'nome_arvore': f'{nome} {numero}', 'unidade': unidade})

    def _excluir(self, driver):
        if self.fechar_navegador:
            raise InvalidSessionIdException()
        if self.selecionado in self.nao_excluiveis:
            raise TimeoutException()
        self.excluidos.append(self.selecionado)

    def _listar(self, driver):
        if self.leituras_atrasadas > 0:
            self.leituras_atrasadas -= 1
            return [dict(d) for d in self.docs]
        return [dict(d) for d in self.docs if d['numero_sei'] not in self.excluidos]

    def _acessar(self, driver, num):
        self.acessos += 1

    def instalar(self, monkeypatch) -> None:
        monkeypatch.setattr(fluxo, 'acessar_processo', self._acessar)
        monkeypatch.setattr(fluxo.time, 'sleep', lambda segundos: None)
        monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(fluxo, 'listar_documentos_arvore', self._listar)
        monkeypatch.setattr(fluxo, 'selecionar_doc', lambda driver, doc: setattr(self, 'selecionado', doc['numero_sei']))
        monkeypatch.setattr(fluxo, 'excluir_doc', self._excluir)
        monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: setattr(self, 'recarregamentos', self.recarregamentos + 1))


@pytest.fixture
def arvore(monkeypatch):
    arvore = ArvoreFalsa()
    arvore.instalar(monkeypatch)
    arvore.doc('100', UNIDADE_APIS)
    arvore.doc('200', UNIDADE_GEACS)
    arvore.doc('300', UNIDADE_DEPROC)
    arvore.doc('400', UNIDADE_DEPROC, 'PDF')
    return arvore


def _passar():
    return fluxo._processar_linha(object(), 'PROC')


def test_exclui_todos_os_documentos_da_deproc_do_ultimo_para_o_primeiro(arvore):
    registro = _passar()

    assert registro.erro is None
    assert arvore.excluidos == ['400', '300']
    assert [d['numero_sei'] for d in arvore._listar(None)] == ['100', '200']
    assert registro.docs_excluidos == ['400', '300']
    assert '2 excluído(s): 400; 300' in registro.to_dict()['deproc_excluir_docs']


def test_sem_documento_da_deproc_nada_e_excluido(arvore):
    arvore.docs = arvore.docs[:2]
    registro = _passar()

    assert registro.erro is None
    assert arvore.excluidos == []
    assert 'nenhum documento da DEPROC' in registro.to_dict()['deproc_excluir_docs']


def test_documento_que_nao_pode_ser_excluido_nao_impede_os_outros(arvore):
    arvore.nao_excluiveis = {'400'}
    registro = _passar()

    assert arvore.excluidos == ['300']
    assert registro.docs_nao_excluidos == ['400']
    assert registro.tipo_erro == 'ErroAvaliacao'
    assert arvore.recarregamentos == 1
    resumo = registro.to_dict()['deproc_excluir_docs']
    assert '1 excluído(s): 300' in resumo
    assert 'não excluído(s): 400' in resumo
    assert 'ERRO (ErroAvaliacao)' in resumo


def test_processo_fechado_nao_reabre_nem_exclui(arvore):
    arvore.processo_fechado = True
    registro = _passar()

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert arvore.excluidos == []


def test_navegador_fechado_para_o_processo(arvore):
    arvore.fechar_navegador = True
    registro = _passar()

    assert registro.tipo_erro == 'InvalidSessionIdException'
    assert arvore.excluidos == []


def test_planilha_de_controle_so_grava_a_coluna_propria(arvore, tmp_path):
    arquivo = tmp_path / 'controle.xlsx'
    anterior = {
        'num_processo': 'PROC',
        'data_execucao': 'exec1',
        'ultima_passagem': datetime(2026, 11, 1, 9),
        'fluxo': 'DEPROC - COPARTICIPAÇÃO',
        'prox_acao': 'Assinar',
        'tipo_erro': 'X',
        'erro': 'erro antigo',
    }
    PlanilhaControleGeral('deproc_calcula_copa', 'exec1', arquivo).registrar(anterior)

    PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo).registrar(_passar().to_dict())

    aba = load_workbook(arquivo)['processos']
    cabecalho = [c.value for c in aba[1]]
    linha = dict(zip(cabecalho, (c.value for c in aba[2]), strict=True))
    assert linha['prox_acao'] == 'Assinar'
    assert linha['fluxo'] == 'DEPROC - COPARTICIPAÇÃO'
    assert linha['erro'] == 'erro antigo'
    assert '2 excluído(s)' in linha['deproc_excluir_docs']
    assert linha['script'] == fluxo.SCRIPT


def test_arvore_atrasada_nao_conta_como_nao_excluido(arvore):
    # A 1ª leitura (lista os docs) e as 2 seguintes (conferência) ainda
    # mostram os excluídos: a conferência reabre o processo e relê
    arvore.leituras_atrasadas = 3
    registro = _passar()

    assert registro.erro is None
    assert registro.docs_excluidos == ['400', '300']
    assert registro.docs_nao_excluidos == []
    assert arvore.acessos == 2


def test_excluido_que_continua_na_arvore_conta_como_nao_excluido(arvore, monkeypatch):
    arvore.leituras_atrasadas = 1000
    monkeypatch.setattr(fluxo, 'TEMPO_CONFERENCIA', 0)
    registro = _passar()

    assert registro.tipo_erro == 'ErroAvaliacao'
    assert registro.docs_excluidos == []
    assert registro.docs_nao_excluidos == ['300', '400']
