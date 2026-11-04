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


def citar_documentos(docs: tuple[str, ...], singular: str, plural: str) -> str:
    """Relatórios citados pelo número SEI, com a preposição do trecho:
    citar_documentos(('1',), 'no', 'nos') -> 'no documento 1';
    citar_documentos(('1', '2'), 'no', 'nos') -> 'nos documentos 1 e 2'."""
    if len(docs) == 1:
        return f'{singular} documento {docs[0]}'
    return f'{plural} documentos {", ".join(docs[:-1])} e {docs[-1]}'
