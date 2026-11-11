"""Base dos fluxos de resposta (TODO: ainda não montados): o processo, parado
com um marcador "Aguarda" depois que o memo foi assinado e encaminhado,
recebeu a resposta da APIS, da DISA ou da DEPROC.

- run_geacs_resp_apis (main_geacs_resp_apis.py): TAGS_AGUARDA_RESPOSTA_APIS;
- run_geacs_resp_disa (main_geacs_resp_disa.py): TAGS_AGUARDA_RESPOSTA_DISA;
- run_geacs_resp_deproc (main_geacs_resp_deproc.py): TAGS_AGUARDA_RESPOSTA_DEPROC.

Para cada processo da aba do fluxo (geacs_resp_apis, geacs_resp_disa ou
geacs_resp_deproc) de processos_a_processar.xlsx, a primeira coisa é conferir
se ele tem um dos marcadores "Aguarda" do fluxo (conferir_marcador_aguarda).
Depois, cada fluxo chama a sua função tratar_resposta, que ainda não foi
montada: levanta FluxoNaoMontado, sem nenhuma ação no SEI.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

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
from Registro import ProxAcao, RegistroResposta, registrar_erro, registrar_sem_acesso
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import estado_atual, registrar_tags

logger = logging.getLogger(__name__)


class FluxoNaoMontado(ErroAvaliacao):
    """O fluxo de resposta ainda não foi montado (TODO): nada é feito no SEI."""


class SemMarcadorAguarda(ErroAvaliacao):
    """O processo não tem o marcador "Aguarda" do fluxo: não aguarda a
    resposta desta unidade (ou o memo ainda não foi assinado)."""


@dataclass(frozen=True)
class FluxoResposta:
    # Nome do script: aba de processos_a_processar.xlsx, coluna script da
    # planilha de controle e nome do log
    script: str
    # Coluna fluxo da planilha de controle
    fluxo: str
    # Unidade que respondeu (mensagens)
    unidade_resposta: str
    # Marcadores "Aguarda" que levam o processo a este fluxo
    tags_aguarda: tuple[str, ...]


# Recebe o driver, o registro e o marcador "Aguarda" do processo
TratarResposta = Callable[[webdriver.Remote, RegistroResposta, str], None]


def conferir_marcador_aguarda(registro: RegistroResposta, fluxo: FluxoResposta) -> str:
    """O marcador "Aguarda" do processo, se for um dos do fluxo. Sem ele (ou
    com outro estado): SemMarcadorAguarda, sem nenhuma ação no SEI. Mais de um
    estado: ErroAvaliacao (estado_atual)."""
    estado = estado_atual(registro)
    if estado not in fluxo.tags_aguarda:
        raise SemMarcadorAguarda(f'Processo sem marcador "Aguarda" da {fluxo.unidade_resposta} (estado atual: {estado or "nenhum"}): não está aguardando resposta da {fluxo.unidade_resposta}')
    registro.marcador_aguarda = estado
    # Enquanto a resposta não for tratada, o processo continua aguardando
    registro.prox_acao = ProxAcao.AGUARDAR_RESPOSTA_MEMO
    logger.info(f'Marcador "Aguarda": "{estado}"')
    return estado


def fluxo_nao_montado(fluxo: FluxoResposta) -> FluxoNaoMontado:
    return FluxoNaoMontado(f'Fluxo {fluxo.script} (resposta da {fluxo.unidade_resposta}) ainda não montado: nenhuma ação no SEI')


def processar_linha(driver: webdriver.Remote, num_processo, fluxo: FluxoResposta, tratar_resposta: TratarResposta, agora: str) -> RegistroResposta:
    registro = RegistroResposta(num_processo=num_processo, data_execucao=agora, fluxo=fluxo.fluxo)

    try:
        acessar_processo(driver, num_processo)
        registrar_tags(registro, listar_marcadores(driver))
        logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
        tag = conferir_marcador_aguarda(registro, fluxo)
        tratar_resposta(driver, registro, tag)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except ErroAvaliacao as e:
        # Problema esperado (inclusive o fluxo não montado): sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    return registro


def executar(fluxo: FluxoResposta, tratar_resposta: TratarResposta) -> None:
    agora = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    arq_log = DIR_LOG / f'{agora}_execucao_{fluxo.script}.log'
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(arq_log)

    registros_log: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({fluxo.fluxo}) =================')
        logger.info(f'Log: {arq_log}')

        processos = ler_processos_a_processar(fluxo.script)
        total = len(processos)

        controle = PlanilhaControleGeral(fluxo.script, agora)
        driver = abrir_sei(UNIDADE_GEACS)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = processar_linha(driver, num_processo, fluxo, tratar_resposta, agora)
                dados = registro.to_dict()
                registros_log.append(dados)
                controle.registrar(dados)

                log_fim_processo(logger, registro, datetime.now() - t_ini)

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    break

    except Exception:
        logger.exception(f'Erro crítico na execução ({fluxo.fluxo})')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_log)
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')
