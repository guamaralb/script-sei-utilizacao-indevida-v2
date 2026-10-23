"""Memo à APIS-Utilização de matrículas não encontradas na base APIS
(listagem de todos os beneficiários).

Retomada: se o memo já estiver na árvore (encontrado pelo assunto) e o
processo não tiver o marcador, o memo não é recriado; quem chama só
adiciona o marcador.
"""

import logging

from constantes import (
    BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from memos_sei import incluir_memo
from rede_propria import ErroAvaliacao, NaoEncontradas
from selenium import webdriver

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import (
    PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
    MemoApisMatNaoEncontradas,
)

logger = logging.getLogger(__name__)


def incluir_memo_apis_mat_nao_encontradas(driver: webdriver.Remote, registro, base_apis: NaoEncontradas) -> None:
    if BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS is None:
        raise ErroAvaliacao('Bloco do memo à APIS de matrículas não encontradas não configurado (constantes.BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS)')

    memo = MemoApisMatNaoEncontradas(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        titular=base_apis.titular,
        dependentes=base_apis.dependentes,
        memo_apis=registro.memo_apis,
    )
    incluir_memo(
        driver,
        registro,
        memo,
        BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS,
        'memo_apis_mat_nao_encontradas',
        'à APIS de matrículas não encontradas',
        padrao_assunto=PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
    )
