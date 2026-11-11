"""Abertura do navegador, login e troca de unidade no SEI (usado por todos
os fluxos).

Credenciais no .env: SEI_LOGIN, SEI_SENHA e SEI_ORGAO.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sei_automacao import efetuar_login, iniciar_sei, trocar_unidade
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

logger = logging.getLogger(__name__)

URL_SEI = 'https://www.sei.mg.gov.br'

_SESSAO_ENCERRADA = (InvalidSessionIdException, NoSuchWindowException)


def sessao_encerrada(registro) -> bool:
    """O navegador foi fechado durante o processo: fica registrado como erro
    dele, mas o loop para, pois todos os seguintes falhariam."""
    return registro.tipo_erro in {erro.__name__ for erro in _SESSAO_ENCERRADA}


def restaurar_navegador(driver: webdriver.Remote) -> None:
    """Depois de um erro inesperado, a tela pode ficar presa (ex.: janela
    sobre a árvore) e derrubar os processos seguintes: recarrega a página."""
    try:
        driver.switch_to.default_content()
        driver.refresh()
    except Exception:
        logger.warning('Não foi possível recarregar a página depois do erro', exc_info=True)


def alterar_unidade_sei(driver: webdriver.Remote, unidade: str) -> None:
    """Troca a unidade em que o script trabalha no SEI (GEACS nos fluxos da
    GEACS; DEPROC no fluxo DEPROC), com trocar_unidade da sei_automacao."""
    logger.info(f'Trocando para a unidade {unidade}')
    trocar_unidade(driver, unidade)
    logger.info(f'Unidade do SEI: {unidade}')


def abrir_sei(unidade: str, download_dir: Path | None = None) -> webdriver.Remote:
    load_dotenv()
    logger.info('Iniciando navegador e login no SEI')
    opcoes = {'download_dir': download_dir} if download_dir else {}
    # iniciar_sei já abre a página do SEI (e fecha o navegador se falhar)
    driver = iniciar_sei(URL_SEI, driver_type='chrome', **opcoes)
    try:
        driver.maximize_window()
        efetuar_login(driver, os.getenv('SEI_LOGIN'), os.getenv('SEI_SENHA'), os.getenv('SEI_ORGAO'))
    except Exception:
        driver.quit()
        raise
    logger.info('Login no SEI efetuado')
    try:
        alterar_unidade_sei(driver, unidade)
    except Exception:
        driver.quit()
        raise
    return driver
