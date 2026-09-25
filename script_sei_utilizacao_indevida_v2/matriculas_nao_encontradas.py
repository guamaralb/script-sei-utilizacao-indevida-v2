"""Tratamento das matrículas não encontradas na base da rede própria.

Usado pelo fluxo normal dos NOVOS, pela rotina de correção e, no futuro,
pelo fluxo dos VELHOS (cada um com o seu marcador).
"""

import logging

from rede_propria import MatriculasNaoEncontradas
from sei_automacao.processo import adicionar_marcador
from selenium import webdriver
from tags import registrar_tags

logger = logging.getLogger(__name__)


def marcar_matriculas_nao_encontradas(
    driver: webdriver.Remote,
    registro,
    erro: MatriculasNaoEncontradas,
    tag: str,
) -> None:
    """Registra as matrículas e adiciona o marcador. Quem chama deve
    levantar o erro de novo para parar o processamento."""
    registro.matriculas_nao_encontradas = list(erro.matriculas)
    logger.warning(f'Matrícula(s) não encontrada(s) na base da rede própria: {erro.matriculas}')

    adicionar_marcador(driver, tag)
    registrar_tags(registro, [tag])
    logger.info(f'Marcador adicionado: "{tag}"')
    registro.prox_acao = 'Verificar matrícula(s) não encontrada(s) na base da rede própria'
