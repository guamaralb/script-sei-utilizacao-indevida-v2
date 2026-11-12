"""Conferência da prox_acao da planilha de controle (fluxo GEACS VERIFICAR
MARCADORES): confere se ela faz sentido com os marcadores do processo e se os
memorandos e relatórios que os marcadores indicam estão na árvore. Só leitura:
nenhuma ação no SEI.

Cada problema vira uma frase em registro.inconsistencias (coluna
verificar_marcadores_inconsistencia). Conferências:

1. combinação de marcadores (tags.conferir_marcadores, as mesmas regras do
   fluxo inicial);
2. prox_acao x marcador de estado (a que o geacs_inicial daria hoje);
3. caso base DISA x MANTIS da planilha x marcador do memo (se preenchido);
4. memo do marcador "No Bloco" / "Aguarda" na árvore (pelo assunto), na rodada
   (só "No Bloco"), com os relatórios do MANTIS que ele cita antes dele, e o
   número SEI da planilha na árvore;
5. "No Bloco APIS: Sem Memo" com memo da APIS destinado à GEACS na árvore;
6. retomada (01.06 / 01.08) com memo do fluxo já na rodada, sem o marcador.

A árvore e os textos dos memos só são lidos quando alguma conferência
precisa deles.
"""

import logging
import re
from dataclasses import dataclass
from types import SimpleNamespace

from docs_processo import filtrar_memos_geacs, ler_texto_doc, obter_memos_apis_para_geacs
from Registro import PROX_ACAO_POR_CONCLUSAO, PROX_ACAO_POR_NO_BLOCO, ProxAcao, RegistroVerificarMarcadores
from sei_automacao.processo import listar_documentos_arvore
from selenium import webdriver
from tags import (
    AGUARDA_POR_NO_BLOCO,
    PREFIXO,
    PREFIXO_VELHO,
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_APIS_SEM_USO,
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAGS_ESTADO_NOVO,
    TAGS_PARADA_NOVO,
    TAGS_RETOMADA_NOVO,
    TAGS_TRATAMENTO_MANUAL,
    MarcadoresInconsistentes,
    conferir_marcadores,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisFormatoInvalido import PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisPeriodoDependentes import PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemUso import PADRAO_ASSUNTO_MEMO_APIS_SEM_USO
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoDoMarcador:
    """Memo que o marcador "No Bloco" (e o seu "Aguarda") indica."""

    descricao: str
    padrao_assunto: re.Pattern
    # Coluna da planilha de controle com o número SEI do memo
    coluna_sei: str
    # Relatórios do MANTIS (RP / RC) que o memo cita, anexados antes dele
    redes_relatorios: tuple[str, ...] = ()
    # Caso base DISA x MANTIS (coluna caso_disa_mantis): (DISA, MANTIS RP,
    # MANTIS RC), None = qualquer
    caso: tuple[str | None, str | None, str | None] | None = None


_MEMO_POR_NO_BLOCO = {
    TAG_MEMO_APIS_SEM_MEMO: MemoDoMarcador('à APIS (sem memorando para a GEACS)', PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO, 'memo_apis_sem_memo_sei'),
    TAG_MEMO_APIS_FORMATO_INVALIDO: MemoDoMarcador('à APIS (formato inválido)', PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO, 'memo_apis_formato_invalido_sei'),
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: MemoDoMarcador('à APIS (matrículas não encontradas)', PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS, 'memo_apis_mat_nao_encontradas_sei'),
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: MemoDoMarcador('à APIS (período dos dependentes)', PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES, 'memo_apis_periodo_deps_sei'),
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA: MemoDoMarcador('à DISA (validar e complementar)', PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, 'memo_disa_sei', ('RP',), ('sim', 'sim', None)),
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA: MemoDoMarcador('à DISA (validar; não consta)', PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA, 'memo_disa_sei', ('RP',), ('não', 'sim', None)),
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO: MemoDoMarcador('à DISA (sem MANTIS: solicita relatório)', PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO, 'memo_disa_sei', (), ('sim', 'não', None)),
    TAG_MEMO_DEPROC_COPARTICIPACAO: MemoDoMarcador('DEPROC (coparticipação)', PADRAO_ASSUNTO_MEMO_DEPROC, 'memo_deproc_sei', ('RC',), ('não', 'não', 'sim')),
    TAG_NO_BLOCO_APIS_SEM_USO: MemoDoMarcador('à APIS (nenhum uso nas bases)', PADRAO_ASSUNTO_MEMO_APIS_SEM_USO, 'memo_apis_sem_uso_sei', (), ('não', 'não', 'não')),
}
# O "Aguarda" (manual, depois da assinatura) indica o mesmo memo
_NO_BLOCO_POR_AGUARDA = {aguarda: no_bloco for no_bloco, aguarda in AGUARDA_POR_NO_BLOCO.items()}

# Valem com qualquer marcador: o erro da passagem está nas colunas tipo_erro
# e erro, ou o fluxo não mexe nos marcadores
_PROX_ACOES_SEMPRE_ACEITAS = frozenset({
    ProxAcao.VERIFICAR_ERRO,
    ProxAcao.VERIFICAR_ACESSO_UNIDADE,
    ProxAcao.VERIFICAR_FORMATO_MEMO,
    ProxAcao.ADC_PDF_ANT_AUT_SEM_PLANILHAS,
    ProxAcao.ADC_PDF_ANT_MAN_SEM_PLANILHAS,
})
# ADC PDF ANT AUT/MAN em processo que já tinha estado (ou VELHO): o estado
# fica como estava
_PROX_ACOES_ESTADO_MANTIDO = (ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO, ProxAcao.ADC_PDF_ANT_MAN_ESTADO_MANTIDO)
_PROX_ACOES_AGUARDA_FLUXO_NORMAL = (ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL, ProxAcao.ADC_PDF_ANT_MAN_AGUARDA_FLUXO_NORMAL)
# prox_acao dos fluxos da DEPROC: a última passagem foi na unidade da DEPROC,
# com outros marcadores
_PREFIXO_PROX_ACAO_DEPROC = 'DEPROC:'

# prox_acao que o geacs_inicial dá (sem erro) a cada estado em que para
_PROX_ACAO_DO_INICIAL = {
    **PROX_ACAO_POR_NO_BLOCO,
    **dict.fromkeys(TAGS_PARADA_NOVO, ProxAcao.AGUARDAR_RESPOSTA_MEMO),
    **PROX_ACAO_POR_CONCLUSAO,
}

_PADRAO_CASO = re.compile(r'DISA\s+(sim|não),\s*MANTIS\s+RP\s+(sim|não),\s*MANTIS\s+RC\s+(sim|não)', re.IGNORECASE)
_RODAR_INICIAL = 'rodar o geacs_inicial atualiza a prox_acao'


def _curto(tag: str) -> str:
    return tag.removeprefix(PREFIXO).removeprefix(PREFIXO_VELHO)


def _numero_sei(valor) -> str | None:
    """Número SEI lido da planilha (texto ou número)."""
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).strip()
    return texto or None


