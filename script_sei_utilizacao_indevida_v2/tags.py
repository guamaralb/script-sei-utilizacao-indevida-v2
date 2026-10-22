"""Marcadores do SEI usados pelo script v2.

Marcadores de estado: o processo tem no máximo um. Ao adicionar um marcador
de estado, o estado anterior é removido (o SEI mostra só onde o processo
está). Os demais marcadores (NOVO, informativos e os da versão anterior do
fluxo) se acumulam.
"""

import logging

from rede_propria import ErroAvaliacao
from sei_automacao.processo import adicionar_marcador
from selenium import webdriver

try:
    from sei_automacao.processo import remover_marcador

    REMOCAO_DE_MARCADOR_DISPONIVEL = True
except ImportError:
    # TODO: implementar remover_marcador(driver, marcador) na sei_automacao
    # (sei_automacao.processo). Enquanto não existir, o main.py não roda.
    REMOCAO_DE_MARCADOR_DISPONIVEL = False

    def remover_marcador(driver: webdriver.Remote, marcador: str) -> None:
        raise NotImplementedError(f'remover_marcador não existe na sei_automacao (marcador "{marcador}")')


logger = logging.getLogger(__name__)

# Numeração: o número após o "1." é a ordem de inserção. Marcadores com o
# mesmo número são alternativos (o processo recebe um ou outro).
# O SEI limita o nome do marcador a 50 caracteres.

# Todo processo tratado pelo script (não há mais diferença entre NOVO e
# VELHO na classificação; o antigo "2 - Processo VELHO" é ignorado)
TAG_PROCESSO_NOVO = 'Script v2 - 1 - Processo NOVO'
TAG_PERIODO_VAR_DEP = 'Script v2 - 1.1 - Período Variável p/ Dependentes'
# Matrícula(s) não encontrada(s) na base geral (listagem de todos os
# beneficiários) e na base da rede própria (DISA)
TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO = 'Script v2 - 1.2.1 - Mat. N Encontradas Base Geral'
TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO = 'Script v2 - 1.2.2 - Mat. N Encontradas Base DISA'

# Versão anterior do fluxo e rotina de correção (não são mais adicionados).
# Com "Memos DISA e DEPROC no Bloco", o processo é VELHO: foi enviado à DISA
# e à DEPROC antes da avaliação da rede própria.
TAG_AVALIADO_USO_REDE_PROPRIA = 'Script v2 - 1.2 - Avaliado Se Usou Rede Própria'
TAG_MEMOS_DISA_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memo DEPROC no Bloco'
TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO = 'Script v2 - 1.4 - Memo Não Usou Rede no Bloco'

# Marcadores de estado. Os de memo indicam que o memo foi criado e inserido
# no bloco.
# Memo da APIS ausente ou em formato inválido (alternativos): processo parado
TAG_MEMO_APIS_SEM_MEMO = 'Script v2 - 1.5 - Memo APIS Sem Memo p/ GEACS'
TAG_MEMO_APIS_FORMATO_INVALIDO = 'Script v2 - 1.5 - Memo APIS Formato Inválido'
TAG_AVALIADO_USO_REDE_PROPRIA_DISA = 'Script v2 - 1.6 - Avaliado Uso Rede Própria DISA'
# Depois do 1.2.1 (matrícula não encontrada na base geral): processo parado
TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS = 'Script v2 - 1.6.1 - Memo APIS Mat. N Encontradas'
# Depois do 1.1 (período variável para dependentes): processo parado
TAG_MEMO_APIS_PERIODO_DEPENDENTES = 'Script v2 - 1.7 - Memo APIS Período Dependentes'
TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS = 'Script v2 - 1.8 - Avaliado Uso Rede Própria MANTIS'
# Versão anterior do fluxo (não é mais adicionado): processo parado
TAG_MEMO_DISA_VALIDAR_USOS_MANTIS = 'Script v2 - 1.8.1 - Memo DISA Validar Usos MANTIS'
# Relatórios da rede própria e memo à DISA (validar) no bloco
TAG_MEMO_DISA_USO_REDE_PROPRIA = 'Script v2 - 1.9 - Memo DISA Uso Rede Própria'
# Conclusão do fluxo normal (alternativos): relatórios da rede credenciada e
# memo DEPROC no bloco, com ou sem o memo à DISA
TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO = 'Script v2 - 1.10 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_COPARTICIPACAO = 'Script v2 - 1.10 - Memo DEPROC Coparticipação'
# Conclusão do processo VELHO (alternativos)
# TODO: cadastrar os dois no SEI antes de rodar
TAG_VELHO_MEMO_DISA = 'Script v2 - 1.11 - VELHO Memo DISA no Bloco'
TAG_VELHO_MEMO_DEPROC = 'Script v2 - 1.11 - VELHO Memo DEPROC no Bloco'

