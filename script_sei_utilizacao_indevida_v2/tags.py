"""Marcadores do SEI usados pelos scripts v2.

Módulo compartilhado entre main.py e main_add_memo_nao_usou_rede_propria.py,
para que um script não precise importar o outro.
"""

# Numeração: o primeiro número é o ramo (1 = NOVO, 2 = VELHO) e o número
# após o ponto é a ordem de inserção no ramo. Marcadores com o mesmo número
# são alternativos (o processo recebe um ou outro).
# O SEI limita o nome do marcador a 50 caracteres.

# NOVOS
TAG_PROCESSO_NOVO = 'Script v2 - 1 - Processo NOVO'
TAG_PERIODO_VAR_DEP = 'Script v2 - 1.1 - Período Variável p/ Dependentes'
TAG_AVALIADO_USO_REDE_PROPRIA = 'Script v2 - 1.2 - Avaliado Se Usou Rede Própria'
# Matrícula(s) não encontrada(s) na base da rede própria: processamento parado
TAG_MAT_NAO_ENCONTRADAS_NOVO = 'Script v2 - 1.2.1 - Mat. N Encontradas Base DISA'
TAG_MEMOS_DISA_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memos DISA e DEPROC no Bloco'
TAG_MEMO_DEPROC_NO_BLOCO = 'Script v2 - 1.3 - Memo DEPROC no Bloco'
# Rotina de correção: inserido antes do 1.2
TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO = 'Script v2 - 1.4 - Memo Não Usou Rede no Bloco'

# VELHOS
TAG_PROCESSO_VELHO = 'Script v2 - 2 - Processo VELHO'
# Pendências indicadas pelas instruções da APIS
TAG_TRANSFORMAR_EXCEL_EM_PDF = 'Script v2 - 2.1 - Transformar Excel em PDF'
TAG_REFAZER_REL_UI = 'Script v2 - 2.1 - Refazer Relatório de UI'
# Matrícula(s) não encontrada(s) na base da rede própria: processamento parado
TAG_MAT_NAO_ENCONTRADAS_VELHO = 'Script v2 - 2.1.1 - Mat. N Encontradas Base DISA'
# Conclusão
TAG_REL_UI_TRANSFORMADO_PDF = 'Script v2 - 2.2 - Excel Transformado em PDF'
TAG_NOVO_REL_UI_GERADO = 'Script v2 - 2.2 - Relatório de UI Refeito'

# Marcadores manuais (não são colocados pelo script)
TAG_PLANILHADO = 'PLANILHADO'
TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'

_ATRIBUTO_REGISTRO_POR_TAG = {
    TAG_PROCESSO_NOVO: 'tag_processo_novo',
    TAG_PROCESSO_VELHO: 'tag_processo_velho',
    TAG_PERIODO_VAR_DEP: 'tag_periodo_var_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA: 'tag_avaliado_se_usou_rede_propria',
    TAG_MAT_NAO_ENCONTRADAS_NOVO: 'tag_mat_nao_encontradas_novo',
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO: 'tag_memos_no_bloco',
    TAG_MEMO_DEPROC_NO_BLOCO: 'tag_memo_deproc_no_bloco',
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO: ('tag_memo_nao_usou_rede_propria_no_bloco'),
    TAG_TRANSFORMAR_EXCEL_EM_PDF: 'tag_transformar_excel_em_pdf',
    TAG_REFAZER_REL_UI: 'tag_refazer_rel_ui',
    TAG_MAT_NAO_ENCONTRADAS_VELHO: 'tag_mat_nao_encontradas_velho',
    TAG_REL_UI_TRANSFORMADO_PDF: 'tag_rel_ui_transformado_pdf',
    TAG_NOVO_REL_UI_GERADO: 'tag_novo_rel_ui_gerado',
    TAG_PLANILHADO: 'tag_planilhado',
    TAG_UI_INSERIDA: 'tag_ui_inserida',
}

TAGS_SCRIPT = frozenset(tag for tag in _ATRIBUTO_REGISTRO_POR_TAG if tag.startswith('Script v2'))


def normalizar_tags(tags: list) -> list[str]:
    return [str(tag).strip() for tag in tags]


def registrar_tags(registro, tags: list[str]) -> None:
    """Marca no registro os atributos correspondentes às tags do processo.

    Tags sem atributo equivalente no registro são ignoradas.
    """
    for tag in normalizar_tags(tags):
        atributo = _ATRIBUTO_REGISTRO_POR_TAG.get(tag)
        if atributo and hasattr(registro, atributo):
            setattr(registro, atributo, True)
