"""Fluxo GEACS VERIFICAR MARCADORES (task run_geacs_verificar_marcadores), na
unidade da GEACS: lê os marcadores de cada processo e atualiza as colunas de
marcadores da planilha de controle: uma coluna tag_* por marcador válido na
GEACS (tags.TAGS_VALIDOS_GEACS) e demais_marcadores com os outros (versão
anterior, manuais, antigos).

Confere também se a prox_acao registrada na planilha faz sentido com os
marcadores e se os memorandos que os marcadores indicam estão na árvore
(conferencia_prox_acao). Os problemas vão para a coluna
verificar_marcadores_inconsistencia.

Para cada processo da aba geacs_verificar_marcadores de
processos_a_processar.xlsx: abre o processo, lê os marcadores e, se preciso, a
árvore e os memos. Nenhuma ação no SEI. Não altera a prox_acao
(RegistroVerificarMarcadores).
"""

import logging
from datetime import datetime

from conferencia_prox_acao import conferir_processo
from constantes import DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_GEACS
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from planilha_controle import PlanilhaControleGeral
from processos_a_processar import ler_processos_a_processar
from rede_propria import ErroAvaliacao
from Registro import RegistroVerificarMarcadores, registrar_erro, registrar_sem_acesso
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import TAGS_VALIDOS_GEACS, registrar_tags

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_verificar_marcadores'
FLUXO = 'GEACS VERIFICAR MARCADORES - ATUALIZAR COLUNAS DE MARCADORES'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_verificar_marcadores.log'

logger = logging.getLogger(__name__)


def verificar_marcadores(driver: webdriver.Remote, registro: RegistroVerificarMarcadores, linha_planilha: dict | None) -> None:
    """linha_planilha: a linha do processo na planilha de controle (None:
    planilha não lida)."""
    registrar_tags(registro, listar_marcadores(driver))
    registro.marcadores_lidos = True
    validos = sorted(tag for tag in registro.marcadores_sei if tag in TAGS_VALIDOS_GEACS)
    demais = sorted(tag for tag in registro.marcadores_sei if tag not in TAGS_VALIDOS_GEACS)
    logger.info(f'Marcadores válidos: {validos or "nenhum"}')
    if demais:
        logger.info(f'Demais marcadores: {demais}')
    conferir_processo(driver, registro, linha_planilha)
    for problema in registro.inconsistencias:
        logger.warning(f'Inconsistência: {problema}')
    if not registro.inconsistencias:
        logger.info('prox_acao, marcadores e memorandos consistentes')


def _processar_linha(driver: webdriver.Remote, num_processo, linha_planilha: dict | None = None) -> RegistroVerificarMarcadores:
    registro = RegistroVerificarMarcadores(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        verificar_marcadores(driver, registro, linha_planilha)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except ErroAvaliacao as e:
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    return registro


def main():
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros_log: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')

        processos = ler_processos_a_processar(SCRIPT)
        total = len(processos)

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        driver = abrir_sei(UNIDADE_GEACS)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, controle.linha_processo(num_processo))
                registros_log.append(registro.para_log())
                controle.registrar(registro.to_dict())

                log_fim_processo(logger, registro, datetime.now() - t_ini)

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    break

    except Exception:
        logger.exception(f'Erro crítico na execução ({FLUXO})')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_log)
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
