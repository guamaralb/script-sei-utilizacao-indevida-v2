import logging
import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_GERAL,
    ARQ_MANTIS_REDE_CREDENCIADA,
    ARQ_MANTIS_REDE_PROPRIA,
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
from docs_processo import filtrar_docs_geacs, filtrar_memos_geacs
from dotenv import load_dotenv
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from mantis import BasesMantis, carregar_bases_mantis
from planilha_controle import salvar_planilha_controle
from processar_novo import obter_dados_ui, processar_novo
from processar_velho import processar_velho
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMain, registrar_erro
from sei_automacao.auth.login import efetuar_login
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from tags import (
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAGS_MEMO_NOVO,
    TAGS_MEMO_PARADA_NOVO,
    TAGS_RETOMADA_NOVO,
    TAGS_SCRIPT,
    adicionar_tag,
    normalizar_tags,
    registrar_tags,
)

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

load_dotenv()

SEI_LOGIN = os.getenv('SEI_LOGIN')
SEI_SENHA = os.getenv('SEI_SENHA')
SEI_ORGAO = os.getenv('SEI_ORGAO')

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

DIR_UI = DIR_DADOS / 'utilizacoes'
DIR_UI_NOVAS = DIR_UI / 'novas'
DIR_UI_ANTIGAS = DIR_UI / 'antigas'
DIR_UI_NOVAS_XLS = DIR_UI_NOVAS / 'xlsx'
DIR_UI_NOVAS_PDF = DIR_UI_NOVAS / 'pdf'
DIR_UI_ANTIGAS_XLS = DIR_UI_ANTIGAS / 'xlsx'
DIR_UI_ANTIGAS_PDF = DIR_UI_ANTIGAS / 'pdf'

for diretorio in [
    DIR_DADOS,
    DIR_INPUTS,
    DIR_CONTROLE,
    DIR_LOG,
    DIR_UI_ANTIGAS_XLS,
]:
    diretorio.mkdir(parents=True, exist_ok=True)

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_PROCESSOS_PROCESSADOS = DIR_CONTROLE / f'processos_processados_{AGORA}.xlsx'
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'

configurar_logging(ARQ_LOG)
logger = logging.getLogger(__name__)


@dataclass
class ContextoLinha:
    driver: webdriver.Remote
    tds_docs: list[dict]
    docs_geacs: list[dict]
    memos_geacs: list[dict]
    tags: list[str]
    bases: BasesUso
    bases_mantis: BasesMantis


# ---------------------------------------------------------------------------
# Processos sem marcadores do script
# ---------------------------------------------------------------------------


def _tratar_sem_marcadores(ctx: ContextoLinha, registro: RegistroMain):
    if ctx.docs_geacs:
        logger.info(f'Classificação: VELHO ({len(ctx.docs_geacs)} documento(s) da GEACS na árvore)')
        registro.fluxo = 'VELHO - classificação'
        adicionar_tag(ctx.driver, registro, TAG_PROCESSO_VELHO)
        registro.prox_acao = ProxAcao.PROCESSAR_VELHO
        return registro

    logger.info('Classificação: NOVO (sem documentos da GEACS na árvore)')
    registro.fluxo = 'NOVO - classificação'
    adicionar_tag(ctx.driver, registro, TAG_PROCESSO_NOVO)
    return processar_novo(ctx.driver, registro, ctx.tds_docs, ctx.bases, ctx.bases_mantis)


# ---------------------------------------------------------------------------
# VELHOS
# ---------------------------------------------------------------------------


def _tratar_tag_rel_ui_transformado_pdf(ctx: ContextoLinha, registro: RegistroMain):
    # TODO: implementar
    registro.fluxo = 'VELHO - Excel transformado em PDF'
    registro.prox_acao = ProxAcao.VELHO_CONCLUIDO
    return registro


def _tratar_tag_novo_rel_ui_gerado(ctx: ContextoLinha, registro: RegistroMain):
    # TODO: implementar
    registro.fluxo = 'VELHO - relatório de UI refeito'
    registro.prox_acao = ProxAcao.VELHO_CONCLUIDO
    return registro


