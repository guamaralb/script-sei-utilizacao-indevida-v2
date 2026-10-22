from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

import pandas as pd
from constantes import DIR_DADOS
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ARQ_LOGO = DIR_DADOS / 'img' / 'logo.jpg'

COL_WITDHS_DEP_DICT = {
    'PRESTADOR': 180,
    'MATRICULA DEPENDENTE': 90,
    'NOME DEPENDENTE': 180,
    'DATA DO ATENDIMENTO': 90,
    'VALOR PAGO': 80,
}

COL_WITDHS_TIT_DICT = {
    'PRESTADOR': 300,
    'DATA DO ATENDIMENTO': 90,
    'PROCEDIMENTO': 300,
    'VALOR PAGO': 80,
}


def _formatar_valor_monetario(valor: float) -> str:
    formatado = f'{valor:,.2f}'
    return formatado.replace(',', 'X').replace('.', ',').replace('X', '.')


def _build_table_row(row, valor_col_index, matricula_dep_index, normal):
    linha = []

    for i, cell in enumerate(row):
        if i == valor_col_index and pd.notna(cell):
            linha.append(_formatar_valor_monetario(float(cell)))

        elif i == matricula_dep_index and pd.notna(cell):
            linha.append(str(int(cell)))

        elif pd.notna(cell) and isinstance(cell, (pd.Timestamp,)):
            linha.append(cell.strftime('%d/%m/%Y'))

        else:
            # Paragraph interpreta marcação: "&" e "<" no texto quebram o PDF
            linha.append(Paragraph(escape(str(cell)), normal))

    return linha


def transformar_xls_em_pdf(
    tit_matricula: str,
    tit_nome: str,
    tipo: Literal['Titular', 'Dependente(s)'],
    df: pd.DataFrame,
    path_destino: Path,
    rede: str = '',
) -> Path:
    """rede (opcional): nome da rede no título e no nome do arquivo."""
    styles = getSampleStyleSheet()
    normal = styles['BodyText']
    header_style = styles['Heading4']

    table_header = ParagraphStyle(
        'table_header',
        parent=styles['BodyText'],
        textColor=colors.white,
        fontName='Helvetica-Bold',
        alignment=1,
    )

    caminho_pdf = path_destino / f'Utilizacao{f"-{rede}" if rede else ""}-{tipo}-{tit_matricula}.pdf'

    doc = SimpleDocTemplate(
        str(caminho_pdf),
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=40,
        bottomMargin=30,
    )

    elements = []

    logo = Image(str(ARQ_LOGO), width=120, height=60)
    info = Paragraph(
        f'<b>Relatório de Utilização{f" na {escape(rede)}" if rede else ""} Por {tipo}</b><br/>Beneficiário Titular: {escape(tit_nome)} - {tit_matricula}',
        header_style,
    )
    elements.append(Table([[logo, info]], colWidths=[150, 650]))
    elements.append(Spacer(1, 20))

    valor_col_index = df.columns.get_loc('VALOR PAGO') if 'VALOR PAGO' in df.columns else None
    matricula_dep_index = df.columns.get_loc('MATRICULA DEPENDENTE') if 'MATRICULA DEPENDENTE' in df.columns else None

    data = [[Paragraph(col, table_header) for col in df.columns]]
    for _, row in df.iterrows():
        data.append(_build_table_row(row, valor_col_index, matricula_dep_index, normal))

    if tipo == 'Titular':
        col_widths = [COL_WITDHS_TIT_DICT.get(col, 100) for col in df.columns]
    elif tipo == 'Dependente(s)':
        col_widths = [COL_WITDHS_DEP_DICT.get(col, 100) for col in df.columns]
    else:
        col_widths = []

    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightblue]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]

    if valor_col_index is not None:
        style_commands.append((
            'ALIGN',
            (valor_col_index, 1),
            (valor_col_index, -1),
            'RIGHT',
        ))
        style_commands.append((
            'ALIGN',
            (valor_col_index, 0),
            (valor_col_index, 0),
            'RIGHT',
        ))

    table.setStyle(TableStyle(style_commands))
    elements.append(table)
    doc.build(elements)

    return caminho_pdf
