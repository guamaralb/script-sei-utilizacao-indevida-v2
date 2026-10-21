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
)
from correcao_rede_propria import (
    corrigir_uso_rede_propria,
    verificar_memo_uso_rede,
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
from processar_novo import encontrar_memo_sem_marcador, obter_dados_ui, processar_novo
from processar_velho import processar_velho
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMain, registrar_erro
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei
from tags import (
    MEMOS_POR_ESTADO_NOVO,
    REMOCAO_DE_MARCADOR_DISPONIVEL,
    TAG_AVALIADO_USO_REDE_PROPRIA,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_DISA_VELHO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_VELHO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_NOVO_REL_UI_GERADO,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAG_REFAZER_REL_UI,
    TAG_REL_UI_TRANSFORMADO_PDF,
    TAG_TRANSFORMAR_EXCEL_EM_PDF,
    TAGS_CONCLUSAO_NOVO,
    TAGS_ESTADO_NOVO,
    TAGS_ESTADO_VELHO,
    TAGS_PARADA_NOVO,
    TAGS_SCRIPT,
    adicionar_tag,
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

_MSG_PARADO_MAT_NAO_ENCONTRADAS = 'Processamento parado: matrícula(s) não encontrada(s) na base geral e/ou na base da rede própria. Corrigir e remover o(s) marcador(es) para reprocessar'


def _conferir_memos_geacs(registro: RegistroMain, esperado: int, motivo: str) -> None:
    """Os memos da GEACS na árvore precisam corresponder aos marcadores;
    senão o processo é verificado manualmente (evita duplicidade)."""
    registro.qnt_memos_geacs_esperada = esperado
    quant = len(registro.memos_geacs)
    if quant != esperado:
        registro.prox_acao = ProxAcao.VERIFICAR_QNT_MEMOS
        raise ErroAvaliacao(f'{motivo} indica {esperado} memorando(s) da GEACS, mas há {quant} na árvore. Verificar manualmente para evitar duplicidade.')
    logger.info(f'Quantidade de memos da GEACS confere ({quant})')


# ---------------------------------------------------------------------------
# VELHOS
# ---------------------------------------------------------------------------

# TODO: implementar o fluxo de cada pendência (2.1) e o fluxo após a
# conclusão (2.2). Por enquanto só registram a próxima ação.
_ESTADOS_VELHO = {
    TAG_TRANSFORMAR_EXCEL_EM_PDF: ('VELHO - transformar Excel em PDF', ProxAcao.VELHO_TRANSFORMAR_PDF),
    TAG_REFAZER_REL_UI: ('VELHO - refazer relatório de UI', ProxAcao.VELHO_REFAZER_REL_UI),
    TAG_REL_UI_TRANSFORMADO_PDF: ('VELHO - Excel transformado em PDF', ProxAcao.VELHO_CONCLUIDO),
    TAG_NOVO_REL_UI_GERADO: ('VELHO - relatório de UI refeito', ProxAcao.VELHO_CONCLUIDO),
}


def _tratar_velho(driver: webdriver.Remote, registro: RegistroMain) -> None:
    if tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_VELHO) or tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_DISA_VELHO):
        registro.fluxo = 'VELHO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao(_MSG_PARADO_MAT_NAO_ENCONTRADAS)

    estado = estado_atual(registro, TAGS_ESTADO_VELHO)
    if estado is None:
        logger.info('Fluxo: VELHO - identificação das instruções da APIS')
        registro.fluxo = 'VELHO - identificação das instruções'
        processar_velho(driver, registro)
        return

    logger.info(f'Fluxo: VELHO com marcador "{estado}"')
    registro.fluxo, registro.prox_acao = _ESTADOS_VELHO[estado]


# ---------------------------------------------------------------------------
# NOVOS: versão anterior do fluxo normal (1.2, 1.3 e 1.4)
# ---------------------------------------------------------------------------


def _tratar_novo_avaliado(driver: webdriver.Remote, registro: RegistroMain) -> None:
    """Processo já avaliado: confere os memos esperados na árvore."""
    logger.info('Fluxo: NOVO já avaliado - conferência dos memos na árvore')
    registro.fluxo = 'NOVO - já avaliado'
    com_memo_uso_rede = tem_tag(registro, TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO)
    if com_memo_uso_rede:
        verificar_memo_uso_rede(driver, registro)

    if tem_tag(registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO):
        esperado, acao = 2 + int(com_memo_uso_rede), ProxAcao.ASSINAR_DISA_DEPROC
    elif tem_tag(registro, TAG_MEMO_DEPROC_NO_BLOCO):
        esperado, acao = 1, ProxAcao.ASSINAR_DEPROC
    else:
        raise ErroAvaliacao('Processo avaliado quanto à rede própria, mas sem marcador de memos no bloco')

    _conferir_memos_geacs(registro, esperado, 'Marcadores da versão anterior do fluxo')
    registro.prox_acao = acao


def _corrigir_novo_sem_avaliacao(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso) -> None:
    """Processo enviado à DISA e à DEPROC sem avaliação da rede própria."""
    logger.info('Fluxo: NOVO enviado à DISA e DEPROC sem avaliação da rede própria - correção')
    registro.fluxo = 'NOVO - correção'
    dados_ui = obter_dados_ui(driver, registro)
    corrigir_uso_rede_propria(driver, registro, dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)


