import logging

from constantes import (
    BLOCO_MEMOS_DISA_DEPROC,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import ler_texto_doc, obter_ultimo_memo_apis
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui
from matriculas_nao_encontradas import marcar_matriculas_nao_encontradas
from rede_propria import (
    BasesUso,
    ErroAvaliacao,
    MatriculasNaoEncontradas,
    avaliar_uso,
    registrar_uso,
)
from Registro import RegistroMain
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import adicionar_marcador, incluir_doc_sei_memo
from selenium import webdriver
from tags import (
    TAG_AVALIADO_USO_REDE_PROPRIA,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_PERIODO_VAR_DEP,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import MemoDisa
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    UsoRedeBeneficiarios,
)

logger = logging.getLogger(__name__)


def _adicionar_marcador(driver: webdriver.Remote, tag: str) -> None:
    adicionar_marcador(driver, tag)
    logger.info(f'Marcador adicionado: "{tag}"')


def obter_dados_ui(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> DadosUI:
    """Extrai as instruções do último memorando da APIS-Utilização."""
    memo_apis = obter_ultimo_memo_apis(tds_docs)
    if memo_apis is None:
        raise ErroAvaliacao('Não foi encontrado memorando da APIS-Utilização na árvore')
    registro.ult_memo_obtido = True

    doc_text = ler_texto_doc(driver, memo_apis)
    registro.conteudo_ult_memo_obtido = True

    try:
        dados_ui = extrair_dados_ui(doc_text)
    except FormatoMemorandoInvalido:
        registro.prox_acao = 'Verificar erro no formato do memo'
        raise

    registro.dados_ui = dados_ui
    logger.info(
        f'Instruções da APIS extraídas | Titular: {dados_ui.matricula_titular} '
        f'| Período titular: {dados_ui.periodo_titular} | '
        f'Dependentes: {dados_ui.matriculas_dependentes or "-"} | '
        f'Período variável p/ dependentes: '
        f'{"sim" if dados_ui.periodo_dependentes else "não"}'
    )
    return dados_ui


def _incluir_memo_disa(
    driver: webdriver.Remote,
    registro: RegistroMain,
    dados_ui: DadosUI,
    uso: UsoRedeBeneficiarios,
) -> None:
    memo = MemoDisa(
        dados=dados_ui,
        uso=uso,
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
    )
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    registro.memo_disa_criado = True
    logger.info('Memo DISA criado')

    inserir_bloco_ass(driver, BLOCO_MEMOS_DISA_DEPROC)
    registro.memo_disa_inserido_bloco = True
    logger.info(f'Memo DISA inserido no bloco {BLOCO_MEMOS_DISA_DEPROC}')


def _incluir_memo_deproc(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI) -> None:
    memo = MemoDeproc(
        dados=dados_ui,
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
    )
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    registro.memo_deproc_criado = True
    logger.info('Memo DEPROC criado')

    inserir_bloco_ass(driver, BLOCO_MEMOS_DISA_DEPROC)
    registro.memo_deproc_inserido_bloco = True
    logger.info(f'Memo DEPROC inserido no bloco {BLOCO_MEMOS_DISA_DEPROC}')


def processar_novo(
    driver: webdriver.Remote,
    registro: RegistroMain,
    tds_docs: list[dict],
    bases: BasesUso,
) -> RegistroMain:
    """Fluxo normal de processos NOVOS.

    - Alguém usou a rede própria: memo DISA (quem usou e quem não usou)
      e memo DEPROC (todos).
    - Ninguém usou: somente memo DEPROC.

    Os marcadores de conclusão (avaliado e memos no bloco) só são
    colocados depois que os memos estão no bloco. Assim, se o script
    falhar no meio, o processo fica com o marcador NOVO e com memos da
    GEACS, e a próxima execução o sinaliza para verificação em vez de
    duplicar memos.
    """
    dados_ui = obter_dados_ui(driver, registro, tds_docs)

    try:
        uso = avaliar_uso(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    except MatriculasNaoEncontradas as e:
        marcar_matriculas_nao_encontradas(driver, registro, e, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO)
        raise
    registrar_uso(registro, uso)

    if dados_ui.periodo_dependentes:
        _adicionar_marcador(driver, TAG_PERIODO_VAR_DEP)
        registro.tag_periodo_var_deps = True

    if uso.alguem_usou:
        logger.info('Alguém usou a rede própria: memos DISA e DEPROC')
        _incluir_memo_disa(driver, registro, dados_ui, uso)
    else:
        logger.info('Ninguém usou a rede própria: somente memo DEPROC')
    _incluir_memo_deproc(driver, registro, dados_ui)

    _adicionar_marcador(driver, TAG_AVALIADO_USO_REDE_PROPRIA)
    registro.tag_avaliado_se_usou_rede_propria = True

    if uso.alguem_usou:
        _adicionar_marcador(driver, TAG_MEMOS_DISA_DEPROC_NO_BLOCO)
        registro.tag_memos_no_bloco = True
        registro.prox_acao = 'Assinar memorandos DISA e DEPROC e encaminhar'
    else:
        _adicionar_marcador(driver, TAG_MEMO_DEPROC_NO_BLOCO)
        registro.tag_memo_deproc_no_bloco = True
        registro.prox_acao = 'Assinar memorando DEPROC e encaminhar'

    return registro
