import logging
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
    DIR_UTILIZACOES_MANTIS_PDF,
)
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from mantis import BasesMantis, carregar_bases_mantis
from planilha_controle import PlanilhaControleGeral
from processar_novo import processar_novo
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMain, registrar_erro
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei
from tags import (
    REMOCAO_DE_MARCADOR_DISPONIVEL,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_PROCESSO_NOVO,
    TAG_VELHO_MEMO_DEPROC,
    TAG_VELHO_MEMO_DISA,
    TAGS_PARADA_NOVO,
    TAGS_TRATAMENTO_MANUAL,
    MarcadoresInconsistentes,
    adicionar_tag,
    conferir_marcadores,
    estado_atual,
    registrar_tags,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'main'

DIR_UI_ANTIGAS_XLS = DIR_DADOS / 'utilizacoes' / 'antigas' / 'xlsx'

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'

logger = logging.getLogger(__name__)

_MSG_PARADO_MAT_NAO_ENCONTRADAS = 'Parado pela versão anterior do fluxo: matrícula(s) não encontrada(s) na base geral e/ou DISA. Corrigir e remover o(s) marcador(es) para reprocessar'

_PROX_ACAO_POR_CONCLUSAO = {
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO: ProxAcao.ASSINAR_DISA_DEPROC,
    TAG_MEMO_DEPROC_COPARTICIPACAO: ProxAcao.ASSINAR_DEPROC,
    TAG_VELHO_MEMO_DISA: ProxAcao.VELHO_ASSINAR_DISA,
    TAG_VELHO_MEMO_DEPROC: ProxAcao.VELHO_ASSINAR_DEPROC,
}


def _conferir_marcadores(registro: RegistroMain, momento: str) -> None:
    try:
        conferir_marcadores(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def _tratar(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso, bases_mantis: BasesMantis) -> None:
    """Decide, pelos marcadores, se o processo está parado, concluído ou
    segue (do início ou retomando) para o fluxo de processar_novo."""
    _conferir_marcadores(registro, 'no início da passagem')
    if not tem_tag(registro, TAG_PROCESSO_NOVO):
        # Inclusive os que já têm documento da GEACS ou o antigo
        # "2 - Processo VELHO": a APIS pede para refazer a consulta
        logger.info('Classificação: processo sem o marcador NOVO - fluxo do início')
        registro.fluxo = 'NOVO - classificação'
        adicionar_tag(driver, registro, TAG_PROCESSO_NOVO)
        processar_novo(driver, registro, bases, bases_mantis)
        return

    registro.velho = tem_tag(registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO)
    estado = estado_atual(registro)

    if estado in TAGS_PARADA_NOVO:
        # TODO: definir o processamento na próxima execução (depois da
        # resposta da APIS ou da DISA ao memo enviado)
        registro.fluxo = 'parado (aguardando resposta ao memo)'
        registro.prox_acao = ProxAcao.AGUARDAR_RESPOSTA_MEMO
        raise ErroAvaliacao(f'Processamento parado: memo enviado, aguardando resposta ({estado})')

    if estado in _PROX_ACAO_POR_CONCLUSAO:
        logger.info(f'Fluxo: concluído ("{estado}")')
        registro.fluxo = 'concluído'
        registro.prox_acao = _PROX_ACAO_POR_CONCLUSAO[estado]
        return

    if registro.velho:
        manuais = TAGS_TRATAMENTO_MANUAL.intersection(registro.marcadores_atuais)
        if manuais:
            logger.info(f'VELHO tratado manualmente ({sorted(manuais)}): fora do escopo')
            registro.fluxo = 'VELHO - tratado manualmente'
            registro.prox_acao = ProxAcao.FORA_DO_ESCOPO
            return
    elif estado is None:
        # Versão anterior do fluxo (sem marcador de estado)
        if tem_tag(registro, TAG_MEMO_DEPROC_NO_BLOCO):
            logger.info('Fluxo: concluído na versão anterior (só memo DEPROC)')
            registro.fluxo = 'concluído (versão anterior)'
            registro.prox_acao = ProxAcao.ASSINAR_DEPROC
            return
        if tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO) or tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO):
            registro.fluxo = 'parado (matrículas não encontradas)'
            registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
            raise ErroAvaliacao(_MSG_PARADO_MAT_NAO_ENCONTRADAS)

    if estado is None:
        logger.info(f'Fluxo: {"VELHO (enviado à DISA e à DEPROC antes da avaliação)" if registro.velho else "NOVO"} - do início')
    else:
        logger.info(f'Fluxo: retomada (estado "{estado}")')
    processar_novo(driver, registro, bases, bases_mantis)


def _processar_linha(driver: webdriver.Remote, num_processo, bases: BasesUso, bases_mantis: BasesMantis) -> RegistroMain:
    registro = RegistroMain(num_processo=num_processo, data_execucao=AGORA)

    try:
        acessar_processo(driver, num_processo)
        registro.registrar_arvore(listar_documentos_arvore(driver))
        registrar_tags(registro, listar_marcadores(driver))
        logger.info(f'Árvore: {len(registro.tds_docs)} documento(s) | GEACS: {registro.qnt_docs_geacs_na_arvore} documento(s), {registro.qnt_memos_geacs_na_arvore} memorando(s)')
        logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')

        _tratar(driver, registro, bases, bases_mantis)
        _conferir_marcadores(registro, 'no fim da passagem')

    except (ErroAvaliacao, FormatoMemorandoInvalido, TextoMemoPendente) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def main():
    for diretorio in [DIR_DADOS, DIR_INPUTS, DIR_CONTROLE, DIR_LOG, DIR_UI_ANTIGAS_XLS, DIR_UTILIZACOES_MANTIS_PDF]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    if not REMOCAO_DE_MARCADOR_DISPONIVEL:
        msg = 'A sei_automacao ainda não tem remover_marcador (sei_automacao.processo), necessária para trocar os marcadores de estado. Execução não iniciada.'
        logger.error(msg)
        raise SystemExit(msg)

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

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        driver = abrir_sei(download_dir=DIR_UI_ANTIGAS_XLS)

        for i, num_processo in enumerate(df_processos['num_sei'], start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, bases, bases_mantis)
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
