"""Criação dos memos da GEACS no SEI (memo e bloco de assinatura) e
registro do número SEI deles na planilha de controle.

Usado pelo fluxo normal, pela rotina de correção e pelo memo à APIS de
matrículas não encontradas.
"""

import logging
import re

from docs_processo import encontrar_memo_geacs_por_assunto, memos_geacs_novos
from sei_automacao.classes.Memorando import Memorando
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import incluir_doc_sei_memo
from selenium import webdriver

logger = logging.getLogger(__name__)


def incluir_memo(
    driver: webdriver.Remote,
    registro,
    memo: Memorando,
    bloco: int,
    prefixo: str,
    descricao: str,
    padrao_assunto: re.Pattern | None = None,
) -> None:
    """Cria o memo, insere no bloco e preenche <prefixo>_criado e
    <prefixo>_inserido_bloco no registro.

    Com padrao_assunto, antes procura o memo entre os memos da GEACS na
    árvore. Se ele já existe (passagem anterior que falhou antes de
    adicionar o marcador), não é recriado: preenche <prefixo>_na_arvore e
    <prefixo>_sei, e quem chamou só adiciona o marcador."""
    if padrao_assunto is not None and registro.memos_geacs:
        existente = encontrar_memo_geacs_por_assunto(driver, registro.tds_docs, padrao_assunto, descricao)
        if existente is not None:
            setattr(registro, f'{prefixo}_na_arvore', True)
            setattr(registro, f'{prefixo}_sei', existente['numero_sei'])
            logger.warning(f'Retomada: memo {descricao} já está na árvore ({existente["numero_sei"]}); não será recriado, só recebe o marcador. Confira se está no bloco {bloco}')
            return

    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    setattr(registro, f'{prefixo}_criado', True)
    registro.memos_criados.append(prefixo)
    logger.info(f'Memo {descricao} criado')

    inserir_bloco_ass(driver, bloco)
    setattr(registro, f'{prefixo}_inserido_bloco', True)
    logger.info(f'Memo {descricao} inserido no bloco {bloco}')


def registrar_numeros_memos(driver: webdriver.Remote, registro) -> None:
    """Obtém o número SEI dos memos criados na passagem (os memos da GEACS
    que não estavam na árvore), na ordem de criação, e preenche
    <prefixo>_sei. É só informativo: uma falha aqui não interrompe o
    processo, que já está com os memos no bloco e com os marcadores."""
    if not registro.memos_criados:
        return
    try:
        novos = memos_geacs_novos(driver, registro.tds_docs)
    except Exception:
        logger.exception('Não foi possível obter o número SEI dos memos criados')
        return

    if len(novos) != len(registro.memos_criados):
        logger.warning(f'Número SEI dos memos não registrado: esperado(s) {len(registro.memos_criados)} memo(s) novo(s) na árvore, encontrado(s) {len(novos)}')
        return
    for prefixo, doc in zip(registro.memos_criados, novos, strict=True):
        setattr(registro, f'{prefixo}_sei', doc['numero_sei'])
