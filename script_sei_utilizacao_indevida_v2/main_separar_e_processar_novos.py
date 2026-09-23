import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from processar_novo import processar_novo
from Registro import RegistroSepararProecessarNovos
from sei_automacao.auth.login import efetuar_login
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import adicionar_marcador
from sei_automacao.processo.arvore import listar_documentos_arvore
from sei_automacao.processo.marcadores import listar_marcadores
from sei_automacao.ubiquo.busca import acessar_processo

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

for diretorio in [DIR_DADOS, DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
    diretorio.mkdir(parents=True, exist_ok=True)

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_PROCESSOS_PROCESSADOS = (
    DIR_CONTROLE / f'processos_processados_{AGORA}.xlsx'
)
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'

_NUM_MEMOS_PROCESSO_NOVO = 2
_MARCADOR_PROCESSO_NOVO = 'Script v2 - Processo NOVO'
_MARCADOR_PROCESSO_VELHO = 'Script v2 - Processo VELHO'
_MARCADOR_PERIODO_VAR_DEP = 'Script v2 - Período Variável Para Dependentes'
_MARCADOR_MEMOS_NO_BLOCO = 'Script v2 - Memos DISA e DEPROC no bloco'
_MARCADOR_PLANILHADO = 'PLANILHADO'
_MARCADOR_UI_INSERIDA = 'UTILIZAÇÃO INSERIDA'


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
    marcadores: list

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
        adicionar_marcador(ctx.driver, _MARCADOR_PROCESSO_VELHO)
        registro.marcador_processo_velho = True
        registro.prox_acao = 'Processar processos VELHOS'
        return registro

    adicionar_marcador(ctx.driver, _MARCADOR_PROCESSO_NOVO)
    registro.marcador_processo_novo = True
    return processar_novo(
        ctx.driver,
        registro,
        ctx.tds_docs,
        _MARCADOR_PERIODO_VAR_DEP,
        _MARCADOR_MEMOS_NO_BLOCO,
    )


def _tratar_marcador_novo_sem_marcador_memos_no_bloco(ctx, registro):
    registro.marcador_processo_novo = True
    quant_docs_geacs = ctx.quant_docs_geacs

    if quant_docs_geacs == _NUM_MEMOS_PROCESSO_NOVO:
        registro.prox_acao = 'Processo já contém 2 memos da GEACS. Pulado.'
        return registro

    if quant_docs_geacs == 0:
        return processar_novo(
            ctx.driver,
            registro,
            ctx.tds_docs,
            _MARCADOR_PERIODO_VAR_DEP,
            _MARCADOR_MEMOS_NO_BLOCO,
        )

    registro.erro = f'Identificados {quant_docs_geacs} docs da geacs'
    return registro


def _classificar_e_processar(ctx, registro):
    if (
        len(ctx.marcadores) == 0
        or _MARCADOR_PLANILHADO in ctx.marcadores
        or _MARCADOR_UI_INSERIDA in ctx.marcadores
    ):
        return _tratar_sem_marcadores(ctx, registro)

    if registro.marcador_processo_velho:
        registro.marcador_processo_velho = True
        registro.prox_acao = 'Processar processos VELHOS'
        return registro

    if registro.marcador_processo_novo:
        if registro.marcador_memos_no_bloco:
            if registro.qnt_docs_geacs_na_arvore == _NUM_MEMOS_PROCESSO_NOVO:
                registro.prox_acao = 'Assinar memorandos e encaminhar'
                return registro
            else:
                registro.prox_acao = (
                    'Processo NOVO com marcador de memos no bloco, mas '
                    f'quantidade de docs da GEACS na árvore é '
                    f'{registro.qnt_docs_geacs_na_arvore}. Verificar.'
                )
                return registro
        else:
            return _tratar_marcador_novo_sem_marcador_memos_no_bloco(
                ctx, registro
            )

    elif registro.marcador_memos_no_bloco:
        registro.erro = 'Marcador de memos_no_bloco sem processo_novo'

    registro.erro = f'Combinação de marcadores não tratados: {ctx.marcadores}'
    return registro


def _processar_linha(driver, num_processo):
    registro = RegistroSepararProecessarNovos(num_processo=num_processo)

    try:
        acessar_processo(driver, num_processo)
        tds_docs = listar_documentos_arvore(driver)
        docs_geacs = _filtrar_docs_geacs(tds_docs)
        marcadores = listar_marcadores(driver)

        registro.qnt_docs_geacs_na_arvore = len(docs_geacs)

        ctx = ContextoLinha(
            driver=driver,
            tds_docs=tds_docs,
            docs_geacs=docs_geacs,
            marcadores=marcadores,
        )

        for marcador in marcadores:
            if marcador == _MARCADOR_PROCESSO_NOVO:
                registro.marcador_processo_novo = True
            if marcador == _MARCADOR_PROCESSO_VELHO:
                registro.marcador_processo_velho = True
            if marcador == _MARCADOR_PLANILHADO:
                registro.marcador_planilhado = True
            if marcador == _MARCADOR_UI_INSERIDA:
                registro.marcador_ui_inserida = True
            if marcador == _MARCADOR_PERIODO_VAR_DEP:
                registro.marcador_periodo_var_deps = True
            if marcador == _MARCADOR_MEMOS_NO_BLOCO:
                registro.marcador_memos_no_bloco = True

        registro = _classificar_e_processar(ctx, registro)

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

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        t_ini_geral = datetime.now()

        driver = iniciar_driver(driver_type='chrome')
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