# ---------------------------------------------------------------------------
# prox_acao x marcadores
# ---------------------------------------------------------------------------


def _esperadas(marcadores: set[str], estado: str | None) -> tuple[tuple[str | None, ...], str, bool]:
    """As prox_acao possíveis com estes marcadores (a primeira é a que o
    geacs_inicial daria), o que a define (para a mensagem) e se rodar o
    geacs_inicial a atualiza (sem alterar o estado)."""
    if TAG_PROCESSO_VELHO in marcadores:
        velho = ProxAcao.FORA_DO_ESCOPO if TAGS_TRATAMENTO_MANUAL & marcadores else ProxAcao.VELHO_AGUARDAR_DEFINICAO
        return (velho, *_PROX_ACOES_ESTADO_MANTIDO), f'o marcador "{_curto(TAG_PROCESSO_VELHO)}"', True
    if estado is None:
        if TAG_PROCESSO_NOVO in marcadores:
            # O fluxo inicial sempre termina com um estado: sem ele, a última
            # passagem falhou antes (as prox_acao de erro são sempre aceitas)
            return (ProxAcao.VERIFICAR_ERRO,), f'o marcador "{_curto(TAG_PROCESSO_NOVO)}" sem marcador de estado', False
        return (None,), 'o processo sem marcadores do script', False

    descricao = f'o marcador "{_curto(estado)}"'
    if estado in _PROX_ACAO_DO_INICIAL:
        return (_PROX_ACAO_DO_INICIAL[estado], *_PROX_ACOES_ESTADO_MANTIDO), descricao, True
    if estado == TAG_AGUARDA_FLUXO_NORMAL:
        return _PROX_ACOES_AGUARDA_FLUXO_NORMAL, descricao, False
    # Retomada (01.06, 01.08) e os 01.11 sem o 00 (versão anterior): estado
    # intermediário, a última passagem não terminou
    return (ProxAcao.VERIFICAR_ERRO, *_PROX_ACOES_ESTADO_MANTIDO), f'{descricao} (estado intermediário: a última passagem não terminou)', False


