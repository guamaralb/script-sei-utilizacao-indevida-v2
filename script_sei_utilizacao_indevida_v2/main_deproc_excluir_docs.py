"""Fluxo DEPROC EXCLUIR DOCS (task run_deproc_excluir_docs), na unidade da
DEPROC: exclui os documentos da DEPROC (UNIDADE_DEPROC) gerados pelo fluxo
DEPROC (main_deproc_calcula_copa.py): o relatório de coparticipação em PDF,
reconhecido pelo nome na árvore, e o memo de resultado à GEACS, pelo assunto
no texto. Os outros documentos da DEPROC são mantidos.

Para cada processo da aba deproc_excluir_docs de processos_a_processar.xlsx:
abre o processo, lista a árvore, separa os documentos gerados pelo script,
seleciona cada um (do último para o primeiro) e o exclui (excluir_doc da
sei_automacao). Documento que não pode ser excluído (ex.: assinado ou já
enviado) ou memo que não pôde ser lido fica na lista dos não excluídos e os
demais seguem. No fim, relê a árvore para conferir e, se todos os gerados
foram excluídos, remove os marcadores da DEPROC (TAGS_DEPROC_REMOVIDOS_AO_EXCLUIR).

Não adiciona marcadores e não altera a prox_acao: na planilha de controle, só a
coluna deproc_excluir_docs e as colunas dos marcadores da DEPROC
(RegistroDeprocExcluirDocs).
"""

import logging
import re
import time
from datetime import datetime

