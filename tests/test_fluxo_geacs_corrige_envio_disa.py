"""Fluxo GEACS CORRIGE ENVIO DISA (main_geacs_corrige_envio_disa.py): troca o
memo à DISA "Validar (N Consta)" pelo memo DEPROC, com o SEI simulado."""

import re

import main_geacs_corrige_envio_disa as fluxo
import pytest
from constantes import UNIDADE_GEACS
from Registro import ProxAcao
from tags import (
    TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    TAG_MAT_NAO_ENCONTRADAS_APIS,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
    TAG_PROCESSO_NOVO,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC_DUAS_REDES
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
    ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
    MemoDisaValidarConsta,
    MemoDisaValidarNaoConsta,
)
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import UsoRedeBeneficiarios
from tests.sei_falso import MANTIS_DEPENDENTE_USOU, MANTIS_DUAS_REDES, DriverFalso, SEIFalso, bases
from tests.test_memo_disa import ASSINATURA, DADOS, MEMO_APIS

# Como o texto vem do SEI: quebras de linha no meio do trecho
TEXTO_MEMO_N_CONSTA = (
    f'Assunto: {ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA}\n'
    'Embora a Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791) não indique\n'
    'atendimento para as matrículas relacionadas, foram identificados atendimentos'
)
PDF_DEP_RP = 'PDF Utilização Dep. RP - 12345678 - 20261110_101010'
PDF_TIT_RC = 'PDF Utilização Tit. RC - 12345678 - 20261110_101011'


class SEICorrige(SEIFalso):
    def __init__(self):
        super().__init__()
        self.nao_excluiveis: set[str] = set()
        # Excluído sem erro, mas continua na árvore
        self.excluidos_que_ficam: set[str] = set()
        self.selecionado: str | None = None
        self.excluidos: list[str] = []
        self.nao_cancelaveis: set[str] = set()
        self.cancelados: list[tuple[str, str]] = []

    def _excluir(self, driver):
        if self.selecionado in self.nao_excluiveis:
            raise RuntimeError('Documento assinado: só pode ser cancelado')
        self.excluidos.append(self.selecionado)
        if self.selecionado not in self.excluidos_que_ficam:
            self.docs = [doc for doc in self.docs if doc['numero_sei'] != self.selecionado]

    def _cancelar(self, driver, motivo):
        if self.selecionado in self.nao_cancelaveis:
            raise RuntimeError('Opção "Cancelar Documento" indisponível')
        # O cancelado continua na árvore
        self.cancelados.append((self.selecionado, motivo))

    def processo_n_consta(self, estado: str = TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, *, com_rc: bool = False) -> str:
        """Processo enviado à DISA (N Consta): relatório RP (e RC) e o memo à
        DISA na rodada. Devolve o número do memo."""
        self.novo_processo()
        self.tags = [TAG_PROCESSO_NOVO, estado]
        self.novo_doc(PDF_DEP_RP, UNIDADE_GEACS, '')
        if com_rc:
            self.novo_doc(PDF_TIT_RC, UNIDADE_GEACS, '')
        return self.novo_doc('Memorando 9', UNIDADE_GEACS, TEXTO_MEMO_N_CONSTA)

    def instalar(self, monkeypatch) -> None:
        super().instalar(monkeypatch)
        monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(self.tags))
        monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(fluxo, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in self.docs])
        monkeypatch.setattr(fluxo, 'garantir_marcadores_no_sei', lambda driver, lista: None)
        monkeypatch.setattr(fluxo, 'ler_texto_doc', lambda driver, doc: self.textos[doc['numero_sei']])
        monkeypatch.setattr(fluxo, 'selecionar_doc', lambda driver, doc: setattr(self, 'selecionado', doc['numero_sei']))
        monkeypatch.setattr(fluxo, 'excluir_doc', self._excluir)
        monkeypatch.setattr(fluxo, 'cancelar_doc', self._cancelar)
        monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
        monkeypatch.setattr(fluxo, 'TEMPO_CONFERENCIA', 0)


@pytest.fixture
def sei(monkeypatch):
    sei = SEICorrige()
    sei.instalar(monkeypatch)
    return sei


def _passar(sei, bases_uso=None, bases_mantis=MANTIS_DEPENDENTE_USOU):
    sei.memos_passagem = 0
    return fluxo._processar_linha(DriverFalso(), 'PROC', bases_uso or bases(tit_usou=False), bases_mantis)


