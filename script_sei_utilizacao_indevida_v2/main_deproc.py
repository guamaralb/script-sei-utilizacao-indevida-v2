"""Fluxo DEPROC (task run_deproc), na unidade da DEPROC: confere que o memo
DEPROC da GEACS está assinado, apura a coparticipação na base do MANTIS
(coparticipacao_deproc.py), anexa o relatório em PDF (relatorio_deproc.py) e
cria o memo de resultado da DEPROC à GEACS, no bloco próprio.

Usa os marcadores da unidade da DEPROC ("Script v2 DEPROC - ...", em
tags.py), como os da GEACS: 1 (tratado), 1.1 (relatório anexado, estado de
retomada) e 1.2 (memo no bloco, estado de conclusão). Dentro de cada etapa,
a retomada é pelo nome do PDF e pelo assunto do memo, na rodada (depois do
último memo da APIS destinado à GEACS).
"""

import logging
import re
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_DEPROC,
    BLOCO_MEMO_DEPROC_RESULTADO,
    CARGO_SIGNATARIO_DEPROC,
    DIR_CONTROLE,
    DIR_FLUXO_DEPROC_PDF,
    DIR_INPUTS,
    DIR_LOG,
    NOME_SIGNATARIO,
    NOME_SIGNATARIO_DEPROC,
    PADRAO_ASSINATURA_MEMO_DEPROC,
    UNIDADE_DEPROC,
    UNIDADE_GEACS,
)
from coparticipacao_deproc import MatriculasDivergentes, ResultadoDeproc, apurar_coparticipacao, carregar_base_deproc
from docs_processo import encontrar_memo_por_assunto
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from marcadores_disponiveis import garantir_marcadores_no_sei
from memos_sei import incluir_memo, registrar_numeros_memos
from planilha_controle import PlanilhaControleGeral
from processar_novo import obter_dados_ui
from processo_fechado import ProcessoFechadoNoSetor, tem_incluir_documento
from processos_a_processar import ler_processos_a_processar
from rede_propria import ErroAvaliacao
from Registro import ProxAcao, RegistroDeproc, registrar_erro
from relatorio_deproc import incluir_relatorio_deproc
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import (
    TAG_DEPROC_CONCLUIDO_MEMO,
    TAG_DEPROC_RELATORIO_ANEXADO,
    TAG_DEPROC_TRATADO,
    TAGS_DEPROC,
    TAGS_ESTADO_DEPROC,
    MarcadoresInconsistentes,
    adicionar_tag,
    adicionar_tag_se_ausente,
    conferir_marcadores_deproc,
    estado_atual,
    registrar_tags,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeprocResultado import PADRAO_ASSUNTO_MEMO_DEPROC_RESULTADO, MemoDeprocResultado
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'deproc'
FLUXO = 'DEPROC - COPARTICIPAÇÃO'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_deproc.log'

_PADRAO_ASSINATURA = re.compile(PADRAO_ASSINATURA_MEMO_DEPROC, re.IGNORECASE)

logger = logging.getLogger(__name__)


def _memo_deproc_assinado(driver: webdriver.Remote, registro: RegistroDeproc) -> DocArvore:
    """O memo DEPROC da GEACS na rodada, assinado pela Bruna. Sem o memo ou
    sem a assinatura: ErroAvaliacao, sem ação no SEI."""
    encontrado = encontrar_memo_por_assunto(driver, registro.docs_rodada, PADRAO_ASSUNTO_MEMO_DEPROC, 'DEPROC (da GEACS)', UNIDADE_GEACS)
    if encontrado is None:
        raise ErroAvaliacao('Memo DEPROC da GEACS não encontrado depois do último memo da APIS destinado à GEACS')

    memo, texto = encontrado
    registro.memo_deproc_geacs_sei = memo['numero_sei']
    registro.memo_deproc_assinado = _PADRAO_ASSINATURA.search(texto) is not None
    if not registro.memo_deproc_assinado:
        raise ErroAvaliacao(f'Memo DEPROC da GEACS ({memo["numero_sei"]}) ainda não assinado por {NOME_SIGNATARIO}')
    logger.info(f'Memo DEPROC da GEACS assinado: {memo["numero_sei"]}')
    return memo


def _registrar_resultado(registro: RegistroDeproc, resultado: ResultadoDeproc) -> None:
    registro.linhas_base_deproc = resultado.linhas_processo
    registro.linhas_fora_periodo_deproc = resultado.linhas_fora_periodo
    registro.atendimentos_deproc = len(resultado.atendimentos)
    registro.valor_total_coparticipacao = resultado.totais.coparticipacao
    registro.valor_total_descontado = resultado.totais.descontado
    registro.valor_total_em_aberto = resultado.totais.em_aberto


def _montar_memo(registro: RegistroDeproc, dados: DadosUI, resultado: ResultadoDeproc, memo_deproc_geacs: DocArvore, doc_relatorio: str | None) -> MemoDeprocResultado:
    return MemoDeprocResultado(
        dados=dados,
        resultado=resultado,
        doc_relatorio=doc_relatorio,
        memo_apis=registro.memo_apis,
        memo_deproc_geacs=memo_deproc_geacs,
        nome_signatario=NOME_SIGNATARIO_DEPROC,
        cargo_signatario=CARGO_SIGNATARIO_DEPROC,
    )


def _conferir_configuracao() -> None:
    """Antes de qualquer documento: sem bloco ou signatário, o memo não pode
    ser criado, e o relatório ficaria sem memo."""
    if BLOCO_MEMO_DEPROC_RESULTADO is None:
        raise ErroAvaliacao('Bloco do memo de resultado da DEPROC não configurado (BLOCO_MEMO_DEPROC_RESULTADO)')
    if NOME_SIGNATARIO_DEPROC is None:
        raise ErroAvaliacao('Signatário do memo de resultado da DEPROC não configurado (NOME_SIGNATARIO_DEPROC)')


def _conferir_marcadores(registro: RegistroDeproc, momento: str) -> None:
    try:
        conferir_marcadores_deproc(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def processar_deproc(driver: webdriver.Remote, registro: RegistroDeproc, base: pd.DataFrame) -> None:
    registrar_tags(registro, listar_marcadores(driver))
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
    _conferir_marcadores(registro, 'no início da passagem')

    estado = estado_atual(registro, TAGS_ESTADO_DEPROC)
    if estado == TAG_DEPROC_CONCLUIDO_MEMO:
        logger.info('Concluído: memo de resultado da DEPROC já no bloco')
        registro.prox_acao = ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO
        return

    # Na DEPROC, o processo precisa estar aberto na unidade (enviado pela
    # GEACS); não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da DEPROC: não está aberto na unidade (não reaberto)')
    # Antes de listar a árvore: a conferência recarrega a página e fecha as
    # pastas. Sem os marcadores cadastrados na DEPROC, nada é feito
    garantir_marcadores_no_sei(driver, list(TAGS_DEPROC))
    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')

    dados = obter_dados_ui(driver, registro)
    memo_deproc_geacs = _memo_deproc_assinado(driver, registro)

    try:
        resultado = apurar_coparticipacao(base, registro.num_processo, dados)
    except MatriculasDivergentes as e:
        registro.matriculas_divergentes_deproc = e.divergentes
        raise
    _registrar_resultado(registro, resultado)

    # Memo montado antes do relatório só para conferir texto, bloco e
    # signatário: nada é anexado se o memo não puder ser criado
    _conferir_configuracao()
    _montar_memo(registro, dados, resultado, memo_deproc_geacs, '<relatório a anexar>')

    adicionar_tag_se_ausente(driver, registro, TAG_DEPROC_TRATADO)
    doc_relatorio = None
    if not resultado.atendimentos.empty:
        # Com o 1.1 (retomada), o relatório é encontrado pelo nome
        doc_relatorio = incluir_relatorio_deproc(driver, registro, resultado, dados)
        if estado != TAG_DEPROC_RELATORIO_ANEXADO:
            adicionar_tag(driver, registro, TAG_DEPROC_RELATORIO_ANEXADO)
    memo = _montar_memo(registro, dados, resultado, memo_deproc_geacs, doc_relatorio)
    incluir_memo(
        driver,
        registro,
        memo,
        BLOCO_MEMO_DEPROC_RESULTADO,
        'memo_deproc_resultado',
        'de resultado da DEPROC',
        PADRAO_ASSUNTO_MEMO_DEPROC_RESULTADO,
        unidade=UNIDADE_DEPROC,
    )
    adicionar_tag(driver, registro, TAG_DEPROC_CONCLUIDO_MEMO)
    registrar_numeros_memos(driver, registro, UNIDADE_DEPROC)
    registro.prox_acao = ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO


def _processar_linha(driver: webdriver.Remote, num_processo, base: pd.DataFrame) -> RegistroDeproc:
    registro = RegistroDeproc(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        processar_deproc(driver, registro, base)
        _conferir_marcadores(registro, 'no fim da passagem')

    except (ErroAvaliacao, FormatoMemorandoInvalido, TextoMemoPendente) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    return registro


def main():
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG, DIR_FLUXO_DEPROC_PDF]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')

        processos = ler_processos_a_processar(SCRIPT)
        total = len(processos)

        base = carregar_base_deproc(ARQ_BASE_DEPROC)
        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        driver = abrir_sei(UNIDADE_DEPROC)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, base)
                registros_processados.append(registro.to_dict())
                controle.registrar(registros_processados[-1])

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
        log_resumo(logger, registros_processados)
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
