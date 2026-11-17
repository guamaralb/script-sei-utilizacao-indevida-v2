"""Fluxo GEACS TODAS INFOS (task run_geacs_todas_infos), na unidade da GEACS:
retorno final à APIS (MemoApisComTodasAsInformacoes) depois do retorno da
DEPROC.

Para cada processo da aba geacs_todas_infos de processos_a_processar.xlsx:

1. lê os marcadores e confere a combinação (tags.conferir_marcadores). Com o
   01.12 (memo no bloco) ou o 01.12.1 (encaminhado), só registra a prox_acao;
   sem o 01.10.1 - Aguarda DEPROC: Coparticipação, para com erro;
2. sem "Incluir Documento" (fechado no setor), para sem reabrir;
3. lê o último memo da APIS destinado à GEACS (define a rodada) e procura o
   memo de resultado da DEPROC (MemoGeacsCalculoCopa) na rodada, assinado;
4. caminho: direto à DEPROC ou pela DISA antes (memo da GEACS à DISA na
   rodada). Pela DISA, para com erro: sem resposta da DISA, ou com resposta
   (leitura ainda não implementada, TODO);
5. lê e recalcula os valores (todas_infos.apurar_todas_infos): divergência
   para o processo, sem criar o memo;
6. cria o memo à APIS, insere no bloco BLOCO_MEMO_APIS_TODAS_INFOS e adiciona
   o 01.12 - No Bloco APIS: Todas as Infos (remove o 01.10.1). Retomada: o
   memo já na rodada (pelo assunto) não é recriado.

Depois da assinatura, quem encaminha coloca à mão o 01.12.1 - Encaminhado
APIS: Todas as Infos e remove o 01.12.
"""

import logging
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_APIS,
    ARQ_BASE_DEPROC,
    ARQ_MANTIS_REDE_CREDENCIADA,
    ARQ_MANTIS_REDE_CREDENCIADA_DEPS_NAO_ENCONTRADOS,
    ARQ_MANTIS_REDE_PROPRIA,
    ARQ_MANTIS_REDE_PROPRIA_DEPS_NAO_ENCONTRADOS,
    ARQ_USO_REDE_PROPRIA,
    BLOCO_MEMO_APIS_TODAS_INFOS,
    CARGO_SIGNATARIO_GERENCIA,
    DIR_CONTROLE,
    DIR_INPUTS,
    DIR_LOG,
    NOME_SIGNATARIO_GERENCIA,
    UNIDADE_GEACS,
)
from coparticipacao_deproc import carregar_base_deproc
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from mantis import BasesMantis, carregar_bases_mantis
from marcadores_disponiveis import garantir_marcadores_no_sei
from memos_sei import incluir_memo, registrar_numeros_memos
from planilha_controle import PlanilhaControleGeral
from processar_novo import obter_dados_ui
from processo_fechado import ProcessoFechadoNoSetor, tem_incluir_documento
from processos_a_processar import ler_processos_a_processar
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import PROX_ACAO_POR_CONCLUSAO, PROX_ACAO_POR_NO_BLOCO, ProxAcao, RegistroTodasInfos, registrar_erro, registrar_sem_acesso
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import (
    TAG_AGUARDA_DEPROC_COPARTICIPACAO,
    TAG_ENCAMINHADO_APIS_TODAS_INFOS,
    TAG_NO_BLOCO_APIS_TODAS_INFOS,
    MarcadoresInconsistentes,
    adicionar_tag,
    conferir_marcadores,
    estado_atual,
    registrar_tags,
)
from todas_infos import apurar_todas_infos, identificar_caminho, memo_calculo_copa

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, MemoApisComTodasAsInformacoes

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_todas_infos'
FLUXO = 'TODAS INFOS - RETORNO FINAL À APIS'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_todas_infos.log'

logger = logging.getLogger(__name__)


class SemAguardaDeproc(ErroAvaliacao):
    """O processo não está aguardando o retorno da DEPROC (01.10.1)."""


