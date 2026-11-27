"""Fluxo GEACS VERIFICAR MARCADORES (task run_geacs_verificar_marcadores): lê
os marcadores de cada processo na GEACS e, depois de todos, na DEPROC, e
atualiza a planilha de controle: marcadores_pre_fluxo, marcadores_pos_fluxo e
estado_atual (da DEPROC: marcadores_deproc_pre_fluxo, marcadores_deproc_pos_fluxo
e estado_atual_deproc).

Confere também se a prox_acao registrada na planilha faz sentido com os
marcadores e se os memorandos que os marcadores indicam estão na árvore
(conferencia_prox_acao). Logo no começo, troca o "No Bloco" cujo memo da rodada
já está assinado (Gustavo, Bruna ou Danúbia) pelo marcador de assinado
("Aguarda" ou "Encaminhado"). Depois, para cada marcador "Aguarda" ou
"Encaminhado", confere o memo do marcador: assinado, com os marcadores
consistentes, a prox_acao passa a ser Aguardar retorno da <unidade>.

O que fazer com o processo vai para a prox_acao, com o prefixo "VERIFICAR
MARCADORES: " (ex.: "VERIFICAR MARCADORES: Rodar geacs_todas_infos"), e as
inconsistências e os erros da passagem, para tipo_erro e erro, com o mesmo
prefixo (RegistroVerificarMarcadores). O processo aguardando resposta fica sem
erro. Na aba processos, script e ultima_passagem continuam os do último fluxo
que agiu no processo: a passagem fica em verificar_marcadores_em (e no
histórico).

Para cada processo da aba geacs_verificar_marcadores de
processos_a_processar.xlsx (aba vazia: todos os processos da planilha de
controle geral): abre o processo, lê os marcadores e, se preciso, a árvore e
os memos. Única ação no SEI: a troca do "No Bloco" (processo fechado na GEACS é
reaberto para a troca e concluído de novo). Depois de todos na GEACS, troca
para a unidade da DEPROC e lê os marcadores dos processos que já deveriam
estar ou ter passado pela DEPROC (conferencia_prox_acao.passa_pela_deproc),
sem ação no SEI (conferencia_prox_acao.conferir_deproc).
"""

import logging
from datetime import datetime
from types import SimpleNamespace

from conferencia_prox_acao import (
    AcaoSugerida,
    ArvoreProcesso,
    atualizar_prox_acao_pela_situacao,
    conferir_deproc,
    conferir_memos_aguarda,
    conferir_processo,
    passa_pela_deproc,
    trocar_no_bloco_assinado,
)
from constantes import DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_DEPROC, UNIDADE_GEACS
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
from Registro import RegistroVerificarMarcadores, mensagem_erro, registrar_erro, registrar_sem_acesso
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, alterar_unidade_sei, restaurar_navegador, sessao_encerrada
from tags import TAGS_VALIDOS_GEACS, normalizar_tags, registrar_tags

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
    # Sem conferir se o processo está aberto (o "Incluir Documento" espera até
    # 15 s no fechado): só a troca do "No Bloco" assinado confere, para reabrir
    # Logo no começo: "No Bloco" com o memo assinado vira o marcador de
    # assinado, e o memo de cada "Aguarda" assinado atualiza a planilha
    arvore = ArvoreProcesso(driver)
    trocar_no_bloco_assinado(driver, arvore, registro, linha_planilha)
    conferir_memos_aguarda(arvore, registro, linha_planilha)
    # Situação conhecida pelos marcadores e pela árvore: o próprio verificar
    # corrige a prox_acao (na conclusão, sempre a de concluído)
    atualizar_prox_acao_pela_situacao(arvore, registro, linha_planilha)
    validos = sorted(tag for tag in registro.marcadores_sei if tag in TAGS_VALIDOS_GEACS)
    demais = sorted(tag for tag in registro.marcadores_sei if tag not in TAGS_VALIDOS_GEACS)
    logger.info(f'Marcadores válidos: {validos or "nenhum"}')
    if demais:
        logger.info(f'Demais marcadores: {demais}')
    conferir_processo(driver, registro, linha_planilha, arvore)
    for problema in registro.inconsistencias:
        logger.warning(f'Inconsistência: {problema}')
    if not registro.inconsistencias:
        logger.info('prox_acao, marcadores e memorandos consistentes')
    for acao in dict.fromkeys(registro.acoes_sugeridas):
        logger.info(f'Ação sugerida: {acao}')


