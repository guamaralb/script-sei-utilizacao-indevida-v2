"""Confere se os marcadores existem no SEI antes de criar memos.

O marcador de conclusão só é adicionado depois que o memo está no bloco.
Se o nome do marcador não existir no SEI, o memo fica no bloco sem
marcador. Por isso, antes de criar memos, confere-se se os marcadores que
serão usados estão cadastrados na unidade.

A lista é lida na tela "Gerenciar Marcador" do processo aberto (sem
salvar nada) uma vez por execução e guardada em memória.
"""

import logging

from rede_propria import ErroAvaliacao
from sei_automacao.processo import listar_marcadores_disponiveis
from selenium import webdriver

logger = logging.getLogger(__name__)

_marcadores_da_unidade: set[str] | None = None


def _ler_marcadores_da_unidade(driver: webdriver.Remote) -> set[str]:
    nomes = listar_marcadores_disponiveis(driver)
    logger.info(f'Marcadores cadastrados na unidade: {len(nomes)}')
    return nomes


def garantir_marcadores_no_sei(driver: webdriver.Remote, tags: list[str]) -> None:
    """Levanta ErroAvaliacao se algum marcador não estiver cadastrado no SEI.

    Chame antes de criar memos. Se faltar algum marcador na lista em
    memória, a lista é relida uma vez (pode ter sido cadastrado durante a
    execução).
    """
    global _marcadores_da_unidade  # noqa: PLW0603

    if _marcadores_da_unidade is None or any(t not in _marcadores_da_unidade for t in tags):
        _marcadores_da_unidade = _ler_marcadores_da_unidade(driver)

    faltando = [t for t in tags if t not in _marcadores_da_unidade]
    if faltando:
        raise ErroAvaliacao(f'Marcador(es) não cadastrado(s) no SEI (nenhum memo foi criado): {faltando}')
