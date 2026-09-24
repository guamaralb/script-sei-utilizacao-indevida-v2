"""Marcadores do SEI usados pelos scripts v2.

Módulo compartilhado entre main.py e main_add_memo_nao_usou_rede_propria.py,
para que um script não precise importar o outro.
"""

TAG_PROCESSO_NOVO = 'Script v2 - Processo NOVO'
TAG_PROCESSO_VELHO = 'Script v2 - Processo VELHO'
TAG_PERIODO_VAR_DEP = 'Script v2 - Período Variável Para Dependentes'

TAG_AVALIADO_USO_REDE_PROPRIA = 'Script v2 - Avaliado Se Usou Rede Própria'
TAG_MEMOS_DISA_DEPROC_NO_BLOCO = 'Script v2 - Memos DISA e DEPROC no bloco'
TAG_MEMO_DEPROC_NO_BLOCO = 'Script v2 - Memo DEPROC no bloco'
TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO = 'Script v2 - Memo Não Usou Rede Propria No Bloco'

TAG_REL_UI_TRANSFORMADO_PDF = 'Script v2 - Rel. de UI Velho Transformado em PDF'
TAG_NOVO_REL_UI_GERADO = 'Script v2 - Novo Rel. de UI Gerado'

# Marcadores manuais (não são colocados pelo script)
TAG_PLANILHADO = 'PLANILHADO'
TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'

_ATRIBUTO_REGISTRO_POR_TAG = {
    TAG_PROCESSO_NOVO: 'tag_processo_novo',
    TAG_PROCESSO_VELHO: 'tag_processo_velho',
    TAG_PERIODO_VAR_DEP: 'tag_periodo_var_deps',
    TAG_AVALIADO_USO_REDE_PROPRIA: 'tag_avaliado_se_usou_rede_propria',
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO: 'tag_memos_no_bloco',
    TAG_MEMO_DEPROC_NO_BLOCO: 'tag_memo_deproc_no_bloco',
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO: ('tag_memo_nao_usou_rede_propria_no_bloco'),
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
