"""Fluxo de excluir os documentos da DEPROC (main_deproc_excluir_docs.py),
com a árvore simulada."""

from datetime import datetime

import main_deproc_excluir_docs as fluxo
import pytest
import tags
from constantes import UNIDADE_APIS, UNIDADE_DEPROC, UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral
from selenium.common.exceptions import InvalidSessionIdException, TimeoutException
from tags import (
    TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA,
    TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA,
    TAG_DEPROC_RELATORIO_ANEXADO,
    TAG_DEPROC_TRATADO,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import ASSUNTO_MEMO_GEACS_CALCULO_COPA


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
        self.textos: dict[str, str] = {}
        self.nao_legiveis: set[str] = set()
        self.marcadores: list[str] = []
        self.marcadores_lidos = 0

    def _listar_marcadores(self, driver):
        self.marcadores_lidos += 1
        return list(self.marcadores)

    def _remover_marcador(self, driver, marcadores):
        for marcador in marcadores:
            if marcador in self.marcadores:
                self.marcadores.remove(marcador)

    def doc(self, numero: str, unidade: str, nome: str | None = None, texto: str = '') -> None:
        self.docs.append({'numero_sei': numero, 'nome_arvore': nome or f'Memorando {numero}', 'unidade': unidade})
        self.textos[numero] = texto

    def _ler_texto(self, driver, doc):
        if doc['numero_sei'] in self.nao_legiveis:
            raise TimeoutException()
        return self.textos[doc['numero_sei']]

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
        monkeypatch.setattr(fluxo, 'ler_texto_doc', self._ler_texto)
        monkeypatch.setattr(fluxo, 'listar_marcadores', self._listar_marcadores)
        monkeypatch.setattr(tags, 'remover_marcador', self._remover_marcador)
        monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: setattr(self, 'recarregamentos', self.recarregamentos + 1))


@pytest.fixture
def arvore(monkeypatch):
    arvore = ArvoreFalsa()
    arvore.instalar(monkeypatch)
    arvore.doc('100', UNIDADE_APIS)
    arvore.doc('200', UNIDADE_GEACS)
    # Gerados pelo deproc_calcula_copa: relatório (pelo nome) e memo (pelo assunto)
    arvore.doc('300', UNIDADE_DEPROC, 'PDF Coparticipação - 12345678 - 20261112_101500')
    arvore.doc('400', UNIDADE_DEPROC, texto=MEMO_GERADO)
    return arvore


MEMO_GERADO = f'Para: IPSEMG/GEACS - Utilização\nAssunto: {ASSUNTO_MEMO_GEACS_CALCULO_COPA}\nTexto'


def _passar():
    return fluxo._processar_linha(object(), 'PROC')


def test_exclui_os_documentos_gerados_do_ultimo_para_o_primeiro(arvore):
    registro = _passar()

    assert registro.erro is None
    assert arvore.excluidos == ['400', '300']
    assert [d['numero_sei'] for d in arvore._listar(None)] == ['100', '200']
    assert registro.docs_excluidos == ['400', '300']
    assert '2 excluído(s): 400; 300' in registro.to_dict()['deproc_excluir_docs']


def test_mantem_documentos_da_deproc_nao_gerados_pelo_script(arvore):
    arvore.doc('500', UNIDADE_DEPROC, texto='Assunto: Despacho qualquer\nRetorno do levantamento solicitado')
    arvore.doc('600', UNIDADE_DEPROC, 'PDF Relatório manual')
    arvore.doc('700', UNIDADE_DEPROC, 'Despacho 700', texto=MEMO_GERADO)
    arvore.doc('800', UNIDADE_DEPROC, texto='Assunto: Coparticipação apurada – utilização indevida da assistência à saúde')
    registro = _passar()

    assert registro.erro is None
    # 800: memo com o assunto da versão anterior; 700 não é memorando
    assert arvore.excluidos == ['800', '400', '300']
    assert registro.docs_mantidos == ['500', '600', '700']
    assert 'mantido(s), não gerado(s) pelo script: 500; 600; 700' in registro.to_dict()['deproc_excluir_docs']


