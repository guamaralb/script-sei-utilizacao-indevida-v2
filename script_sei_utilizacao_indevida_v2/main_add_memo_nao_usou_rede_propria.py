"""Correção dos processos NOVOS encaminhados à DISA e à DEPROC sem a
avaliação do uso da rede própria.

Lê a planilha compilada gerada pelo main.py (matrículas) e os marcadores
diretamente do SEI.
"""

import logging
import os
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_GERAL,
    ARQ_USO_REDE_PROPRIA,
    DIR_CONTROLE,
    DIR_DADOS,
    DIR_INPUTS,
    DIR_LOG,
)
from correcao_rede_propria import (
    corrigir_uso_rede_propria,
    verificar_memo_uso_rede,
)
from docs_processo import filtrar_memos_geacs
from dotenv import load_dotenv
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from planilha_controle import salvar_planilha_controle
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMainAddMemoNaoUsouRedePropria, registrar_erro
from sei_automacao.auth.login import efetuar_login
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from tags import normalizar_tags, registrar_tags

load_dotenv()

SEI_LOGIN = os.getenv('SEI_LOGIN')
SEI_SENHA = os.getenv('SEI_SENHA')
SEI_ORGAO = os.getenv('SEI_ORGAO')

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

DIR_CONTROLE_MAIN = DIR_CONTROLE / 'main'
DIR_CONTROLE_NAO_USOU_REDE_PROPRIA = DIR_CONTROLE / 'main_add_memo_nao_usou_rede_propria'
DIR_LOG_NAO_USOU_REDE_PROPRIA = DIR_LOG / 'main_add_memo_nao_usou_rede_propria'

for diretorio in [
    DIR_DADOS,
    DIR_INPUTS,
    DIR_CONTROLE,
    DIR_CONTROLE_NAO_USOU_REDE_PROPRIA,
    DIR_LOG,
    DIR_LOG_NAO_USOU_REDE_PROPRIA,
]:
    diretorio.mkdir(parents=True, exist_ok=True)

ARQ_COMPILADO = DIR_CONTROLE_MAIN / '_processos_processados-COMPILADO-2026_09_23.xlsx'
ARQ_LOG = DIR_LOG_NAO_USOU_REDE_PROPRIA / f'{AGORA}_execucao.log'
ARQ_CONTROLE = DIR_CONTROLE_NAO_USOU_REDE_PROPRIA / f'{AGORA}_processos_add_memo_nao_uso_rede_propria.xlsx'

configurar_logging(ARQ_LOG)
logger = logging.getLogger(__name__)


def _listar_arvore(driver, registro: RegistroMainAddMemoNaoUsouRedePropria) -> list[dict]:
    tds_docs = listar_documentos_arvore(driver)
    registro.qnt_memos_geacs_na_arvore = len(filtrar_memos_geacs(tds_docs))
    return tds_docs


def _avaliar_processo(
    driver,
    linha: pd.Series,
    bases: BasesUso,
    registro: RegistroMainAddMemoNaoUsouRedePropria,
) -> None:
    acessar_processo(driver, registro.num_processo)
    tags = normalizar_tags(listar_marcadores(driver))
    registro.marcadores_sei = tags
    registrar_tags(registro, tags)
    logger.info(f'Marcadores: {tags or "nenhum"}')

    if not registro.tag_processo_novo:
        if registro.tag_processo_velho:
            logger.info('Processo VELHO: fora do escopo da correção')
            registro.fluxo = 'VELHO - fora do escopo'
            registro.prox_acao = ProxAcao.FORA_DO_ESCOPO
            return
        raise ErroAvaliacao('Processo não marcado como NOVO nem VELHO no SEI')

    if registro.tag_mat_nao_encontradas_base_geral_novo or registro.tag_mat_nao_encontradas_novo:
        registro.fluxo = 'NOVO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao('Processamento parado: matrícula(s) não encontrada(s) na base da rede própria. Corrigir e remover o marcador para reprocessar')

    if registro.tag_avaliado_se_usou_rede_propria:
        registro.fluxo = 'NOVO - já avaliado'
        if registro.tag_memo_nao_usou_rede_propria_no_bloco:
            logger.info('Já avaliado e com memo no bloco: conferindo memo na árvore')
            tds_docs = _listar_arvore(driver, registro)
            verificar_memo_uso_rede(driver, registro, tds_docs)
            registro.prox_acao = ProxAcao.ASSINAR_USO_REDE
        else:
            logger.info('Já avaliado, sem memo de uso da rede própria')
            registro.prox_acao = ProxAcao.NADA_A_FAZER
        return

    if not registro.tag_memos_no_bloco:
        logger.info('Sem marcador de memos DISA e DEPROC no bloco: não se enquadra na correção')
        registro.fluxo = 'NOVO - não se enquadra na correção'
        registro.prox_acao = ProxAcao.FORA_DO_ESCOPO
        return

    registro.fluxo = 'NOVO - correção'
    tds_docs = _listar_arvore(driver, registro)
    corrigir_uso_rede_propria(
        driver,
        registro,
        tds_docs,
        linha['matricula_titular'],
        linha['matriculas_dependentes'],
        bases,
    )


def _processar_linha(driver, linha: pd.Series, bases: BasesUso) -> RegistroMainAddMemoNaoUsouRedePropria:
    registro = RegistroMainAddMemoNaoUsouRedePropria(
        num_processo=linha['num_processo'],
        data_execucao=AGORA,
        matricula_titular=linha['matricula_titular'],
        matriculas_dependentes=linha['matriculas_dependentes'],
    )

    try:
        _avaliar_processo(driver, linha, bases, registro)
    except ErroAvaliacao as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)
    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def _salvar_resultado(registros_processados: list[dict]) -> None:
    salvar_planilha_controle(registros_processados, ARQ_CONTROLE)


def main():
    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        logger.info(f'Log: {ARQ_LOG}')

        df_processos = pd.read_excel(
            io=ARQ_COMPILADO,
            sheet_name='FINAL',
            dtype={'matricula_titular': str, 'matriculas_dependentes': str},
        )
        total = len(df_processos)
        logger.info(f'{total} processo(s) lido(s) de {ARQ_COMPILADO.name}')

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_GERAL)

        logger.info('Iniciando navegador e login no SEI')
        driver = iniciar_driver(driver_type='chrome')
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')
        efetuar_login(driver, SEI_LOGIN, SEI_SENHA, SEI_ORGAO)
        logger.info('Login no SEI efetuado')

        for i, (_, linha) in enumerate(df_processos.iterrows(), start=1):
            with contexto_processo(linha['num_processo']):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, linha, bases)
                registros_processados.append(registro.to_dict())

                log_fim_processo(logger, registro, datetime.now() - t_ini)

    except Exception:
        logger.exception('Erro crítico na execução do main')
        raise

    finally:
        _salvar_resultado(registros_processados)
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_processados)
        duracao_geral = formatar_duracao(datetime.now() - t_ini_geral)
        logger.info(f'Duração total da execução: {duracao_geral}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
