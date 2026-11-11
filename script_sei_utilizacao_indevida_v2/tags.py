"""Marcadores do SEI usados pelo script v2.

Os marcadores do SEI são de cada unidade: os TAG_DEPROC_* só existem na
DEPROC (fluxo DEPROC) e os demais, só na GEACS. Por isso podem ter o mesmo
nome (ex.: "v2: 01 - Tratado pelo Script").

Marcadores de estado: o processo tem no máximo um. Ao adicionar um marcador
de estado, o estado anterior é removido (o SEI mostra só onde o processo
está). O mesmo vale para cada par base DISA/MANTIS (usou ou não a rede
própria). Os demais marcadores (VELHO, NOVO, informativos e os da versão
anterior do fluxo) se acumulam.
"""

import logging

from rede_propria import ErroAvaliacao
from sei_automacao.processo import adicionar_marcador, remover_marcador
from selenium import webdriver

logger = logging.getLogger(__name__)

# Prefixos: "v2: " (fluxo atual) e "v2v: " (versão anterior, de propósito,
# para sinalizar que são velhos)
PREFIXO = 'v2: '
PREFIXO_VELHO = 'v2v: '

# Numeração: os dois primeiros números têm dois dígitos (01.08.3); o número
# após o "01." é a ordem de inserção. Marcadores com o mesmo número são
# alternativos (o processo recebe um ou outro). Um ".1" no fim é o marcador
# manual "Aguarda", colocado depois da assinatura do memo do mesmo número.
# O SEI limita o nome do marcador a 50 caracteres.

# Processo VELHO: enviado à DISA e à DEPROC antes da avaliação da rede
# própria. Separado no início do fluxo e não processado (TODO: fluxo próprio)
TAG_PROCESSO_VELHO = 'v2: 00 - Processo VELHO'

# Todo processo tratado pelo script, exceto o VELHO (o antigo
# "02 - Processo VELHO" é ignorado)
TAG_PROCESSO_NOVO = 'v2: 01 - Tratado pelo Script'
TAG_PERIODO_VAR_DEP = 'v2: 01.01 - Período Variável p/ Dependentes'
# Matrícula(s) não encontrada(s) na base APIS (listagem de todos os
# beneficiários)
TAG_MAT_NAO_ENCONTRADAS_APIS = 'v2: 01.02.1 - Mat. N Encontradas Base APIS'

# Versão anterior do fluxo e rotina de correção (não são mais adicionados).
# Com "Memos DISA e DEPROC no Bloco", o processo é VELHO: foi enviado à DISA
# e à DEPROC antes da avaliação da rede própria.
TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO = 'v2v: 01.02.2 - Mat. N Encontradas Base DISA'
TAG_AVALIADO_USO_REDE_PROPRIA = 'v2v: 01.02 - Avaliado Se Usou Rede Própria'
TAG_MEMOS_DISA_DEPROC_NO_BLOCO = 'v2v: 01.03 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_NO_BLOCO = 'v2v: 01.03 - Memo DEPROC no Bloco'
TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO = 'v2v: 01.04 - Memo Não Usou Rede no Bloco'

# Informativos da comparação base DISA x MANTIS, um par por base (e por
# rede, no MANTIS). Os do mesmo par são alternativos
TAG_DISA_USOU_RP = 'v2: 01.06.2 - Base DISA: Usou RP'
TAG_DISA_NAO_USOU_RP = 'v2: 01.06.2 - Base DISA: Não Usou RP'
TAG_MANTIS_USOU_RP = 'v2: 01.08.2 - MANTIS: Usou RP'
TAG_MANTIS_NAO_USOU_RP = 'v2: 01.08.2 - MANTIS: Não Usou RP'
TAG_MANTIS_USOU_RC = 'v2: 01.08.3 - MANTIS: Usou RC'
TAG_MANTIS_NAO_USOU_RC = 'v2: 01.08.3 - MANTIS: Não Usou RC'

