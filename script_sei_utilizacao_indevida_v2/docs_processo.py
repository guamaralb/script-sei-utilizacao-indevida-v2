"""Filtros e buscas na árvore de documentos do processo."""

import logging
import re

from constantes import UNIDADE_APIS, UNIDADE_GEACS
from sei_automacao.documento import obter_conteudo_doc
from sei_automacao.processo.arvore import listar_documentos_arvore, selecionar_doc_arvore
from selenium import webdriver

logger = logging.getLogger(__name__)

# Trechos que indicam que o memorando da APIS é destinado à GEACS. Tolera
# espaços/quebras de linha variáveis e maiúsculas/minúsculas.
TRECHOS_DESTINO_GEACS = (
    'Solicita-se à Gerência de Auditoria e Contas da Saúde - GEACS',
    'Para: Bruna Miller Lavarini',
    'Para: Bruna Miiller Lavarini',
)
_PADRAO_DESTINO_GEACS = re.compile(
    '|'.join(r'\s*'.join(re.escape(parte) for parte in trecho.split()) for trecho in TRECHOS_DESTINO_GEACS),
    re.IGNORECASE,
)


def _eh_memorando(doc: dict) -> bool:
    return 'Memorando' in doc['nome_arvore']


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def filtrar_docs_geacs(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in tds_docs if UNIDADE_GEACS in doc['unidade']]


def filtrar_memos_geacs(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in filtrar_docs_geacs(tds_docs) if _eh_memorando(doc)]


def filtrar_memos_apis(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in tds_docs if _eh_memorando(doc) and UNIDADE_APIS in doc['unidade']]


def eh_destinado_geacs(texto: str) -> bool:
    return _PADRAO_DESTINO_GEACS.search(texto) is not None


def obter_memos_apis_para_geacs(driver: webdriver.Remote, tds_docs: list[dict]) -> list[tuple[dict, str]]:
    """Lê todos os memorandos da APIS da árvore e devolve, na ordem da
    árvore, os destinados à GEACS (com o texto já lido)."""
    memos = filtrar_memos_apis(tds_docs)
    para_geacs = []
    for memo in memos:
        texto = ler_texto_doc(driver, memo)
        if eh_destinado_geacs(texto):
            para_geacs.append((memo, texto))
        else:
            logger.debug(f'Memorando da APIS não destinado à GEACS: {_descrever(memo)}')
    logger.info(f'{len(memos)} memorando(s) da APIS na árvore; destinado(s) à GEACS: {[_descrever(memo) for memo, _ in para_geacs] or "nenhum"}')
    return para_geacs


def ler_texto_doc(driver: webdriver.Remote, doc: dict) -> str:
    logger.debug(f'Lendo documento {_descrever(doc)}')
    selecionar_doc_arvore(driver, numero_sei=doc['numero_sei'])
    texto = obter_conteudo_doc(driver, formato='texto')
    logger.debug(f'Documento {doc["numero_sei"]} lido ({len(texto)} caracteres)')
    return texto


def encontrar_memo_geacs_por_assunto(driver: webdriver.Remote, tds_docs: list[dict], padrao: re.Pattern, descricao: str) -> dict | None:
    """O memo da GEACS mais recente cujo texto casa com o padrão do assunto."""
    memos_geacs = filtrar_memos_geacs(tds_docs)
    logger.debug(f'Procurando memo {descricao} em {len(memos_geacs)} memorando(s) da GEACS')
    for memo in reversed(memos_geacs):
        if padrao.search(ler_texto_doc(driver, memo)):
            logger.info(f'Memo {descricao} encontrado: {_descrever(memo)}')
            return memo

    logger.info(f'Memo {descricao} não encontrado na árvore')
    return None


def encontrar_doc_por_nome(tds_docs: list[dict], inicio_nome: str) -> dict | None:
    """O documento mais recente cujo nome na árvore começa com inicio_nome."""
    return next((doc for doc in reversed(tds_docs) if doc['nome_arvore'].startswith(inicio_nome)), None)


def memos_geacs_novos(driver: webdriver.Remote, tds_docs_antes: list[dict]) -> list[dict]:
    """Relê a árvore e devolve, na ordem da árvore, os memos da GEACS que
    não estavam em tds_docs_antes (memos criados na execução)."""
    antes = {doc['numero_sei'] for doc in tds_docs_antes}
    novos = [doc for doc in filtrar_memos_geacs(listar_documentos_arvore(driver)) if doc['numero_sei'] not in antes]
    logger.info(f'Memo(s) criado(s) na árvore: {[_descrever(doc) for doc in novos] or "nenhum"}')
    return novos
