"""Fluxo DEPROC: relatório em PDF da coparticipação, no formato do extrato de
utilização do IPSEMG (um bloco por beneficiário, atendimentos agrupados por
data, prestador e procedimento, subtotal e totais), anexado ao processo como
documento externo antes do memo de resultado.

Retomada: o PDF já anexado na rodada (procurado pelo início do nome) não é
anexado de novo.
"""

import logging
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from constantes import DIR_FLUXO_DEPROC_PDF
from coparticipacao_deproc import (
    COL_CATEGORIA,
    COL_DATA,
    COL_MATRICULA,
    COL_NOME,
    COL_PRESTADOR,
    COL_PROCEDIMENTO,
    COL_QTDE,
    COL_VALOR,
    TITULAR,
    ResultadoDeproc,
    formatar_matricula_com_dv,
    mesma_matricula,
)
from docs_processo import encontrar_doc_por_nome, numero_sei_por_nome
from rede_propria import ErroAvaliacao, normalizar_matricula
from relatorios_mantis import TIPO_DOC, anexar_pdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from selenium import webdriver
from transformar_xls_em_pdf import ARQ_LOGO, formatar_valor_monetario

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI

logger = logging.getLogger(__name__)

_TITULO = 'Extrato de Utilização da Assistência à Saúde IPSEMG'
# Largura útil da página (A4 deitada, sem as margens)
_LARGURA = 780
# Faixa do beneficiário: matrícula, nome, categoria (e período, no modelo com
# período por dependente)
_LARGURAS_BENEFICIARIO = (90, 330, 360)
_LARGURAS_BENEFICIARIO_COM_PERIODO = (90, 300, 160, 230)
# Atendimentos: data, prestador, procedimento, qtde, valor
_COLUNAS_ATENDIMENTOS = (COL_DATA, COL_PRESTADOR, COL_PROCEDIMENTO, COL_QTDE, COL_VALOR)
_ROTULOS_ATENDIMENTOS = ('DATA ATENDIMENTO', 'PRESTADOR', 'PROCEDIMENTO', 'QTDE', 'VALOR DA COPARTICIPAÇÃO')
_LARGURAS_ATENDIMENTOS = (75, 300, 255, 50, 100)
_ROTULO_TOTAL = 280
_VALOR_TOTAL = 100


def inicio_nome_relatorio_deproc(matricula_titular: str) -> str:
    """Início do número do documento (sem a data e hora da inclusão), com a
    matrícula normalizada (no memo pode vir com barra ou hífen)."""
    return f'Coparticipação - {normalizar_matricula(matricula_titular)}'


def formatar_reais(valor: float) -> str:
    return f'R$ {formatar_valor_monetario(valor)}'


def resumir_atendimentos(atendimentos: pd.DataFrame) -> pd.DataFrame:
    """Atendimentos de um beneficiário agrupados por data, prestador e
    procedimento, com QTDE e valor somados (como no extrato do IPSEMG). As
    linhas cuja soma do valor da coparticipação é 0 (ex.: isentos, cálculo
    impedido) não entram no relatório."""
    resumo = atendimentos.groupby([COL_DATA, COL_PRESTADOR, COL_PROCEDIMENTO], as_index=False, sort=True)[[COL_QTDE, COL_VALOR]].sum()
    resumo[COL_VALOR] = resumo[COL_VALOR].round(2)
    return resumo[resumo[COL_VALOR] != 0].reset_index(drop=True)


def _periodo_proprio(dados: DadosUI, matricula: str) -> str | None:
    return next((p for m, p in (dados.periodos_por_dependente or {}).items() if mesma_matricula(normalizar_matricula(m), matricula)), None)


