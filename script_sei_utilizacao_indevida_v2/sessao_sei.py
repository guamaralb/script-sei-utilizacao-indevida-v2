"""Abertura do navegador, login e troca de unidade no SEI (usado por todos
os fluxos).

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


def restaurar_navegador(driver: webdriver.Remote) -> None:
    """Depois de um erro inesperado, a tela pode ficar presa (ex.: janela
    sobre a árvore) e derrubar os processos seguintes: recarrega a página."""
    try:
        driver.switch_to.default_content()
        driver.refresh()
    except Exception:
        logger.warning('Não foi possível recarregar a página depois do erro', exc_info=True)


def alterar_unidade_sei(driver: webdriver.Remote, unidade: str) -> None:
    """Troca a unidade em que o script trabalha no SEI (GEACS nos fluxos
    normal, ADC PDF ANT AUT e PDF; DEPROC no fluxo DEPROC).

    TODO: implementar na sei_automacao (alterar_unidade_sei) e chamar aqui.
    Até lá, não faz nada: o usuário precisa entrar no SEI já na unidade
    certa."""
    logger.warning(f'TODO alterar_unidade_sei: troca de unidade ainda não implementada; confira se o SEI está na unidade {unidade}')


def abrir_sei(unidade: str, download_dir: Path | None = None) -> webdriver.Remote:
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
    try:
        alterar_unidade_sei(driver, unidade)
    except Exception:
        driver.quit()
        raise
    return driver
