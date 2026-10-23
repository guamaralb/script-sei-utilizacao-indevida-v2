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

BLOCO_MEMO_DEPROC = 7697744
# Memos à DISA (um bloco por caso da comparação base DISA x MANTIS).
# TODO: preencher. Com None, o processo para com erro antes de criar o memo.
BLOCO_MEMO_DISA_VALIDAR_CONSTA = None
BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA = None
BLOCO_MEMO_DISA_RELATORIO = None
BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS = 7711907
BLOCO_MEMO_APIS_SEM_MEMO = 7730344
BLOCO_MEMO_APIS_FORMATO_INVALIDO = 7730341
BLOCO_MEMO_APIS_PERIODO_DEPENDENTES = 7730905

NOME_SIGNATARIO = 'Bruna Miiller Lavarini'
CARGO_SIGNATARIO = 'Gerência de Auditoria e Contas da Saúde'

# Processo VELHO: memos da GEACS à DISA e à DEPROC (seguidos) datados antes
# desta data
DATA_CORTE_PROCESSO_VELHO = date(2026, 10, 1)
