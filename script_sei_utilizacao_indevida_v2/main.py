import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from processar_novo import processar_novo
from processar_velho import processar_velho
from Registro import RegistroMain
from sei_automacao.auth.login import efetuar_login
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import adicionar_marcador
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo
from selenium import webdriver

load_dotenv()

SEI_LOGIN = os.getenv('SEI_LOGIN')
SEI_SENHA = os.getenv('SEI_SENHA')
SEI_ORGAO = os.getenv('SEI_ORGAO')

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

DIR_BASE = Path(__file__).resolve().parent.parent

DIR_DADOS = DIR_BASE / 'dados'

DIR_INPUTS = DIR_DADOS / 'inputs'
DIR_CONTROLE = DIR_DADOS / 'controle'
DIR_LOG = DIR_BASE / 'logs'
DIR_UI = DIR_DADOS / 'utilizacoes'

DIR_UI_NOVAS = DIR_UI / 'novas'
DIR_UI_ANTIGAS = DIR_UI / 'antigas'

DIR_UI_NOVAS_XLS = DIR_UI_NOVAS / 'xlsx'
DIR_UI_NOVAS_PDF = DIR_UI_NOVAS / 'pdf'

DIR_UI_ANTIGAS_XLS = DIR_UI_ANTIGAS / 'xlsx'
DIR_UI_ANTIGAS_PDF = DIR_UI_ANTIGAS / 'pdf'

