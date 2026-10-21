"""Correção dos processos NOVOS encaminhados à DISA e à DEPROC sem a
avaliação do uso da rede própria.

Candidatos (ver _ler_processos): processos da planilha de controle geral
com 1.3 Memos DISA e DEPROC e sem 1.2 e, da planilha compilada antiga, os
que ainda não estão nela. Os marcadores são lidos diretamente do SEI. O
resultado vai para a planilha de controle geral.
"""

import logging
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_GERAL,
    ARQ_CONTROLE_GERAL,
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
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from planilha_controle import PlanilhaControleGeral
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMainAddMemoNaoUsouRedePropria, registrar_erro
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei
from tags import (
    TAG_AVALIADO_USO_REDE_PROPRIA,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAGS_TRATAMENTO_MANUAL,
    registrar_tags,
    tem_tag,
)

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'correcao_rede_propria'

DIR_LOG_NAO_USOU_REDE_PROPRIA = DIR_LOG / 'main_add_memo_nao_usou_rede_propria'

# Planilha compilada das execuções de setembro de 2026 (anteriores à planilha
# de controle geral). Tem matrículas de memos no modelo antigo, que o main.py
# não lê mais.
ARQ_COMPILADO = DIR_INPUTS / 'processos_processados_mas_nao_olhou_rede_propria.xlsx'
ARQ_LOG = DIR_LOG_NAO_USOU_REDE_PROPRIA / f'{AGORA}_execucao.log'

_COLUNAS_ENTRADA = ['num_processo', 'matricula_titular', 'matriculas_dependentes']

logger = logging.getLogger(__name__)


def _chave(num_processo) -> str:
    return str(num_processo).strip()


def _ler_candidatos_controle_geral() -> pd.DataFrame:
    """Processos que terminaram a última passagem com 1.3 Memos DISA e
    DEPROC e sem 1.2 (enviados sem avaliação da rede própria)."""
    if not ARQ_CONTROLE_GERAL.exists():
        logger.info(f'{ARQ_CONTROLE_GERAL.name} ainda não existe: só a planilha compilada será usada')
        return pd.DataFrame(columns=_COLUNAS_ENTRADA)
    df = pd.read_excel(ARQ_CONTROLE_GERAL, sheet_name='processos', dtype=object)
    for coluna in ('tag_memos_no_bloco', 'tag_avaliado_se_usou_rede_propria', 'matricula_titular', 'matriculas_dependentes'):
        if coluna not in df:
            df[coluna] = None
    candidatos = df[df['tag_memos_no_bloco'].eq(True) & ~df['tag_avaliado_se_usou_rede_propria'].eq(True)]
    logger.info(f'{len(candidatos)} candidato(s) na planilha de controle geral ({len(df)} processo(s))')
    return candidatos[_COLUNAS_ENTRADA]


def _ler_processos() -> pd.DataFrame:
    """Candidatos da planilha de controle geral mais os processos da
    planilha compilada que ainda não estão nela. As matrículas vêm da
    planilha de controle geral; se estiverem vazias, da compilada."""
    geral = _ler_candidatos_controle_geral()
    compilado = pd.read_excel(ARQ_COMPILADO, sheet_name='FINAL', dtype={'matricula_titular': str, 'matriculas_dependentes': str})[_COLUNAS_ENTRADA]
    compilado = compilado.set_index(compilado['num_processo'].map(_chave))

    no_controle_geral = set()
    if ARQ_CONTROLE_GERAL.exists():
        no_controle_geral = set(pd.read_excel(ARQ_CONTROLE_GERAL, sheet_name='processos', usecols=['num_processo'], dtype=object)['num_processo'].map(_chave))

    linhas = []
    for linha in geral.to_dict('records'):
        reserva = compilado.loc[_chave(linha['num_processo'])] if _chave(linha['num_processo']) in compilado.index else None
        for coluna in ('matricula_titular', 'matriculas_dependentes'):
            if pd.isna(linha[coluna]) and reserva is not None:
                linha[coluna] = reserva[coluna]
        linhas.append(linha)
    novos = compilado[~compilado.index.isin(no_controle_geral)]
    linhas += novos.to_dict('records')
    logger.info(f'{len(novos)} processo(s) da planilha compilada ainda fora da planilha de controle geral')
    return pd.DataFrame(linhas, columns=_COLUNAS_ENTRADA)