def _memos_deproc(sei) -> list[str]:
    return [sei.textos[d['numero_sei']] for d in sei.docs if ASSUNTO_MEMO_DEPROC_DUAS_REDES in sei.textos[d['numero_sei']]]


@pytest.mark.parametrize('estado', [TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA])
def test_troca_o_memo_a_disa_pelo_memo_deproc(sei, estado):
    memo_disa = sei.processo_n_consta(estado)
    registro = _passar(sei)

    assert registro.erro is None
    assert sei.excluidos == [memo_disa]
    assert memo_disa not in [doc['numero_sei'] for doc in sei.docs]
    assert registro.memos_disa_n_consta_sei == [memo_disa]
    assert registro.memos_disa_excluidos_sei == [memo_disa]
    # Só o 01 e o No Bloco DEPROC
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_COPARTICIPACAO]
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert registro.caso_disa_mantis == 'DISA não, MANTIS RP sim, MANTIS RC não'
    (texto,) = _memos_deproc(sei)
    rp = sei.numero_sei(PDF_DEP_RP)
    assert f'constantes do documento {rp}' in texto
    assert registro.relatorios_rp_sei == [rp]
    assert registro.memo_deproc_sei is not None
    assert 'memo à DISA excluído' in registro.to_dict()['corrige_envio_disa']


def test_memo_deproc_com_as_duas_redes(sei):
    sei.processo_n_consta(com_rc=True)
    registro = _passar(sei, bases_mantis=MANTIS_DUAS_REDES)

    assert registro.erro is None
    (texto,) = _memos_deproc(sei)
    assert f'constantes do documento {sei.numero_sei(PDF_TIT_RC)}' in texto
    assert f'constantes do documento {sei.numero_sei(PDF_DEP_RP)}' in texto


def test_mantem_o_informativo(sei):
    sei.processo_n_consta()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MAT_NAO_ENCONTRADAS_APIS, TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA]
    registro = _passar(sei)

    assert registro.erro is None
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_MAT_NAO_ENCONTRADAS_APIS, TAG_MEMO_DEPROC_COPARTICIPACAO]


@pytest.mark.parametrize('ficou_na_arvore', [False, True])
def test_memo_a_disa_nao_excluido_e_cancelado(sei, ficou_na_arvore):
    memo_disa = sei.processo_n_consta(TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA)
    if ficou_na_arvore:
        sei.excluidos_que_ficam = {memo_disa}
    else:
        sei.nao_excluiveis = {memo_disa}
    registro = _passar(sei)

    assert registro.erro is None
    assert sei.cancelados == [(memo_disa, fluxo.MOTIVO_CANCELAMENTO)]
    assert 'não deverão passar pela DISA' in fluxo.MOTIVO_CANCELAMENTO
    assert registro.memos_disa_cancelados_sei == [memo_disa]
    assert registro.memos_disa_excluidos_sei == []
    assert registro.memos_disa_nao_excluidos_sei == []
    assert len(_memos_deproc(sei)) == 1
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_COPARTICIPACAO]
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert f'memo à DISA cancelado: {memo_disa}' in registro.to_dict()['corrige_envio_disa']
    # O cancelado fica na árvore, mas não é lido de novo na busca do memo DEPROC
    assert memo_disa in [doc['numero_sei'] for doc in sei.docs]
    assert memo_disa not in [doc['numero_sei'] for doc in registro.docs_rodada]


def test_memo_a_disa_nem_excluido_nem_cancelado_para_sem_criar_nada(sei):
    memo_disa = sei.processo_n_consta(TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA)
    sei.nao_excluiveis = {memo_disa}
    sei.nao_cancelaveis = {memo_disa}
    registro = _passar(sei)

    assert registro.tipo_erro == 'MemoDisaNaoExcluido'
    assert registro.prox_acao == ProxAcao.VERIFICAR_MEMO_DISA_NAO_EXCLUIDO
    assert registro.memos_disa_nao_excluidos_sei == [memo_disa]
    assert registro.memos_disa_excluidos_sei == []
    assert registro.memos_disa_cancelados_sei == []
    assert _memos_deproc(sei) == []
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA]
    assert 'ERRO (MemoDisaNaoExcluido)' in registro.to_dict()['corrige_envio_disa']


