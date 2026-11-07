"""Abertura do navegador e login no SEI (usado pelos dois scripts).

Credenciais no .env: SEI_LOGIN, SEI_SENHA e SEI_ORGAO.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sei_automacao.auth.login import efetuar_login
from sei_automacao.driver import iniciar_driver
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

logger = logging.getLogger(__name__)

_SESSAO_ENCERRADA = (InvalidSessionIdException, NoSuchWindowException)


def sessao_encerrada(registro) -> bool:
    """O navegador foi fechado durante o processo: fica registrado como erro
    dele, mas o loop para, pois todos os seguintes falhariam."""
    return registro.tipo_erro in {erro.__name__ for erro in _SESSAO_ENCERRADA}


def abrir_sei(download_dir: Path | None = None) -> webdriver.Remote:
    load_dotenv()
    logger.info('Iniciando navegador e login no SEI')
    opcoes = {'download_dir': download_dir} if download_dir else {}
    driver = iniciar_driver(driver_type='chrome', **opcoes)
    try:
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')
        efetuar_login(driver, os.getenv('SEI_LOGIN'), os.getenv('SEI_SENHA'), os.getenv('SEI_ORGAO'))
    except Exception:
        driver.quit()
        raise
    logger.info('Login no SEI efetuado')
    return driver
