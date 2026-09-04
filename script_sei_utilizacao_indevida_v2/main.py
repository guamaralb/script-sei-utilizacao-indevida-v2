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
            io=ARQ_PROCESSOS_NAO_PROCESSADOS, sheet_name='processos'
        )

        for _, linha in df_processos_nao_processados.iterrows():
            num_processo = linha['num_sei']
            logger.info(f'{num_processo} - INICIANDO PROCESSAMENTO')

            acessar_processo(driver, num_processo)

            docs = listar_documentos_arvore(driver)

            ultimo_doc = docs[-1]

            selecionar_doc_arvore(driver, numero_sei=ultimo_doc['numero_sei'])

            doc_text = obter_conteudo_doc(driver, formato='web_element')

            print(doc_text)

    except Exception:
        logger.error('Erro critico na execução do main')
        raise

    finally:
        driver.quit()
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