def test_um_excluido_e_outro_cancelado(sei):
    memo_1 = sei.processo_n_consta()
    memo_2 = sei.novo_doc('Memorando 10', UNIDADE_GEACS, TEXTO_MEMO_N_CONSTA)
    sei.nao_excluiveis = {memo_1}
    registro = _passar(sei)

    assert registro.erro is None
    assert registro.memos_disa_excluidos_sei == [memo_2]
    assert registro.memos_disa_cancelados_sei == [memo_1]
    resumo = registro.to_dict()['corrige_envio_disa']
    assert f'memo à DISA excluído: {memo_2}; memo à DISA cancelado: {memo_1}' in resumo


def test_sem_marcador_da_disa_para_sem_acao(sei):
    sei.processo_n_consta()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_COPARTICIPACAO]
    registro = _passar(sei)

    assert registro.tipo_erro == 'SemMarcadorDisa'
    assert sei.excluidos == []
    assert _memos_deproc(sei) == []


def test_outro_memo_a_disa_nada_a_corrigir(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_NO_BLOCO_DISA_VALIDAR_CONSTA]
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA)
    registro = _passar(sei, bases(tit_usou=True))

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA
    assert sei.excluidos == []
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_NO_BLOCO_DISA_VALIDAR_CONSTA]
    assert 'nada a corrigir' in registro.to_dict()['corrige_envio_disa']


def test_com_uso_na_base_disa_nao_corrige(sei):
    sei.processo_n_consta()
    registro = _passar(sei, bases(tit_usou=True))

    assert registro.tipo_erro == 'CasoNaoCorrigivel'
    assert 'DISA sim' in registro.erro
    assert sei.excluidos == []
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA]


def test_sem_o_relatorio_rp_nao_corrige(sei):
    sei.processo_n_consta()
    sei.docs = [doc for doc in sei.docs if not doc['nome_arvore'].startswith('PDF ')]
    registro = _passar(sei)

    assert registro.tipo_erro == 'CasoNaoCorrigivel'
    assert 'sem PDF na rodada' in registro.erro
    assert sei.excluidos == []


def test_retomada_memo_a_disa_ja_excluido(sei):
    # Passagem anterior excluiu o memo à DISA e falhou antes do memo DEPROC
    memo_disa = sei.processo_n_consta()
    sei.docs = [doc for doc in sei.docs if doc['numero_sei'] != memo_disa]
    registro = _passar(sei)

    assert registro.erro is None
    assert sei.excluidos == []
    assert len(_memos_deproc(sei)) == 1
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_COPARTICIPACAO]
    assert 'já excluído antes' in registro.to_dict()['corrige_envio_disa']


def test_retomada_memo_deproc_ja_criado(sei):
    # Falhou entre o memo DEPROC e o marcador: o memo não é recriado
    memo_disa = sei.processo_n_consta()
    sei.docs = [doc for doc in sei.docs if doc['numero_sei'] != memo_disa]
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC_DUAS_REDES)
    registro = _passar(sei)

    assert registro.erro is None
    assert registro.memo_deproc_na_arvore is True
    assert sei.memos_passagem == 0
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_COPARTICIPACAO]


def test_processo_fechado_nao_reabre(sei):
    sei.processo_n_consta()
    sei.processo_fechado = True
    registro = _passar(sei)

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert sei.excluidos == []


def test_trecho_do_memo_ignora_espacos_e_maiusculas():
    assert fluxo.eh_memo_disa_n_consta(TEXTO_MEMO_N_CONSTA.upper())
    assert not fluxo.eh_memo_disa_n_consta(f'Assunto: {ASSUNTO_MEMO_DISA_VALIDAR_CONSTA}')


def test_trecho_casa_com_o_memo_a_disa_n_consta_real():
    # O texto que o geacs_inicial gerava (MemoDisaValidarNaoConsta), sem as
    # tags HTML, como o SEI devolve
    def texto(classe, usou_disa):
        memo = classe(dados=DADOS, memo_apis=MEMO_APIS, uso_disa=UsoRedeBeneficiarios('1234567', usou_disa), tit_usou_mantis=True, deps_que_usaram_mantis=(), docs_relatorio_rp=('1',), **ASSINATURA)
        return re.sub(r'<[^>]+>', ' ', memo.texto_principal())

    assert fluxo.eh_memo_disa_n_consta(texto(MemoDisaValidarNaoConsta, False))
    assert not fluxo.eh_memo_disa_n_consta(texto(MemoDisaValidarConsta, True))