for diretorio in [DIR_DADOS, DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
    diretorio.mkdir(parents=True, exist_ok=True)

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_PROCESSOS_PROCESSADOS = (
    DIR_CONTROLE / f'processos_processados_{AGORA}.xlsx'
)
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'

_NUM_MEMOS_PROCESSO_NOVO = 2
_TAG_PROCESSO_NOVO = 'Script v2 - Processo NOVO'
_TAG_PROCESSO_VELHO = 'Script v2 - Processo VELHO'
_TAG_PERIODO_VAR_DEP = 'Script v2 - Período Variável Para Dependentes'
_TAG_MEMOS_NO_BLOCO = 'Script v2 - Memos DISA e DEPROC no bloco'
_TAG_PLANILHADO = 'PLANILHADO'
_TAG_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'
_TAG_RELATORIO_UI_TRANSFORMADO_PDF = (
    'Script v2 - Rel. de UI Velho Transformado em PDF'
)
_TAG_NOVO_RELATORIO_UI_GERADO = 'Script v2 - Novo Rel. de UI Gerado'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ARQ_LOG, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger()


@dataclass
class ContextoLinha:
    driver: object
    tds_docs: list
    docs_geacs: list
    tags: list

    @property
    def quant_docs_geacs(self) -> int:
        return len(self.docs_geacs)


def _filtrar_docs_geacs(tds_docs):
    return [
        doc
        for doc in tds_docs
        if 'IPSEMG/GEACS - Utilização' in doc['unidade']
    ]


def _tratar_sem_marcadores(ctx, registro):
    if len(ctx.docs_geacs) > 0:
        adicionar_marcador(ctx.driver, _TAG_PROCESSO_VELHO)
        registro.tag_processo_velho = True
        registro.prox_acao = 'Processar processos VELHOS'
        return registro

    adicionar_marcador(ctx.driver, _TAG_PROCESSO_NOVO)
    registro.tag_processo_novo = True
    return processar_novo(
        ctx.driver,
        registro,
        ctx.tds_docs,
        _TAG_PERIODO_VAR_DEP,
        _TAG_MEMOS_NO_BLOCO,
    )


def _tratar_tag_novo_sem_tag_memos_no_bloco(ctx, registro):
    registro.tag_processo_novo = True
    quant_docs_geacs = ctx.quant_docs_geacs

    if quant_docs_geacs == _NUM_MEMOS_PROCESSO_NOVO:
        registro.prox_acao = 'Processo já contém 2 memos da GEACS. Pulado.'
        return registro

    if quant_docs_geacs == 0:
        return processar_novo(
            ctx.driver,
            registro,
            ctx.tds_docs,
            _TAG_PERIODO_VAR_DEP,
            _TAG_MEMOS_NO_BLOCO,
        )

    registro.erro = f'Identificados {quant_docs_geacs} docs da geacs'
    return registro


def _tratar_tag_rel_ui_transformado_pdf(
    ctx: ContextoLinha, registro: RegistroMain
):
    ...
    return registro


def _tratar_tag_novo_rel_ui_gerado(ctx: ContextoLinha, registro: RegistroMain):
    ...
    return registro


def _classificar_e_processar(
    driver: webdriver.Remote, ctx: ContextoLinha, registro: RegistroMain
) -> RegistroMain:
    if len(ctx.tags) == 0:
        registro = _tratar_sem_marcadores(ctx, registro)

    elif registro.tag_processo_velho:
        if registro.tag_rel_ui_transformado_pdf:
            registro = _tratar_tag_rel_ui_transformado_pdf(ctx, registro)
        elif registro.tag_novo_rel_ui_gerado:
            registro = _tratar_tag_novo_rel_ui_gerado(ctx, registro)
        else:
            registro = processar_velho(
                driver, registro, ctx.docs_geacs, ctx.tds_docs
            )

    elif registro.tag_processo_novo:
        if registro.tag_memos_no_bloco:
            if registro.qnt_docs_geacs_na_arvore == _NUM_MEMOS_PROCESSO_NOVO:
                registro.prox_acao = 'Assinar memorandos e encaminhar'
            else:
                registro.prox_acao = (
                    'Processo NOVO com tag de memos no bloco, mas '
                    f'quantidade de docs da GEACS na árvore é '
                    f'{registro.qnt_docs_geacs_na_arvore}. Verificar.'
                )
        else:
            registro = _tratar_tag_novo_sem_tag_memos_no_bloco(ctx, registro)

    elif registro.tag_memos_no_bloco:
        registro.erro = 'Marcador de memos_no_bloco sem processo_novo'

    else:
        registro.erro = f'Combinação de tags não tratados: {ctx.tags}'

    return registro


def _processar_linha(driver, num_processo):
    registro = RegistroMain(num_processo=num_processo)

    try:
        acessar_processo(driver, num_processo)
        tds_docs = listar_documentos_arvore(driver)
        docs_geacs = _filtrar_docs_geacs(tds_docs)
        tags = listar_marcadores(driver)

        registro.qnt_docs_geacs_na_arvore = len(docs_geacs)

        ctx = ContextoLinha(
            driver=driver,
            tds_docs=tds_docs,
            docs_geacs=docs_geacs,
            tags=tags,
        )

        for tag in tags:
            if tag == _TAG_PROCESSO_NOVO:
                registro.tag_processo_novo = True
            if tag == _TAG_PROCESSO_VELHO:
                registro.tag_processo_velho = True
            if tag == _TAG_PLANILHADO:
                registro.tag_planilhado = True
            if tag == _TAG_UI_INSERIDA:
                registro.tag_ui_inserida = True
            if tag == _TAG_PERIODO_VAR_DEP:
                registro.tag_periodo_var_deps = True
            if tag == _TAG_MEMOS_NO_BLOCO:
                registro.tag_memos_no_bloco = True
            if tag == _TAG_RELATORIO_UI_TRANSFORMADO_PDF:
                registro.tag_rel_ui_transformado_pdf = True
            if tag == _TAG_NOVO_RELATORIO_UI_GERADO:
                registro.tag_novo_rel_ui_gerado

        registro = _classificar_e_processar(driver, ctx, registro)

    except Exception as e:
        registro.erro = f'{type(e).__name__}: {e}'
        logger.exception(f'{num_processo} - erro durante o processamento')

    return registro


def _salvar_resultado(registros_processados):
    if not registros_processados:
        return
    df = pd.DataFrame(registros_processados)
    df.to_excel(ARQ_PROCESSOS_PROCESSADOS, index=False)


def main():
    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()
    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        driver = iniciar_driver(
            driver_type='chrome', download_dir=DIR_UI_ANTIGAS_XLS
        )
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')

        efetuar_login(driver, SEI_LOGIN, SEI_SENHA, SEI_ORGAO)

        df_processos = pd.read_excel(
            io=ARQ_PROCESSOS_NAO_PROCESSADOS,
            sheet_name='processos_reais',
        )

        for _, linha in df_processos.iterrows():
            num_processo = linha['num_sei']
            t_ini = datetime.now()
            logger.info(f'{num_processo} - PROCESSAMENTO INICIADO')

            registro = _processar_linha(driver, num_processo)

            registros_processados.append(registro.to_dict())

            t_fim = datetime.now()
            duracao = t_fim - t_ini
            logger.info(
                f'{num_processo} - PROCESSAMENTO FINALIZADO ({duracao})'
            )

    except Exception:
        logger.error('Erro critico na execução do main')
        raise

    finally:
        _salvar_resultado(registros_processados)
        if driver is not None:
            driver.quit()
        t_fim_geral = datetime.now()
        duracao_geral = t_fim_geral - t_ini_geral
        logger.info(f'Duração total da execução: {duracao_geral}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
