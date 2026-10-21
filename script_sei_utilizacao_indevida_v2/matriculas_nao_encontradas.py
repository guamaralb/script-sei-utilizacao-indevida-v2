"""Tratamento das matrículas não encontradas na base geral (listagem de
todos os beneficiários) e na base da rede própria (DISA).

Usado pelo fluxo normal dos NOVOS, pela rotina de correção e, no futuro,
pelo fluxo dos VELHOS (cada um com os seus marcadores).

Base geral: cria o memo à APIS-Utilização e o insere no bloco; o marcador
da base geral (1.2.1/2.1.1) só é adicionado depois disso, e também indica
que o memo está no bloco.

Retomada: se o memo já estiver na árvore (encontrado pelo assunto) e o
processo não tiver o marcador, o memo não é recriado; só os marcadores são
adicionados.
"""

import logging

from constantes import (
    BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from marcadores_disponiveis import garantir_marcadores_no_sei
from memos_sei import incluir_memo, registrar_numeros_memos
from rede_propria import ErroAvaliacao, MatriculasNaoEncontradas, NaoEncontradas
from Registro import ProxAcao
from selenium import webdriver
from tags import adicionar_tag

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import (
    PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
    MemoApisMatNaoEncontradas,
)

logger = logging.getLogger(__name__)


def incluir_memo_apis_mat_nao_encontradas(driver: webdriver.Remote, registro, base_geral: NaoEncontradas) -> None:
    if BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS is None:
        raise ErroAvaliacao('Bloco do memo à APIS de matrículas não encontradas não configurado (constantes.BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS)')

    memo = MemoApisMatNaoEncontradas(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        titular=base_geral.titular,
        dependentes=base_geral.dependentes,
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


def marcar_matriculas_nao_encontradas(
    driver: webdriver.Remote,
    registro,
    erro: MatriculasNaoEncontradas,
    tag_base_geral: str,
    tag_base_rede: str,
) -> None:
    """Registra as matrículas, cria o memo à APIS (base geral) e adiciona o
    marcador de cada base em que houve matrícula não encontrada. Quem chama
    deve levantar o erro de novo para parar o processamento."""
    if erro.base_geral:
        registro.titular_nao_encontrado_base_geral = erro.base_geral.titular
        registro.deps_nao_encontrados_base_geral = list(erro.base_geral.dependentes)
        logger.warning(f'Não encontrado(s) na base geral | {erro.base_geral.descrever()}')
    if erro.base_rede:
        registro.titular_nao_encontrado = erro.base_rede.titular
        registro.deps_nao_encontrados = list(erro.base_rede.dependentes)
        logger.warning(f'Não encontrado(s) na base da rede própria | {erro.base_rede.descrever()}')
    registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS

    tags = ([tag_base_geral] if erro.base_geral else []) + ([tag_base_rede] if erro.base_rede else [])
    garantir_marcadores_no_sei(driver, tags)

    if erro.base_geral:
        incluir_memo_apis_mat_nao_encontradas(driver, registro, erro.base_geral)
        adicionar_tag(driver, registro, tag_base_geral)
        registro.prox_acao = ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS

    if erro.base_rede:
        adicionar_tag(driver, registro, tag_base_rede)

    registrar_numeros_memos(driver, registro)
