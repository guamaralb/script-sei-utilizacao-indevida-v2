"""Relatórios em PDF dos atendimentos do MANTIS, anexados ao processo
(documento externo) antes do memo correspondente: rede própria, antes do
memo à DISA; rede credenciada, antes do memo à DEPROC.

Um PDF para o titular e outro para os dependentes, só de quem tem
atendimento no período de apuração. Retomada: o PDF já anexado na rodada
atual (procurado pelo início do nome na árvore) não é anexado de novo.

incluir_relatorios devolve o número SEI dos PDFs (anexados agora ou já na
árvore), citados no memo à DISA e no memo à DEPROC.
"""

import logging
from datetime import datetime

import pandas as pd
from constantes import DIR_UTILIZACOES_MANTIS_PDF
from docs_processo import encontrar_doc_por_nome, numero_sei_por_nome
from mantis import UsoMantis
from rede_propria import ErroAvaliacao
from sei_automacao.processo import incluir_doc_externo
from selenium import webdriver
from transformar_xls_em_pdf import transformar_xls_em_pdf

logger = logging.getLogger(__name__)

TIPO_DOC = 'PDF'

# (sigla no nome do documento, nome no título do PDF). A sigla mantém o
# nome na árvore curto.
REDE_PROPRIA = ('RP', 'Rede Própria')
REDE_CREDENCIADA = ('RC', 'Rede Credenciada')


def _data(atendimento) -> pd.Timestamp:
    return pd.Timestamp(atendimento.data)


def _df_titular(uso: UsoMantis) -> pd.DataFrame:
    linhas = [
        {
            'PRESTADOR': a.prestador,
            'DATA DO ATENDIMENTO': _data(a),
            'PROCEDIMENTO': a.procedimento,
            'VALOR PAGO': a.valor,
        }
        for a in sorted(uso.tit_atendimentos, key=lambda a: a.data)
    ]
    return pd.DataFrame(linhas)


def _df_dependentes(uso: UsoMantis) -> pd.DataFrame:
    linhas = [
        {
            'PRESTADOR': a.prestador,
            'MATRICULA DEPENDENTE': matricula,
            'NOME DEPENDENTE': a.nome_dependente,
            'DATA DO ATENDIMENTO': _data(a),
            'VALOR PAGO': a.valor,
        }
        for matricula, a in sorted(uso.deps_atendimentos, key=lambda item: (item[0], item[1].data))
    ]
    return pd.DataFrame(linhas)


def inicio_nome_relatorio(rede: tuple[str, str], tipo_curto: str, matricula_titular: str) -> str:
    """Início do número do documento (sem a data e hora da inclusão)."""
    return f'Utilização {tipo_curto} {rede[0]} - {matricula_titular}'


def _incluir(
    driver: webdriver.Remote,
    registro,
    rede: tuple[str, str],
    tipo: str,
    tipo_curto: str,
    df: pd.DataFrame,
    nome_titular: str,
    matricula_titular: str,
) -> str:
    """Anexa o PDF e devolve o número SEI dele."""
    inicio = inicio_nome_relatorio(rede, tipo_curto, matricula_titular)
    existente = encontrar_doc_por_nome(registro.docs_rodada, f'{TIPO_DOC} {inicio}')
    if existente is not None:
        registro.relatorios_na_arvore.append(existente['numero_sei'])
        logger.warning(f'Retomada: relatório {rede[1]} ({tipo}) já está na árvore ({existente["numero_sei"]}); não será anexado de novo')
        return existente['numero_sei']

    agora = datetime.now()
    caminho_pdf = transformar_xls_em_pdf(
        tit_matricula=matricula_titular,
        tit_nome=nome_titular.upper(),
        tipo=tipo,
        df=df,
        path_destino=DIR_UTILIZACOES_MANTIS_PDF,
        rede=rede[1],
    )
    num = f'{inicio} - {agora:%Y%m%d_%H%M%S}'
    incluir_doc_externo(
        driver,
        tipo_doc=TIPO_DOC,
        num=num,
        formato='Nato-digital',
        data=f'{agora:%d/%m/%Y}',
        path_anexo=caminho_pdf,
        nivel_acesso='Restrito',
        hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
    )
    registro.relatorios_incluidos.append(num)
    numero_sei = numero_sei_por_nome(driver, f'{TIPO_DOC} {num}')
    if numero_sei is None:
        raise ErroAvaliacao(f'Relatório {rede[1]} ({tipo}) anexado, mas não encontrado na árvore ({num}): a próxima execução o encontra pelo nome')
    logger.info(f'Relatório {rede[1]} ({tipo}) anexado ao processo: {num} ({numero_sei})')
    return numero_sei


def incluir_relatorios(
    driver: webdriver.Remote,
    registro,
    uso: UsoMantis,
    rede: tuple[str, str],
    nome_titular: str,
    matricula_titular: str,
) -> tuple[str, ...]:
    """Anexa os PDFs da rede (titular e dependentes) de quem tem
    atendimento e devolve o número SEI deles. Sem nenhum atendimento, não
    anexa nada."""
    docs = []
    if uso.tit_atendimentos:
        docs.append(_incluir(driver, registro, rede, 'Titular', 'Tit.', _df_titular(uso), nome_titular, matricula_titular))
    if uso.deps_atendimentos:
        docs.append(_incluir(driver, registro, rede, 'Dependente(s)', 'Dep.', _df_dependentes(uso), nome_titular, matricula_titular))
    return tuple(docs)
