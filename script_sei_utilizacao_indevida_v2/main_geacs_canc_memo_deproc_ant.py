"""Fluxo GEACS CANC MEMO DEPROC ANT (task run_geacs_canc_memo_deproc_ant):
cancela o memo DEPROC antigo da GEACS - Utilização, que será ou já foi
substituído por uma nova versão.

Para cada processo da aba geacs_canc_memo_deproc_ant de
processos_a_processar.xlsx: abre o processo, procura entre os memorandos da
GEACS (toda a árvore) o que casa com PADRAO_MEMO_DEPROC_ANTIGO e o cancela
(cancelar_doc da sei_automacao). Não lê nem adiciona marcadores e não altera
a prox_acao: na planilha de controle, só as colunas canc_memo_deproc_ant_*.
"""

import logging
import re
from datetime import datetime

from constantes import DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_GEACS
from docs_processo import filtrar_memos_geacs, ler_texto_doc, selecionar_doc
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from planilha_controle import PlanilhaControleGeral
from processo_fechado import ProcessoFechadoNoSetor, tem_incluir_documento
from processos_a_processar import ler_processos_a_processar
from rede_propria import ErroAvaliacao
from Registro import RegistroCancMemoDeprocAnt, registrar_erro, registrar_sem_acesso
from sei_automacao.documento import cancelar_doc
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_canc_memo_deproc_ant'
FLUXO = 'CANC MEMO DEPROC ANT - CANCELAR MEMO DEPROC ANTIGO'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_canc_memo_deproc_ant.log'

MOTIVO_CANCELAMENTO = 'Documento será ou já foi substituído por uma nova versão'

# TODO: definir o padrão que identifica o memo DEPROC antigo no texto do
# memorando da GEACS (ex.: o assunto antigo e a data, como
# re.compile(r'Levantamento de coparticipação - utilização indevida', re.IGNORECASE)).
# Com None, nenhum documento é cancelado: cada processo para com erro
PADRAO_MEMO_DEPROC_ANTIGO: re.Pattern | None = None

logger = logging.getLogger(__name__)


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def encontrar_memo_deproc_antigo(driver: webdriver.Remote, tds_docs: list[dict]) -> dict:
    """O memorando da GEACS (toda a árvore) que casa com o padrão. Nenhum ou
    mais de um: ErroAvaliacao, sem cancelar nada."""
    if PADRAO_MEMO_DEPROC_ANTIGO is None:
        raise ErroAvaliacao('Padrão do memo DEPROC antigo não definido (PADRAO_MEMO_DEPROC_ANTIGO): nenhum documento cancelado')

    memos = filtrar_memos_geacs(tds_docs)
    encontrados = [memo for memo in memos if PADRAO_MEMO_DEPROC_ANTIGO.search(ler_texto_doc(driver, memo))]
    logger.info(f'{len(memos)} memorando(s) da GEACS; memo DEPROC antigo: {[_descrever(m) for m in encontrados] or "nenhum"}')
    if not encontrados:
        raise ErroAvaliacao('Memo DEPROC antigo não encontrado entre os memorandos da GEACS')
    if len(encontrados) > 1:
        raise ErroAvaliacao(f'Mais de um memo DEPROC antigo ({", ".join(m["numero_sei"] for m in encontrados)}): nenhum cancelado; conferir manualmente')
    return encontrados[0]


def cancelar_memo_deproc_antigo(driver: webdriver.Remote, registro: RegistroCancMemoDeprocAnt) -> None:
    # O cancelamento exige o processo aberto na unidade; não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" (fechado no setor): memo não cancelado (não reaberto)')
    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s) | GEACS: {registro.qnt_memos_geacs_na_arvore} memorando(s)')

    memo = encontrar_memo_deproc_antigo(driver, registro.tds_docs)
    registro.canc_memo_deproc_ant_sei = memo['numero_sei']
    registro.canc_memo_deproc_ant_nome = memo['nome_arvore']

    selecionar_doc(driver, memo)
    try:
        cancelar_doc(driver, MOTIVO_CANCELAMENTO)
    except TimeoutException as e:
        raise ErroAvaliacao(f'Opção "Cancelar Documento" indisponível para {_descrever(memo)} (já cancelado, assinado ou sem permissão)') from e
    registro.canc_memo_deproc_ant_cancelado = True
    logger.info(f'Memo DEPROC antigo cancelado: {_descrever(memo)} | Motivo: "{MOTIVO_CANCELAMENTO}"')


def _processar_linha(driver: webdriver.Remote, num_processo) -> RegistroCancMemoDeprocAnt:
    registro = RegistroCancMemoDeprocAnt(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        cancelar_memo_deproc_antigo(driver, registro)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except ErroAvaliacao as e:
        # Problema esperado nos dados: sem traceback
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

                registro = _processar_linha(driver, num_processo)
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