class _Estilos:
    def __init__(self):
        base = getSampleStyleSheet()['BodyText']
        self.normal = ParagraphStyle('deproc_normal', parent=base, fontSize=8, leading=10)
        self.negrito = ParagraphStyle('deproc_negrito', parent=self.normal, fontName='Helvetica-Bold')
        self.rotulo = ParagraphStyle('deproc_rotulo', parent=self.negrito, textColor=colors.white)
        self.cabecalho = ParagraphStyle('deproc_cabecalho_tabela', parent=self.negrito, alignment=1)
        self.cabecalho_esquerda = ParagraphStyle('deproc_cabecalho_esquerda', parent=self.negrito)
        self.titulo = ParagraphStyle('deproc_titulo', parent=base, fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=1)
        self.periodo = ParagraphStyle('deproc_periodo', parent=base, fontSize=9, leading=12, alignment=2)
        self.total = ParagraphStyle('deproc_total', parent=base, fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=2)


def _texto(valor, estilo: ParagraphStyle) -> Paragraph:
    # Paragraph interpreta marcação: "&" e "<" no texto quebram o PDF
    return Paragraph(escape(str(valor)), estilo)


def _cabecalho(dados: DadosUI, num_processo: str, estilos: _Estilos) -> Table:
    titulo = Paragraph(f'{escape(_TITULO)}<br/><font size="9">Processo SEI nº {escape(num_processo)}</font>', estilos.titulo)
    periodo = Paragraph(f'<b>PERÍODO REFERÊNCIA:</b><br/>{escape(dados.periodo_titular)}', estilos.periodo)
    tabela = Table([[Image(str(ARQ_LOGO), width=120, height=60), titulo, periodo]], colWidths=[150, 430, 200])
    tabela.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    return tabela


def _faixa_beneficiario(subtotal, nome: str, periodo: str | None, com_periodo: bool, estilos: _Estilos) -> Table:
    rotulos = ['MATRÍCULA', 'NOME BENEFICIÁRIO', 'CATEGORIA']
    valores = [formatar_matricula_com_dv(subtotal.matricula), nome, subtotal.categoria]
    if com_periodo:
        rotulos.append('PERÍODO DE APURAÇÃO')
        valores.append(periodo or '')
    tabela = Table(
        [[_texto(r, estilos.rotulo) for r in rotulos], [_texto(v, estilos.negrito) for v in valores]],
        colWidths=_LARGURAS_BENEFICIARIO_COM_PERIODO if com_periodo else _LARGURAS_BENEFICIARIO,
    )
    tabela.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
            ('LINEBELOW', (0, 1), (-1, 1), 1, colors.darkblue),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
    )
    return tabela


def _tabela_atendimentos(resumo: pd.DataFrame, estilos: _Estilos) -> Table:
    # Prestador e procedimento alinhados à esquerda, como no extrato
    linhas = [[_texto(r, estilos.cabecalho_esquerda if r in {'PRESTADOR', 'PROCEDIMENTO'} else estilos.cabecalho) for r in _ROTULOS_ATENDIMENTOS]]
    for linha in resumo.itertuples(index=False):
        valores = dict(zip(resumo.columns, linha, strict=True))
        linhas.append([
            pd.Timestamp(valores[COL_DATA]).strftime('%d/%m/%Y'),
            _texto(valores[COL_PRESTADOR], estilos.normal),
            _texto(valores[COL_PROCEDIMENTO], estilos.normal),
            str(int(valores[COL_QTDE])),
            formatar_reais(float(valores[COL_VALOR])),
        ])
    tabela = Table(linhas, colWidths=_LARGURAS_ATENDIMENTOS, repeatRows=1)
    tabela.setStyle(
        TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightblue]),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ])
    )
    return tabela


def _linha_total(rotulo: str, valor: float, estilos: _Estilos) -> Table:
    tabela = Table(
        [['', _texto(rotulo, estilos.total), _texto(formatar_reais(valor), estilos.total)]],
        colWidths=[_LARGURA - _ROTULO_TOTAL - _VALOR_TOTAL, _ROTULO_TOTAL, _VALOR_TOTAL],
    )
    tabela.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    return tabela


