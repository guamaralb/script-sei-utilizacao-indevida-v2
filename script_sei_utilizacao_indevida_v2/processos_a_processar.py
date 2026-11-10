"""Lista de processos de cada fluxo: dados/inputs/processos_a_processar.xlsx,
uma aba por fluxo, com o mesmo nome do script na planilha de controle
(geacs, geacs_adc_pdf_ant_aut, geacs_adc_pdf_ant_man, deproc), coluna num_sei."""

import logging

import pandas as pd
from constantes import DIR_INPUTS

logger = logging.getLogger(__name__)

ARQ_PROCESSOS_A_PROCESSAR = DIR_INPUTS / 'processos_a_processar.xlsx'
COLUNA_PROCESSO = 'num_sei'


def ler_processos_a_processar(aba: str) -> list[str]:
    """Processos da aba do fluxo, na ordem da planilha, sem linhas vazias."""
    try:
        df = pd.read_excel(io=ARQ_PROCESSOS_A_PROCESSAR, sheet_name=aba)
    except ValueError as e:
        raise ValueError(f'Aba "{aba}" não encontrada em {ARQ_PROCESSOS_A_PROCESSAR.name}: crie a aba do fluxo com a coluna {COLUNA_PROCESSO}') from e
    if COLUNA_PROCESSO not in df.columns:
        raise ValueError(f'Aba "{aba}" de {ARQ_PROCESSOS_A_PROCESSAR.name} sem a coluna {COLUNA_PROCESSO}')

    processos = [str(num).strip() for num in df[COLUNA_PROCESSO].dropna() if str(num).strip()]
    logger.info(f'{len(processos)} processo(s) lido(s) de {ARQ_PROCESSOS_A_PROCESSAR.name}, aba {aba}')
    return processos
