import re
from typing import Dict

from Registro import RegistroMain
from sei_automacao.documento import obter_conteudo_doc
from sei_automacao.processo.arvore import (
    selecionar_doc_arvore,
)
from selenium import webdriver

_MARCADORES_REFAZER_V1: Dict[str, str] = {
    'pedido de atualização': r'atualiza[cç][ãa]o do levantamento',
    'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
    'campo "Nome completo"': r'Nome completo:',
    'campo "Matrícula" (titular)': r'Matr[íi]cula:',
    'campo "Período titular"': r'Per[íi]odo de apura[çc][ãa]o do titular:',
}


_MARCADORES_REFAZER_V2: Dict[str, str] = {
    'pedido de atualização': r'atualiza[cç][ãa]o do levantamento',
    'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
    'campo "Nome completo"': r'Nome completo:',
    'campo "Matrícula" (titular)': r'Matr[íi]cula:',
    'campo "Período titular"': r'Per[íi]odo de apura[çc][ãa]o do titular:',
}


def _obtem_memos_apis(tds_docs: list[dict]):
    indice_email_apis = next(
        (
            i
            for i, doc in enumerate(tds_docs)
            if (
                'E-mail' in doc['nome_arvore']
                and 'IPSEMG/APIS-Utilização' in doc['unidade']
            )
        ),
        None,
    )

    if indice_email_apis is None:
        return []

    docs_apos_email = tds_docs[indice_email_apis + 1 :]

    return [
        doc
        for doc in docs_apos_email
        if (
            'Memorando' in doc['nome_arvore']
            and 'IPSEMG/APIS-Utilização' in doc['unidade']
        )
    ]


def _encontrar_instrucoes(driver: webdriver.Remote, memos_apis: list[dict]):
    instrucoes = []

    for memo in memos_apis:
        selecionar_doc_arvore(driver, memo['numero_sei'])
        txt_memo = obter_conteudo_doc(driver, 'texto')

        marcadores_refazer_v1_faltantes = [
            descricao
            for descricao, padrao in _MARCADORES_REFAZER_V1.items()
            if not re.search(padrao, txt_memo, flags=re.IGNORECASE)
        ]

        if not marcadores_refazer_v1_faltantes:
            instrucoes.append('refazer1')

        else:
            marcadores_refazer_v2_faltantes = [
                descricao
                for descricao, padrao in _MARCADORES_REFAZER_V2.items()
                if not re.search(padrao, txt_memo, flags=re.IGNORECASE)
            ]

            if not marcadores_refazer_v2_faltantes:
                instrucoes.append('refazer2')

    return instrucoes


def _baixar_planilha_antigas(
    driver: webdriver.Remote, docs_geacs: list[dict]
) -> None:
    planilhas_ui_antigas = [
        doc
        for doc in docs_geacs
        if 'Planilha Utilização' in doc['nome_arvore']
    ]

    for planilha in planilhas_ui_antigas:
        selecionar_doc_arvore(driver, planilha['numero_sei'])


def processar_velho(
    driver: webdriver.Remote,
    registro: RegistroMain,
    docs_geacs: list[dict],
    tds_docs: list[dict],
) -> dict:
    try:
        memos_apis = _obtem_memos_apis(tds_docs)

        if not memos_apis:
            registro.erro = (
                'Não foi encontrado o e-mail da APIS '
                'utilizado como referência para a busca '
                'das instruções'
            )

        else:
            instrucoes = _encontrar_instrucoes(driver, memos_apis)

            print(instrucoes)

            if instrucoes == ['gerar_pdf']:
                _baixar_planilha_antigas(driver, docs_geacs)
            elif instrucoes == ['refazer1']:
                ...
            elif instrucoes == ['refazer2']:
                ...

        return registro

    except Exception as e:
        registro.erro = f'{type(e).__name__}: {e}'
        return registro