def _tratar_tag_transformar_excel_em_pdf(ctx: ContextoLinha, registro: RegistroMain):
    # TODO: implementar
    registro.fluxo = 'VELHO - transformar Excel em PDF'
    registro.prox_acao = ProxAcao.VELHO_TRANSFORMAR_PDF
    return registro


def _tratar_tag_refazer_rel_ui(ctx: ContextoLinha, registro: RegistroMain):
    # TODO: implementar
    registro.fluxo = 'VELHO - refazer relatório de UI'
    registro.prox_acao = ProxAcao.VELHO_REFAZER_REL_UI
    return registro


_MSG_PARADO_MAT_NAO_ENCONTRADAS = 'Processamento parado: matrícula(s) não encontrada(s) na base geral e/ou na base da rede própria. Corrigir e remover o(s) marcador(es) para reprocessar'


def _tratar_velho(ctx: ContextoLinha, registro: RegistroMain):
    if registro.tag_mat_nao_encontradas_base_geral_velho or registro.tag_mat_nao_encontradas_velho:
        registro.fluxo = 'VELHO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao(_MSG_PARADO_MAT_NAO_ENCONTRADAS)
    if registro.tag_rel_ui_transformado_pdf:
        logger.info('Fluxo: VELHO com relatório de UI transformado em PDF')
        return _tratar_tag_rel_ui_transformado_pdf(ctx, registro)
    if registro.tag_novo_rel_ui_gerado:
        logger.info('Fluxo: VELHO com novo relatório de UI gerado')
        return _tratar_tag_novo_rel_ui_gerado(ctx, registro)
    if registro.tag_transformar_excel_em_pdf and registro.tag_refazer_rel_ui:
        raise ErroAvaliacao('Processo VELHO marcado para transformar Excel em PDF e para refazer o relatório de UI')
    if registro.tag_transformar_excel_em_pdf:
        logger.info('Fluxo: VELHO pendente de transformar Excel em PDF')
        return _tratar_tag_transformar_excel_em_pdf(ctx, registro)
    if registro.tag_refazer_rel_ui:
        logger.info('Fluxo: VELHO pendente de refazer relatório de UI')
        return _tratar_tag_refazer_rel_ui(ctx, registro)
    logger.info('Fluxo: VELHO - identificação das instruções da APIS')
    registro.fluxo = 'VELHO - identificação das instruções'
    return processar_velho(ctx.driver, registro, ctx.docs_geacs, ctx.tds_docs)


# ---------------------------------------------------------------------------
# NOVOS
# ---------------------------------------------------------------------------


def _tratar_novo_avaliado(ctx: ContextoLinha, registro: RegistroMain):
    """Processo já avaliado: confere os memos esperados na árvore."""
    logger.info('Fluxo: NOVO já avaliado - conferência dos memos na árvore')
    registro.fluxo = 'NOVO - já avaliado'
    if registro.tag_memo_nao_usou_rede_propria_no_bloco:
        verificar_memo_uso_rede(ctx.driver, registro, ctx.tds_docs)

    if registro.tag_memos_no_bloco:
        esperado = 2 + int(registro.tag_memo_nao_usou_rede_propria_no_bloco)
        acao = ProxAcao.ASSINAR_DISA_DEPROC
    elif registro.tag_memo_deproc_no_bloco:
        esperado = 1
        acao = ProxAcao.ASSINAR_DEPROC
    else:
        raise ErroAvaliacao('Processo avaliado quanto à rede própria, mas sem marcador de memos no bloco')

    registro.qnt_memos_geacs_esperada = esperado
    quant = len(ctx.memos_geacs)
    if quant == esperado:
        logger.info(f'Quantidade de memos da GEACS confere ({quant})')
        registro.prox_acao = acao
    else:
        logger.warning(f'Quantidade de memos da GEACS não confere: esperado {esperado}, encontrado {quant}')
        registro.prox_acao = ProxAcao.VERIFICAR_QNT_MEMOS
    return registro


