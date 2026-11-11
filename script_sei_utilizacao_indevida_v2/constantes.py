"""Constantes do script."""

from datetime import date
from pathlib import Path

DIR_BASE = Path(__file__).resolve().parent.parent
DIR_DADOS = DIR_BASE / 'dados'
DIR_INPUTS = DIR_DADOS / 'inputs'
DIR_CONTROLE = DIR_DADOS / 'controle'
DIR_LOG = DIR_BASE / 'logs'

# Uma linha por processo (aba "processos") e uma por passagem (aba
# "historico")
ARQ_CONTROLE_GERAL = DIR_CONTROLE / 'controle_geral_de_processos.xlsx'
DIR_BACKUP_CONTROLE = DIR_CONTROLE / 'backup'

DIR_UTILIZACOES = DIR_DADOS / 'utilizacoes'
DIR_UTILIZACOES_OUTRAS = DIR_UTILIZACOES / 'outras'
DIR_UTILIZACOES_OUTRAS_PDF = DIR_UTILIZACOES_OUTRAS / 'pdf'
# Relatórios em PDF dos atendimentos do MANTIS, anexados aos processos
DIR_UTILIZACOES_MANTIS_PDF = DIR_UTILIZACOES / 'mantis' / 'pdf'

# Fluxo alternativo ADC PDF ANT AUT: planilhas baixadas do SEI e PDFs gerados
DIR_ADC_PDF_ANT_AUT = DIR_DADOS / 'geacs_adc_pdf_ant_aut'
DIR_ADC_PDF_ANT_AUT_PLANILHAS = DIR_ADC_PDF_ANT_AUT / 'planilhas_baixadas'
DIR_ADC_PDF_ANT_AUT_PDF = DIR_ADC_PDF_ANT_AUT / 'pdfs'

# Fluxo ADC PDF ANT MAN: planilhas colocadas à mão na pasta e PDFs gerados
DIR_ADC_PDF_ANT_MAN = DIR_DADOS / 'geacs_adc_pdf_ant_man'
DIR_ADC_PDF_ANT_MAN_PLANILHAS = DIR_ADC_PDF_ANT_MAN / 'planilhas'
DIR_ADC_PDF_ANT_MAN_PDF = DIR_ADC_PDF_ANT_MAN / 'pdf'

# Fluxo DEPROC: base de coparticipação do MANTIS (aba "Resultado") e PDFs
# gerados
DIR_FLUXO_DEPROC = DIR_DADOS / 'fluxo_deproc'
DIR_FLUXO_DEPROC_PDF = DIR_FLUXO_DEPROC / 'pdf'
ARQ_BASE_DEPROC = DIR_FLUXO_DEPROC / 'Relatório Base 2 - MANTIS # 11281 - BASE 2019.xlsx'

ARQ_USO_REDE_PROPRIA = DIR_INPUTS / 'beneficiarios_atendidos_rede_propria-2026_09_23.xlsx'
# Base APIS: listagem de todos os beneficiários da demanda (a base DISA é
# feita a partir dela). Matrículas com DV.
ARQ_BASE_APIS = DIR_INPUTS / 'planilha_da_galantini_com_listagem_de_todos_beneficiarios.xlsx'
# Utilização registrada no MANTIS (abas TITULARES e DEPENDENTES)
ARQ_MANTIS_REDE_PROPRIA = DIR_INPUTS / 'utilizacao_MANTIS-rede_propria.xlsx'
ARQ_MANTIS_REDE_CREDENCIADA = DIR_INPUTS / 'utilizacao_MANTIS-rede_credenciada.xlsx'

# Grafias exatas retornadas pela árvore do SEI (são diferentes entre si)
UNIDADE_GEACS = 'IPSEMG/GEACS - Utilização'
UNIDADE_APIS = 'IPSEMG/APIS-Utilização'
UNIDADE_DEPROC = 'IPSEMG/DEPROC-Utilização'

BLOCO_MEMO_DEPROC = 7697744

# Memos à DISA (um bloco por caso da comparação base DISA x MANTIS).
BLOCO_MEMO_DISA_VALIDAR_CONSTA = 7730939
BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA = 7744344
BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO = 7744345

# Memos à APIS
BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS = 7711907
BLOCO_MEMO_APIS_SEM_MEMO = 7730344
BLOCO_MEMO_APIS_FORMATO_INVALIDO = 7730341
BLOCO_MEMO_APIS_PERIODO_DEPENDENTES = 7730905
BLOCO_MEMO_APIS_SEM_USO = 7744349

# Memo da DEPROC à GEACS com o cálculo da coparticipação (fluxo DEPROC), na
# unidade da DEPROC. Com None, o processo para com erro antes de criar
# qualquer documento
BLOCO_MEMO_GEACS_CALCULO_COPA = 7765003

NOME_SIGNATARIO = 'Bruna Miiller Lavarini'
CARGO_SIGNATARIO = 'Gerência de Auditoria e Contas da Saúde'
# Quem assina o memo DEPROC (fluxo DEPROC): procurado no texto da assinatura
# eletrônica, com e sem o "i" a mais
PADRAO_ASSINATURA_MEMO_DEPROC = r'assinado\s+eletronicamente\s+por\s+Bruna\s+Mii?ller\s+Lavarini'
# Quem assina o memo da DEPROC à GEACS com o cálculo da coparticipação
# (MemoGeacsCalculoCopa, fluxo DEPROC). Com None, o processo para com erro
# antes de criar qualquer documento
NOME_SIGNATARIO_DEPROC = 'Danúbia Lacerda Gomes de Oliveira'
CARGO_SIGNATARIO_DEPROC = 'Departamento de Processamento de Contas e Coparticipação - DEPROC'

# Processo VELHO: memorando da GEACS à DISA e/ou à DEPROC datado antes desta
# data ("Belo Horizonte, <dia> de <mês> de <ano>." no texto)
DATA_CORTE_PROCESSO_VELHO = date(2026, 10, 15)

# Fluxo GEACS CANC MEMO DEPROC ANT: só são cancelados os memos DEPROC antigos
# datados antes deste dia ("Belo Horizonte, <dia> de <mês> de <ano>.")
DATA_CORTE_MEMO_DEPROC_ANTIGO = date(2026, 10, 15)
