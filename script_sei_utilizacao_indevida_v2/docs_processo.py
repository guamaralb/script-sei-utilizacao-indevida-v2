"""Filtros e buscas na árvore de documentos do processo."""

import logging
import re
from datetime import date

from constantes import DATA_CORTE_PROCESSO_VELHO, UNIDADE_APIS, UNIDADE_GEACS
from rede_propria import ErroAvaliacao
from sei_automacao.documento import obter_conteudo_doc
from sei_automacao.processo.arvore import listar_documentos_arvore, selecionar_doc_arvore
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)

# Trechos que indicam que o memorando da APIS é destinado à GEACS. Tolera
# espaços/quebras de linha variáveis e maiúsculas/minúsculas.
TRECHOS_DESTINO_GEACS = (
    'Solicita-se à Gerência de Auditoria e Contas da Saúde - GEACS',
    'Para: Bruna Miller Lavarini',
    'Para: Bruna Miiller Lavarini',
)


def _regex_trecho(trecho: str) -> str:
    return r'\s*'.join(re.escape(parte) for parte in trecho.split())


_PADRAO_DESTINO_GEACS = re.compile('|'.join(_regex_trecho(trecho) for trecho in TRECHOS_DESTINO_GEACS), re.IGNORECASE)

# Processo VELHO: memo da GEACS à DISA seguido de memo à DEPROC, os dois
# datados antes de DATA_CORTE_PROCESSO_VELHO
_PADRAO_PARA_DISA = re.compile(_regex_trecho('Para: IPSEMG/DISA-UTI-INDEV'), re.IGNORECASE)
_PADRAO_PARA_DEPROC = re.compile(_regex_trecho('Para: IPSEMG/DEPROC') + r'\b', re.IGNORECASE)
# "Belo Horizonte, 18 de setembro de 2026."
_PADRAO_DATA_MEMO = re.compile(r'Belo\s+Horizonte\s*,\s*(\d{1,2})\s*[º°]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})', re.IGNORECASE)
_MESES = {
    nome: numero
    for numero, nome in enumerate(
        ('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'),
        start=1,
    )
}


def _eh_memorando(doc: dict) -> bool:
    return 'Memorando' in doc['nome_arvore']


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def filtrar_docs_geacs(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in tds_docs if UNIDADE_GEACS in doc['unidade']]


def filtrar_memos_geacs(tds_docs: list[dict]) -> list[dict]:
    return filtrar_memos_unidade(tds_docs, UNIDADE_GEACS)


def filtrar_memos_unidade(tds_docs: list[dict], unidade: str) -> list[dict]:
    return [doc for doc in tds_docs if _eh_memorando(doc) and unidade in doc['unidade']]


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


def _doc_nao_encontrado(erro: Exception) -> bool:
    """selecionar_doc_arvore levanta Exception("Documento não encontrado")
    (a mensagem vem com o acento trocado)."""
    return type(erro) is Exception and 'encontrado' in str(erro)


def _rolar_ate_doc(driver: webdriver.Remote, numero_sei: str) -> None:
    """Centraliza o documento no frame da árvore: no fim da árvore, o clique
    caía em outro elemento."""
    driver.switch_to.default_content()
    driver.switch_to.frame('ifrArvore')
    try:
        elemento = driver.find_element(By.XPATH, f'//a[span[contains(text(), "{numero_sei}")]]')
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    except NoSuchElementException:
        pass
    finally:
        driver.switch_to.default_content()


def selecionar_doc(driver: webdriver.Remote, doc: dict) -> None:
    """Depois de adicionar um marcador ou reabrir o processo, as pastas da
    árvore fecham e o documento some; no fim da árvore, o clique pode ser
    interceptado. Nos dois casos, relê a árvore (reabre as pastas), centraliza
    o documento e tenta mais uma vez."""
    try:
        selecionar_doc_arvore(driver, numero_sei=doc['numero_sei'])
    except Exception as e:
        if not (isinstance(e, ElementClickInterceptedException) or _doc_nao_encontrado(e)):
            raise
        logger.warning(f'Documento {_descrever(doc)} não selecionado na árvore ({type(e).__name__}): relendo a árvore e tentando de novo')
        listar_documentos_arvore(driver)
        _rolar_ate_doc(driver, doc['numero_sei'])
        selecionar_doc_arvore(driver, numero_sei=doc['numero_sei'])


def ler_texto_doc(driver: webdriver.Remote, doc: dict) -> str:
    logger.debug(f'Lendo documento {_descrever(doc)}')
    selecionar_doc(driver, doc)
    texto = obter_conteudo_doc(driver, formato='texto')
    logger.debug(f'Documento {doc["numero_sei"]} lido ({len(texto)} caracteres)')
    return texto