def test_so_documentos_nao_gerados_nada_e_excluido(arvore):
    arvore.docs = arvore.docs[:2]
    arvore.doc('500', UNIDADE_DEPROC, texto='Outro memo')
    registro = _passar()

    assert registro.erro is None
    assert arvore.excluidos == []
    assert 'nenhum documento gerado pelo deproc_calcula_copa' in registro.to_dict()['deproc_excluir_docs']


def test_memo_que_nao_pode_ser_lido_nao_e_excluido(arvore):
    arvore.nao_legiveis = {'400'}
    registro = _passar()

    assert arvore.excluidos == ['300']
    assert registro.docs_nao_excluidos == ['400']
    assert registro.tipo_erro == 'ErroAvaliacao'


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
    # O resultado da passagem fica só no histórico
    assert 'deproc_excluir_docs' not in linha
    assert linha['script'] == fluxo.SCRIPT
    historico = PlanilhaControleGeral(fluxo.SCRIPT, 'exec3', arquivo).historico.ler()
    assert '2 excluído(s)' in historico[-1]['deproc_excluir_docs']


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


# --- marcadores da DEPROC -----------------------------------------------------

OUTRO_MARCADOR = 'PLANILHADO'


def test_remove_os_marcadores_da_deproc_depois_de_excluir(arvore):
    arvore.marcadores = [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA, OUTRO_MARCADOR]
    registro = _passar()

    assert registro.erro is None
    assert arvore.excluidos == ['400', '300']
    # O 01 por último; marcadores que não são da DEPROC ficam
    assert registro.marcadores_removidos == [TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA, TAG_DEPROC_TRATADO]
    assert arvore.marcadores == [OUTRO_MARCADOR]
    dados = registro.to_dict()
    assert 'marcador(es) removido(s)' in dados['deproc_excluir_docs']
    assert dados['marcadores_deproc_pos_fluxo'] == OUTRO_MARCADOR
    assert dados['estado_atual_deproc'] is None
    assert dados['estado_atual_deproc'] is None


def test_remove_todos_os_estados_da_deproc(arvore):
    arvore.marcadores = [TAG_DEPROC_TRATADO, TAG_DEPROC_RELATORIO_ANEXADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA, TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA]
    _passar()

    assert arvore.marcadores == []


def test_sem_documento_gerado_remove_os_marcadores(arvore):
    arvore.docs = arvore.docs[:2]
    arvore.marcadores = [TAG_DEPROC_TRATADO, TAG_DEPROC_RELATORIO_ANEXADO]
    registro = _passar()

    assert registro.erro is None
    assert arvore.marcadores == []


def test_sem_marcador_da_deproc_nada_e_removido(arvore):
    arvore.marcadores = [OUTRO_MARCADOR]
    registro = _passar()

    assert registro.erro is None
    assert registro.marcadores_removidos == []
    assert arvore.marcadores == [OUTRO_MARCADOR]
    assert 'marcador' not in registro.to_dict()['deproc_excluir_docs']


@pytest.mark.parametrize(
    'preparar',
    [
        pytest.param(lambda arvore: setattr(arvore, 'nao_excluiveis', {'400'}), id='documento_nao_excluido'),
        pytest.param(lambda arvore: setattr(arvore, 'nao_legiveis', {'400'}), id='memo_nao_lido'),
    ],
)
def test_documento_gerado_que_ficou_mantem_os_marcadores(arvore, preparar):
    arvore.marcadores = [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]
    preparar(arvore)
    registro = _passar()

    assert registro.tipo_erro == 'ErroAvaliacao'
    assert 'marcadores da DEPROC mantidos' in registro.erro
    assert arvore.marcadores_lidos == 0
    assert arvore.marcadores == [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]
    # Sem ler os marcadores, as colunas deles ficam como estavam na planilha
    assert 'marcadores_deproc_pos_fluxo' not in registro.to_dict()


def test_processo_fechado_nao_remove_marcadores(arvore):
    arvore.processo_fechado = True
    arvore.marcadores = [TAG_DEPROC_TRATADO]
    _passar()

    assert arvore.marcadores == [TAG_DEPROC_TRATADO]