# Marcadores de estado. Os "No Bloco" indicam que o memo foi criado e
# inserido no bloco (aguarda assinatura); cada um tem um "Aguarda", colocado
# à mão depois da assinatura (quem coloca remove o "No Bloco"): o processo
# aguarda a resposta do destinatário.
# Memo da APIS ausente ou em formato inválido (alternativos)
TAG_MEMO_APIS_SEM_MEMO = 'v2: 01.05 - No Bloco APIS: Sem Memo p/ GEACS'
TAG_MEMO_APIS_FORMATO_INVALIDO = 'v2: 01.05 - No Bloco APIS: Formato Inválido'
TAG_AGUARDA_APIS_SEM_MEMO = 'v2: 01.05.1 - Aguarda APIS: Sem Memo p/ GEACS'
TAG_AGUARDA_APIS_FORMATO_INVALIDO = 'v2: 01.05.1 - Aguarda APIS: Formato Inválido'
TAG_AVALIADO_USO_REDE_PROPRIA_DISA = 'v2: 01.06 - Avaliado Uso Rede Própria DISA'
# Depois do 01.02.1 (matrícula não encontrada na base APIS)
TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS = 'v2: 01.06.1 - No Bloco APIS: Matrículas'
TAG_AGUARDA_APIS_MATRICULAS = 'v2: 01.06.1.1 - Aguarda APIS: Matrículas'
# Depois do 01.01 (período variável para dependentes)
TAG_MEMO_APIS_PERIODO_DEPENDENTES = 'v2: 01.07 - No Bloco APIS: Período Deps'
TAG_AGUARDA_APIS_PERIODO_DEPS = 'v2: 01.07.1 - Aguarda APIS: Período Deps'
TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS = 'v2: 01.08 - Avaliado Uso Rede Própria MANTIS'
# Memo à DISA (alternativos). Quem vai para a DISA não vai para a DEPROC
# Base DISA sim, MANTIS sim: validar e complementar (relatórios RP anexados)
TAG_NO_BLOCO_DISA_VALIDAR_CONSTA = 'v2: 01.09 - No Bloco DISA: Validar (Consta)'
# Base DISA não, MANTIS sim: validar (relatórios RP anexados)
TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA = 'v2: 01.09 - No Bloco DISA: Validar (N Consta)'
# Base DISA sim, MANTIS não: relatório da DISA
TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO = 'v2: 01.09 - No Bloco DISA: Relat. s/ MANTIS'
TAG_AGUARDA_DISA_VALIDAR_CONSTA = 'v2: 01.09.1 - Aguarda DISA: Validar (Consta)'
TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA = 'v2: 01.09.1 - Aguarda DISA: Validar (N Consta)'
TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO = 'v2: 01.09.1 - Aguarda DISA: Relat. s/ MANTIS'
# Base DISA não e MANTIS RP não (alternativos):
# - MANTIS RC sim: relatórios RC e memo DEPROC no bloco;
# - MANTIS RC não: memo à APIS (nenhum uso nas bases) no bloco
TAG_MEMO_DEPROC_COPARTICIPACAO = 'v2: 01.10 - No Bloco DEPROC: Coparticipação'
TAG_NO_BLOCO_APIS_SEM_USO = 'v2: 01.10 - No Bloco APIS: Sem Uso'
TAG_AGUARDA_DEPROC_COPARTICIPACAO = 'v2: 01.10.1 - Aguarda DEPROC: Coparticipação'
TAG_AGUARDA_APIS_SEM_USO = 'v2: 01.10.1 - Aguarda APIS: Sem Uso'

# Estados da versão anterior do fluxo (não são mais adicionados)
TAG_MEMO_DISA_VALIDAR_USOS_MANTIS = 'v2: 01.08.1 - Memo DISA Validar Usos MANTIS'
# Memo à DISA no bloco antes do memo DEPROC: tratado como parada
TAG_MEMO_DISA_USO_REDE_PROPRIA = 'v2: 01.09 - Memo DISA Uso Rede Própria'
TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO = 'v2: 01.10 - Concluído: Memos DISA e DEPROC'
TAG_VELHO_MEMO_DISA = 'v2: 01.11 - VELHO Concluído: Memo DISA'
TAG_VELHO_MEMO_DEPROC = 'v2: 01.11 - VELHO Concluído: Memo DEPROC'

