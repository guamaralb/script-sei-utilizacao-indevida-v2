"""Conferência da prox_acao da planilha de controle (fluxo GEACS VERIFICAR
MARCADORES): confere se ela faz sentido com os marcadores do processo e se os
memorandos e relatórios que os marcadores indicam estão na árvore. A única
ação no SEI é a troca do "No Bloco" pelo marcador de assinado
(trocar_no_bloco_assinado).

Cada problema vira uma frase em registro.inconsistencias (coluna
verificar_marcadores_inconsistencia) e uma ação curta em
registro.acoes_sugeridas (coluna verificar_marcadores_acao_sugerida, valores
de AcaoSugerida). Conferências:

1. combinação de marcadores (tags.conferir_marcadores, as mesmas regras do
   fluxo inicial);
2. prox_acao x marcador de estado (a que o geacs_inicial daria hoje). As de
   erro (Registro.PROX_ACOES_A_VERIFICAR) valem com qualquer marcador, exceto
   "Verificar acesso" de uma passagem da GEACS (a GEACS acabou de abrir o
   processo); as da DEPROC ("DEPROC: ..."), só com o 01.10 / 01.10.1 da DEPROC;
3. caso base DISA x MANTIS da planilha x marcador do memo (se preenchido);
4. memo do marcador "No Bloco" / "Aguarda" / "Encaminhado" (01.12.1) na
   árvore (pelo assunto), na rodada (só "No Bloco"), com os relatórios do
   MANTIS que ele cita antes dele, o número SEI da planilha na árvore e a
   assinatura ("No Bloco" com o memo assinado: falta trocar o marcador;
   "Aguarda" / "Encaminhado" com o memo não assinado);
5. "No Bloco APIS: Sem Memo" com memo da APIS destinado à GEACS na árvore;
6. retomada (01.06 / 01.08) com memo do fluxo já na rodada, sem o marcador.

Além dos problemas, sugere o próximo fluxo (sugestoes_de_fluxo, só a ação):
estado N Consta (geacs_corrige_envio_disa), "Aguarda DEPROC" com o memo de
resultado da DEPROC assinado na rodada (geacs_todas_infos) e "Aguarda DISA"
com documento da DISA depois do memo (resposta da DISA).

Antes de tudo (trocar_no_bloco_assinado), o "No Bloco" cujo memo da rodada já
está assinado por Gustavo, Bruna ou Danúbia é trocado pelo marcador de assinado
("Aguarda" ou, no 01.12, "Encaminhado"), com a prox_acao que o geacs_inicial
daria. Depois (conferir_memos_aguarda), para cada marcador "Aguarda" do
processo, procura o memo do marcador assinado por Gustavo, Bruna ou Danúbia
(PADRAO_ASSINATURA_MEMO_AGUARDA). Achou: atualiza a planilha de controle com
o número SEI do memo (coluna do memo e
verificar_marcadores_memo_aguarda_assinado) e, com os marcadores
consistentes, a prox_acao (Aguardar resposta ao memo enviado, a que o
geacs_inicial daria).

A árvore e os textos dos memos só são lidos quando alguma conferência
precisa deles.
"""

import logging
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import NamedTuple