def _processar_linha(driver: webdriver.Remote, num_processo, linha_planilha: dict | None = None) -> RegistroVerificarMarcadores:
    """A passagem na GEACS."""
    registro = RegistroVerificarMarcadores(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)
    registro.carregar_planilha(linha_planilha)

    try:
        acessar_processo(driver, num_processo)
        verificar_marcadores(driver, registro, linha_planilha)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)
        registro.acoes_sugeridas.append(AcaoSugerida.VERIFICAR_ACESSO_GEACS)

    except ErroAvaliacao as e:
        registrar_erro(registro, e)
        registro.acoes_sugeridas.append(AcaoSugerida.VERIFICAR_ERRO)

    except Exception as e:
        registrar_erro(registro, e)
        registro.acoes_sugeridas.append(AcaoSugerida.VERIFICAR_ERRO)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    return registro


def verificar_na_deproc(driver: webdriver.Remote, registro: RegistroVerificarMarcadores) -> None:
    """A passagem na DEPROC (já na unidade da DEPROC): lê os marcadores e os
    confere com o estado da GEACS, sem ação no SEI. Erro: em erros_deproc (a
    passagem na GEACS fica como estava)."""
    try:
        acessar_processo(driver, registro.num_processo)
        registro.marcadores_deproc = normalizar_tags(listar_marcadores(driver))
        registro.marcadores_deproc_lidos = True
        conferir_deproc(registro)

    except UnidadeSemAcessoException as e:
        logger.warning('DEPROC sem acesso ao processo')
        registro.erros_deproc.append((type(e).__name__, f'DEPROC: {mensagem_erro(e)}'))
        registro.acoes_sugeridas.append(AcaoSugerida.VERIFICAR_ACESSO_DEPROC)

    except Exception as e:
        logger.exception('Erro inesperado na verificação na DEPROC')
        registro.erros_deproc.append((type(e).__name__, f'DEPROC: {mensagem_erro(e)}'))
        registro.acoes_sugeridas.append(AcaoSugerida.VERIFICAR_ERRO)
        restaurar_navegador(driver)


def _sessao_encerrada_na_deproc(registro: RegistroVerificarMarcadores) -> bool:
    return any(sessao_encerrada(SimpleNamespace(tipo_erro=tipo)) for tipo, _ in registro.erros_deproc)


def _verificar_deproc(driver: webdriver.Remote, controle: PlanilhaControleGeral, registros: list[RegistroVerificarMarcadores]) -> None:
    """Depois de todos os processos na GEACS: os que já deveriam estar ou ter
    passado pela DEPROC (passa_pela_deproc) são verificados na unidade da
    DEPROC e gravados de novo na planilha (e no histórico)."""
    selecionados = [registro for registro in registros if passa_pela_deproc(registro, controle.linha_processo(registro.num_processo))]
    logger.info(f'================= DEPROC: {len(selecionados)} processo(s) que já deveriam estar ou ter passado pela DEPROC =================')
    if not selecionados:
        return
    alterar_unidade_sei(driver, UNIDADE_DEPROC)
    total = len(selecionados)
    for i, registro in enumerate(selecionados, start=1):
        with contexto_processo(registro.num_processo):
            t_ini = datetime.now()
            logger.info(f'INÍCIO DEPROC [{i}/{total}]')
            verificar_na_deproc(driver, registro)
            controle.registrar(registro.to_dict())
            log_fim_processo(logger, SimpleNamespace(**registro.para_log()), datetime.now() - t_ini)
            if _sessao_encerrada_na_deproc(registro):
                logger.warning(f'Navegador fechado: verificação na DEPROC interrompida em {i} de {total} processo(s)')
                break


def main():
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros: list[RegistroVerificarMarcadores] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')

        processos = ler_processos_a_processar(SCRIPT)

        # script e ultima_passagem continuam os do último fluxo que agiu no
        # processo (a passagem fica em verificar_marcadores_em e no histórico)
        controle = PlanilhaControleGeral(SCRIPT, AGORA, colunas_so_historico=RegistroVerificarMarcadores.COLUNAS_SO_HISTORICO)
        if not processos:
            processos = controle.processos_da_planilha()
            logger.info(f'Aba {SCRIPT} vazia: {len(processos)} processo(s) da planilha de controle geral (todos)')
        total = len(processos)
        if not processos:
            return
        driver = abrir_sei(UNIDADE_GEACS)

        interrompida = False
        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, controle.linha_processo(num_processo))
                registros.append(registro)
                controle.registrar(registro.to_dict())

                log_fim_processo(logger, SimpleNamespace(**registro.para_log()), datetime.now() - t_ini)

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    interrompida = True
                    break

        if not interrompida:
            _verificar_deproc(driver, controle, registros)

    except Exception:
        logger.exception(f'Erro crítico na execução ({FLUXO})')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, [registro.para_log() for registro in registros])
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