# Estado de entrada: PDF das planilhas inserido pelo fluxo ADC PDF ANT AUT
# (main_geacs_adc_pdf_ant_aut.py). O fluxo normal trata o processo do início e troca este
# estado pelo seguinte
TAG_AGUARDA_FLUXO_NORMAL = 'v2: 01.00 - Aguarda Script: Fluxo Normal'

# Marcadores manuais (não são colocados pelo script)
TAG_PLANILHADO = 'PLANILHADO'
TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'
TAG_MANUAL = 'MANUAL'
TAG_ASSINADO = 'ASSINADO'

# Processos VELHOS tratados manualmente: fora do escopo
TAGS_TRATAMENTO_MANUAL = frozenset({TAG_MANUAL, TAG_ASSINADO})

# Memo no bloco -> marcador manual depois da assinatura
AGUARDA_POR_NO_BLOCO = {
    TAG_MEMO_APIS_SEM_MEMO: TAG_AGUARDA_APIS_SEM_MEMO,
    TAG_MEMO_APIS_FORMATO_INVALIDO: TAG_AGUARDA_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: TAG_AGUARDA_APIS_MATRICULAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: TAG_AGUARDA_APIS_PERIODO_DEPS,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA: TAG_AGUARDA_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA: TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO: TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO,
    TAG_MEMO_DEPROC_COPARTICIPACAO: TAG_AGUARDA_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_APIS_SEM_USO: TAG_AGUARDA_APIS_SEM_USO,
}
# Memo no bloco: aguarda assinatura (prox_acao: assinar e encaminhar)
TAGS_NO_BLOCO_NOVO = tuple(AGUARDA_POR_NO_BLOCO)
# Memo assinado e encaminhado (marcador manual) ou estado da versão
# anterior: processo parado até a resposta do destinatário
TAGS_PARADA_NOVO = (
    *AGUARDA_POR_NO_BLOCO.values(),
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS,
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
)
TAGS_CONCLUSAO_NOVO = (
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_VELHO_MEMO_DISA,
    TAG_VELHO_MEMO_DEPROC,
)
# Estados em que o fluxo é retomado
TAGS_RETOMADA_NOVO = (
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
)
TAGS_ESTADO_NOVO = (TAG_AGUARDA_FLUXO_NORMAL, *TAGS_NO_BLOCO_NOVO, *TAGS_PARADA_NOVO, *TAGS_RETOMADA_NOVO, *TAGS_CONCLUSAO_NOVO)
TAGS_DUPLA_DISA = (TAG_DISA_USOU_RP, TAG_DISA_NAO_USOU_RP)
TAGS_DUPLA_MANTIS = (TAG_MANTIS_USOU_RP, TAG_MANTIS_NAO_USOU_RP)
TAGS_DUPLA_MANTIS_RC = (TAG_MANTIS_USOU_RC, TAG_MANTIS_NAO_USOU_RC)
_DUPLAS = (TAGS_DUPLA_DISA, TAGS_DUPLA_MANTIS, TAGS_DUPLA_MANTIS_RC)
# Marcadores da unidade da DEPROC (fluxo DEPROC). Os marcadores do SEI são de
# cada unidade: estes só existem na DEPROC, e os acima, só na GEACS. Mesmo
# prefixo, mesma numeração (ordem de inserção) e mesmas regras de estado.
TAG_DEPROC_TRATADO = 'v2: 01 - Tratado pelo Script'
# Estado (retomada): relatório de coparticipação anexado; falta o memo
TAG_DEPROC_RELATORIO_ANEXADO = 'v2: 01.01 - Relatório Copart. Anexado'
# Estado (conclusão): memo de resultado da DEPROC à GEACS no bloco
TAG_DEPROC_CONCLUIDO_MEMO = 'v2: 01.02 - Concluído: Memo p/ GEACS'
TAGS_ESTADO_DEPROC = (TAG_DEPROC_RELATORIO_ANEXADO, TAG_DEPROC_CONCLUIDO_MEMO)
TAGS_DEPROC = (TAG_DEPROC_TRATADO, *TAGS_ESTADO_DEPROC)

