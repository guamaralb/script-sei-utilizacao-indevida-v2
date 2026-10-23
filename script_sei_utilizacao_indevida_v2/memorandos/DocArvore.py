from typing import TypedDict


class DocArvore(TypedDict):
    """Documento da árvore do processo, como vem de listar_documentos_arvore."""

    numero_sei: str
    nome_arvore: str
    unidade: str