def encontrar_memo_por_assunto(driver: webdriver.Remote, tds_docs: list[dict], padrao: re.Pattern, descricao: str, unidade: str) -> tuple[dict, str] | None:
    """O memo mais recente da unidade cujo texto casa com o padrão do
    assunto, com o texto lido."""
    memos = filtrar_memos_unidade(tds_docs, unidade)
    logger.debug(f'Procurando memo {descricao} em {len(memos)} memorando(s) da unidade {unidade}')
    for memo in reversed(memos):
        texto = ler_texto_doc(driver, memo)
        if padrao.search(texto):
            logger.info(f'Memo {descricao} encontrado: {_descrever(memo)}')
            return memo, texto

    logger.info(f'Memo {descricao} não encontrado na árvore')
    return None


def encontrar_doc_por_nome(tds_docs: list[dict], inicio_nome: str) -> dict | None:
    """O documento mais recente cujo nome na árvore começa com inicio_nome."""
    return next((doc for doc in reversed(tds_docs) if doc['nome_arvore'].startswith(inicio_nome)), None)


def numero_sei_por_nome(driver: webdriver.Remote, nome: str) -> str | None:
    """Número SEI do documento mais recente com esse início de nome, relendo
    a árvore (ex.: documento que acabou de ser incluído)."""
    doc = encontrar_doc_por_nome(listar_documentos_arvore(driver), nome)
    return doc['numero_sei'] if doc is not None else None


def memos_geacs_novos(driver: webdriver.Remote, tds_docs_antes: list[dict], unidade: str = UNIDADE_GEACS) -> list[dict]:
    """Relê a árvore e devolve, na ordem da árvore, os memos da unidade
    (GEACS, por padrão) que não estavam em tds_docs_antes (memos criados na
    execução)."""
    antes = {doc['numero_sei'] for doc in tds_docs_antes}
    novos = [doc for doc in filtrar_memos_unidade(listar_documentos_arvore(driver), unidade) if doc['numero_sei'] not in antes]
    logger.info(f'Memo(s) criado(s) na árvore: {[_descrever(doc) for doc in novos] or "nenhum"}')
    return novos


def data_memo(texto: str) -> date | None:
    """Data do memo ("Belo Horizonte, 18 de setembro de 2026.") ou None."""
    achado = _PADRAO_DATA_MEMO.search(texto)
    if achado is None:
        return None
    dia, mes, ano = achado.groups()
    numero_mes = _MESES.get(mes.casefold())
    if numero_mes is None:
        return None
    try:
        return date(int(ano), numero_mes, int(dia))
    except ValueError:
        return None


def _destino_memo(texto: str) -> str | None:
    if _PADRAO_PARA_DISA.search(texto):
        return 'DISA'
    if _PADRAO_PARA_DEPROC.search(texto):
        return 'DEPROC'
    return None


def encontrar_memos_velho(driver: webdriver.Remote, tds_docs: list[dict]) -> tuple[dict, dict] | None:
    """Lê todos os memorandos da GEACS da árvore e devolve o primeiro par de
    memos seguidos (entre os memorandos da GEACS) à DISA e à DEPROC, nessa
    ordem, os dois datados antes de DATA_CORTE_PROCESSO_VELHO. Sem par, None.

    Levanta ErroAvaliacao se um par não tiver a data legível: sem ela não
    dá para saber se o processo é VELHO."""
    anterior: tuple[dict, str, str | None] | None = None
    for memo in filtrar_memos_geacs(tds_docs):
        texto = ler_texto_doc(driver, memo)
        destino = _destino_memo(texto)
        if destino == 'DEPROC' and anterior is not None and anterior[2] == 'DISA':
            datas = (data_memo(anterior[1]), data_memo(texto))
            if None in datas:
                raise ErroAvaliacao(
                    f'Memos à DISA e à DEPROC seguidos ({anterior[0]["numero_sei"]} e {memo["numero_sei"]}) sem a data no formato '
                    '"Belo Horizonte, <dia> de <mês> de <ano>": não foi possível conferir se o processo é VELHO'
                )
            if all(d < DATA_CORTE_PROCESSO_VELHO for d in datas):
                logger.info(f'Memos à DISA e à DEPROC anteriores a {DATA_CORTE_PROCESSO_VELHO:%d/%m/%Y}: {_descrever(anterior[0])} e {_descrever(memo)}')
                return anterior[0], memo
        anterior = (memo, texto, destino)
    return None
