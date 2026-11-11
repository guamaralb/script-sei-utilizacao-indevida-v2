"""Fluxo DEPROC EXCLUIR DOCS (task run_deproc_excluir_docs), na unidade da
DEPROC: exclui todos os documentos da DEPROC (UNIDADE_DEPROC) do processo.

Para cada processo da aba deproc_excluir_docs de processos_a_processar.xlsx:
abre o processo, lista a árvore, seleciona cada documento da DEPROC (do último
para o primeiro) e o exclui (excluir_doc da sei_automacao). Documento que não
pode ser excluído (ex.: assinado ou já enviado) fica na lista dos não excluídos
e os demais seguem. No fim, relê a árvore para conferir.

Não lê nem adiciona marcadores e não altera a prox_acao: na planilha de
controle, só a coluna deproc_excluir_docs (RegistroDeprocExcluirDocs).
"""

import logging
import time
from datetime import datetime

from constantes import DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_DEPROC
from docs_processo import selecionar_doc
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
from Registro import RegistroDeprocExcluirDocs, registrar_erro, registrar_sem_acesso
from sei_automacao.documento import excluir_doc
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'deproc_excluir_docs'
FLUXO = 'DEPROC EXCLUIR DOCS - EXCLUIR DOCUMENTOS DA DEPROC'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_deproc_excluir_docs.log'

# Logo depois da exclusão, a árvore ainda mostra o documento: a conferência
# reabre o processo e relê a árvore por até este tempo (segundos)
TEMPO_CONFERENCIA = 15

logger = logging.getLogger(__name__)

# Navegador fechado: para o processo (e o loop), sem tentar os outros documentos
_SESSAO_ENCERRADA = (InvalidSessionIdException, NoSuchWindowException)


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def filtrar_docs_deproc(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in tds_docs if UNIDADE_DEPROC in doc['unidade']]


def _docs_deproc_restantes(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs) -> list[str]:
    """Documentos da DEPROC que continuam na árvore depois das exclusões.
    A árvore demora a refletir a exclusão: reabre o processo e relê até os
    excluídos sumirem ou passar TEMPO_CONFERENCIA."""
    acessar_processo(driver, registro.num_processo)
    limite = time.monotonic() + TEMPO_CONFERENCIA
    while True:
        restantes = [doc['numero_sei'] for doc in filtrar_docs_deproc(listar_documentos_arvore(driver))]
        ainda_na_arvore = [numero for numero in restantes if numero in registro.docs_excluidos]
        if not ainda_na_arvore or time.monotonic() >= limite:
            return restantes
        logger.debug(f'Excluído(s) ainda na árvore: {ainda_na_arvore}; relendo')
        time.sleep(1)


def excluir_docs_deproc(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs) -> None:
    # A exclusão exige o processo aberto na unidade; não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da DEPROC: nenhum documento excluído (não reaberto)')

    docs = filtrar_docs_deproc(listar_documentos_arvore(driver))
    registro.docs_deproc = [doc['numero_sei'] for doc in docs]
    logger.info(f'Documentos da DEPROC na árvore: {[_descrever(doc) for doc in docs] or "nenhum"}')

    # Do último para o primeiro: um documento posterior pode citar o anterior
    for doc in reversed(docs):
        try:
            selecionar_doc(driver, doc)
            excluir_doc(driver)
        except _SESSAO_ENCERRADA:
            raise
        except Exception:
            logger.warning(f'Documento não excluído: {_descrever(doc)} (assinado, já enviado ou sem permissão?)', exc_info=True)
            registro.docs_nao_excluidos.append(doc['numero_sei'])
            restaurar_navegador(driver)
            continue
        registro.docs_excluidos.append(doc['numero_sei'])
        logger.info(f'Documento excluído: {_descrever(doc)}')

    if not docs:
        return
    for numero in _docs_deproc_restantes(driver, registro):
        if numero in registro.docs_excluidos:
            # A exclusão não deu erro, mas o documento continua na árvore
            registro.docs_excluidos.remove(numero)
        if numero not in registro.docs_nao_excluidos:
            registro.docs_nao_excluidos.append(numero)
    if registro.docs_nao_excluidos:
        raise ErroAvaliacao(f'Documento(s) da DEPROC não excluído(s): {", ".join(registro.docs_nao_excluidos)}')


def _processar_linha(driver: webdriver.Remote, num_processo) -> RegistroDeprocExcluirDocs:
    registro = RegistroDeprocExcluirDocs(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        excluir_docs_deproc(driver, registro)

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except ErroAvaliacao as e:
        # Problema esperado: sem traceback
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
        driver = abrir_sei(UNIDADE_DEPROC)

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