from constantes import DIR_CONTROLE, DIR_INPUTS, DIR_LOG, UNIDADE_DEPROC
from docs_processo import filtrar_memos_unidade, ler_texto_doc, selecionar_doc
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
from relatorios_mantis import TIPO_DOC
from sei_automacao.documento import excluir_doc
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore, listar_marcadores
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import (
    TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA,
    TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA,
    TAG_DEPROC_RELATORIO_ANEXADO,
    TAG_DEPROC_TRATADO,
    registrar_tags,
    remover_tag,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import (
    PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA,
    PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA_ANTERIOR,
)

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'deproc_excluir_docs'
FLUXO = 'DEPROC EXCLUIR DOCS - EXCLUIR DOCUMENTOS DA DEPROC'

# Relatório de coparticipação (relatorio_deproc.incluir_relatorio_deproc):
# "PDF Coparticipação - <matrícula> - <AAAAMMDD_HHMMSS>"
_PADRAO_NOME_RELATORIO = re.compile(rf'^{re.escape(TIPO_DOC)}\s+Coparticipação - \d+ - \d{{8}}_\d{{6}}', re.IGNORECASE)

# Memo de resultado à GEACS (MemoGeacsCalculoCopa), assunto atual e anterior
_PADROES_ASSUNTO_MEMO = (PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA, PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA_ANTERIOR)

# Marcadores da DEPROC removidos depois de excluir os documentos, para o
# deproc_calcula_copa começar do início. O 01 por último: se a remoção falhar
# no meio, não sobra estado sem o 01 (marcadores inconsistentes)
TAGS_DEPROC_REMOVIDOS_AO_EXCLUIR = (
    TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA,
    TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA,
    TAG_DEPROC_RELATORIO_ANEXADO,
    TAG_DEPROC_TRATADO,
)

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


def eh_relatorio_gerado(doc: dict) -> bool:
    return _PADRAO_NOME_RELATORIO.match(doc['nome_arvore'].strip()) is not None


def eh_memo_gerado(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in _PADROES_ASSUNTO_MEMO)


def _separar_docs_gerados(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs, docs: list[dict]) -> list[dict]:
    """Documentos da DEPROC gerados pelo fluxo DEPROC, na ordem da árvore: os
    PDFs pelo nome e os memorandos pelo assunto no texto. Os outros vão para
    docs_mantidos; memo que não pôde ser lido, para docs_nao_excluidos."""
    memos = {doc['numero_sei'] for doc in filtrar_memos_unidade(docs, UNIDADE_DEPROC)}
    gerados = []
    for doc in docs:
        if eh_relatorio_gerado(doc):
            gerados.append(doc)
            continue
        if doc['numero_sei'] in memos:
            try:
                texto = ler_texto_doc(driver, doc)
            except _SESSAO_ENCERRADA:
                raise
            except Exception:
                logger.warning(f'Memorando não lido: {_descrever(doc)}; não será excluído', exc_info=True)
                registro.docs_nao_excluidos.append(doc['numero_sei'])
                restaurar_navegador(driver)
                continue
            if eh_memo_gerado(texto):
                gerados.append(doc)
                continue
        registro.docs_mantidos.append(doc['numero_sei'])
    return gerados


def _docs_gerados_restantes(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs) -> list[str]:
    """Documentos gerados pelo script que continuam na árvore depois das exclusões.
    A árvore demora a refletir a exclusão: reabre o processo e relê até os
    excluídos sumirem ou passar TEMPO_CONFERENCIA."""
    acessar_processo(driver, registro.num_processo)
    limite = time.monotonic() + TEMPO_CONFERENCIA
    while True:
        restantes = [doc['numero_sei'] for doc in filtrar_docs_deproc(listar_documentos_arvore(driver)) if doc['numero_sei'] in registro.docs_gerados]
        ainda_na_arvore = [numero for numero in restantes if numero in registro.docs_excluidos]
        if not ainda_na_arvore or time.monotonic() >= limite:
            return restantes
        logger.debug(f'Excluído(s) ainda na árvore: {ainda_na_arvore}; relendo')
        time.sleep(1)


def remover_marcadores_deproc(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs) -> None:
    """Remove os marcadores da DEPROC que o processo tiver (lidos agora)."""
    registrar_tags(registro, listar_marcadores(driver))
    registro.marcadores_lidos = True
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
    a_remover = [tag for tag in TAGS_DEPROC_REMOVIDOS_AO_EXCLUIR if tem_tag(registro, tag)]
    if not a_remover:
        logger.info('Nenhum marcador da DEPROC a remover')
        return
    for tag in a_remover:
        remover_tag(driver, registro, tag)


def excluir_docs_deproc(driver: webdriver.Remote, registro: RegistroDeprocExcluirDocs) -> None:
    # A exclusão exige o processo aberto na unidade; não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da DEPROC: nenhum documento excluído (não reaberto)')

    docs_deproc = filtrar_docs_deproc(listar_documentos_arvore(driver))
    registro.docs_deproc = [doc['numero_sei'] for doc in docs_deproc]
    logger.info(f'Documentos da DEPROC na árvore: {[_descrever(doc) for doc in docs_deproc] or "nenhum"}')

    docs = _separar_docs_gerados(driver, registro, docs_deproc)
    registro.docs_gerados = [doc['numero_sei'] for doc in docs]
    logger.info(f'Documentos gerados pelo deproc_calcula_copa: {[_descrever(doc) for doc in docs] or "nenhum"}')
    if registro.docs_mantidos:
        logger.info(f'Documentos da DEPROC mantidos (não gerados pelo script): {registro.docs_mantidos}')

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

    if docs:
        for numero in _docs_gerados_restantes(driver, registro):
            if numero in registro.docs_excluidos:
                # A exclusão não deu erro, mas o documento continua na árvore
                registro.docs_excluidos.remove(numero)
            if numero not in registro.docs_nao_excluidos:
                registro.docs_nao_excluidos.append(numero)
    if registro.docs_nao_excluidos:
        # Os marcadores ficam: o processo ainda tem documento gerado pelo script
        raise ErroAvaliacao(f'Documento(s) da DEPROC não excluído(s): {", ".join(registro.docs_nao_excluidos)}; marcadores da DEPROC mantidos')
    remover_marcadores_deproc(driver, registro)


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
