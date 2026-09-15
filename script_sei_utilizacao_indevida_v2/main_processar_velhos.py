# LINE-LENGHT ----------------------------------------------------------------
import logging
import os
from datetime import datetime
from pathlib import Path

# from time import sleep
import pandas as pd
from dotenv import load_dotenv
from sei_automacao.auth.login import efetuar_login
from sei_automacao.documento import obter_conteudo_doc
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import adicionar_marcador
from sei_automacao.processo.arvore import (
    listar_documentos_arvore,
    selecionar_doc_arvore,
)
from sei_automacao.ubiquo.busca import acessar_processo

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

            memos = [
                doc
                for doc in tds_docs
                if 'IPSEMG/GEACS - Utilização' in doc['unidade']
            ]

            ultimo_doc = memos[-1]

            selecionar_doc_arvore(driver, numero_sei=ultimo_doc['numero_sei'])

            doc_text = obter_conteudo_doc(driver, formato='texto')

            flag_refazer = False
            flag_novo = False

            for trecho in SINALIZADORES_DE_PROCESSO_A_REFAZER:
                if trecho in doc_text:
                    print(trecho)
                    flag_refazer = True
                    break

            if not flag_refazer:
                for trecho in SINALIZADORES_DE_PROCESSO_NOVO:
                    if trecho in doc_text:
                        print(trecho)
                        flag_novo = True
                        break

            if flag_refazer and not flag_novo:
                adicionar_marcador(driver, 'TESTE - Refazer')
            elif not flag_refazer and flag_novo:
                adicionar_marcador(driver, 'TESTE - Novo')
            elif flag_refazer and flag_novo:
                raise Exception('Processo marcado como novo e refazer')
            else:
                raise Exception(
                    'Processo não marcado nem como novo nem como refazer'
                )

    except Exception:
        logger.error('Erro critico na execução do main')
        raise

    finally:
        driver.quit()
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
