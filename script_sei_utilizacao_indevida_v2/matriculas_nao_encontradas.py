"""Tratamento das matrículas não encontradas na base geral (listagem de
todos os beneficiários) e na base da rede própria (DISA).

Usado pelo fluxo normal dos NOVOS, pela rotina de correção e, no futuro,
pelo fluxo dos VELHOS (cada um com os seus marcadores).
"""

import logging

from rede_propria import MatriculasNaoEncontradas
from sei_automacao.processo import adicionar_marcador
from selenium import webdriver
from tags import registrar_tags

logger = logging.getLogger(__name__)


def _adicionar_marcador(driver: webdriver.Remote, registro, tag: str) -> None:
    adicionar_marcador(driver, tag)
    registrar_tags(registro, [tag])
    logger.info(f'Marcador adicionado: "{tag}"')


def marcar_matriculas_nao_encontradas(
    driver: webdriver.Remote,
    registro,
    erro: MatriculasNaoEncontradas,
    tag_base_geral: str,
    tag_base_rede: str,
) -> None:
    """Registra as matrículas e adiciona o marcador de cada base em que houve
    matrícula não encontrada. Quem chama deve levantar o erro de novo para
    parar o processamento."""
    if erro.base_geral:
        registro.titular_nao_encontrado_base_geral = erro.base_geral.titular
        registro.deps_nao_encontrados_base_geral = list(erro.base_geral.dependentes)
        logger.warning(f'Não encontrado(s) na base geral | {erro.base_geral.descrever()}')
        _adicionar_marcador(driver, registro, tag_base_geral)

    if erro.base_rede:
        registro.titular_nao_encontrado = erro.base_rede.titular
        registro.deps_nao_encontrados = list(erro.base_rede.dependentes)
        logger.warning(f'Não encontrado(s) na base da rede própria | {erro.base_rede.descrever()}')
        _adicionar_marcador(driver, registro, tag_base_rede)

    registro.prox_acao = 'Verificar matrícula(s) não encontrada(s)'
