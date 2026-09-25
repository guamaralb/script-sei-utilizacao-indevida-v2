"""Filtros e buscas na árvore de documentos do processo."""

import logging

from constantes import UNIDADE_APIS, UNIDADE_GEACS
from sei_automacao.documento import obter_conteudo_doc
from sei_automacao.processo.arvore import listar_documentos_arvore, selecionar_doc_arvore
from selenium import webdriver

from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    PADRAO_ASSUNTO_MEMO_USO_REDE,
)

logger = logging.getLogger(__name__)


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


def obter_ultimo_memo_apis(tds_docs: list[dict]) -> dict | None:
    memos = filtrar_memos_apis(tds_docs)
    if not memos:
        logger.debug('Nenhum memorando da APIS na árvore')
        return None
    logger.info(f'{len(memos)} memorando(s) da APIS na árvore; usando o último: {_descrever(memos[-1])}')
    return memos[-1]


def obter_memos_apis_apos_email(tds_docs: list[dict]) -> list[dict] | None:
    """Memorandos da APIS posteriores ao e-mail da APIS.

    Retorna None se o e-mail de referência não existir na árvore.
    """
    indice_email = next(
        (i for i, doc in enumerate(tds_docs) if 'E-mail' in doc['nome_arvore'] and UNIDADE_APIS in doc['unidade']),
        None,
    )
    if indice_email is None:
        logger.debug('E-mail de referência da APIS não encontrado na árvore')
        return None

    memos = filtrar_memos_apis(tds_docs[indice_email + 1 :])
    logger.info(f'E-mail da APIS encontrado: {_descrever(tds_docs[indice_email])} | {len(memos)} memorando(s) da APIS depois dele')
    return memos


def ler_texto_doc(driver: webdriver.Remote, doc: dict) -> str:
    logger.debug(f'Lendo documento {_descrever(doc)}')
    selecionar_doc_arvore(driver, numero_sei=doc['numero_sei'])
    texto = obter_conteudo_doc(driver, formato='texto')
    logger.debug(f'Documento {doc["numero_sei"]} lido ({len(texto)} caracteres)')
    return texto


def encontrar_memo_uso_rede(driver: webdriver.Remote, tds_docs: list[dict]) -> dict | None:
    """Procura, pelo assunto, o memo que informa o uso da rede própria
    (memo do fluxo de correção)."""
    memos_geacs = filtrar_memos_geacs(tds_docs)
    logger.debug(f'Procurando memo de uso da rede própria em {len(memos_geacs)} memorando(s) da GEACS')
    for memo in reversed(memos_geacs):
        if PADRAO_ASSUNTO_MEMO_USO_REDE.search(ler_texto_doc(driver, memo)):
            logger.info(f'Memo de uso da rede própria encontrado: {_descrever(memo)}')
            return memo

    logger.info('Memo de uso da rede própria não encontrado na árvore')
    return None


def memos_geacs_novos(driver: webdriver.Remote, tds_docs_antes: list[dict]) -> list[dict]:
    """Relê a árvore e devolve, na ordem da árvore, os memos da GEACS que
    não estavam em tds_docs_antes (memos criados na execução)."""
    antes = {doc['numero_sei'] for doc in tds_docs_antes}
    novos = [doc for doc in filtrar_memos_geacs(listar_documentos_arvore(driver)) if doc['numero_sei'] not in antes]
    logger.info(f'Memo(s) criado(s) na árvore: {[_descrever(doc) for doc in novos] or "nenhum"}')
    return novos