def gerar_pdf_deproc(resultado: ResultadoDeproc, dados: DadosUI, num_processo: str, path_destino: Path = DIR_FLUXO_DEPROC_PDF) -> Path:
    """Extrato por beneficiário (titular primeiro): faixa com matrícula, nome
    e categoria, atendimentos agrupados (resumir_atendimentos, sem as linhas
    de valor 0) e SUBTOTAL; no fim, os três totais (coparticipação,
    descontado, em aberto). Beneficiário sem nenhuma linha de valor
    diferente de 0 não aparece."""
    path_destino.mkdir(parents=True, exist_ok=True)
    caminho_pdf = path_destino / f'Coparticipacao-{normalizar_matricula(dados.matricula_titular)}.pdf'
    estilos = _Estilos()
    com_periodo = bool(dados.periodos_por_dependente)

    elementos = [_cabecalho(dados, num_processo, estilos), Spacer(1, 16)]
    atendimentos = resultado.atendimentos
    for subtotal in resultado.subtotais:
        do_beneficiario = atendimentos[(atendimentos[COL_MATRICULA] == subtotal.matricula) & (atendimentos[COL_CATEGORIA] == subtotal.categoria)]
        resumo = resumir_atendimentos(do_beneficiario)
        if resumo.empty:
            continue
        nome = do_beneficiario[COL_NOME].iloc[0]
        periodo = dados.periodo_titular if subtotal.categoria == TITULAR else (_periodo_proprio(dados, subtotal.matricula) or dados.periodo_titular)
        elementos += [
            KeepTogether([
                _faixa_beneficiario(subtotal, nome, periodo, com_periodo, estilos),
                Spacer(1, 4),
                _tabela_atendimentos(resumo, estilos),
            ]),
            Spacer(1, 6),
            _linha_total('SUBTOTAL :', subtotal.valor, estilos),
            Spacer(1, 14),
        ]

    totais = resultado.totais
    elementos.append(
        KeepTogether([
            _linha_total('VALOR TOTAL DA COPARTICIPAÇÃO :', totais.coparticipacao, estilos),
            _linha_total('VALOR TOTAL DESCONTADO :', totais.descontado, estilos),
            _linha_total('VALOR TOTAL EM ABERTO :', totais.em_aberto, estilos),
        ])
    )

    doc = SimpleDocTemplate(str(caminho_pdf), pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    doc.build(elementos)
    return caminho_pdf


def incluir_relatorio_deproc(driver: webdriver.Remote, registro, resultado: ResultadoDeproc, dados: DadosUI) -> str:
    """Anexa o PDF (ou reaproveita o da rodada) e devolve o número SEI dele."""
    inicio = inicio_nome_relatorio_deproc(dados.matricula_titular)
    existente = encontrar_doc_por_nome(registro.docs_rodada, f'{TIPO_DOC} {inicio}')
    if existente is not None:
        registro.relatorio_deproc_na_arvore = True
        registro.relatorio_deproc_sei = existente['numero_sei']
        logger.warning(f'Retomada: relatório de coparticipação já está na árvore ({existente["numero_sei"]}); não será anexado de novo')
        return existente['numero_sei']

    agora = datetime.now()
    caminho_pdf = gerar_pdf_deproc(resultado, dados, registro.num_processo)
    num = f'{inicio} - {agora:%Y%m%d_%H%M%S}'
    anexar_pdf(driver, num, caminho_pdf, agora)
    registro.relatorio_deproc_incluido = num
    numero_sei = numero_sei_por_nome(driver, f'{TIPO_DOC} {num}')
    if numero_sei is None:
        raise ErroAvaliacao(f'Relatório de coparticipação anexado, mas não encontrado na árvore ({num}): a próxima execução o encontra pelo nome')
    registro.relatorio_deproc_sei = numero_sei
    logger.info(f'Relatório de coparticipação anexado ao processo: {num} ({numero_sei})')
    return numero_sei
