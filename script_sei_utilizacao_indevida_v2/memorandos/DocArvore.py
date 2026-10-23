import re
from typing import TypedDict


class DocArvore(TypedDict):
    """Documento da árvore do processo, como vem de listar_documentos_arvore."""

    numero_sei: str
    nome_arvore: str
    unidade: str


def identificar_doc(doc: DocArvore) -> str:
    """Identificação do documento no texto dos memos, com o que a árvore
    traz (sem o ano): 'Memorando 2627' da 'IPSEMG/APIS-Utilização' ->
    'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)'."""
    tipo_numero = re.fullmatch(r'(.+?)\s+(\d+)', doc['nome_arvore'].strip())
    if tipo_numero is None:
        return f'{doc["nome_arvore"]} {doc["unidade"].upper()} ({doc["numero_sei"]})'
    tipo, numero = tipo_numero.groups()
    return f'{tipo} {doc["unidade"].upper()} nº {numero} ({doc["numero_sei"]})'
