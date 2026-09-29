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
from sei_automacao.core.buttons import clicar_adicionar_btnAdicionar
from sei_automacao.core.iframes import trocar_iframe
from sei_automacao.processo.marcadores import (
    clicar_gerenciar_marcadores,
    procurar_sbmSalvar,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

_marcadores_da_unidade: set[str] | None = None


def _normalizar(texto: str) -> str:
    # Equivalente ao normalize-space() usado pela biblioteca ao selecionar
    return ' '.join(texto.split())


def _ler_marcadores_da_unidade(driver: webdriver.Remote) -> set[str]:
    driver.refresh()
    driver.switch_to.default_content()
    trocar_iframe(driver, 'ifrConteudoVisualizacao')
    clicar_gerenciar_marcadores(driver)
    trocar_iframe(driver, 'ifrVisualizacao')
    if not procurar_sbmSalvar(driver):
        clicar_adicionar_btnAdicionar(driver)

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#selMarcador')))
    opcoes = driver.find_elements(By.CSS_SELECTOR, '#selMarcador label.dd-option-text')
    nomes = {_normalizar(o.get_attribute('textContent') or '') for o in opcoes} - {''}

    # Sai da tela sem salvar
    driver.refresh()
    driver.switch_to.default_content()

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
