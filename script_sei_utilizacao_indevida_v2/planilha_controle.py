"""Gravação e formatação da planilha de controle (uma linha por processo).

Usado por main.py e por main_add_memo_nao_usou_rede_propria.py.

Formatação:
    - cabeçalho congelado e com filtro;
    - largura das colunas ajustada ao conteúdo;
    - linha com erro destacada em vermelho claro;
    - células de matrículas não encontradas destacadas em amarelo.
"""

import logging
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

_LARGURA_MAXIMA = 60
_PREENCHIMENTO_ERRO = PatternFill(fill_type='solid', start_color='FFF4CCCC', end_color='FFF4CCCC')
_PREENCHIMENTO_NAO_ENCONTRADA = PatternFill(fill_type='solid', start_color='FFFFE599', end_color='FFFFE599')

_COLUNAS_NAO_ENCONTRADAS = (
    'titular_nao_encontrado_base_geral',
    'deps_nao_encontrados_base_geral',
    'titular_nao_encontrado',
    'deps_nao_encontrados',
)


def _formatar(planilha, colunas: list[str]) -> None:
    planilha.freeze_panes = 'B2'
    planilha.auto_filter.ref = planilha.dimensions
    for celula in planilha[1]:
        celula.font = Font(bold=True)

    for indice, coluna in enumerate(colunas, start=1):
        valores = [str(c.value) for c in planilha[get_column_letter(indice)] if c.value is not None]
        largura = max((len(v) for v in valores), default=len(coluna))
        planilha.column_dimensions[get_column_letter(indice)].width = min(largura + 2, _LARGURA_MAXIMA)

    idx_erro = colunas.index('erro') + 1 if 'erro' in colunas else None
    idx_nao_encontradas = [colunas.index(c) + 1 for c in _COLUNAS_NAO_ENCONTRADAS if c in colunas]

    for linha in planilha.iter_rows(min_row=2):
        if idx_erro and linha[idx_erro - 1].value:
            for celula in linha:
                celula.fill = _PREENCHIMENTO_ERRO
        for idx in idx_nao_encontradas:
            if linha[idx - 1].value:
                linha[idx - 1].fill = _PREENCHIMENTO_NAO_ENCONTRADA


def salvar_planilha_controle(registros: list[dict], arquivo: Path) -> None:
    if not registros:
        return
    df = pd.DataFrame(registros)
    try:
        df.to_excel(arquivo, index=False)
        logger.info(f'Planilha de controle salva: {arquivo}')
    except Exception:
        logger.exception(f'Falha ao salvar planilha de controle: {arquivo}')
        return

    # A formatação é opcional: se falhar, a planilha sem formatação já está salva
    try:
        with pd.ExcelWriter(arquivo, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            _formatar(writer.sheets['Sheet1'], list(df.columns))
    except Exception:
        logger.exception(f'Falha ao formatar a planilha de controle: {arquivo}')