def conferir_prox_acao(prox_acao: str | None, marcadores: list[str]) -> list[str]:
    """Confere a prox_acao da planilha com os marcadores do processo. Devolve
    os problemas (vazia: faz sentido)."""
    atuais = set(marcadores)
    try:
        conferir_marcadores(SimpleNamespace(marcadores_atuais=list(marcadores)))
    except MarcadoresInconsistentes as e:
        # Sem estado único não há prox_acao esperada
        if prox_acao == ProxAcao.VERIFICAR_MARCADORES:
            return [str(e)]
        return [f'{e} (prox_acao "{prox_acao or "(vazia)"}"; esperada: "{ProxAcao.VERIFICAR_MARCADORES}")']

    if prox_acao is not None and (prox_acao in _PROX_ACOES_SEMPRE_ACEITAS or prox_acao.startswith(_PREFIXO_PROX_ACAO_DEPROC)):
        return []
    if prox_acao == ProxAcao.VERIFICAR_MARCADORES:
        return [f'prox_acao "{prox_acao}", mas os marcadores estão consistentes ({_RODAR_INICIAL})']

    estado = next((tag for tag in TAGS_ESTADO_NOVO if tag in atuais), None)
    esperadas, origem, pelo_inicial = _esperadas(atuais, estado)
    if prox_acao in esperadas:
        return []
    esperada = esperadas[0] or '(vazia)'
    dica = f' ({_RODAR_INICIAL})' if pelo_inicial else ''
    return [f'prox_acao "{prox_acao or "(vazia)"}" não condiz com {origem}; esperada: "{esperada}"{dica}']


def conferir_caso_disa_mantis(caso: str | None, no_bloco: str) -> list[str]:
    """O caso base DISA x MANTIS da planilha (se preenchido) é o do memo do
    marcador."""
    memo = _MEMO_POR_NO_BLOCO[no_bloco]
    if memo.caso is None or not caso:
        return []
    achado = _PADRAO_CASO.search(str(caso))
    if achado is None:
        return []
    valores = tuple(v.casefold() for v in achado.groups())
    if all(esperado is None or esperado == valor for esperado, valor in zip(memo.caso, valores, strict=True)):
        return []
    return [f'caso_disa_mantis "{caso}" não condiz com o memo {memo.descricao} do marcador "{_curto(no_bloco)}"']


# ---------------------------------------------------------------------------
# Memorandos e relatórios na árvore
# ---------------------------------------------------------------------------


class _Arvore:
    """Árvore e textos dos memos, lidos uma vez e só quando preciso."""

    def __init__(self, driver: webdriver.Remote):
        self.driver = driver
        self._docs: list[dict] | None = None
        self._textos: dict[str, str] = {}
        self._memos_apis: list[dict] | None = None

    @property
    def docs(self) -> list[dict]:
        if self._docs is None:
            self._docs = listar_documentos_arvore(self.driver)
        return self._docs

    def texto(self, doc: dict) -> str:
        if doc['numero_sei'] not in self._textos:
            self._textos[doc['numero_sei']] = ler_texto_doc(self.driver, doc)
        return self._textos[doc['numero_sei']]

    @property
    def memos_apis_para_geacs(self) -> list[dict]:
        if self._memos_apis is None:
            self._memos_apis = [memo for memo, _ in obter_memos_apis_para_geacs(self.driver, self.docs)]
        return self._memos_apis

    def indice(self, doc: dict) -> int:
        return next(i for i, d in enumerate(self.docs) if d['numero_sei'] == doc['numero_sei'])

    def inicio_rodada(self, ate: int | None = None) -> int:
        """Índice do primeiro documento depois do último memo da APIS
        destinado à GEACS (antes de "ate", se informado). 0 sem memo."""
        indices = [self.indice(memo) for memo in self.memos_apis_para_geacs]
        if ate is not None:
            indices = [i for i in indices if i < ate]
        return max(indices) + 1 if indices else 0

    def ultimo_memo_geacs(self, padrao: re.Pattern, docs: list[dict] | None = None) -> dict | None:
        """O memo da GEACS mais recente cujo texto casa com o padrão."""
        return next((memo for memo in reversed(filtrar_memos_geacs(self.docs if docs is None else docs)) if padrao.search(self.texto(memo))), None)


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def _relatorio_da_rede(doc: dict, rede: str) -> bool:
    """Relatório do MANTIS: "PDF Utilização <Tit.|Dep.> <RP|RC> - ..."."""
    return re.match(rf'PDF\s+Utiliza[çc][ãa]o\s+(Tit\.|Dep\.)\s+{rede}\b', doc['nome_arvore'], re.IGNORECASE) is not None