def _corrigir_novo_sem_avaliacao(ctx: ContextoLinha, registro: RegistroMain):
    """Processo enviado à DISA e à DEPROC sem avaliação da rede própria."""
    logger.info('Fluxo: NOVO enviado à DISA e DEPROC sem avaliação da rede própria - correção')
    registro.fluxo = 'NOVO - correção'
    dados_ui = obter_dados_ui(ctx.driver, registro, ctx.tds_docs)
    corrigir_uso_rede_propria(
        ctx.driver,
        registro,
        ctx.tds_docs,
        dados_ui.matricula_titular,
        dados_ui.matriculas_dependentes,
        ctx.bases,
    )
    return registro


def _conferir_novo_concluido(ctx: ContextoLinha, registro: RegistroMain):
    """Fluxo normal concluído (memo DEPROC no bloco): confere os memos da
    GEACS na árvore."""
    logger.info('Fluxo: NOVO concluído - conferência dos memos na árvore')
    registro.fluxo = 'NOVO - concluído'
    esperado = sum(1 for tag in TAGS_MEMO_NOVO if tag in ctx.tags)
    acao = ProxAcao.ASSINAR_DISA_DEPROC if TAG_MEMO_DISA_USO_REDE_PROPRIA in ctx.tags else ProxAcao.ASSINAR_DEPROC

    registro.qnt_memos_geacs_esperada = esperado
    quant = len(ctx.memos_geacs)
    if quant == esperado:
        logger.info(f'Quantidade de memos da GEACS confere ({quant})')
        registro.prox_acao = acao
    else:
        logger.warning(f'Quantidade de memos da GEACS não confere: esperado {esperado}, encontrado {quant}')
        registro.prox_acao = ProxAcao.VERIFICAR_QNT_MEMOS
    return registro


def _processar_novo_ou_retomar(ctx: ContextoLinha, registro: RegistroMain):
    """Fluxo normal, do início ou retomando pelos marcadores. Cada memo da
    GEACS na árvore precisa ter o seu marcador; senão há memo sem marcador
    e o processo é verificado manualmente (evita duplicidade).

    TODO: procurar pelo assunto os memos sem marcador e só adicionar o
    marcador (retomada, como o memo à APIS de matrículas não encontradas)."""
    esperado = sum(1 for tag in TAGS_MEMO_NOVO if tag in ctx.tags)
    quant = len(ctx.memos_geacs)
    if quant != esperado:
        registro.qnt_memos_geacs_esperada = esperado
        raise ErroAvaliacao(f'Processo NOVO com {quant} memorando(s) da GEACS e {esperado} marcador(es) de memo. Verificar manualmente para evitar duplicidade.')

    if any(tag in ctx.tags for tag in TAGS_RETOMADA_NOVO):
        logger.info('Fluxo: NOVO - retomada do fluxo normal pelos marcadores')
    else:
        logger.info('Fluxo: NOVO sem memos da GEACS - fluxo normal')
    return processar_novo(ctx.driver, registro, ctx.tds_docs, ctx.bases, ctx.bases_mantis)


def _tratar_novo(ctx: ContextoLinha, registro: RegistroMain):
    parada = [tag for tag in TAGS_MEMO_PARADA_NOVO if tag in ctx.tags]
    if parada:
        # TODO: definir o processamento na próxima execução (depois da
        # resposta da APIS ou da DISA ao memo enviado)
        registro.fluxo = 'NOVO - parado (aguardando resposta ao memo)'
        registro.prox_acao = ProxAcao.AGUARDAR_RESPOSTA_MEMO
        raise ErroAvaliacao(f'Processamento parado: memo enviado, aguardando resposta ({", ".join(parada)})')

    # No fluxo normal, 1.2.1 sem o marcador do memo à APIS e 1.2.2 vêm
    # sempre com o avaliado (DISA) e são retomados. Sem ele, são da versão
    # anterior do fluxo, em que esses marcadores paravam o processo.
    if not registro.tag_avaliado_uso_rede_propria_disa and (registro.tag_mat_nao_encontradas_base_geral_novo or registro.tag_mat_nao_encontradas_novo):
        registro.fluxo = 'NOVO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao(_MSG_PARADO_MAT_NAO_ENCONTRADAS)

    if TAG_MEMO_DEPROC_COPARTICIPACAO in ctx.tags:
        return _conferir_novo_concluido(ctx, registro)

    # Marcadores da versão anterior do fluxo normal (1.2, 1.3 e 1.4)
    if registro.tag_avaliado_se_usou_rede_propria:
        return _tratar_novo_avaliado(ctx, registro)

    if registro.tag_memos_no_bloco:
        return _corrigir_novo_sem_avaliacao(ctx, registro)

    if registro.tag_memo_deproc_no_bloco:
        raise ErroAvaliacao('Marcador de memo DEPROC no bloco sem marcador de avaliação da rede própria')

    if registro.tag_memo_nao_usou_rede_propria_no_bloco:
        raise ErroAvaliacao('Marcador de memo de uso da rede própria sem marcador de memos DISA e DEPROC no bloco')

    return _processar_novo_ou_retomar(ctx, registro)


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------