def _conferir_marcadores(registro: RegistroTodasInfos, momento: str) -> None:
    try:
        conferir_marcadores(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def processar_todas_infos(
    driver: webdriver.Remote,
    registro: RegistroTodasInfos,
    bases: BasesUso,
    bases_mantis: BasesMantis,
    base_deproc: pd.DataFrame,
) -> None:
    registrar_tags(registro, listar_marcadores(driver))
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
    _conferir_marcadores(registro, 'no início da passagem')

    estado = estado_atual(registro)
    if estado == TAG_NO_BLOCO_APIS_TODAS_INFOS:
        logger.info('Memo à APIS (todas as informações) no bloco: aguarda assinatura')
        registro.prox_acao = PROX_ACAO_POR_NO_BLOCO[estado]
        return
    if estado == TAG_ENCAMINHADO_APIS_TODAS_INFOS:
        logger.info('Memo à APIS (todas as informações) já encaminhado')
        registro.prox_acao = PROX_ACAO_POR_CONCLUSAO[estado]
        return
    if estado != TAG_AGUARDA_DEPROC_COPARTICIPACAO:
        raise SemAguardaDeproc(f'Processo sem o marcador "{TAG_AGUARDA_DEPROC_COPARTICIPACAO}" (estado atual: {estado or "nenhum"})')

    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da GEACS: nenhum memo criado (não reaberto)')
    garantir_marcadores_no_sei(driver, [TAG_NO_BLOCO_APIS_TODAS_INFOS])

    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')
    dados_ui = obter_dados_ui(driver, registro)
    _, texto_memo_copa = memo_calculo_copa(driver, registro)
    identificar_caminho(driver, registro)
    dados_memo, beneficiarios, doc_copart = apurar_todas_infos(driver, registro, dados_ui, texto_memo_copa, bases, bases_mantis, base_deproc)
    registro.doc_coparticipacao_sei = doc_copart

    # Montado antes de qualquer ação no SEI
    memo = MemoApisComTodasAsInformacoes(
        dados=dados_memo,
        memo_apis=registro.memo_apis,
        beneficiarios=beneficiarios,
        doc_coparticipacao=doc_copart,
        nome_signatario=NOME_SIGNATARIO_GERENCIA,
        cargo_signatario=CARGO_SIGNATARIO_GERENCIA,
    )
    registro.fluxo = f'{FLUXO} - caminho {registro.caminho_todas_infos}'
    incluir_memo(
        driver,
        registro,
        memo,
        BLOCO_MEMO_APIS_TODAS_INFOS,
        'memo_apis_todas_infos',
        'à APIS (todas as informações)',
        PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES,
    )
    adicionar_tag(driver, registro, TAG_NO_BLOCO_APIS_TODAS_INFOS)
    registrar_numeros_memos(driver, registro)
    registro.prox_acao = ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS


def _processar_linha(driver: webdriver.Remote, num_processo, bases: BasesUso, bases_mantis: BasesMantis, base_deproc: pd.DataFrame) -> RegistroTodasInfos:
    registro = RegistroTodasInfos(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        processar_todas_infos(driver, registro, bases, bases_mantis, base_deproc)
        _conferir_marcadores(registro, 'no fim da passagem')

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except (ErroAvaliacao, FormatoMemorandoInvalido) as e:
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

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')

        processos = ler_processos_a_processar(SCRIPT)
        total = len(processos)

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_APIS)
        bases_mantis = carregar_bases_mantis(
            ARQ_MANTIS_REDE_PROPRIA,
            ARQ_MANTIS_REDE_CREDENCIADA,
            ARQ_MANTIS_REDE_PROPRIA_DEPS_NAO_ENCONTRADOS,
            ARQ_MANTIS_REDE_CREDENCIADA_DEPS_NAO_ENCONTRADOS,
        )
        base_deproc = carregar_base_deproc(ARQ_BASE_DEPROC)

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        # Login e troca para a unidade da GEACS
        driver = abrir_sei(UNIDADE_GEACS)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, bases, bases_mantis, base_deproc)
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
