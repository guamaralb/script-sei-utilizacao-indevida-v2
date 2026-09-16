# LINE-LENGHT ----------------------------------------------------------------
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from memorandos.DadosProcesso import DadosProcesso
from sei_automacao.auth.login import efetuar_login
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import adicionar_marcador, incluir_doc_sei_memo
from sei_automacao.processo.arvore import (
    listar_documentos_arvore,
)
from sei_automacao.ubiquo.busca import acessar_processo

from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import MemoDisa

load_dotenv()

SEI_LOGIN = os.getenv('SEI_LOGIN')
SEI_SENHA = os.getenv('SEI_SENHA')
SEI_ORGAO = os.getenv('SEI_ORGAO')

AGORA = datetime.now().strftime('%Y%m%d_%H%M%S')

DIR_BASE = Path(__file__).resolve().parent.parent
DIR_DADOS = DIR_BASE / 'dados'
DIR_INPUTS = DIR_DADOS / 'inputs'
DIR_LOG = DIR_BASE / 'logs'
DIR_CONSOLIDACOES = DIR_DADOS / 'consolidacoes'

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_LOG = DIR_LOG / f'{AGORA}_execucao.log'
ARQ_CONSOLIDACAO = DIR_CONSOLIDACOES / f'{AGORA}_consolidacao.xlsx'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ARQ_LOG, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger()

SINALIZADORES_DE_PROCESSO_NOVO = [
    'entileza realizar o levantamento de utilização de procedimentos na sa',
    ', o levantamento dos valores de utilização indevida da assistência à sa',
]

SINALIZADORES_DE_PROCESSO_A_REFAZER = [
    'atualização do levantamento',
    'realizar novo levantamento',
]
_LEN_DATA_MM_AAAA = 7

_TRANSLATE_FROM = 'ÁÀÂÃÄáàâãäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇç'
_TRANSLATE_TO = 'AAAAAaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCc'


def main():
    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')
        driver = iniciar_driver(driver_type='chrome')
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')

        efetuar_login(driver, SEI_LOGIN, SEI_SENHA, SEI_ORGAO)

        df_processos_nao_processados = pd.read_excel(
            io=ARQ_PROCESSOS_NAO_PROCESSADOS, sheet_name='processos_reais'
        )

        for _, linha in df_processos_nao_processados.iterrows():
            num_processo = linha['num_sei']
            logger.info(f'{num_processo} - INICIANDO PROCESSAMENTO')

            acessar_processo(driver, num_processo)

            tds_docs = listar_documentos_arvore(driver)

            docs_geacs = [
                doc
                for doc in tds_docs
                if 'IPSEMG/GEACS - Utilização' in doc['unidade']
            ]

            # Se NÃO HOUVER documentos gerados pela GEACS:
            if len(docs_geacs) > 0:
                adicionar_marcador(driver, 'Script v2 - Processo VELHO')
                continue

            adicionar_marcador(driver, 'Script v2 - Processo NOVO')

            dados_processo = DadosProcesso(
                nome_titular='Titular',
                matricula_titular='Matricula',
                periodo_titular='Periodo',
                matriculas_dependentes='Matriculas',
                periodo_dependentes='PeriodoDeps',
            )
            # Memorando DISA
            memo_disa = MemoDisa(
                dados=dados_processo,
                nome_signatario='Bruna Miiller Lavarini',
                cargo_signatario='Gerência de Auditoria e Contas da Saúde',
            )
            incluir_doc_sei_memo(driver, **memo_disa.para_kwargs_inserir_doc())
            inserir_bloco_ass(driver, 7697744)

            # Memorando DEPROC
            memo_disa = MemoDeproc(
                dados=dados_processo,
                nome_signatario='Bruna Miiller Lavarini',
                cargo_signatario='Gerência de Auditoria e Contas da Saúde',
            )
            incluir_doc_sei_memo(driver, **memo_disa.para_kwargs_inserir_doc())
            inserir_bloco_ass(driver, 7697744)

    except Exception:
        logger.error('Erro critico na execução do main')
        raise

    finally:
        driver.quit()
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