from constantes import PADRAO_ASSINATURA_MEMO_AGUARDA, PREFIXO_UNIDADE_DISA, UNIDADE_DEPROC
from docs_processo import filtrar_memos_geacs, filtrar_memos_unidade, ler_texto_doc, obter_memos_apis_para_geacs
from marcadores_disponiveis import garantir_marcadores_no_sei
from processo_fechado import ProcessoFechadoNoSetor, reabrir_processo_fechado
from rede_propria import ErroAvaliacao
from Registro import PROX_ACAO_POR_CONCLUSAO, PROX_ACAO_POR_NO_BLOCO, PROX_ACOES_A_VERIFICAR, ProxAcao, RegistroVerificarMarcadores
from sei_automacao.processo import acessar_processo, concluir_processo, listar_documentos_arvore
from selenium import webdriver
from tags import (
    AGUARDA_POR_NO_BLOCO,
    PREFIXO,
    PREFIXO_VELHO,
    TAG_AGUARDA_DEPROC_COPARTICIPACAO,
    TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_ENCAMINHADO_APIS_TODAS_INFOS,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_APIS_SEM_USO,
    TAG_NO_BLOCO_APIS_TODAS_INFOS,
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAGS_AGUARDA_RESPOSTA_DISA,
    TAGS_ESTADO_NOVO,
    TAGS_PARADA_NOVO,
    TAGS_RETOMADA_NOVO,
    TAGS_TRATAMENTO_MANUAL,
    MarcadoresInconsistentes,
    adicionar_tag,
    conferir_marcadores,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES
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
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA

logger = logging.getLogger(__name__)


class AcaoSugerida:
    """Valores da coluna verificar_marcadores_acao_sugerida: o que fazer com
    o processo (para filtrar e montar as abas de processos_a_processar)."""

    RODAR_INICIAL = 'Rodar geacs_inicial'
    RODAR_TODAS_INFOS = 'Rodar geacs_todas_infos'
    RODAR_CORRIGE_ENVIO_DISA = 'Rodar geacs_corrige_envio_disa'
    TRATAR_RESPOSTA_DISA = 'Tratar a resposta da DISA (geacs_resp_disa, TODO)'
    TROCAR_MARCADOR_ASSINADO = 'Trocar o No Bloco pelo marcador de assinado (memo já assinado)'
    CORRIGIR_MARCADORES = 'Corrigir marcadores no SEI'
    VERIFICAR_MANUALMENTE = 'Verificar manualmente'


class Problema(NamedTuple):
    """Uma inconsistência: a frase (coluna verificar_marcadores_inconsistencia)
    e a ação sugerida (verificar_marcadores_acao_sugerida)."""

    frase: str
    acao: str


@dataclass(frozen=True)
class MemoDoMarcador:
    """Memo que o marcador "No Bloco" (e o seu "Aguarda") indica."""

    descricao: str
    padrao_assunto: re.Pattern
    # Coluna da planilha de controle com o número SEI do memo
    coluna_sei: str
    # Relatórios do MANTIS (RP / RC) que o memo cita, anexados antes dele
    redes_relatorios: tuple[str, ...] = ()
    # Casos base DISA x MANTIS possíveis (coluna caso_disa_mantis), cada um
    # (DISA, MANTIS RP, MANTIS RC), None = qualquer
    casos: tuple[tuple[str | None, str | None, str | None], ...] = ()
    # Memo DEPROC: cita os relatórios das redes com uso no MANTIS (RP e/ou
    # RC), pelo caso_disa_mantis; sem o caso, algum dos dois
    relatorios_pelo_caso: bool = False


_MEMO_POR_NO_BLOCO = {
    TAG_MEMO_APIS_SEM_MEMO: MemoDoMarcador('à APIS (sem memorando para a GEACS)', PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO, 'memo_apis_sem_memo_sei'),
    TAG_MEMO_APIS_FORMATO_INVALIDO: MemoDoMarcador('à APIS (formato inválido)', PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO, 'memo_apis_formato_invalido_sei'),
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: MemoDoMarcador('à APIS (matrículas não encontradas)', PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS, 'memo_apis_mat_nao_encontradas_sei'),
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: MemoDoMarcador('à APIS (período dos dependentes)', PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES, 'memo_apis_periodo_deps_sei'),
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA: MemoDoMarcador('à DISA (validar e complementar)', PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, 'memo_disa_sei', ('RP',), (('sim', 'sim', None),)),
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA: MemoDoMarcador('à DISA (validar; não consta)', PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA, 'memo_disa_sei', ('RP',), (('não', 'sim', None),)),
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO: MemoDoMarcador('à DISA (sem MANTIS: solicita relatório)', PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO, 'memo_disa_sei', (), (('sim', 'não', None),)),
    TAG_MEMO_DEPROC_COPARTICIPACAO: MemoDoMarcador(
        'DEPROC (coparticipação)', PADRAO_ASSUNTO_MEMO_DEPROC, 'memo_deproc_sei', casos=(('não', 'sim', None), ('não', 'não', 'sim')), relatorios_pelo_caso=True
    ),
    TAG_NO_BLOCO_APIS_SEM_USO: MemoDoMarcador('à APIS (nenhum uso nas bases)', PADRAO_ASSUNTO_MEMO_APIS_SEM_USO, 'memo_apis_sem_uso_sei', (), (('não', 'não', 'não'),)),
    TAG_NO_BLOCO_APIS_TODAS_INFOS: MemoDoMarcador('à APIS (todas as informações)', PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, 'memo_apis_todas_infos_sei'),
}
# Marcador manual depois da assinatura (o "Aguarda" e, no retorno final à
# APIS, o "Encaminhado"), que indica o mesmo memo do seu "No Bloco"
_ASSINADO_POR_NO_BLOCO = {**AGUARDA_POR_NO_BLOCO, TAG_NO_BLOCO_APIS_TODAS_INFOS: TAG_ENCAMINHADO_APIS_TODAS_INFOS}
_NO_BLOCO_POR_ASSINADO = {assinado: no_bloco for no_bloco, assinado in _ASSINADO_POR_NO_BLOCO.items()}

_PADRAO_ASSINADO = re.compile(r'assinado\s+eletronicamente\s+por', re.IGNORECASE)
_PADRAO_ASSINADO_POR = re.compile(PADRAO_ASSINATURA_MEMO_AGUARDA, re.IGNORECASE)
# Marcadores "Aguarda" (manuais, depois da assinatura) com memo conhecido
_TAGS_AGUARDA = frozenset(AGUARDA_POR_NO_BLOCO.values())

# ADC PDF ANT AUT/MAN em processo que já tinha estado (ou VELHO): o estado
# fica como estava
_PROX_ACOES_ESTADO_MANTIDO = (ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO, ProxAcao.ADC_PDF_ANT_MAN_ESTADO_MANTIDO)
_PROX_ACOES_AGUARDA_FLUXO_NORMAL = (ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL, ProxAcao.ADC_PDF_ANT_MAN_AGUARDA_FLUXO_NORMAL)
# prox_acao dos fluxos da DEPROC: a última passagem foi na unidade da DEPROC,
# com outros marcadores. Na GEACS, o processo está com o memo DEPROC (no bloco
# ou, depois da assinatura, aguardando a DEPROC)
_PREFIXO_PROX_ACAO_DEPROC = 'DEPROC:'
_ESTADOS_COM_A_DEPROC = frozenset({TAG_MEMO_DEPROC_COPARTICIPACAO, TAG_AGUARDA_DEPROC_COPARTICIPACAO})
# Memo à DISA "Validar (N Consta)": pela regra atual, o processo vai direto à
# DEPROC (fluxo geacs_corrige_envio_disa)
_ESTADOS_N_CONSTA = frozenset({TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA})

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


def _passagem_na_deproc(fluxo) -> bool:
    """A última passagem que gravou a prox_acao foi na unidade da DEPROC
    (coluna fluxo: "DEPROC - ...")."""
    return str(fluxo).strip().upper().startswith('DEPROC')


def _aceita_com_o_estado(prox_acao: str | None, estado: str | None) -> bool:
    """As de erro valem com qualquer marcador (o erro está nas colunas
    tipo_erro e erro); as da DEPROC, com o memo DEPROC na GEACS."""
    if prox_acao in PROX_ACOES_A_VERIFICAR:
        return True
    return prox_acao is not None and prox_acao.startswith(_PREFIXO_PROX_ACAO_DEPROC) and estado in _ESTADOS_COM_A_DEPROC


def conferir_prox_acao(prox_acao: str | None, marcadores: list[str], fluxo: str | None = None) -> list[Problema]:
    """Confere a prox_acao da planilha com os marcadores do processo. fluxo:
    a coluna fluxo da planilha (a última passagem que gravou a prox_acao).
    Devolve os problemas (vazia: faz sentido)."""
    atuais = set(marcadores)
    try:
        conferir_marcadores(SimpleNamespace(marcadores_atuais=list(marcadores)))
    except MarcadoresInconsistentes as e:
        # Sem estado único não há prox_acao esperada
        if prox_acao == ProxAcao.VERIFICAR_MARCADORES:
            return [Problema(str(e), AcaoSugerida.CORRIGIR_MARCADORES)]
        return [Problema(f'{e} (prox_acao "{prox_acao or "(vazia)"}"; esperada: "{ProxAcao.VERIFICAR_MARCADORES}")', AcaoSugerida.CORRIGIR_MARCADORES)]

    estado = next((tag for tag in TAGS_ESTADO_NOVO if tag in atuais), None)
    # A GEACS acabou de abrir o processo: a falta de acesso numa passagem da
    # GEACS foi resolvida. Na da DEPROC (ou sem a coluna fluxo), não dá para saber
    if prox_acao == ProxAcao.VERIFICAR_ACESSO_UNIDADE and fluxo and not _passagem_na_deproc(fluxo):
        frase = f'prox_acao "{prox_acao}", mas a GEACS abriu o processo nesta passagem: o acesso foi resolvido ({_RODAR_INICIAL})'
        return [Problema(frase, AcaoSugerida.RODAR_INICIAL)]
    if prox_acao == ProxAcao.VERIFICAR_MARCADORES:
        return [Problema(f'prox_acao "{prox_acao}", mas os marcadores estão consistentes ({_RODAR_INICIAL})', AcaoSugerida.RODAR_INICIAL)]

    esperadas, origem, pelo_inicial = _esperadas(atuais, estado)
    if prox_acao in esperadas or _aceita_com_o_estado(prox_acao, estado):
        return []
    esperada = esperadas[0] or '(vazia)'
    dica = f' ({_RODAR_INICIAL})' if pelo_inicial else ''
    # Com marcadores do script, o geacs_inicial continua o fluxo (ou só
    # atualiza a prox_acao); sem eles, não há o que rodar
    tratado = estado is not None or bool(atuais & {TAG_PROCESSO_NOVO, TAG_PROCESSO_VELHO})
    acao = AcaoSugerida.RODAR_INICIAL if tratado else AcaoSugerida.VERIFICAR_MANUALMENTE
    return [Problema(f'prox_acao "{prox_acao or "(vazia)"}" não condiz com {origem}; esperada: "{esperada}"{dica}', acao)]


def _valores_caso(caso) -> tuple[str, str, str] | None:
    """('sim'|'não', ...) do caso_disa_mantis da planilha (None se vazio ou
    fora do padrão)."""
    achado = _PADRAO_CASO.search(str(caso)) if caso else None
    return tuple(v.casefold() for v in achado.groups()) if achado else None


def conferir_caso_disa_mantis(caso: str | None, no_bloco: str) -> list[Problema]:
    """O caso base DISA x MANTIS da planilha (se preenchido) é o do memo do
    marcador."""
    memo = _MEMO_POR_NO_BLOCO[no_bloco]
    valores = _valores_caso(caso)
    if not memo.casos or valores is None:
        return []
    if any(all(esperado is None or esperado == valor for esperado, valor in zip(possivel, valores, strict=True)) for possivel in memo.casos):
        return []
    return [Problema(f'caso_disa_mantis "{caso}" não condiz com o memo {memo.descricao} do marcador "{_curto(no_bloco)}"', AcaoSugerida.VERIFICAR_MANUALMENTE)]


# ---------------------------------------------------------------------------
# Memorandos e relatórios na árvore
# ---------------------------------------------------------------------------


class ArvoreProcesso:
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

    def assinado(self, doc: dict) -> bool:
        return _PADRAO_ASSINADO.search(self.texto(doc)) is not None

    def signatario(self, doc: dict) -> str | None:
        """Quem assinou o memo, se for Gustavo, Bruna ou Danúbia
        (PADRAO_ASSINATURA_MEMO_AGUARDA); None se não."""
        achado = _PADRAO_ASSINADO_POR.search(self.texto(doc))
        return ' '.join(achado.group(1).split()) if achado else None


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def _relatorio_da_rede(doc: dict, rede: str) -> bool:
    """Relatório do MANTIS: "PDF Utilização <Tit.|Dep.> <RP|RC> - ..."."""
    return re.match(rf'PDF\s+Utiliza[çc][ãa]o\s+(Tit\.|Dep\.)\s+{rede}\b', doc['nome_arvore'], re.IGNORECASE) is not None


def _redes_citadas(memo: MemoDoMarcador, linha: dict) -> tuple[str, ...]:
    """Relatórios que o memo cita. O memo DEPROC cita os das redes com uso no
    MANTIS (caso_disa_mantis)."""
    if not memo.relatorios_pelo_caso:
        return memo.redes_relatorios
    valores = _valores_caso(linha.get('caso_disa_mantis'))
    if valores is None:
        return ()
    return tuple(rede for rede, usou in (('RP', valores[1]), ('RC', valores[2])) if usou == 'sim')


def _conferir_assinatura(arvore: ArvoreProcesso, estado: str, memo: MemoDoMarcador, encontrado: dict) -> list[Problema]:
    """No Bloco: o memo ainda não foi assinado. Aguarda / Encaminhado
    (colocados depois da assinatura): o memo está assinado."""
    assinado = arvore.assinado(encontrado)
    if estado in _ASSINADO_POR_NO_BLOCO and assinado:
        frase = f'memo {memo.descricao} ({encontrado["numero_sei"]}) já assinado, mas o processo continua com o "{_curto(estado)}": troque pelo "{_curto(_ASSINADO_POR_NO_BLOCO[estado])}"'
        return [Problema(frase, AcaoSugerida.TROCAR_MARCADOR_ASSINADO)]
    if estado in _NO_BLOCO_POR_ASSINADO and not assinado:
        return [Problema(f'marcador "{_curto(estado)}", mas o memo {memo.descricao} ({encontrado["numero_sei"]}) não está assinado', AcaoSugerida.VERIFICAR_MANUALMENTE)]
    return []


def conferir_memo_do_marcador(arvore: ArvoreProcesso, estado: str, linha: dict) -> list[Problema]:
    """O memo do marcador "No Bloco" (ou do seu "Aguarda" / "Encaminhado")
    está na árvore, com os relatórios que ele cita antes dele e a assinatura
    condizente com o marcador. O do "No Bloco" precisa estar na rodada (depois
    do último memo da APIS destinado à GEACS); o do "Aguarda" pode estar antes
    (a resposta da APIS é um novo memo)."""
    depois_da_assinatura = estado in _NO_BLOCO_POR_ASSINADO
    no_bloco = _NO_BLOCO_POR_ASSINADO.get(estado, estado)
    memo = _MEMO_POR_NO_BLOCO[no_bloco]
    manual = AcaoSugerida.VERIFICAR_MANUALMENTE
    problemas = []

    encontrado = arvore.ultimo_memo_geacs(memo.padrao_assunto)
    if encontrado is None:
        problemas.append(Problema(f'marcador "{_curto(estado)}" sem o memo {memo.descricao} na árvore (procurado pelo assunto)', manual))
    else:
        indice = arvore.indice(encontrado)
        numero = encontrado['numero_sei']
        logger.info(f'Memo {memo.descricao} do marcador "{_curto(estado)}": {_descrever(encontrado)}')
        if not depois_da_assinatura and indice < arvore.inicio_rodada():
            frase = f'memo {memo.descricao} ({numero}) é de antes do último memo da APIS destinado à GEACS: o marcador "{_curto(estado)}" é de um pedido anterior'
            problemas.append(Problema(frase, manual))
        inicio = arvore.inicio_rodada(ate=indice)
        antes = arvore.docs[inicio:indice]
        for rede in _redes_citadas(memo, linha):
            if not any(_relatorio_da_rede(doc, rede) for doc in antes):
                problemas.append(Problema(f'memo {memo.descricao} ({numero}) sem relatório {rede} do MANTIS antes dele na rodada', manual))
        if memo.relatorios_pelo_caso and _valores_caso(linha.get('caso_disa_mantis')) is None and not any(_relatorio_da_rede(doc, r) for doc in antes for r in ('RP', 'RC')):
            problemas.append(Problema(f'memo {memo.descricao} ({numero}) sem relatório RP ou RC do MANTIS antes dele na rodada', manual))
        problemas += _conferir_assinatura(arvore, estado, memo, encontrado)

    numero_planilha = _numero_sei(linha.get(memo.coluna_sei))
    if numero_planilha is not None and all(doc['numero_sei'] != numero_planilha for doc in arvore.docs):
        problemas.append(Problema(f'{memo.coluna_sei} = {numero_planilha} na planilha, mas o documento não está na árvore', manual))

    if no_bloco == TAG_MEMO_APIS_SEM_MEMO and not depois_da_assinatura and arvore.memos_apis_para_geacs:
        ultimo = arvore.memos_apis_para_geacs[-1]
        frase = f'marcador "{_curto(estado)}", mas o processo tem memo da APIS destinado à GEACS ({ultimo["numero_sei"]}): o memo à APIS (sem memorando) não é mais necessário'
        problemas.append(Problema(frase, manual))
    return problemas


def conferir_retomada(arvore: ArvoreProcesso, estado: str) -> list[Problema]:
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
            frase = (
                f'estado "{_curto(estado)}" com o memo {memo.descricao} ({encontrado["numero_sei"]}) na rodada, sem o marcador "{_curto(no_bloco)}" '
                '(o geacs_inicial reaproveita o memo e adiciona o marcador)'
            )
            problemas.append(Problema(frase, AcaoSugerida.RODAR_INICIAL))
    return problemas


# ---------------------------------------------------------------------------
# Próximo fluxo
# ---------------------------------------------------------------------------


def _memo_resultado_deproc_assinado(arvore: ArvoreProcesso) -> dict | None:
    """O memo de resultado da DEPROC (MemoGeacsCalculoCopa) da rodada, se
    assinado."""
    rodada = arvore.docs[arvore.inicio_rodada() :]
    for memo in reversed(filtrar_memos_unidade(rodada, UNIDADE_DEPROC)):
        if PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA.search(arvore.texto(memo)):
            if arvore.assinado(memo):
                return memo
            logger.info(f'Memo de resultado da DEPROC na rodada, ainda não assinado: {_descrever(memo)}')
            return None
    return None


def _resposta_disa(arvore: ArvoreProcesso, estado: str) -> dict | None:
    """Documento de uma unidade da DISA depois do memo à DISA do marcador."""
    memo = arvore.ultimo_memo_geacs(_MEMO_POR_NO_BLOCO[_NO_BLOCO_POR_ASSINADO[estado]].padrao_assunto)
    if memo is None:
        return None
    depois = arvore.docs[arvore.indice(memo) + 1 :]
    return next((doc for doc in reversed(depois) if doc['unidade'].upper().startswith(PREFIXO_UNIDADE_DISA)), None)


def sugestoes_de_fluxo(arvore: ArvoreProcesso, estado: str) -> list[str]:
    """O próximo fluxo do processo, quando ele já pode seguir (não é
    inconsistência: só a ação sugerida)."""
    acoes = []
    if estado in _ESTADOS_N_CONSTA:
        logger.info('Memo à DISA "Validar (N Consta)": pela regra atual, o processo vai direto à DEPROC (geacs_corrige_envio_disa)')
        acoes.append(AcaoSugerida.RODAR_CORRIGE_ENVIO_DISA)
    if estado == TAG_AGUARDA_DEPROC_COPARTICIPACAO:
        memo = _memo_resultado_deproc_assinado(arvore)
        if memo is not None:
            logger.info(f'Memo de resultado da DEPROC assinado na rodada ({_descrever(memo)}): pronto para o geacs_todas_infos')
            acoes.append(AcaoSugerida.RODAR_TODAS_INFOS)
    if estado in TAGS_AGUARDA_RESPOSTA_DISA:
        resposta = _resposta_disa(arvore, estado)
        if resposta is not None:
            logger.info(f'Documento da DISA depois do memo à DISA: {_descrever(resposta)}')
            acoes.append(AcaoSugerida.TRATAR_RESPOSTA_DISA)
    return acoes


# ---------------------------------------------------------------------------
# Começo do fluxo: "No Bloco" com o memo assinado e memo do "Aguarda" assinado
# ---------------------------------------------------------------------------


def _marcadores_consistentes(marcadores: list[str]) -> bool:
    try:
        conferir_marcadores(SimpleNamespace(marcadores_atuais=list(marcadores)))
    except MarcadoresInconsistentes:
        return False
    return True


def trocar_no_bloco_assinado(driver: webdriver.Remote, arvore: ArvoreProcesso, registro: RegistroVerificarMarcadores, linha: dict | None) -> None:
    """Começo do fluxo: o estado "No Bloco" com o memo dele na rodada já
    assinado por Gustavo, Bruna ou Danúbia (PADRAO_ASSINATURA_MEMO_AGUARDA) é
    trocado pelo marcador de assinado ("Aguarda" ou, no 01.12, "Encaminhado"),
    com tags.adicionar_tag (que remove o "No Bloco"). A prox_acao passa a ser a
    que o geacs_inicial daria ao novo estado (exceto a da DEPROC, que diz mais).

    Só com os marcadores consistentes (um estado) e o marcador novo cadastrado
    no SEI (senão, inconsistência e nada muda). Processo fechado na GEACS (sem
    "Incluir Documento"): é reaberto, o marcador é trocado e o processo é
    concluído de novo (_concluir_de_novo, mesmo se a troca falhar). Com o
    MANUAL, o fechado não é reaberto (TAGS_TRATAMENTO_MANUAL), e o marcador
    não é trocado."""
    estados = [tag for tag in TAGS_ESTADO_NOVO if tag in registro.marcadores_atuais]
    if len(estados) != 1 or estados[0] not in _ASSINADO_POR_NO_BLOCO or not _marcadores_consistentes(registro.marcadores_atuais):
        return
    no_bloco = estados[0]
    novo = _ASSINADO_POR_NO_BLOCO[no_bloco]
    memo = _MEMO_POR_NO_BLOCO[no_bloco]
    encontrado = arvore.ultimo_memo_geacs(memo.padrao_assunto)
    if encontrado is None or arvore.indice(encontrado) < arvore.inicio_rodada():
        # Sem o memo da rodada: a conferência do memo do marcador aponta
        return
    signatario = arvore.signatario(encontrado)
    if signatario is None:
        return
    reaberto = False
    if not registro.aberto_na_geacs:
        if TAGS_TRATAMENTO_MANUAL & set(registro.marcadores_atuais):
            logger.info(f'Memo {memo.descricao} ({_descrever(encontrado)}) assinado, mas o processo está fechado na GEACS e tem o MANUAL: não é reaberto')
            return
        logger.info(f'Memo {memo.descricao} ({_descrever(encontrado)}) assinado e processo fechado na GEACS: reabre para trocar o "{_curto(no_bloco)}"')
        try:
            reabrir_processo_fechado(driver, registro)
        except ProcessoFechadoNoSetor as e:
            logger.warning(f'Marcador "{_curto(no_bloco)}" não trocado: {e}')
            _registrar(
                registro,
                [Problema(f'memo {memo.descricao} ({encontrado["numero_sei"]}) assinado, mas o processo fechado não pôde ser reaberto para trocar o marcador', AcaoSugerida.TROCAR_MARCADOR_ASSINADO)],
            )
            return
        reaberto = True

    try:
        try:
            garantir_marcadores_no_sei(driver, [novo])
        except ErroAvaliacao as e:
            logger.warning(f'Marcador "{_curto(no_bloco)}" não trocado: {e}')
            _registrar(registro, [Problema(f'memo {memo.descricao} ({encontrado["numero_sei"]}) assinado, mas o "{_curto(novo)}" não está cadastrado no SEI', AcaoSugerida.CORRIGIR_MARCADORES)])
            return
        logger.info(f'Memo {memo.descricao} assinado por {signatario} ({_descrever(encontrado)}): troca "{_curto(no_bloco)}" -> "{_curto(novo)}"')
        adicionar_tag(driver, registro, novo)
        registro.marcadores_trocados.append(f'{_curto(no_bloco)} -> {_curto(novo)}: {encontrado["numero_sei"]} ({signatario})')
        # Antes de concluir: a troca vale mesmo se a conclusão falhar
        _atualizar_prox_acao_pela_troca(registro, linha, novo)
    finally:
        if reaberto:
            _concluir_de_novo(driver, registro)


def _atualizar_prox_acao_pela_troca(registro: RegistroVerificarMarcadores, linha: dict | None, novo: str) -> None:
    """A prox_acao do novo estado (exceto a da DEPROC, que diz mais)."""
    atual = (linha or {}).get('prox_acao')
    esperada = _PROX_ACAO_DO_INICIAL[novo]
    if atual != esperada and not (isinstance(atual, str) and atual.startswith(_PREFIXO_PROX_ACAO_DEPROC)):
        registro.prox_acao_atualizada = esperada
        logger.info(f'Planilha: prox_acao "{atual or "(vazia)"}" -> "{esperada}" (marcador trocado)')


def _concluir_de_novo(driver: webdriver.Remote, registro: RegistroVerificarMarcadores) -> None:
    """Conclui o processo reaberto para trocar o marcador (volta a ficar
    fechado na GEACS). Falhou: ErroAvaliacao (concluir à mão)."""
    try:
        acessar_processo(driver, registro.num_processo)
        concluir_processo(driver)
        acessar_processo(driver, registro.num_processo)
    except Exception as e:
        logger.exception('Falha ao concluir de novo o processo reaberto para trocar o marcador')
        raise ErroAvaliacao('Processo reaberto para trocar o marcador e não foi concluído de novo: conclua à mão no SEI') from e
    registro.concluido_de_novo = True
    if registro.marcadores_trocados:
        registro.marcadores_trocados[-1] += ' (processo reaberto e concluído de novo)'
    logger.info('Processo concluído de novo na GEACS (estava fechado antes da troca do marcador)')


def conferir_memos_aguarda(arvore: ArvoreProcesso, registro: RegistroVerificarMarcadores, linha: dict | None) -> None:
    """Começo do fluxo: para cada marcador "Aguarda" do processo, procura o
    memo do marcador (o mais recente da GEACS com o assunto do memo) assinado
    por Gustavo, Bruna ou Danúbia. Achou: registra o número SEI na coluna do
    memo (memo_disa_sei, memo_deproc_sei, ...) e em
    verificar_marcadores_memo_aguarda_assinado. Se o "Aguarda" é o único estado
    e os marcadores estão consistentes, atualiza também a prox_acao para
    Aguardar resposta ao memo enviado (exceto a prox_acao da DEPROC, que diz
    mais). Sem o memo ou sem a assinatura, nada muda aqui (a conferência do memo
    do marcador aponta o problema)."""
    aguardas = [tag for tag in registro.marcadores_atuais if tag in _TAGS_AGUARDA]
    if not aguardas:
        return
    assinados = []
    for tag in aguardas:
        memo = _MEMO_POR_NO_BLOCO[_NO_BLOCO_POR_ASSINADO[tag]]
        encontrado = arvore.ultimo_memo_geacs(memo.padrao_assunto)
        if encontrado is None:
            logger.info(f'Marcador "{_curto(tag)}" sem o memo {memo.descricao} na árvore')
            continue
        signatario = arvore.signatario(encontrado)
        if signatario is None:
            logger.info(f'Memo {memo.descricao} do marcador "{_curto(tag)}" ({_descrever(encontrado)}) sem assinatura de Gustavo, Bruna ou Danúbia')
            continue
        numero = encontrado['numero_sei']
        logger.info(f'Memo {memo.descricao} do marcador "{_curto(tag)}" assinado por {signatario}: {_descrever(encontrado)}')
        registro.memos_aguarda_assinados.append(f'{_curto(tag)}: {numero} ({signatario})')
        anterior = _numero_sei((linha or {}).get(memo.coluna_sei))
        if anterior != numero:
            logger.info(f'Planilha: {memo.coluna_sei} = {numero} (antes: {anterior or "vazia"})')
        registro.colunas_memo_aguarda[memo.coluna_sei] = numero
        assinados.append(tag)

    estados = [tag for tag in TAGS_ESTADO_NOVO if tag in registro.marcadores_atuais]
    if len(estados) != 1 or estados[0] not in assinados or not _marcadores_consistentes(registro.marcadores_atuais):
        return
    atual = registro.prox_acao_atualizada or (linha or {}).get('prox_acao')
    if atual == ProxAcao.AGUARDAR_RESPOSTA_MEMO or (isinstance(atual, str) and atual.startswith(_PREFIXO_PROX_ACAO_DEPROC)):
        return
    registro.prox_acao_atualizada = ProxAcao.AGUARDAR_RESPOSTA_MEMO
    logger.info(f'Planilha: prox_acao "{atual or "(vazia)"}" -> "{ProxAcao.AGUARDAR_RESPOSTA_MEMO}" (memo do "Aguarda" assinado)')


# ---------------------------------------------------------------------------
# Conferência do processo
# ---------------------------------------------------------------------------


def _registrar(registro: RegistroVerificarMarcadores, problemas: list[Problema]) -> None:
    registro.inconsistencias += [p.frase for p in problemas]
    registro.acoes_sugeridas += [p.acao for p in problemas]


def conferir_processo(driver: webdriver.Remote, registro: RegistroVerificarMarcadores, linha: dict | None, arvore: ArvoreProcesso | None = None) -> None:
    """Preenche registro.inconsistencias e registro.acoes_sugeridas. linha: a
    linha do processo na planilha de controle (None: planilha não lida, a
    prox_acao não é conferida). arvore: a já lida (conferir_memos_aguarda).
    A prox_acao conferida é a atualizada pelo memo do "Aguarda" assinado."""
    arvore = arvore or ArvoreProcesso(driver)
    if linha is not None and registro.prox_acao_atualizada is not None:
        linha = {**linha, 'prox_acao': registro.prox_acao_atualizada}
    marcadores = registro.marcadores_atuais
    atuais = set(marcadores)
    if linha is None:
        logger.warning('Planilha de controle não lida: a prox_acao não é conferida')
    else:
        _registrar(registro, conferir_prox_acao(linha.get('prox_acao'), marcadores, linha.get('fluxo')))

    estados = [tag for tag in TAGS_ESTADO_NOVO if tag in atuais]
    if len(estados) != 1:
        # Sem estado não há memo a conferir; com mais de um, a combinação já
        # é inconsistente
        return
    estado = estados[0]
    no_bloco = _NO_BLOCO_POR_ASSINADO.get(estado, estado)
    if no_bloco in _MEMO_POR_NO_BLOCO:
        if linha is not None:
            _registrar(registro, conferir_caso_disa_mantis(linha.get('caso_disa_mantis'), no_bloco))
        _registrar(registro, conferir_memo_do_marcador(arvore, estado, linha or {}))
    elif estado in TAGS_RETOMADA_NOVO:
        _registrar(registro, conferir_retomada(arvore, estado))
    registro.acoes_sugeridas += sugestoes_de_fluxo(arvore, estado)