# Grupos de alternativos: adicionar um remove os outros do mesmo grupo
_GRUPOS_ALTERNATIVOS = (TAGS_ESTADO_NOVO, *_DUPLAS, TAGS_ESTADO_DEPROC)

# Coluna da planilha de controle de cada marcador (indica se o processo
# terminou a passagem com o marcador)
_COLUNA_POR_TAG = {
    TAG_PROCESSO_VELHO: 'tag_processo_velho',
    TAG_PROCESSO_NOVO: 'tag_processo_novo',
    TAG_AGUARDA_FLUXO_NORMAL: 'tag_aguarda_fluxo_normal',
    TAG_PLANILHADO: 'tag_planilhado',
    TAG_UI_INSERIDA: 'tag_ui_inserida',
    TAG_PERIODO_VAR_DEP: 'tag_periodo_variavel_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA: 'tag_avaliado_se_usou_rede_propria',
    TAG_MAT_NAO_ENCONTRADAS_APIS: 'tag_mat_nao_encontradas_base_geral_novo',
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO: 'tag_mat_nao_encontradas_novo',
    TAG_MEMO_APIS_SEM_MEMO: 'tag_memo_apis_sem_memo',
    TAG_MEMO_APIS_FORMATO_INVALIDO: 'tag_memo_apis_formato_invalido',
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: 'tag_memo_apis_mat_nao_encontradas',
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: 'tag_memo_apis_periodo_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA: 'tag_avaliado_uso_rede_propria_disa',
    TAG_DISA_USOU_RP: 'tag_base_disa_usou_rp',
    TAG_DISA_NAO_USOU_RP: 'tag_base_disa_nao_usou_rp',
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS: 'tag_avaliado_uso_rede_propria_mantis',
    TAG_MANTIS_USOU_RP: 'tag_mantis_usou_rp',
    TAG_MANTIS_NAO_USOU_RP: 'tag_mantis_nao_usou_rp',
    TAG_MANTIS_USOU_RC: 'tag_mantis_usou_rc',
    TAG_MANTIS_NAO_USOU_RC: 'tag_mantis_nao_usou_rc',
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS: 'tag_memo_disa_validar_usos_mantis',
    TAG_MEMO_DISA_USO_REDE_PROPRIA: 'tag_memo_disa_uso_rede_propria',
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA: 'tag_aguarda_disa_validar_consta',
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA: 'tag_aguarda_disa_validar_nao_consta',
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO: 'tag_aguarda_disa_sem_mantis_relatorio',
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO: 'tag_memos_disa_deproc_coparticipacao',
    TAG_MEMO_DEPROC_COPARTICIPACAO: 'tag_memo_deproc_coparticipacao',
    TAG_NO_BLOCO_APIS_SEM_USO: 'tag_aguarda_apis_sem_uso',
    # Marcadores manuais depois da assinatura (memo à APIS, DISA ou DEPROC)
    TAG_AGUARDA_APIS_SEM_MEMO: 'tag_aguarda_resposta_apis_sem_memo',
    TAG_AGUARDA_APIS_FORMATO_INVALIDO: 'tag_aguarda_resposta_apis_formato_invalido',
    TAG_AGUARDA_APIS_MATRICULAS: 'tag_aguarda_resposta_apis_matriculas',
    TAG_AGUARDA_APIS_PERIODO_DEPS: 'tag_aguarda_resposta_apis_periodo_deps',
    TAG_AGUARDA_DISA_VALIDAR_CONSTA: 'tag_aguarda_resposta_disa_validar_consta',
    TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA: 'tag_aguarda_resposta_disa_validar_nao_consta',
    TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO: 'tag_aguarda_resposta_disa_sem_mantis_relatorio',
    TAG_AGUARDA_DEPROC_COPARTICIPACAO: 'tag_aguarda_resposta_deproc_coparticipacao',
    TAG_AGUARDA_APIS_SEM_USO: 'tag_aguarda_resposta_apis_sem_uso',
    TAG_VELHO_MEMO_DISA: 'tag_velho_memo_disa',
    TAG_VELHO_MEMO_DEPROC: 'tag_velho_memo_deproc',
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO: 'tag_memos_no_bloco',
    TAG_MEMO_DEPROC_NO_BLOCO: 'tag_memo_deproc_no_bloco',
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO: 'tag_memo_nao_usou_rede_propria_no_bloco',
}

