"""Processo fechado no setor: sem o botão "Incluir Documento" na tela do
processo. É ele que indica se a unidade pode agir no processo (concluído ou
enviado sem manter aberto, por exemplo). Quando precisa receber documentos,
o processo é reaberto na unidade (`reabrir_processo` da sei_automacao) e
continua aberto depois. Quem decide reabrir é o fluxo (main_geacs._tratar no fluxo
normal; planilhas_adc_pdf_ant_aut no ADC PDF ANT AUT)."""

import logging
import time

from rede_propria import ErroAvaliacao
from sei_automacao.core.iframes import trocar_iframe
from sei_automacao.processo import reabrir_processo
from sei_automacao.utils.encontrar_elemento import encontrar_elemento
from selenium import webdriver

logger = logging.getLogger(__name__)

_TIMEOUT_TELA_PROCESSO = 15
_XPATH_INCLUIR_DOCUMENTO = "//img[@alt='Incluir Documento']"
# Espera depois de reabrir, antes de recarregar a tela do processo
_ESPERA_REABERTURA = 5


class ProcessoFechadoNoSetor(ErroAvaliacao):
    pass


def tem_incluir_documento(driver: webdriver.Remote) -> bool:
    driver.switch_to.default_content()
    trocar_iframe(driver, 'ifrConteudoVisualizacao', timeout=_TIMEOUT_TELA_PROCESSO)
    encontrado = encontrar_elemento(driver, 'XPATH', _XPATH_INCLUIR_DOCUMENTO, timeout=_TIMEOUT_TELA_PROCESSO) is not None
    driver.switch_to.default_content()
    return encontrado


def reabrir_processo_fechado(driver: webdriver.Remote, registro) -> None:
    """Reabre o processo na unidade e confere o "Incluir Documento". Sem como
    reabrir, ou ainda sem o botão depois: `ProcessoFechadoNoSetor`."""
    logger.warning('Processo sem "Incluir Documento": reabrindo')
    try:
        reabrir_processo(driver)
    except ValueError as e:
        raise ProcessoFechadoNoSetor(f'Processo sem "Incluir Documento" e não foi possível reabrir: {e}') from e

    time.sleep(_ESPERA_REABERTURA)
    driver.refresh()
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" depois de reabrir')
    registro.processo_reaberto = True
    logger.info('Processo reaberto na unidade')
