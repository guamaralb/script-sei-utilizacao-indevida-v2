"""Fluxo de processos VELHOS (somente estrutura).

TODO:
    - Definir os marcadores de texto que distinguem "nova pesquisa" de
      "atualizar pesquisa" nos memos da APIS.
    - Avaliar o uso da rede própria antes da pesquisa
      (rede_propria.avaliar_uso). Dependentes citados sem matrícula
      explícita ("AVERIGUAR") já geram ErroAvaliacao. Matrícula não
      encontrada na base geral ou na da rede própria levanta
      MatriculasNaoEncontradas: chamar marcar_matriculas_nao_encontradas com
      TAG_MAT_NAO_ENCONTRADAS_GERAL_VELHO e TAG_MAT_NAO_ENCONTRADAS_DISA_VELHO
      e levantar o erro de novo (os marcadores já são tratados em
      main._tratar_velho).
    - Implementar os fluxos de cada instrução. Por enquanto o processo só
      recebe o marcador da pendência:
        - sem instrução de nova pesquisa: TAG_TRANSFORMAR_EXCEL_EM_PDF;
        - com instrução de nova pesquisa: TAG_REFAZER_REL_UI.
"""

import logging
import re

from docs_processo import ler_texto_doc, obter_memos_apis_apos_email
from rede_propria import ErroAvaliacao
from Registro import RegistroMain
from sei_automacao.processo import adicionar_marcador
from sei_automacao.processo.arvore import selecionar_doc_arvore
from selenium import webdriver
from tags import TAG_REFAZER_REL_UI, TAG_TRANSFORMAR_EXCEL_EM_PDF

logger = logging.getLogger(__name__)

_INSTRUCAO_ATUALIZAR_PESQUISA = 'atualizar_pesquisa'
_INSTRUCAO_NOVA_PESQUISA = 'nova_pesquisa'

# Todos os marcadores de uma instrução precisam estar no texto do memo.
# Instruções com dicionário vazio ainda não foram definidas e são ignoradas.
_MARCADORES_INSTRUCOES: dict[str, dict[str, str]] = {
    # TODO: confirmar marcadores
    _INSTRUCAO_ATUALIZAR_PESQUISA: {
        'pedido de atualização': r'atualiza[cç][ãa]o do levantamento',
        'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
        'campo "Nome completo"': r'Nome completo:',
        'campo "Matrícula" (titular)': r'Matr[íi]cula:',
        'campo "Período titular"': (r'Per[íi]odo de apura[çc][ãa]o do titular:'),
    },
    # TODO: definir marcadores
    _INSTRUCAO_NOVA_PESQUISA: {},
}


def _identificar_instrucao(txt_memo: str) -> str | None:
    for instrucao, marcadores in _MARCADORES_INSTRUCOES.items():
        if not marcadores:
            continue
        if all(re.search(padrao, txt_memo, flags=re.IGNORECASE) for padrao in marcadores.values()):
            return instrucao
    return None


def _encontrar_instrucoes(driver: webdriver.Remote, memos_apis: list[dict]) -> list[str]:
    instrucoes = []
    for memo in memos_apis:
        instrucao = _identificar_instrucao(ler_texto_doc(driver, memo))
        logger.info(f'Memo APIS {memo["numero_sei"]}: instrução {instrucao or "não identificada"}')
        if instrucao:
            instrucoes.append(instrucao)
    return list(dict.fromkeys(instrucoes))


def _baixar_planilhas_antigas(driver: webdriver.Remote, docs_geacs: list[dict]) -> None:
    """TODO: hoje apenas seleciona as planilhas; falta o download."""
    for planilha in docs_geacs:
        if 'Planilha Utilização' in planilha['nome_arvore']:
            selecionar_doc_arvore(driver, planilha['numero_sei'])


def _marcar_transformar_excel_em_pdf(driver: webdriver.Remote, registro: RegistroMain) -> None:
    """Sem instrução de nova pesquisa: o relatório de UI antigo será
    transformado em PDF (fluxo ainda não implementado)."""
    adicionar_marcador(driver, TAG_TRANSFORMAR_EXCEL_EM_PDF)
    registro.tag_transformar_excel_em_pdf = True
    logger.info(f'Marcador adicionado: "{TAG_TRANSFORMAR_EXCEL_EM_PDF}"')
    registro.prox_acao = 'Processo VELHO: transformar Excel em PDF (fluxo ainda não implementado)'


def _marcar_refazer_rel_ui(driver: webdriver.Remote, registro: RegistroMain) -> None:
    """Com instrução de nova pesquisa: o relatório de UI será refeito
    (fluxo ainda não implementado).

    TODO: antes da pesquisa, executar a consulta à DISA e à DEPROC
    (avaliar_uso e memos no bloco 7697744), como no fluxo dos NOVOS.
    """
    adicionar_marcador(driver, TAG_REFAZER_REL_UI)
    registro.tag_refazer_rel_ui = True
    logger.info(f'Marcador adicionado: "{TAG_REFAZER_REL_UI}"')
    registro.prox_acao = 'Processo VELHO: refazer relatório de UI (fluxo ainda não implementado)'


def processar_velho(
    driver: webdriver.Remote,
    registro: RegistroMain,
    docs_geacs: list[dict],
    tds_docs: list[dict],
) -> RegistroMain:
    memos_apis = obter_memos_apis_apos_email(tds_docs)

    if memos_apis is None:
        raise ErroAvaliacao('Não foi encontrado o e-mail da APIS utilizado como referência para a busca das instruções')
    if not memos_apis:
        raise ErroAvaliacao('Não há memorandos da APIS após o e-mail de referência')

    instrucoes = _encontrar_instrucoes(driver, memos_apis)
    registro.instrucoes_velho = '; '.join(instrucoes) or None
    logger.info(f'Instruções identificadas: {instrucoes or "nenhuma"}')

    # TODO: avaliar uso da rede própria aqui (ver docstring do módulo)

    if len(instrucoes) > 1:
        raise ErroAvaliacao(f'Instruções conflitantes nos memos da APIS: {instrucoes}')

    if _INSTRUCAO_NOVA_PESQUISA in instrucoes:
        _marcar_refazer_rel_ui(driver, registro)
    elif instrucoes or _MARCADORES_INSTRUCOES[_INSTRUCAO_NOVA_PESQUISA]:
        _marcar_transformar_excel_em_pdf(driver, registro)
    else:
        # Enquanto os critérios de "nova pesquisa" não forem definidos, não
        # é possível afirmar que o processo não tem essa instrução. Sem o
        # marcador, o processo é reavaliado na próxima execução.
        registro.prox_acao = 'Processo VELHO: nenhuma instrução identificada nos memos da APIS (critérios ainda em definição)'

    return registro
