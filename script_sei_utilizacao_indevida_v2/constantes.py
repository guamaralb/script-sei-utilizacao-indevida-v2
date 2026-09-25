"""Constantes compartilhadas entre main.py e
main_add_memo_nao_usou_rede_propria.py."""

from pathlib import Path

DIR_BASE = Path(__file__).resolve().parent.parent
DIR_DADOS = DIR_BASE / 'dados'
DIR_INPUTS = DIR_DADOS / 'inputs'
DIR_CONTROLE = DIR_DADOS / 'controle'
DIR_LOG = DIR_BASE / 'logs'

ARQ_USO_REDE_PROPRIA = DIR_INPUTS / 'beneficiarios_atendidos_rede_propria-2026_09_23.xlsx'
# Listagem de todos os beneficiários (base geral). Matrículas com DV.
ARQ_BASE_GERAL = DIR_INPUTS / 'planilha_da_galantini_com_listagem_de_todos_beneficiarios.xlsx'

# Grafias exatas retornadas pela árvore do SEI (são diferentes entre si)
UNIDADE_GEACS = 'IPSEMG/GEACS - Utilização'
UNIDADE_APIS = 'IPSEMG/APIS-Utilização'

BLOCO_MEMOS_DISA_DEPROC = 7697744
BLOCO_MEMO_USO_REDE_PROPRIA = 7707212
# Memo à APIS de matrículas não encontradas na base geral.
# TODO: informar o número do bloco. Enquanto for None, o processo com
# matrícula não encontrada na base geral para com erro, sem criar o memo.
BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS: int | None = None

NOME_SIGNATARIO = 'Bruna Miiller Lavarini'
CARGO_SIGNATARIO = 'Gerência de Auditoria e Contas da Saúde'

# Valor usado quando o memo da APIS (modelo velho) cita dependentes sem
# informar as matrículas
VALOR_MATRICULA_DEPENDENTE_AVERIGUAR = 'AVERIGUAR'
