"""Fluxo GEACS CANC MEMO DEPROC ANT (task run_geacs_canc_memo_deproc_ant):
cancela os memos DEPROC antigos da GEACS - Utilização, que serão ou já foram
substituídos por uma nova versão.

Para cada processo da aba geacs_canc_memo_deproc_ant de
processos_a_processar.xlsx: abre o processo, lê todos os memorandos da GEACS
(toda a árvore) e cancela (cancelar_doc da sei_automacao) todos os que têm os
três trechos de TRECHOS_MEMO_DEPROC_ANTIGO e são datados antes de
DATA_CORTE_MEMO_DEPROC_ANTIGO (15/10/2026). Não lê nem adiciona marcadores e não altera
a prox_acao: na planilha de controle, só as colunas canc_memo_deproc_ant_*.
"""

import logging
import re
from datetime import datetime

from constantes import DATA_CORTE_MEMO_DEPROC_ANTIGO, DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_GEACS
from docs_processo import data_memo, filtrar_memos_geacs, ler_texto_doc, selecionar_doc
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
from sei_automacao.processo import acessar_processo, listar_documentos_arvore
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_canc_memo_deproc_ant'
FLUXO = 'CANC MEMO DEPROC ANT - CANCELAR MEMO DEPROC ANTIGO'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_canc_memo_deproc_ant.log'

MOTIVO_CANCELAMENTO = 'Documento será ou já foi substituído por uma nova versão'

# Trechos que o memo DEPROC antigo tem (todos). Espaços, quebras de linha e
# maiúsculas são ignorados; o hífen do assunto pode ser "-" ou "–". "Para:
# IPSEMG/DEPROC" vale também para "IPSEMG/DEPROC-Utilização"
TRECHOS_MEMO_DEPROC_ANTIGO = (
    re.compile(r'Para:\s*IPSEMG/DEPROC', re.IGNORECASE),
    re.compile(r'Assunto:\s*Levantamento\s+de\s+coparticipação\s*[-–]\s*utilização\s+indevida\s+da\s+assistência\s+à\s+saúde', re.IGNORECASE),
    re.compile(r'levantamento\s+dos\s+valores\s+de\s+coparticipação\s+referentes\s+aos\s+atendimentos\s+efetivamente\s+realizados', re.IGNORECASE),
)

logger = logging.getLogger(__name__)


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def eh_memo_deproc_antigo(texto: str) -> bool:
    return all(padrao.search(texto) for padrao in TRECHOS_MEMO_DEPROC_ANTIGO)


def encontrar_memos_deproc_antigos(driver: webdriver.Remote, tds_docs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Os memorandos da GEACS (toda a árvore) com os três trechos: os datados
    antes de DATA_CORTE_MEMO_DEPROC_ANTIGO (a cancelar) e os sem data legível
    (não dá para saber se são antigos)."""
    memos = filtrar_memos_geacs(tds_docs)
    a_cancelar, sem_data = [], []
    for memo in memos:
        texto = ler_texto_doc(driver, memo)
        if not eh_memo_deproc_antigo(texto):
            continue
        data = data_memo(texto)
        if data is None:
            logger.warning(f'Memo DEPROC antigo sem data legível: {_descrever(memo)}')
            sem_data.append(memo)
        elif data < DATA_CORTE_MEMO_DEPROC_ANTIGO:
            a_cancelar.append(memo)
        else:
            logger.info(f'Memo DEPROC de {data:%d/%m/%Y} (a partir de {DATA_CORTE_MEMO_DEPROC_ANTIGO:%d/%m/%Y}): não é cancelado: {_descrever(memo)}')
    logger.info(f'{len(memos)} memorando(s) da GEACS; memos DEPROC antigos a cancelar: {[_descrever(m) for m in a_cancelar] or "nenhum"}')
    return a_cancelar, sem_data


def cancelar_memos_deproc_antigos(driver: webdriver.Remote, registro: RegistroCancMemoDeprocAnt) -> None:
    # O cancelamento exige o processo aberto na unidade; não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" (fechado no setor): nenhum memo cancelado (não reaberto)')
    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s) | GEACS: {registro.qnt_memos_geacs_na_arvore} memorando(s)')

    a_cancelar, sem_data = encontrar_memos_deproc_antigos(driver, registro.tds_docs)
    registro.canc_memo_deproc_ant_nao_cancelados = [memo['numero_sei'] for memo in sem_data]
    sem_opcao = []
    for memo in a_cancelar:
        selecionar_doc(driver, memo)
        try:
            cancelar_doc(driver, MOTIVO_CANCELAMENTO)
        except TimeoutException:
            # Já cancelado, assinado ou sem permissão: segue para os outros
            logger.warning(f'Opção "Cancelar Documento" indisponível: {_descrever(memo)}')
            sem_opcao.append(memo['numero_sei'])
            continue
        registro.canc_memo_deproc_ant_sei.append(memo['numero_sei'])
        registro.canc_memo_deproc_ant_nome.append(memo['nome_arvore'])
        registro.canc_memo_deproc_ant_cancelado = True
        logger.info(f'Memo DEPROC antigo cancelado: {_descrever(memo)} | Motivo: "{MOTIVO_CANCELAMENTO}"')
    registro.canc_memo_deproc_ant_nao_cancelados += sem_opcao

    problemas = []
    if sem_opcao:
        problemas.append(f'opção "Cancelar Documento" indisponível (já cancelado, assinado ou sem permissão): {", ".join(sem_opcao)}')
    if sem_data:
        problemas.append(f'memo DEPROC antigo sem data legível (não cancelado; conferir manualmente): {", ".join(m["numero_sei"] for m in sem_data)}')
    if problemas:
        raise ErroAvaliacao(f'Memo(s) DEPROC antigo(s) não cancelado(s): {"; ".join(problemas)}')


def _processar_linha(driver: webdriver.Remote, num_processo) -> RegistroCancMemoDeprocAnt:
    registro = RegistroCancMemoDeprocAnt(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        cancelar_memos_deproc_antigos(driver, registro)

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