def _fora_do_escopo(registro: RegistroMainAddMemoNaoUsouRedePropria, fluxo: str, motivo: str) -> None:
    logger.info(f'{motivo}: fora do escopo da correção')
    registro.fluxo = fluxo
    registro.prox_acao = ProxAcao.FORA_DO_ESCOPO


def _avaliar_processo(driver: webdriver.Remote, registro: RegistroMainAddMemoNaoUsouRedePropria, bases: BasesUso) -> None:
    acessar_processo(driver, registro.num_processo)
    registrar_tags(registro, listar_marcadores(driver))
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')

    if not tem_tag(registro, TAG_PROCESSO_NOVO):
        if tem_tag(registro, TAG_PROCESSO_VELHO):
            _fora_do_escopo(registro, 'VELHO - fora do escopo', 'Processo VELHO')
            return
        tags_manuais = sorted(TAGS_TRATAMENTO_MANUAL.intersection(registro.marcadores_sei))
        if tags_manuais:
            _fora_do_escopo(registro, 'Tratado manualmente - fora do escopo', f'Processo tratado manualmente ({tags_manuais})')
            return
        raise ErroAvaliacao('Processo não marcado como NOVO nem VELHO no SEI')

    if tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO) or tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO):
        registro.fluxo = 'NOVO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao('Processamento parado: matrícula(s) não encontrada(s) na base da rede própria. Corrigir e remover o marcador para reprocessar')

    if tem_tag(registro, TAG_AVALIADO_USO_REDE_PROPRIA):
        registro.fluxo = 'NOVO - já avaliado'
        if tem_tag(registro, TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO):
            logger.info('Já avaliado e com memo no bloco: conferindo memo na árvore')
            registro.registrar_arvore(listar_documentos_arvore(driver))
            verificar_memo_uso_rede(driver, registro)
            registro.prox_acao = ProxAcao.ASSINAR_USO_REDE
        else:
            logger.info('Já avaliado, sem memo de uso da rede própria')
            registro.prox_acao = ProxAcao.NADA_A_FAZER
        return

    if not tem_tag(registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO):
        _fora_do_escopo(registro, 'NOVO - não se enquadra na correção', 'Sem marcador de memos DISA e DEPROC no bloco')
        return

    registro.fluxo = 'NOVO - correção'
    registro.registrar_arvore(listar_documentos_arvore(driver))
    corrigir_uso_rede_propria(driver, registro, registro.matricula_titular, registro.matriculas_dependentes, bases)


def _processar_linha(driver: webdriver.Remote, linha: pd.Series, bases: BasesUso) -> RegistroMainAddMemoNaoUsouRedePropria:
    registro = RegistroMainAddMemoNaoUsouRedePropria(
        num_processo=linha['num_processo'],
        data_execucao=AGORA,
        matricula_titular=linha['matricula_titular'],
        matriculas_dependentes=linha['matriculas_dependentes'],
    )

    try:
        _avaliar_processo(driver, registro, bases)
    except ErroAvaliacao as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)
    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def main():
    for diretorio in [DIR_DADOS, DIR_INPUTS, DIR_CONTROLE, DIR_LOG, DIR_LOG_NAO_USOU_REDE_PROPRIA]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        logger.info(f'Log: {ARQ_LOG}')

        df_processos = _ler_processos()
        total = len(df_processos)
        logger.info(f'{total} processo(s) a avaliar')

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_GERAL)

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        driver = abrir_sei()

        for i, (_, linha) in enumerate(df_processos.iterrows(), start=1):
            with contexto_processo(linha['num_processo']):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, linha, bases)
                registros_processados.append(registro.to_dict())
                controle.registrar(registros_processados[-1])

                log_fim_processo(logger, registro, datetime.now() - t_ini)

    except Exception:
        logger.exception('Erro crítico na execução do main')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_processados)
        duracao_geral = formatar_duracao(datetime.now() - t_ini_geral)
        logger.info(f'Duração total da execução: {duracao_geral}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