def _tratar_novo_versao_anterior(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso) -> bool:
    """Trata o processo com marcadores da versão anterior do fluxo normal.
    Devolve False se ele não tem nenhum."""
    if tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO) or tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO):
        # No fluxo atual, 1.2.1 e 1.2.2 vêm sempre com um marcador de estado
        registro.fluxo = 'NOVO - parado (matrículas não encontradas)'
        registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS
        raise ErroAvaliacao(_MSG_PARADO_MAT_NAO_ENCONTRADAS)
    if tem_tag(registro, TAG_AVALIADO_USO_REDE_PROPRIA):
        _tratar_novo_avaliado(driver, registro)
        return True
    if tem_tag(registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO):
        _corrigir_novo_sem_avaliacao(driver, registro, bases)
        return True
    if tem_tag(registro, TAG_MEMO_DEPROC_NO_BLOCO):
        raise ErroAvaliacao('Marcador de memo DEPROC no bloco sem marcador de avaliação da rede própria')
    if tem_tag(registro, TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO):
        raise ErroAvaliacao('Marcador de memo de uso da rede própria sem marcador de memos DISA e DEPROC no bloco')
    return False


# ---------------------------------------------------------------------------
# NOVOS
# ---------------------------------------------------------------------------


def _tratar_novo(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso, bases_mantis: BasesMantis) -> None:
    estado = estado_atual(registro, TAGS_ESTADO_NOVO)
    if estado is None and _tratar_novo_versao_anterior(driver, registro, bases):
        return

    esperado = MEMOS_POR_ESTADO_NOVO.get(estado, 0)
    retomada = estado not in TAGS_PARADA_NOVO + TAGS_CONCLUSAO_NOVO
    # Um memo a mais pode ser o da etapa seguinte, criado numa passagem que
    # falhou antes do marcador: se o assunto confirmar, o fluxo normal o
    # reaproveita e só adiciona o marcador
    if retomada and len(registro.memos_geacs) == esperado + 1 and encontrar_memo_sem_marcador(driver, registro):
        logger.warning('Memo da GEACS sem marcador identificado pelo assunto: retomada sem recriar o memo')
        esperado += 1
    _conferir_memos_geacs(registro, esperado, f'Marcador "{estado}"' if estado else 'Processo NOVO sem marcador de estado')

    if estado in TAGS_PARADA_NOVO:
        # TODO: definir o processamento na próxima execução (depois da
        # resposta da APIS ou da DISA ao memo enviado)
        registro.fluxo = 'NOVO - parado (aguardando resposta ao memo)'
        registro.prox_acao = ProxAcao.AGUARDAR_RESPOSTA_MEMO
        raise ErroAvaliacao(f'Processamento parado: memo enviado, aguardando resposta ({estado})')

    if estado in TAGS_CONCLUSAO_NOVO:
        logger.info('Fluxo: NOVO concluído - memos conferidos na árvore')
        registro.fluxo = 'NOVO - concluído'
        registro.prox_acao = ProxAcao.ASSINAR_DISA_DEPROC if estado == TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO else ProxAcao.ASSINAR_DEPROC
        return

    if estado is None:
        logger.info('Fluxo: NOVO sem marcador de estado - fluxo normal do início')
    else:
        logger.info(f'Fluxo: NOVO - retomada do fluxo normal (estado "{estado}")')
    processar_novo(driver, registro, bases, bases_mantis)


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------


def _classificar_e_processar(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso, bases_mantis: BasesMantis) -> None:
    novo, velho = tem_tag(registro, TAG_PROCESSO_NOVO), tem_tag(registro, TAG_PROCESSO_VELHO)
    if novo and velho:
        raise ErroAvaliacao('Processo marcado como NOVO e VELHO')
    if velho:
        _tratar_velho(driver, registro)
        return
    if novo:
        _tratar_novo(driver, registro, bases, bases_mantis)
        return

    tags_script = [t for t in registro.marcadores_sei if t in TAGS_SCRIPT]
    if tags_script:
        raise ErroAvaliacao(f'Marcadores do script sem marcador NOVO/VELHO: {tags_script}')

    # Marcadores manuais (ex.: PLANILHADO) não impedem a classificação
    if registro.docs_geacs:
        logger.info(f'Classificação: VELHO ({len(registro.docs_geacs)} documento(s) da GEACS na árvore)')
        registro.fluxo = 'VELHO - classificação'
        adicionar_tag(driver, registro, TAG_PROCESSO_VELHO)
        registro.prox_acao = ProxAcao.PROCESSAR_VELHO
        return

    logger.info('Classificação: NOVO (sem documentos da GEACS na árvore)')
    registro.fluxo = 'NOVO - classificação'
    adicionar_tag(driver, registro, TAG_PROCESSO_NOVO)
    processar_novo(driver, registro, bases, bases_mantis)


def _processar_linha(driver: webdriver.Remote, num_processo, bases: BasesUso, bases_mantis: BasesMantis) -> RegistroMain:
    registro = RegistroMain(num_processo=num_processo, data_execucao=AGORA)

    try:
        acessar_processo(driver, num_processo)
        registro.registrar_arvore(listar_documentos_arvore(driver))
        registrar_tags(registro, listar_marcadores(driver))
        logger.info(f'Árvore: {len(registro.tds_docs)} documento(s) | GEACS: {registro.qnt_docs_geacs_na_arvore} documento(s), {registro.qnt_memos_geacs_na_arvore} memorando(s)')
        logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')

        _classificar_e_processar(driver, registro, bases, bases_mantis)

    except (ErroAvaliacao, FormatoMemorandoInvalido, TextoMemoPendente) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')

    return registro


def main():
    for diretorio in [DIR_DADOS, DIR_INPUTS, DIR_CONTROLE, DIR_LOG, DIR_UI_ANTIGAS_XLS]:
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
