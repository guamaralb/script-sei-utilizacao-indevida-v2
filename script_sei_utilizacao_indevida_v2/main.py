import logging
from datetime import datetime

import pandas as pd
from constantes import (
    ARQ_BASE_APIS,
    ARQ_MANTIS_REDE_CREDENCIADA,
    ARQ_MANTIS_REDE_PROPRIA,
    ARQ_USO_REDE_PROPRIA,
    DIR_CONTROLE,
    DIR_DADOS,
    DIR_INPUTS,
    DIR_LOG,
    DIR_UTILIZACOES_MANTIS_PDF,
)
from docs_processo import encontrar_memos_velho
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
from planilha_controle import PlanilhaControleGeral
from processar_novo import processar_novo
from processo_fechado import exigir_processo_aberto
from rede_propria import BasesUso, ErroAvaliacao, carregar_bases
from Registro import ProxAcao, RegistroMain, registrar_erro
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver
from sessao_sei import abrir_sei, sessao_encerrada
from tags import (
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
    TAGS_PARADA_NOVO,
    TAGS_TRATAMENTO_MANUAL,
    MarcadoresInconsistentes,
    adicionar_tag,
    adicionar_tag_se_ausente,
    conferir_marcadores,
    eh_velho_pelos_marcadores,
    estado_atual,
    registrar_tags,
    remover_tag,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'main'

DIR_UI_ANTIGAS_XLS = DIR_DADOS / 'utilizacoes' / 'antigas' / 'xlsx'

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'

logger = logging.getLogger(__name__)

# Os 1.11 (VELHO, versão anterior) não chegam aqui: o VELHO é separado antes
_PROX_ACAO_POR_CONCLUSAO = {
    TAG_MEMO_DEPROC_COPARTICIPACAO: ProxAcao.ASSINAR_DEPROC,
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO: ProxAcao.ASSINAR_DISA_DEPROC,
}


def _conferir_marcadores(registro: RegistroMain, momento: str) -> None:
    try:
        conferir_marcadores(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def _sair_da_espera_do_fluxo_normal(driver: webdriver.Remote, registro: RegistroMain) -> None:
    """O VELHO não segue o fluxo normal: não fica aguardando por ele."""
    if tem_tag(registro, TAG_AGUARDA_FLUXO_NORMAL):
        remover_tag(driver, registro, TAG_AGUARDA_FLUXO_NORMAL)


def _separar_velho(driver: webdriver.Remote, registro: RegistroMain) -> None:
    """Processo VELHO: marcado e não processado.

    TODO: definir o fluxo dos processos VELHOS. Todos os processos com o
    marcador VELHO (0) ou com o 1.3 da versão anterior, e os identificados
    na execução, devem passar por ele."""
    registro.velho = True
    manuais = TAGS_TRATAMENTO_MANUAL.intersection(registro.marcadores_atuais)
    if manuais:
        logger.info(f'VELHO tratado manualmente ({sorted(manuais)}): fora do escopo')
        registro.fluxo = 'VELHO - tratado manualmente'
        registro.prox_acao = ProxAcao.FORA_DO_ESCOPO
        _sair_da_espera_do_fluxo_normal(driver, registro)
        return

    logger.info('Fluxo: VELHO - não processado (fluxo ainda não definido)')
    registro.fluxo = 'VELHO - não processado'
    garantir_marcadores_no_sei(driver, [TAG_PROCESSO_VELHO])
    adicionar_tag_se_ausente(driver, registro, TAG_PROCESSO_VELHO)
    _sair_da_espera_do_fluxo_normal(driver, registro)
    registro.prox_acao = ProxAcao.VELHO_AGUARDAR_DEFINICAO


def _eh_velho_pelo_texto(driver: webdriver.Remote, registro: RegistroMain) -> bool:
    """Memos da GEACS à DISA e à DEPROC (seguidos) antes da data de corte."""
    memos = encontrar_memos_velho(driver, registro.tds_docs)
    if memos is None:
        return False
    registro.memos_velho_sei = [memo['numero_sei'] for memo in memos]
    return True


def _tratar(driver: webdriver.Remote, registro: RegistroMain, bases: BasesUso, bases_mantis: BasesMantis) -> None:
    """Separa o processo VELHO e decide, pelos marcadores, se o processo
    está parado, concluído ou segue (do início ou retomando) para o fluxo de
    processar_novo."""
    _conferir_marcadores(registro, 'no início da passagem')
    if eh_velho_pelos_marcadores(registro):
        _separar_velho(driver, registro)
        return

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

    if estado is None and tem_tag(registro, TAG_MEMO_DEPROC_NO_BLOCO):
        logger.info('Fluxo: concluído na versão anterior (só memo DEPROC)')
        registro.fluxo = 'concluído (versão anterior)'
        registro.prox_acao = ProxAcao.ASSINAR_DEPROC
        return

    # Antes de qualquer memo: o VELHO não pode receber memos do fluxo atual
    if _eh_velho_pelo_texto(driver, registro):
        _separar_velho(driver, registro)
        return

    if not tem_tag(registro, TAG_PROCESSO_NOVO):
        # Inclusive os que já têm documento da GEACS ou o antigo
        # "2 - Processo VELHO": a APIS pede para refazer a consulta
        logger.info('Classificação: processo sem o marcador NOVO - fluxo do início')
        registro.fluxo = 'NOVO - classificação'
        adicionar_tag(driver, registro, TAG_PROCESSO_NOVO)
    elif estado is None:
        logger.info('Fluxo: NOVO - do início')
    elif estado == TAG_AGUARDA_FLUXO_NORMAL:
        # O próximo estado do fluxo substitui este
        logger.info('Fluxo: NOVO - do início (veio do fluxo ALT 1)')
    else:
        logger.info(f'Fluxo: retomada (estado "{estado}")')
    processar_novo(driver, registro, bases, bases_mantis)


def _processar_linha(driver: webdriver.Remote, num_processo, bases: BasesUso, bases_mantis: BasesMantis) -> RegistroMain:
    registro = RegistroMain(num_processo=num_processo, data_execucao=AGORA)

    try:
        acessar_processo(driver, num_processo)
        registrar_tags(registro, listar_marcadores(driver))
        exigir_processo_aberto(driver)
        registro.registrar_arvore(listar_documentos_arvore(driver))
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

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        logger.info(f'Log: {ARQ_LOG}')

        df_processos = pd.read_excel(
            io=ARQ_PROCESSOS_NAO_PROCESSADOS,
            sheet_name='fluxo',
        )
        total = len(df_processos)
        logger.info(f'{total} processo(s) lido(s) de {ARQ_PROCESSOS_NAO_PROCESSADOS.name}')

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_APIS)
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

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    break

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