def conferir_memo_do_marcador(arvore: _Arvore, estado: str, linha: dict) -> list[str]:
    """O memo do marcador "No Bloco" (ou do seu "Aguarda") está na árvore,
    com os relatórios que ele cita antes dele. O do "No Bloco" precisa estar
    na rodada (depois do último memo da APIS destinado à GEACS); o do
    "Aguarda" pode estar antes (a resposta da APIS é um novo memo)."""
    aguarda = estado in _NO_BLOCO_POR_AGUARDA
    no_bloco = _NO_BLOCO_POR_AGUARDA.get(estado, estado)
    memo = _MEMO_POR_NO_BLOCO[no_bloco]
    problemas = []

    encontrado = arvore.ultimo_memo_geacs(memo.padrao_assunto)
    if encontrado is None:
        problemas.append(f'marcador "{_curto(estado)}" sem o memo {memo.descricao} na árvore (procurado pelo assunto)')
    else:
        indice = arvore.indice(encontrado)
        logger.info(f'Memo {memo.descricao} do marcador "{_curto(estado)}": {_descrever(encontrado)}')
        if not aguarda and indice < arvore.inicio_rodada():
            problemas.append(f'memo {memo.descricao} ({encontrado["numero_sei"]}) é de antes do último memo da APIS destinado à GEACS: o marcador "{_curto(estado)}" é de um pedido anterior')
        inicio = arvore.inicio_rodada(ate=indice)
        for rede in memo.redes_relatorios:
            if not any(_relatorio_da_rede(doc, rede) for doc in arvore.docs[inicio:indice]):
                problemas.append(f'memo {memo.descricao} ({encontrado["numero_sei"]}) sem relatório {rede} do MANTIS antes dele na rodada')

    numero_planilha = _numero_sei(linha.get(memo.coluna_sei))
    if numero_planilha is not None and all(doc['numero_sei'] != numero_planilha for doc in arvore.docs):
        problemas.append(f'{memo.coluna_sei} = {numero_planilha} na planilha, mas o documento não está na árvore')

    if no_bloco == TAG_MEMO_APIS_SEM_MEMO and not aguarda and arvore.memos_apis_para_geacs:
        ultimo = arvore.memos_apis_para_geacs[-1]
        problemas.append(f'marcador "{_curto(estado)}", mas o processo tem memo da APIS destinado à GEACS ({ultimo["numero_sei"]}): o memo à APIS (sem memorando) não é mais necessário')
    return problemas


def conferir_retomada(arvore: _Arvore, estado: str) -> list[str]:
    """Estado de retomada (01.06, 01.08): nenhum memo do fluxo na rodada. Se
    houver, a passagem falhou depois de criar o memo e antes do marcador (o
    geacs_inicial o reaproveita e só adiciona o marcador)."""
    rodada = arvore.docs[arvore.inicio_rodada() :]
    problemas = []
    vistos = set()
    for no_bloco, memo in _MEMO_POR_NO_BLOCO.items():
        if memo.padrao_assunto.pattern in vistos:
            continue
        vistos.add(memo.padrao_assunto.pattern)
        encontrado = arvore.ultimo_memo_geacs(memo.padrao_assunto, rodada)
        if encontrado is not None:
            problemas.append(
                f'estado "{_curto(estado)}" com o memo {memo.descricao} ({encontrado["numero_sei"]}) na rodada, sem o marcador "{_curto(no_bloco)}" '
                '(o geacs_inicial reaproveita o memo e adiciona o marcador)'
            )
    return problemas


# ---------------------------------------------------------------------------
# Conferência do processo
# ---------------------------------------------------------------------------


def conferir_processo(driver: webdriver.Remote, registro: RegistroVerificarMarcadores, linha: dict | None) -> None:
    """Preenche registro.inconsistencias. linha: a linha do processo na
    planilha de controle (None: planilha não lida, a prox_acao não é
    conferida)."""
    marcadores = registro.marcadores_atuais
    atuais = set(marcadores)
    if linha is None:
        logger.warning('Planilha de controle não lida: a prox_acao não é conferida')
    else:
        registro.inconsistencias += conferir_prox_acao(linha.get('prox_acao'), marcadores)

    estados = [tag for tag in TAGS_ESTADO_NOVO if tag in atuais]
    if len(estados) != 1:
        # Sem estado não há memo a conferir; com mais de um, a combinação já
        # é inconsistente
        return
    estado = estados[0]
    arvore = _Arvore(driver)
    no_bloco = _NO_BLOCO_POR_AGUARDA.get(estado, estado)
    if no_bloco in _MEMO_POR_NO_BLOCO:
        if linha is not None:
            registro.inconsistencias += conferir_caso_disa_mantis(linha.get('caso_disa_mantis'), no_bloco)
        registro.inconsistencias += conferir_memo_do_marcador(arvore, estado, linha or {})
    elif estado in TAGS_RETOMADA_NOVO:
        registro.inconsistencias += conferir_retomada(arvore, estado)
