import logging

from constantes import (
    BLOCO_MEMOS_DISA_DEPROC,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import ler_texto_doc, memos_geacs_novos, obter_ultimo_memo_apis
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui, validar_template
from matriculas_nao_encontradas import marcar_matriculas_nao_encontradas
from rede_propria import (
    BasesUso,
    ErroAvaliacao,
    MatriculasNaoEncontradas,
    avaliar_uso,
    registrar_uso,
)
from Registro import ProxAcao, RegistroMain
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import incluir_doc_sei_memo
from selenium import webdriver
from tags import (
    TAG_AVALIADO_USO_REDE_PROPRIA,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_PERIODO_VAR_DEP,
    adicionar_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import MemoDisa
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    UsoRedeBeneficiarios,
)

logger = logging.getLogger(__name__)


def obter_dados_ui(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> DadosUI:
    """Extrai as instruções do último memorando da APIS-Utilização."""
    memo_apis = obter_ultimo_memo_apis(tds_docs)
    if memo_apis is None:
        raise ErroAvaliacao('Não foi encontrado memorando da APIS-Utilização na árvore')
    registro.ult_memo_obtido = True
    registro.memo_apis_sei = memo_apis['numero_sei']

    doc_text = ler_texto_doc(driver, memo_apis)
    registro.conteudo_ult_memo_obtido = True

    try:
        registro.modelo_memo_apis = validar_template(doc_text)
        dados_ui = extrair_dados_ui(doc_text)
    except FormatoMemorandoInvalido:
        registro.prox_acao = ProxAcao.VERIFICAR_FORMATO_MEMO
        raise

    registro.dados_ui = dados_ui
    logger.info(
        f'Instruções da APIS extraídas (modelo {registro.modelo_memo_apis}) | '
        f'Titular: {dados_ui.matricula_titular} '
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


def _registrar_numeros_memos(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> None:
    """Obtém o número SEI dos memos criados (os memos da GEACS que não
    estavam na árvore). É só informativo: uma falha aqui não interrompe o
    processo, que já está com os memos no bloco e com os marcadores."""
    try:
        novos = memos_geacs_novos(driver, tds_docs)
    except Exception:
        logger.exception('Não foi possível obter o número SEI dos memos criados')
        return

    # Ordem de criação: DISA (se houver) e depois DEPROC
    esperados = int(registro.memo_disa_criado) + int(registro.memo_deproc_criado)
    if len(novos) != esperados:
        logger.warning(f'Número SEI dos memos não registrado: esperado(s) {esperados} memo(s) novo(s) na árvore, encontrado(s) {len(novos)}')
        return
    if registro.memo_disa_criado:
        registro.memo_disa_sei = novos[0]['numero_sei']
    registro.memo_deproc_sei = novos[-1]['numero_sei']


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
    registro.fluxo = 'NOVO - fluxo normal'
    dados_ui = obter_dados_ui(driver, registro, tds_docs)

    try:
        uso = avaliar_uso(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    except MatriculasNaoEncontradas as e:
        marcar_matriculas_nao_encontradas(driver, registro, tds_docs, e, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO)
        raise
    registrar_uso(registro, uso)

    if dados_ui.periodo_dependentes:
        adicionar_tag(driver, registro, TAG_PERIODO_VAR_DEP)

    if uso.alguem_usou:
        logger.info('Alguém usou a rede própria: memos DISA e DEPROC')
        _incluir_memo_disa(driver, registro, dados_ui, uso)
    else:
        logger.info('Ninguém usou a rede própria: somente memo DEPROC')
    _incluir_memo_deproc(driver, registro, dados_ui)

    adicionar_tag(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA)

    if uso.alguem_usou:
        adicionar_tag(driver, registro, TAG_MEMOS_DISA_DEPROC_NO_BLOCO)
        registro.prox_acao = ProxAcao.ASSINAR_DISA_DEPROC
    else:
        adicionar_tag(driver, registro, TAG_MEMO_DEPROC_NO_BLOCO)
        registro.prox_acao = ProxAcao.ASSINAR_DEPROC

    _registrar_numeros_memos(driver, registro, tds_docs)
    return registro
