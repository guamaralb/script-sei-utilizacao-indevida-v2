import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from extrator_dados_processo import (
    extrair_dados_processo,
)
from sei_automacao.auth.login import efetuar_login
from sei_automacao.documento import inserir_bloco_ass, obter_conteudo_doc
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import adicionar_marcador, incluir_doc_sei_memo
from sei_automacao.processo.arvore import (
    listar_documentos_arvore,
    selecionar_doc_arvore,
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
DIR_CONTROLE = DIR_DADOS / 'controle'

ARQ_PROCESSOS_NAO_PROCESSADOS = DIR_INPUTS / 'processos_nao_processados.xlsx'
ARQ_PROCESSOS_PROCESSADOS = DIR_CONTROLE / f'processos_processados{AGORA}.xlsx'
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


def main():
    # Cada item é um dicionário com o status de um processo (uma linha do
    # relatório final). Usamos uma lista de dicts em vez de um DataFrame
    # dentro do loop porque adicionar/atualizar colunas linha a linha num
    # DataFrame é lento e verboso; o DataFrame só é montado uma vez, no fim.
    registros_processados: list[dict] = []

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
            # `registro` é adicionado à lista imediatamente e depois vamos
            # só atualizando suas chaves. Como é o mesmo objeto (por
            # referência), qualquer atualização feita mais abaixo já reflete
            # na lista — inclusive se uma exceção interromper o processo no
            # meio, a linha já estará no relatório final com os campos
            # preenchidos até aquele ponto.
            registro = {'num_sei': num_processo}
            registros_processados.append(registro)
            try:
                acessar_processo(driver, num_processo)

                tds_docs = listar_documentos_arvore(driver)

                docs_geacs = [
                    doc
                    for doc in tds_docs
                    if 'IPSEMG/GEACS - Utilização' in doc['unidade']
                ]

                # Se HOUVER documentos gerados pela GEACS, o processo é antigo:
                if len(docs_geacs) > 0:
                    adicionar_marcador(driver, 'Script v2 - Processo VELHO')
                    registro['marcador_adicionado'] = (
                        'Script v2 - Processo VELHO'
                    )
                    continue

                adicionar_marcador(driver, 'Script v2 - Processo NOVO')
                registro['marcador_adicionado'] = 'Script v2 - Processo NOVO'

                memos = [
                    doc
                    for doc in tds_docs
                    if 'Memorando' in doc['nome_arvore']
                ]

                ultimo_doc = memos[-1]
                selecionar_doc_arvore(
                    driver, numero_sei=ultimo_doc['numero_sei']
                )
                doc_text = obter_conteudo_doc(driver, formato='texto')

                dados_processo = extrair_dados_processo(doc_text)

                if dados_processo.periodo_dependentes:
                    adicionar_marcador(
                        driver, 'Script v2 - Período Variável Para Dependentes'
                    )

                # Memorando DISA
                memo_disa = MemoDisa(
                    dados=dados_processo,
                    nome_signatario='Bruna Miiller Lavarini',
                    cargo_signatario='Gerência de Auditoria e Contas da Saúde',
                )
                incluir_doc_sei_memo(
                    driver, **memo_disa.para_kwargs_inserir_doc()
                )
                inserir_bloco_ass(driver, 7697744)
                registro['memo_disa_no_bloco'] = True

                # Memorando DEPROC
                memo_deproc = MemoDeproc(
                    dados=dados_processo,
                    nome_signatario='Bruna Miiller Lavarini',
                    cargo_signatario='Gerência de Auditoria e Contas da Saúde',
                )
                incluir_doc_sei_memo(
                    driver, **memo_deproc.para_kwargs_inserir_doc()
                )
                inserir_bloco_ass(driver, 7697744)
                registro['memo_deproc_no_bloco'] = True
            except Exception as err:
                registro['erro'] = str(err)

    except Exception:
        logger.error('Erro critico na execução do main')
        raise

    finally:
        df_processos_processados = pd.DataFrame(registros_processados)
        df_processos_processados.to_excel(
            ARQ_PROCESSOS_PROCESSADOS, index=False
        )
        driver.quit()
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