def _classificar_e_processar(ctx: ContextoLinha, registro: RegistroMain):
    if registro.tag_processo_novo and registro.tag_processo_velho:
        raise ErroAvaliacao('Processo marcado como NOVO e VELHO')

    if registro.tag_processo_velho:
        return _tratar_velho(ctx, registro)

    if registro.tag_processo_novo:
        return _tratar_novo(ctx, registro)

    tags_script = [t for t in ctx.tags if t in TAGS_SCRIPT]
    if tags_script:
        raise ErroAvaliacao(f'Marcadores do script sem marcador NOVO/VELHO: {tags_script}')

    # Marcadores manuais (ex.: PLANILHADO) não impedem a classificação
    return _tratar_sem_marcadores(ctx, registro)


def _processar_linha(driver, num_processo, bases: BasesUso, bases_mantis: BasesMantis) -> RegistroMain:
    registro = RegistroMain(num_processo=num_processo, data_execucao=AGORA)

    try:
        acessar_processo(driver, num_processo)
        tds_docs = listar_documentos_arvore(driver)
        tags = normalizar_tags(listar_marcadores(driver))

        ctx = ContextoLinha(
            driver=driver,
            tds_docs=tds_docs,
            docs_geacs=filtrar_docs_geacs(tds_docs),
            memos_geacs=filtrar_memos_geacs(tds_docs),
            tags=tags,
            bases=bases,
            bases_mantis=bases_mantis,
        )
        registro.qnt_docs_geacs_na_arvore = len(ctx.docs_geacs)
        registro.qnt_memos_geacs_na_arvore = len(ctx.memos_geacs)
        logger.info(f'Árvore: {len(tds_docs)} documento(s) | GEACS: {len(ctx.docs_geacs)} documento(s), {len(ctx.memos_geacs)} memorando(s)')
        logger.info(f'Marcadores: {tags or "nenhum"}')

        registro.marcadores_sei = tags
        registrar_tags(registro, tags)

        registro = _classificar_e_processar(ctx, registro)

    except (ErroAvaliacao, FormatoMemorandoInvalido, TextoMemoPendente) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def _salvar_resultado(registros_processados: list[dict]) -> None:
    salvar_planilha_controle(registros_processados, ARQ_PROCESSOS_PROCESSADOS)


def main():
    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        logger.info(f'Log: {ARQ_LOG}')

        df_processos = pd.read_excel(
            io=ARQ_PROCESSOS_NAO_PROCESSADOS,
            sheet_name='processos_reais',
        )
        total = len(df_processos)
        logger.info(f'{total} processo(s) lido(s) de {ARQ_PROCESSOS_NAO_PROCESSADOS.name}')

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_GERAL)
        bases_mantis = carregar_bases_mantis(ARQ_MANTIS_REDE_PROPRIA, ARQ_MANTIS_REDE_CREDENCIADA)

        logger.info('Iniciando navegador e login no SEI')
        driver = iniciar_driver(driver_type='chrome', download_dir=DIR_UI_ANTIGAS_XLS)
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')
        efetuar_login(driver, SEI_LOGIN, SEI_SENHA, SEI_ORGAO)
        logger.info('Login no SEI efetuado')

        for i, (_, linha) in enumerate(df_processos.iterrows(), start=1):
            num_processo = linha['num_sei']
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, bases, bases_mantis)
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
