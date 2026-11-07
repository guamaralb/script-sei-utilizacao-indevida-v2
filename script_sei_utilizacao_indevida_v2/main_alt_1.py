"""Fluxo alternativo ALT 1 (task run_alt_1): insere nos processos o PDF das
planilhas de utilização e os deixa aguardando o fluxo normal (main.py). Ver
planilhas_alt_1.py. O loop (executar) também é usado pelo fluxo PDF."""

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
from constantes import DIR_ALT_1_PDF, DIR_ALT_1_PLANILHAS, DIR_CONTROLE, DIR_INPUTS, DIR_LOG
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from marcadores_disponiveis import garantir_marcadores_no_sei
from planilha_controle import PlanilhaControleGeral
from planilhas_alt_1 import inserir_pdfs_das_planilhas
from rede_propria import ErroAvaliacao
from Registro import RegistroAlt1, registrar_erro
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei, sessao_encerrada
from tags import TAG_AGUARDA_FLUXO_NORMAL, TAG_PROCESSO_NOVO, registrar_tags

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'alt_1'
FLUXO = 'ALT 1 - SOMENTE INSERIR PDF'

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_alt_1.log'

logger = logging.getLogger(__name__)


def _processar_linha(
    driver: webdriver.Remote,
    num_processo,
    fluxo: str = FLUXO,
    data_execucao: str = AGORA,
    inserir: Callable[[webdriver.Remote, RegistroAlt1], None] = inserir_pdfs_das_planilhas,
) -> RegistroAlt1:
    registro = RegistroAlt1(num_processo=num_processo, data_execucao=data_execucao, fluxo=fluxo)

    try:
        acessar_processo(driver, num_processo)
        registrar_tags(registro, listar_marcadores(driver))
        # Antes de listar a árvore: a conferência recarrega a página e fecha
        # as pastas. Sem os marcadores cadastrados, nenhum PDF é inserido
        garantir_marcadores_no_sei(driver, [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL])
        registro.registrar_arvore(listar_documentos_arvore(driver))
        logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')

        inserir(driver, registro)

    except ErroAvaliacao as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def executar(
    script: str,
    fluxo: str,
    data_execucao: str,
    arq_log: Path,
    diretorios: list[Path],
    inserir: Callable[[webdriver.Remote, RegistroAlt1], None],
    download_dir: Path | None = None,
) -> None:
    """Loop dos processos da aba fluxo, com o registro na planilha de controle."""
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG, *diretorios]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(arq_log)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({fluxo}) =================')
        logger.info(f'Log: {arq_log}')

        df_processos = pd.read_excel(io=ARQ_PROCESSOS_NAO_PROCESSADOS, sheet_name='fluxo')
        total = len(df_processos)
        logger.info(f'{total} processo(s) lido(s) de {ARQ_PROCESSOS_NAO_PROCESSADOS.name}')

        controle = PlanilhaControleGeral(script, data_execucao)
        driver = abrir_sei(download_dir=download_dir)

        for i, num_processo in enumerate(df_processos['num_sei'], start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, fluxo, data_execucao, inserir)
                registros_processados.append(registro.to_dict())
                controle.registrar(registros_processados[-1])

                log_fim_processo(logger, registro, datetime.now() - t_ini)

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    break

    except Exception:
        logger.exception(f'Erro crítico na execução ({fluxo})')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_processados)
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


def main():
    executar(SCRIPT, FLUXO, AGORA, ARQ_LOG, [DIR_ALT_1_PLANILHAS, DIR_ALT_1_PDF], inserir_pdfs_das_planilhas, download_dir=DIR_ALT_1_PLANILHAS)


if __name__ == '__main__':
    main()
