"""Fluxo PDF: PDF das planilhas colocadas à mão em dados/fluxo_pdf/planilhas.

Para quando o download do ALT 1 não funciona. A planilha é a mesma da árvore:
o arquivo se chama <número do processo com _ no lugar da barra>-<nome na
árvore>.xlsx. O documento da árvore dá o número SEI, então o PDF, a retomada e
os marcadores são os do ALT 1 (planilhas_alt_1.py), e um PDF que ele já tenha
inserido não é duplicado.
"""

import logging
import unicodedata
from pathlib import Path

from constantes import DIR_FLUXO_PDF_PDF, DIR_FLUXO_PDF_PLANILHAS
from planilhas_alt_1 import deixar_aguardando_fluxo_normal, inserir_pdfs, tipo_da_planilha
from rede_propria import ErroAvaliacao
from Registro import ProxAcao
from selenium import webdriver

logger = logging.getLogger(__name__)

# Metadado que o Windows grava ao lado do arquivo baixado
_SUFIXO_ZONE_IDENTIFIER = ':Zone.Identifier'


def prefixo_do_processo(num_processo: str) -> str:
    return f'{num_processo.replace("/", "_")}-'


def arquivos_do_processo(num_processo: str) -> dict[str, Path]:
    """Arquivos do processo na pasta: nome na árvore -> caminho."""
    prefixo = prefixo_do_processo(num_processo)
    return {
        caminho.stem.removeprefix(prefixo): caminho
        for caminho in sorted(DIR_FLUXO_PDF_PLANILHAS.iterdir())
        if caminho.is_file() and caminho.name.startswith(prefixo) and not caminho.name.endswith(_SUFIXO_ZONE_IDENTIFIER)
    }


def _nome_comparavel(nome: str) -> str:
    """O nome do arquivo pode vir em outra forma Unicode (acento decomposto)
    ou com outras maiúsculas e espaços."""
    return ' '.join(unicodedata.normalize('NFC', nome).casefold().split())


def documento_da_arvore(nome: str, tds_docs: list[dict]) -> dict:
    """Só o nome inteiro: é ele que dá o número SEI no nome do PDF."""
    if tipo_da_planilha({'nome_arvore': nome}) is None:
        raise ErroAvaliacao(f'Arquivo "{nome}": o nome não é de planilha de utilização (Titular, Dependentes ou Anexo RELAÇÃO ATENDIMENTO)')

    encontrados = [doc for doc in tds_docs if _nome_comparavel(doc['nome_arvore']) == _nome_comparavel(nome)]
    if not encontrados:
        raise ErroAvaliacao(f'Arquivo "{nome}": documento não encontrado na árvore')
    if len(encontrados) > 1:
        numeros = ', '.join(doc['numero_sei'] for doc in encontrados)
        raise ErroAvaliacao(f'Arquivo "{nome}": mais de um documento na árvore com esse nome ({numeros}): tratar manualmente')
    return encontrados[0]


def inserir_pdfs_da_pasta(driver: webdriver.Remote, registro) -> None:
    arquivos = arquivos_do_processo(registro.num_processo)
    if not arquivos:
        logger.warning('Nenhuma planilha do processo na pasta')
        registro.prox_acao = ProxAcao.FLUXO_PDF_SEM_PLANILHAS
        return

    # Antes de inserir: um arquivo com problema para o processo sem PDF parcial
    arquivo_por_numero = {}
    planilhas = []
    for nome, caminho in arquivos.items():
        doc = documento_da_arvore(nome, registro.tds_docs)
        arquivo_por_numero[doc['numero_sei']] = caminho
        planilhas.append(doc)

    registro.planilhas_sei = list(arquivo_por_numero)
    logger.info(f'{len(planilhas)} planilha(s) na pasta: {[caminho.name for caminho in arquivos.values()]}')
    inserir_pdfs(driver, registro, planilhas, lambda doc: arquivo_por_numero[doc['numero_sei']], DIR_FLUXO_PDF_PDF)
    registro.prox_acao = ProxAcao.FLUXO_PDF_AGUARDA_FLUXO_NORMAL if deixar_aguardando_fluxo_normal(driver, registro) else ProxAcao.FLUXO_PDF_ESTADO_MANTIDO