# Colunas dos marcadores da DEPROC (só o fluxo DEPROC as grava)
_COLUNA_POR_TAG_DEPROC = {
    TAG_DEPROC_TRATADO: 'tag_deproc_tratado',
    TAG_DEPROC_RELATORIO_ANEXADO: 'tag_deproc_relatorio_anexado',
    TAG_DEPROC_CONCLUIDO_MEMO: 'tag_deproc_concluido_memo',
}

TAGS_SCRIPT = frozenset(tag for tag in (*_COLUNA_POR_TAG, *_COLUNA_POR_TAG_DEPROC) if tag.startswith((PREFIXO, PREFIXO_VELHO)))


def normalizar_tags(tags: list) -> list[str]:
    return [str(tag).strip() for tag in tags]


def registrar_tags(registro, tags: list[str]) -> None:
    """Registra os marcadores lidos do SEI no início da passagem."""
    registro.marcadores_sei = normalizar_tags(tags)
    registro.marcadores_atuais = list(registro.marcadores_sei)


def colunas_tags(marcadores: list[str]) -> dict[str, bool]:
    return {coluna: tag in marcadores for tag, coluna in _COLUNA_POR_TAG.items()}


def colunas_tags_deproc(marcadores: list[str]) -> dict[str, bool]:
    return {coluna: tag in marcadores for tag, coluna in _COLUNA_POR_TAG_DEPROC.items()}


def tem_tag(registro, tag: str) -> bool:
    """O processo tem o marcador agora (lido no início, adicionado e não
    removido na passagem)."""
    return tag in registro.marcadores_atuais


def estado_atual(registro, estados: tuple[str, ...] = TAGS_ESTADO_NOVO) -> str | None:
    """Marcador de estado do processo (ou None). Mais de um é inconsistente:
    a remoção do estado anterior falhou ou o processo é de antes da troca
    de estados."""
    presentes = [tag for tag in estados if tem_tag(registro, tag)]
    if len(presentes) > 1:
        raise ErroAvaliacao(f'Processo com mais de um marcador de estado: {presentes}. Remover manualmente o(s) anterior(es) no SEI')
    return presentes[0] if presentes else None


class MarcadoresInconsistentes(ErroAvaliacao):
    """A combinação de marcadores do processo não é possível no fluxo."""


def _curto(tag: str) -> str:
    return tag.removeprefix(PREFIXO).removeprefix(PREFIXO_VELHO)


_ESTADOS_DISA = (TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO)


def _com_aguarda(estados: tuple[str, ...]) -> tuple[str, ...]:
    """Os estados e, para cada memo no bloco, o marcador manual colocado
    depois da assinatura (vale a mesma regra)."""
    return tuple(dict.fromkeys(t for estado in estados for t in (estado, AGUARDA_POR_NO_BLOCO.get(estado)) if t))