# Marcadores manuais (não são colocados pelo script)
TAG_PLANILHADO = 'PLANILHADO'
TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'
TAG_MANUAL = 'MANUAL'
TAG_ASSINADO = 'ASSINADO'

# Processos VELHOS tratados manualmente: fora do escopo
TAGS_TRATAMENTO_MANUAL = frozenset({TAG_MANUAL, TAG_ASSINADO})

# Memo enviado: processo parado até a resposta do destinatário
TAGS_PARADA_NOVO = (
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS,
)
TAGS_CONCLUSAO_NOVO = (
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_VELHO_MEMO_DISA,
    TAG_VELHO_MEMO_DEPROC,
)
# Estados em que o fluxo é retomado
TAGS_RETOMADA_NOVO = (
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
)
TAGS_ESTADO_NOVO = TAGS_PARADA_NOVO + TAGS_RETOMADA_NOVO + TAGS_CONCLUSAO_NOVO

# Coluna da planilha de controle de cada marcador (indica se o processo
# terminou a passagem com o marcador)
_COLUNA_POR_TAG = {
    TAG_PROCESSO_NOVO: 'tag_processo_novo',
    TAG_PLANILHADO: 'tag_planilhado',
    TAG_UI_INSERIDA: 'tag_ui_inserida',
    TAG_PERIODO_VAR_DEP: 'tag_periodo_variavel_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA: 'tag_avaliado_se_usou_rede_propria',
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO: 'tag_mat_nao_encontradas_base_geral_novo',
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO: 'tag_mat_nao_encontradas_novo',
    TAG_MEMO_APIS_SEM_MEMO: 'tag_memo_apis_sem_memo',
    TAG_MEMO_APIS_FORMATO_INVALIDO: 'tag_memo_apis_formato_invalido',
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: 'tag_memo_apis_mat_nao_encontradas',
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: 'tag_memo_apis_periodo_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA: 'tag_avaliado_uso_rede_propria_disa',
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS: 'tag_avaliado_uso_rede_propria_mantis',
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS: 'tag_memo_disa_validar_usos_mantis',
    TAG_MEMO_DISA_USO_REDE_PROPRIA: 'tag_memo_disa_uso_rede_propria',
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO: 'tag_memos_disa_deproc_coparticipacao',
    TAG_MEMO_DEPROC_COPARTICIPACAO: 'tag_memo_deproc_coparticipacao',
    TAG_VELHO_MEMO_DISA: 'tag_velho_memo_disa',
    TAG_VELHO_MEMO_DEPROC: 'tag_velho_memo_deproc',
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO: 'tag_memos_no_bloco',
    TAG_MEMO_DEPROC_NO_BLOCO: 'tag_memo_deproc_no_bloco',
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO: 'tag_memo_nao_usou_rede_propria_no_bloco',
}

TAGS_SCRIPT = frozenset(tag for tag in _COLUNA_POR_TAG if tag.startswith('Script v2'))


def normalizar_tags(tags: list) -> list[str]:
    return [str(tag).strip() for tag in tags]


def registrar_tags(registro, tags: list[str]) -> None:
    """Registra os marcadores lidos do SEI no início da passagem."""
    registro.marcadores_sei = normalizar_tags(tags)
    registro.marcadores_atuais = list(registro.marcadores_sei)


def colunas_tags(marcadores: list[str]) -> dict[str, bool]:
    return {coluna: tag in marcadores for tag, coluna in _COLUNA_POR_TAG.items()}


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


def remover_tag(driver: webdriver.Remote, registro, tag: str) -> None:
    remover_marcador(driver, tag)
    registro.marcadores_atuais.remove(tag)
    registro.marcadores_removidos.append(tag)
    logger.info(f'Marcador removido: "{tag}"')


def adicionar_tag(driver: webdriver.Remote, registro, tag: str) -> None:
    """Adiciona o marcador no SEI e o registra (coluna
    marcadores_adicionados). Se for um marcador de estado, remove depois o
    estado anterior. Use sempre esta função para adicionar marcadores."""
    adicionar_marcador(driver, tag)
    if tag not in registro.marcadores_atuais:
        registro.marcadores_atuais.append(tag)
    registro.marcadores_adicionados.append(tag)
    logger.info(f'Marcador adicionado: "{tag}"')

    if tag in TAGS_ESTADO_NOVO:
        for anterior in TAGS_ESTADO_NOVO:
            if anterior != tag and tem_tag(registro, anterior):
                remover_tag(driver, registro, anterior)


def adicionar_tag_se_ausente(driver: webdriver.Remote, registro, tag: str) -> None:
    """Adiciona o marcador, a menos que o processo já o tenha (retomada)."""
    if tem_tag(registro, tag):
        logger.info(f'Retomada: o processo já tem o marcador "{tag}"')
        return
    adicionar_tag(driver, registro, tag)
