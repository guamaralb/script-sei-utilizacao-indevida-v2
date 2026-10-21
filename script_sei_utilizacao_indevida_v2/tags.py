"""Marcadores do SEI usados pelos scripts v2.

Módulo compartilhado entre main.py e main_add_memo_nao_usou_rede_propria.py,
para que um script não precise importar o outro.

Marcadores de estado: em cada ramo, o processo tem no máximo um. Ao
adicionar um marcador de estado, o estado anterior é removido (o SEI mostra
só onde o processo está). Os demais marcadores (ramo, informativos e os da
versão anterior do fluxo) se acumulam.
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

# Numeração: o primeiro número é o ramo (1 = NOVO, 2 = VELHO) e o número
# após o ponto é a ordem de inserção no ramo. Marcadores com o mesmo número
# são alternativos (o processo recebe um ou outro).
# O SEI limita o nome do marcador a 50 caracteres.

# NOVOS
TAG_PROCESSO_NOVO = 'Script v2 - 1 - Processo NOVO'
TAG_PERIODO_VAR_DEP = 'Script v2 - 1.1 - Período Variável p/ Dependentes'
TAG_AVALIADO_USO_REDE_PROPRIA = 'Script v2 - 1.2 - Avaliado Se Usou Rede Própria'
# Matrícula(s) não encontrada(s) na base geral (listagem de todos os
# beneficiários) e na base da rede própria (DISA)
TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO = 'Script v2 - 1.2.1 - Mat. N Encontradas Base Geral'
TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO = 'Script v2 - 1.2.2 - Mat. N Encontradas Base DISA'
# Versão anterior do fluxo normal (não são mais adicionados)
TAG_MEMOS_DISA_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memo DEPROC no Bloco'
# Rotina de correção: inserido antes do 1.2
TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO = 'Script v2 - 1.4 - Memo Não Usou Rede no Bloco'

# Fluxo normal (aba 3 do docs/fluxo.drawio): marcadores de estado. Os de
# memo indicam que o memo foi criado e inserido no bloco.
# Memo da APIS ausente ou em formato inválido (alternativos): processo parado
TAG_MEMO_APIS_SEM_MEMO = 'Script v2 - 1.5 - Memo APIS Sem Memo p/ GEACS'
TAG_MEMO_APIS_FORMATO_INVALIDO = 'Script v2 - 1.5 - Memo APIS Formato Inválido'
TAG_AVALIADO_USO_REDE_PROPRIA_DISA = 'Script v2 - 1.6 - Avaliado Uso Rede Própria DISA'
# Depois do 1.2.1 (matrícula não encontrada na base geral): processo parado
TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS = 'Script v2 - 1.6.1 - Memo APIS Mat. N Encontradas'
# Depois do 1.1 (período variável para dependentes): processo parado
TAG_MEMO_APIS_PERIODO_DEPENDENTES = 'Script v2 - 1.7 - Memo APIS Período Dependentes'
TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS = 'Script v2 - 1.8 - Avaliado Uso Rede Própria MANTIS'
# MANTIS com uso da rede própria que a base DISA não tem: processo parado
TAG_MEMO_DISA_VALIDAR_USOS_MANTIS = 'Script v2 - 1.8.1 - Memo DISA Validar Usos MANTIS'
TAG_MEMO_DISA_USO_REDE_PROPRIA = 'Script v2 - 1.9 - Memo DISA Uso Rede Própria'
# Conclusão do fluxo normal (alternativos)
# TODO: cadastrar no SEI o "Memos DISA e DEPROC no Bloco" antes de rodar
TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO = 'Script v2 - 1.10 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_COPARTICIPACAO = 'Script v2 - 1.10 - Memo DEPROC Coparticipação'

# VELHOS
TAG_PROCESSO_VELHO = 'Script v2 - 2 - Processo VELHO'
# Pendências indicadas pelas instruções da APIS
TAG_TRANSFORMAR_EXCEL_EM_PDF = 'Script v2 - 2.1 - Transformar Excel em PDF'
TAG_REFAZER_REL_UI = 'Script v2 - 2.1 - Refazer Relatório de UI'
# Matrícula(s) não encontrada(s): processamento parado (ver NOVOS)
TAG_MAT_NAO_ENCONTRADAS_GERAL_VELHO = 'Script v2 - 2.1.1 - Mat. N Encontradas Base Geral'
TAG_MAT_NAO_ENCONTRADAS_DISA_VELHO = 'Script v2 - 2.1.2 - Mat. N Encontradas Base DISA'
# Conclusão
TAG_REL_UI_TRANSFORMADO_PDF = 'Script v2 - 2.2 - Excel Transformado em PDF'
TAG_NOVO_REL_UI_GERADO = 'Script v2 - 2.2 - Relatório de UI Refeito'

# Marcadores manuais (não são colocados pelo script)
TAG_PLANILHADO = 'PLANILHADO'
TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'
TAG_MANUAL = 'MANUAL'
TAG_ASSINADO = 'ASSINADO'

# Processos tratados manualmente: fora do escopo do script de correção
TAGS_TRATAMENTO_MANUAL = frozenset({TAG_MANUAL, TAG_ASSINADO})

# Fluxo normal: memos da GEACS esperados na árvore em cada estado
MEMOS_POR_ESTADO_NOVO = {
    TAG_MEMO_APIS_SEM_MEMO: 1,
    TAG_MEMO_APIS_FORMATO_INVALIDO: 1,
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA: 0,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS: 1,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES: 1,
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS: 0,
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS: 1,
    TAG_MEMO_DISA_USO_REDE_PROPRIA: 1,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO: 2,
    TAG_MEMO_DEPROC_COPARTICIPACAO: 1,
}
TAGS_ESTADO_NOVO = tuple(MEMOS_POR_ESTADO_NOVO)
# Memo enviado: processo parado até a resposta do destinatário
TAGS_PARADA_NOVO = (
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS,
)
TAGS_CONCLUSAO_NOVO = (TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO, TAG_MEMO_DEPROC_COPARTICIPACAO)

TAGS_ESTADO_VELHO = (
    TAG_TRANSFORMAR_EXCEL_EM_PDF,
    TAG_REFAZER_REL_UI,
    TAG_REL_UI_TRANSFORMADO_PDF,
    TAG_NOVO_REL_UI_GERADO,
)

# Coluna da planilha de controle de cada marcador (indica se o processo
# terminou a passagem com o marcador)
_COLUNA_POR_TAG = {
    TAG_PROCESSO_NOVO: 'tag_processo_novo',
    TAG_PROCESSO_VELHO: 'tag_processo_velho',
    TAG_PLANILHADO: 'tag_planilhado',
    TAG_UI_INSERIDA: 'tag_ui_inserida',
    TAG_PERIODO_VAR_DEP: 'tag_periodo_variavel_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA: 'tag_avaliado_se_usou_rede_propria',
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO: 'tag_mat_nao_encontradas_base_geral_novo',
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO: 'tag_mat_nao_encontradas_novo',
    TAG_MAT_NAO_ENCONTRADAS_GERAL_VELHO: 'tag_mat_nao_encontradas_base_geral_velho',
    TAG_MAT_NAO_ENCONTRADAS_DISA_VELHO: 'tag_mat_nao_encontradas_velho',
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
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO: 'tag_memos_no_bloco',
    TAG_MEMO_DEPROC_NO_BLOCO: 'tag_memo_deproc_no_bloco',
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO: 'tag_memo_nao_usou_rede_propria_no_bloco',
    TAG_TRANSFORMAR_EXCEL_EM_PDF: 'tag_transformar_excel_em_pdf',
    TAG_REFAZER_REL_UI: 'tag_refazer_rel_ui',
    TAG_REL_UI_TRANSFORMADO_PDF: 'tag_rel_ui_transformado_pdf',
    TAG_NOVO_REL_UI_GERADO: 'tag_novo_rel_ui_gerado',
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


def estado_atual(registro, estados: tuple[str, ...]) -> str | None:
    """Marcador de estado do processo (ou None). Mais de um é inconsistente:
    a remoção do estado anterior falhou ou o processo é de antes da troca
    de estados."""
    presentes = [tag for tag in estados if tem_tag(registro, tag)]
    if len(presentes) > 1:
        raise ErroAvaliacao(f'Processo com mais de um marcador de estado: {presentes}. Remover manualmente o(s) anterior(es) no SEI')
    return presentes[0] if presentes else None


def _grupo_de_estados(tag: str) -> tuple[str, ...]:
    for estados in (TAGS_ESTADO_NOVO, TAGS_ESTADO_VELHO):
        if tag in estados:
            return estados
    return ()


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

    for anterior in _grupo_de_estados(tag):
        if anterior != tag and tem_tag(registro, anterior):
            remover_tag(driver, registro, anterior)


def adicionar_tag_se_ausente(driver: webdriver.Remote, registro, tag: str) -> None:
    """Adiciona o marcador, a menos que o processo já o tenha (retomada)."""
    if tem_tag(registro, tag):
        logger.info(f'Retomada: o processo já tem o marcador "{tag}"')
        return
    adicionar_tag(driver, registro, tag)