# Informativos: estados com que podem conviver (os que vêm depois deles no
# fluxo). Sem estado, não há regra (versão anterior ou falha antes do estado)
_ESTADOS_POSSIVEIS_POR_INFORMATIVO = {
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO: tuple(t for t in TAGS_ESTADO_NOVO if t not in _com_aguarda((TAG_MEMO_APIS_SEM_MEMO, TAG_MEMO_APIS_FORMATO_INVALIDO))),
    # Depois do 01.02.1 o processo para (01.06.1); com 01.06 ou 01.08 (retomada),
    # falhou antes do memo
    TAG_MAT_NAO_ENCONTRADAS_APIS: (TAG_AVALIADO_USO_REDE_PROPRIA_DISA, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS),
    TAG_PERIODO_VAR_DEP: (TAG_AVALIADO_USO_REDE_PROPRIA_DISA, TAG_MEMO_APIS_PERIODO_DEPENDENTES),
    TAG_DISA_USOU_RP: (
        TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
        # Período inválido no memo achado depois da base DISA (a versão
        # anterior só validava o período no MANTIS)
        TAG_MEMO_APIS_FORMATO_INVALIDO,
        TAG_MEMO_APIS_PERIODO_DEPENDENTES,
        TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
        TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
        TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO,
    ),
    TAG_DISA_NAO_USOU_RP: (
        TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
        # Período inválido no memo achado depois da base DISA (a versão
        # anterior só validava o período no MANTIS)
        TAG_MEMO_APIS_FORMATO_INVALIDO,
        TAG_MEMO_APIS_PERIODO_DEPENDENTES,
        TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
        TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
        TAG_MEMO_DEPROC_COPARTICIPACAO,
        TAG_NO_BLOCO_APIS_SEM_USO,
    ),
    TAG_MANTIS_USOU_RP: (TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA),
    TAG_MANTIS_NAO_USOU_RP: (TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO, TAG_MEMO_DEPROC_COPARTICIPACAO, TAG_NO_BLOCO_APIS_SEM_USO),
    # A rede credenciada não decide o memo à DISA: qualquer um dos 01.09
    TAG_MANTIS_USOU_RC: (TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, *_ESTADOS_DISA, TAG_MEMO_DEPROC_COPARTICIPACAO),
    TAG_MANTIS_NAO_USOU_RC: (TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, *_ESTADOS_DISA, TAG_NO_BLOCO_APIS_SEM_USO),
}
_ESTADOS_POSSIVEIS_POR_INFORMATIVO = {tag: _com_aguarda(estados) for tag, estados in _ESTADOS_POSSIVEIS_POR_INFORMATIVO.items()}
# Marcador que exige outros
_EXIGIDOS = {
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: (TAG_MAT_NAO_ENCONTRADAS_APIS,),
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: (TAG_PERIODO_VAR_DEP,),
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA: (TAG_DISA_USOU_RP, TAG_MANTIS_USOU_RP),
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA: (TAG_DISA_NAO_USOU_RP, TAG_MANTIS_USOU_RP),
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO: (TAG_DISA_USOU_RP, TAG_MANTIS_NAO_USOU_RP),
    TAG_NO_BLOCO_APIS_SEM_USO: (TAG_DISA_NAO_USOU_RP, TAG_MANTIS_NAO_USOU_RP, TAG_MANTIS_NAO_USOU_RC),
    TAG_VELHO_MEMO_DISA: (TAG_MEMOS_DISA_DEPROC_NO_BLOCO,),
    TAG_VELHO_MEMO_DEPROC: (TAG_MEMOS_DISA_DEPROC_NO_BLOCO,),
}
# O marcador manual exige o mesmo que o do memo no bloco
_EXIGIDOS.update({AGUARDA_POR_NO_BLOCO[tag]: exigidos for tag, exigidos in _EXIGIDOS.items() if tag in AGUARDA_POR_NO_BLOCO})
# Memos à DISA e DEPROC do fluxo atual e da versão anterior: o VELHO não
# passa por eles
_SO_FLUXO_NORMAL = _com_aguarda((
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_APIS_SEM_USO,
))
_INFORMATIVOS = tuple(_ESTADOS_POSSIVEIS_POR_INFORMATIVO)


def eh_velho_pelos_marcadores(registro) -> bool:
    """Marcado como VELHO (00) ou com o 01.03 da versão anterior."""
    return tem_tag(registro, TAG_PROCESSO_VELHO) or tem_tag(registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO)


