"""Fluxo alternativo ADC PDF ANT AUT (task run_geacs_adc_pdf_ant_aut): insere nos processos o PDF das
planilhas de utilização e os deixa aguardando o fluxo normal (main_geacs_inicial.py). Ver
planilhas_adc_pdf_ant_aut.py. O loop (executar) também é usado pelo fluxo ADC PDF ANT MAN."""

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from constantes import DIR_ADC_PDF_ANT_AUT_PDF, DIR_ADC_PDF_ANT_AUT_PLANILHAS, DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_GEACS
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from marcadores_disponiveis import garantir_marcadores_no_sei
from planilha_controle import PlanilhaControleGeral
from planilhas_adc_pdf_ant_aut import inserir_pdfs_das_planilhas
from processos_a_processar import ler_processos_a_processar
from rede_propria import ErroAvaliacao
from Registro import RegistroAdcPdfAnt, registrar_erro, registrar_sem_acesso
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, sessao_encerrada
from tags import TAG_AGUARDA_FLUXO_NORMAL, TAG_PROCESSO_NOVO, registrar_tags

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_adc_pdf_ant_aut'
FLUXO = 'ADC PDF ANT AUT - PLANILHA ANTIGA BAIXADA DO SEI'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_adc_pdf_ant_aut.log'

logger = logging.getLogger(__name__)


def _processar_linha(
    driver: webdriver.Remote,
    num_processo,
    fluxo: str = FLUXO,
    data_execucao: str = AGORA,
    inserir: Callable[[webdriver.Remote, RegistroAdcPdfAnt], None] = inserir_pdfs_das_planilhas,
) -> RegistroAdcPdfAnt:
    registro = RegistroAdcPdfAnt(num_processo=num_processo, data_execucao=data_execucao, fluxo=fluxo)

    try:
        acessar_processo(driver, num_processo)
        registrar_tags(registro, listar_marcadores(driver))
        # Antes de listar a árvore: a conferência recarrega a página e fecha
        # as pastas. Sem os marcadores cadastrados, nenhum PDF é inserido
        garantir_marcadores_no_sei(driver, [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL])
        registro.registrar_arvore(listar_documentos_arvore(driver))
        logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')

        inserir(driver, registro)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

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
    inserir: Callable[[webdriver.Remote, RegistroAdcPdfAnt], None],
    download_dir: Path | None = None,
) -> None:
    """Loop dos processos da aba do script em processos_a_processar.xlsx, com o
    registro na planilha de controle."""
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG, *diretorios]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(arq_log)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({fluxo}) =================')
        logger.info(f'Log: {arq_log}')

        processos = ler_processos_a_processar(script)
        total = len(processos)

        controle = PlanilhaControleGeral(script, data_execucao)
        driver = abrir_sei(UNIDADE_GEACS, download_dir=download_dir)

        for i, num_processo in enumerate(processos, start=1):
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
    executar(SCRIPT, FLUXO, AGORA, ARQ_LOG, [DIR_ADC_PDF_ANT_AUT_PLANILHAS, DIR_ADC_PDF_ANT_AUT_PDF], inserir_pdfs_das_planilhas, download_dir=DIR_ADC_PDF_ANT_AUT_PLANILHAS)


if __name__ == '__main__':
    main()
