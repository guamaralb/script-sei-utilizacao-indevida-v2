"""Processo fechado no setor: sem o botão "Incluir Documento" na tela do
processo. É ele que indica se a unidade pode agir no processo (concluído ou
enviado sem manter aberto, por exemplo)."""

from rede_propria import ErroAvaliacao
from sei_automacao.core.iframes import trocar_iframe
from sei_automacao.utils.encontrar_elemento import encontrar_elemento
from selenium import webdriver

_TIMEOUT_TELA_PROCESSO = 15
_XPATH_INCLUIR_DOCUMENTO = "//img[@alt='Incluir Documento']"


class ProcessoFechadoNoSetor(ErroAvaliacao):
    pass


def tem_incluir_documento(driver: webdriver.Remote) -> bool:
    driver.switch_to.default_content()
    trocar_iframe(driver, 'ifrConteudoVisualizacao', timeout=_TIMEOUT_TELA_PROCESSO)
    encontrado = encontrar_elemento(driver, 'XPATH', _XPATH_INCLUIR_DOCUMENTO, timeout=_TIMEOUT_TELA_PROCESSO) is not None
    driver.switch_to.default_content()
    return encontrado


def exigir_processo_aberto(driver: webdriver.Remote) -> None:
    """Chamada logo depois de abrir o processo, antes de ler a árvore: abrir as
    pastas pode trocar a tela, e o botão sumiria sem o processo estar fechado.

    TODO: definir o que fazer com o processo fechado no setor (reabrir, como no
    ALT 1, ou tratar manualmente). Hoje ele só fica registrado como erro."""
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo fechado no setor: sem o botão Incluir Documento')