def conferir_marcadores(registro) -> None:
    """Confere se a combinação de marcadores atuais é possível no fluxo
    (no início e no fim de cada passagem). Levanta MarcadoresInconsistentes
    com todos os problemas encontrados."""
    atuais = set(registro.marcadores_atuais)
    estados = [tag for tag in TAGS_ESTADO_NOVO if tag in atuais]
    estado = estados[0] if len(estados) == 1 else None
    problemas = []

    if len(estados) > 1:
        problemas.append(f'mais de um marcador de estado ({", ".join(map(_curto, estados))}); remover o(s) anterior(es)')
    for dupla in _DUPLAS:
        if all(tag in atuais for tag in dupla):
            problemas.append(f'{" e ".join(map(_curto, dupla))} (são alternativos)')
    do_fluxo = [tag for tag in (*estados, *_INFORMATIVOS) if tag in atuais]
    if do_fluxo and TAG_PROCESSO_NOVO not in atuais:
        problemas.append(f'{", ".join(map(_curto, do_fluxo))} sem o marcador "{_curto(TAG_PROCESSO_NOVO)}"')
    if TAG_MEMOS_DISA_DEPROC_NO_BLOCO in atuais and TAG_MEMO_DEPROC_NO_BLOCO in atuais:
        problemas.append('os dois marcadores 01.03 (são alternativos)')
    if TAG_MEMO_DEPROC_NO_BLOCO in atuais and estados:
        problemas.append(f'concluído na versão anterior ({_curto(TAG_MEMO_DEPROC_NO_BLOCO)}) com estado do fluxo atual')
    for tag, possiveis in _ESTADOS_POSSIVEIS_POR_INFORMATIVO.items():
        # O 1.0 vem antes de todos: equivale a sem estado (informativo antigo)
        if tag in atuais and estado not in {None, TAG_AGUARDA_FLUXO_NORMAL} and estado not in possiveis:
            problemas.append(f'{_curto(tag)} com o estado {_curto(estado)}')
    for tag, exigidos in _EXIGIDOS.items():
        faltando = [e for e in exigidos if e not in atuais]
        if tag in atuais and faltando:
            problemas.append(f'{_curto(tag)} sem {" e ".join(map(_curto, faltando))}')
    if eh_velho_pelos_marcadores(registro):
        problemas += [f'{_curto(tag)} em processo VELHO' for tag in _SO_FLUXO_NORMAL if tag in atuais]

    if problemas:
        raise MarcadoresInconsistentes(f'Marcadores inconsistentes: {"; ".join(problemas)}. Corrigir manualmente no SEI')


def conferir_marcadores_deproc(registro) -> None:
    """Conferência dos marcadores da DEPROC (no início e no fim de cada
    passagem do fluxo DEPROC): no máximo um estado, e estado só com o 1."""
    atuais = set(registro.marcadores_atuais)
    estados = [tag for tag in TAGS_ESTADO_DEPROC if tag in atuais]
    problemas = []
    if len(estados) > 1:
        problemas.append(f'mais de um marcador de estado ({", ".join(map(_curto, estados))}); remover o(s) anterior(es)')
    if estados and TAG_DEPROC_TRATADO not in atuais:
        problemas.append(f'{", ".join(map(_curto, estados))} sem o marcador "{_curto(TAG_DEPROC_TRATADO)}"')
    if problemas:
        raise MarcadoresInconsistentes(f'Marcadores inconsistentes: {"; ".join(problemas)}. Corrigir manualmente no SEI')


def remover_tag(driver: webdriver.Remote, registro, tag: str) -> None:
    remover_marcador(driver, [tag])
    registro.marcadores_atuais.remove(tag)
    registro.marcadores_removidos.append(tag)
    logger.info(f'Marcador removido: "{tag}"')


def adicionar_tag(driver: webdriver.Remote, registro, tag: str) -> None:
    """Adiciona o marcador no SEI e o registra (coluna
    marcadores_adicionados). Se for de um grupo de alternativos (estado ou
    par base DISA/MANTIS), remove depois o anterior do grupo. Use sempre
    esta função para adicionar marcadores."""
    adicionar_marcador(driver, tag)
    if tag not in registro.marcadores_atuais:
        registro.marcadores_atuais.append(tag)
    registro.marcadores_adicionados.append(tag)
    logger.info(f'Marcador adicionado: "{tag}"')

    for grupo in _GRUPOS_ALTERNATIVOS:
        if tag in grupo:
            for anterior in grupo:
                if anterior != tag and tem_tag(registro, anterior):
                    remover_tag(driver, registro, anterior)


def adicionar_tag_se_ausente(driver: webdriver.Remote, registro, tag: str) -> None:
    """Adiciona o marcador, a menos que o processo já o tenha (retomada)."""
    if tem_tag(registro, tag):
        logger.info(f'Retomada: o processo já tem o marcador "{tag}"')
        return
    adicionar_tag(driver, registro, tag)
