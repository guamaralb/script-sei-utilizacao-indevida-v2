"""Fluxo normal dos processos NOVOS (aba 3 do docs/fluxo.drawio).

Cada memo criado recebe o seu marcador logo depois de entrar no bloco.
Os marcadores são a memória entre execuções: ao retomar, as etapas cujo
marcador já existe são puladas (ver main._tratar_novo).
"""

import logging

from constantes import (
    BLOCO_MEMO_APIS_FORMATO_INVALIDO,
    BLOCO_MEMO_APIS_PERIODO_DEPENDENTES,
    BLOCO_MEMO_APIS_SEM_MEMO,
    BLOCO_MEMO_DISA_VALIDAR_USOS_MANTIS,
    BLOCO_MEMOS_DISA_DEPROC,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import memos_geacs_novos, obter_memos_apis_para_geacs
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui, validar_template
from mantis import AvaliacaoMantis, BasesMantis, avaliar_uso_rede_propria_mantis, usos_mantis_alem_disa
from marcadores_disponiveis import garantir_marcadores_no_sei
from matriculas_nao_encontradas import incluir_memo_apis_mat_nao_encontradas
from rede_propria import (
    AvaliacaoDisa,
    BasesUso,
    ErroAvaliacao,
    avaliar_uso_rede_propria_disa,
    registrar_uso,
)
from Registro import ProxAcao, RegistroMain
from sei_automacao.classes.Memorando import Memorando
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import incluir_doc_sei_memo
from selenium import webdriver
from tags import (
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
    TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO,
    TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
    TAG_MEMO_DISA_VALIDAR_USOS_MANTIS,
    TAG_PERIODO_VAR_DEP,
    adicionar_tag,
    adicionar_tag_se_ausente,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisFormatoInvalido import MemoApisFormatoInvalido
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisPeriodoDependentes import MemoApisPeriodoDependentes
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import MemoApisSemMemo
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import MemoDisa
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaValidarUsosMantis import MemoDisaValidarUsosMantis

logger = logging.getLogger(__name__)


class MemoApisNaoEncontrado(ErroAvaliacao):
    """Não há memorando da APIS destinado à GEACS na árvore."""


def obter_dados_ui(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> DadosUI:
    """Extrai as instruções do memorando da APIS-Utilização destinado à
    GEACS. Deve haver exatamente um na árvore.

    Levanta MemoApisNaoEncontrado (nenhum), ErroAvaliacao (mais de um) ou
    FormatoMemorandoInvalido (inclusive o modelo "velho")."""
    memos_para_geacs = obter_memos_apis_para_geacs(driver, tds_docs)
    registro.memos_apis_geacs_sei = [memo['numero_sei'] for memo, _ in memos_para_geacs]
    if not memos_para_geacs:
        raise MemoApisNaoEncontrado('Não foi encontrado memorando da APIS-Utilização destinado à GEACS na árvore')
    if len(memos_para_geacs) > 1:
        raise ErroAvaliacao(f'Mais de um memorando da APIS-Utilização destinado à GEACS na árvore: {", ".join(registro.memos_apis_geacs_sei)}')

    memo_apis, doc_text = memos_para_geacs[0]
    registro.ult_memo_obtido = True
    registro.memo_apis_sei = memo_apis['numero_sei']
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


# ---------------------------------------------------------------------------
# Memos
# ---------------------------------------------------------------------------


def _incluir_memo(  # noqa: PLR0913, PLR0917
    driver: webdriver.Remote,
    registro: RegistroMain,
    memo: Memorando,
    bloco: int,
    prefixo_registro: str,
    descricao: str,
) -> None:
    """Cria o memo, insere no bloco e preenche <prefixo>_criado e
    <prefixo>_inserido_bloco no registro."""
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    setattr(registro, f'{prefixo_registro}_criado', True)
    registro.memos_criados.append(prefixo_registro)
    logger.info(f'Memo {descricao} criado')

    inserir_bloco_ass(driver, bloco)
    setattr(registro, f'{prefixo_registro}_inserido_bloco', True)
    logger.info(f'Memo {descricao} inserido no bloco {bloco}')


def _registrar_numeros_memos(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> None:
    """Obtém o número SEI dos memos criados (os memos da GEACS que não
    estavam na árvore), na ordem de criação. É só informativo: uma falha
    aqui não interrompe o processo, que já está com os memos no bloco e com
    os marcadores."""
    if not registro.memos_criados:
        return
    try:
        novos = memos_geacs_novos(driver, tds_docs)
    except Exception:
        logger.exception('Não foi possível obter o número SEI dos memos criados')
        return

    if len(novos) != len(registro.memos_criados):
        logger.warning(f'Número SEI dos memos não registrado: esperado(s) {len(registro.memos_criados)} memo(s) novo(s) na árvore, encontrado(s) {len(novos)}')
        return
    for prefixo, doc in zip(registro.memos_criados, novos, strict=True):
        setattr(registro, f'{prefixo}_sei', doc['numero_sei'])


def _finalizar(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict], prox_acao: str) -> RegistroMain:
    registro.prox_acao = prox_acao
    _registrar_numeros_memos(driver, registro, tds_docs)
    return registro


# ---------------------------------------------------------------------------
# Memo da APIS ausente ou inválido
# ---------------------------------------------------------------------------


def _tratar_sem_memo_apis(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict]) -> RegistroMain:
    logger.warning('Nenhum memorando da APIS destinado à GEACS: memo à APIS (sem memorando)')
    registro.fluxo = 'NOVO - sem memo da APIS'
    memo = MemoApisSemMemo(nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO)
    garantir_marcadores_no_sei(driver, [TAG_MEMO_APIS_SEM_MEMO])
    # TODO: antes de criar, procurar o memo pelo assunto (retomada)
    _incluir_memo(driver, registro, memo, BLOCO_MEMO_APIS_SEM_MEMO, 'memo_apis_sem_memo', 'à APIS (sem memorando)')
    adicionar_tag(driver, registro, TAG_MEMO_APIS_SEM_MEMO)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO)


def _tratar_formato_invalido(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict], erro: FormatoMemorandoInvalido) -> RegistroMain:
    logger.warning(f'Memorando da APIS em formato inválido: memo à APIS | {erro}')
    registro.fluxo = 'NOVO - memo da APIS em formato inválido'
    registro.motivo_formato_invalido = str(erro).splitlines()[0]
    memo = MemoApisFormatoInvalido(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        memo_apis_sei=registro.memo_apis_sei,
    )
    garantir_marcadores_no_sei(driver, [TAG_MEMO_APIS_FORMATO_INVALIDO])
    # TODO: antes de criar, procurar o memo pelo assunto (retomada)
    _incluir_memo(driver, registro, memo, BLOCO_MEMO_APIS_FORMATO_INVALIDO, 'memo_apis_formato_invalido', 'à APIS (formato inválido)')
    adicionar_tag(driver, registro, TAG_MEMO_APIS_FORMATO_INVALIDO)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_MEMO_APIS_FORMATO_INVALIDO)


# ---------------------------------------------------------------------------
# Base geral e base DISA
# ---------------------------------------------------------------------------


def _registrar_nao_encontradas(registro: RegistroMain, avaliacao: AvaliacaoDisa) -> None:
    registro.titular_nao_encontrado_base_geral = avaliacao.nao_encontradas_geral.titular
    registro.deps_nao_encontrados_base_geral = list(avaliacao.nao_encontradas_geral.dependentes)
    registro.titular_nao_encontrado = avaliacao.nao_encontradas_disa.titular
    registro.deps_nao_encontrados = list(avaliacao.nao_encontradas_disa.dependentes)


def _avaliar_disa(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI, bases: BasesUso) -> AvaliacaoDisa:
    """Avalia o uso na base DISA e adiciona 1.2.2 (se faltou matrícula na
    base DISA) e o marcador de avaliado (DISA). Os marcadores das etapas
    seguintes que dependem só desta avaliação (1.2.1 e o memo à APIS) são
    conferidos no SEI aqui também, antes de adicionar qualquer um."""
    avaliacao = avaliar_uso_rede_propria_disa(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    _registrar_nao_encontradas(registro, avaliacao)
    registrar_uso(registro, avaliacao.uso)

    tags = [TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO] if avaliacao.nao_encontradas_disa else []
    tags.append(TAG_AVALIADO_USO_REDE_PROPRIA_DISA)
    if avaliacao.nao_encontradas_geral:
        tags += [TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS]
    garantir_marcadores_no_sei(driver, tags)

    if avaliacao.nao_encontradas_disa:
        adicionar_tag_se_ausente(driver, registro, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO)
    adicionar_tag_se_ausente(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_DISA)
    return avaliacao


def _tratar_nao_encontradas_base_geral(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict], avaliacao: AvaliacaoDisa) -> RegistroMain:
    """1.2.1 (pesquisa feita na base) antes do memo; o marcador do memo
    depois que ele está no bloco. O processo para aqui."""
    registro.fluxo = 'NOVO - matrículas não encontradas na base geral'
    adicionar_tag_se_ausente(driver, registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO)
    incluir_memo_apis_mat_nao_encontradas(driver, registro, tds_docs, avaliacao.nao_encontradas_geral)
    if registro.memo_apis_mat_nao_encontradas_criado:
        registro.memos_criados.append('memo_apis_mat_nao_encontradas')
    adicionar_tag(driver, registro, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS)


# ---------------------------------------------------------------------------
# Período variável para dependentes
# ---------------------------------------------------------------------------


def _tratar_periodo_variavel(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict], avaliacao: AvaliacaoDisa) -> RegistroMain:
    """O processo para aqui até a APIS informar o período dos dependentes."""
    registro.fluxo = 'NOVO - período variável para dependentes'
    memo = MemoApisPeriodoDependentes(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        dependentes=avaliacao.dependentes,
    )
    garantir_marcadores_no_sei(driver, [TAG_PERIODO_VAR_DEP, TAG_MEMO_APIS_PERIODO_DEPENDENTES])
    adicionar_tag_se_ausente(driver, registro, TAG_PERIODO_VAR_DEP)
    # TODO: antes de criar, procurar o memo pelo assunto (retomada)
    _incluir_memo(driver, registro, memo, BLOCO_MEMO_APIS_PERIODO_DEPENDENTES, 'memo_apis_periodo_deps', 'à APIS (período dos dependentes)')
    adicionar_tag(driver, registro, TAG_MEMO_APIS_PERIODO_DEPENDENTES)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_MEMO_APIS_PERIODO_DEPS)


# ---------------------------------------------------------------------------
# MANTIS e memos DISA/DEPROC
# ---------------------------------------------------------------------------


def _registrar_uso_mantis(registro: RegistroMain, avaliacao: AvaliacaoMantis) -> None:
    propria, credenciada = avaliacao.rede_propria, avaliacao.rede_credenciada
    registro.tit_usou_mantis_rede_propria = propria.tit_usou
    registro.tit_valor_total_uso_mantis_rede_propria = propria.tit_valor_total
    registro.deps_que_usaram_mantis_rede_propria = list(propria.deps_que_usaram)
    registro.deps_valor_total_uso_mantis_rede_propria = propria.deps_valor_total
    registro.tit_usou_mantis_rede_credenciada = credenciada.tit_usou
    registro.tit_valor_total_uso_mantis_rede_credenciada = credenciada.tit_valor_total
    registro.deps_que_usaram_mantis_rede_credenciada = list(credenciada.deps_que_usaram)
    registro.deps_valor_total_uso_mantis_rede_credenciada = credenciada.deps_valor_total


def _tratar_usos_mantis_alem_disa(driver: webdriver.Remote, registro: RegistroMain, tds_docs: list[dict], memo: MemoDisaValidarUsosMantis) -> RegistroMain:
    """O processo para aqui até a DISA validar os usos.

    TODO: definir o processamento na próxima execução (depois da resposta
    da DISA)."""
    registro.fluxo = 'NOVO - validar usos do MANTIS'
    # TODO: antes de criar, procurar o memo pelo assunto (retomada)
    _incluir_memo(driver, registro, memo, BLOCO_MEMO_DISA_VALIDAR_USOS_MANTIS, 'memo_disa_validar_mantis', 'à DISA (validar usos do MANTIS)')
    adicionar_tag(driver, registro, TAG_MEMO_DISA_VALIDAR_USOS_MANTIS)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_MANTIS)


def _incluir_memo_disa(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI, avaliacao: AvaliacaoDisa) -> None:
    if tem_tag(registro, TAG_MEMO_DISA_USO_REDE_PROPRIA):
        logger.info('Retomada: memo DISA já está no bloco')
        return
    memo = MemoDisa(
        dados=dados_ui,
        uso=avaliacao.uso,
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
    )
    _incluir_memo(driver, registro, memo, BLOCO_MEMOS_DISA_DEPROC, 'memo_disa', 'DISA')
    adicionar_tag(driver, registro, TAG_MEMO_DISA_USO_REDE_PROPRIA)


def _incluir_memo_deproc(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI) -> None:
    memo = MemoDeproc(
        dados=dados_ui,
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
    )
    _incluir_memo(driver, registro, memo, BLOCO_MEMOS_DISA_DEPROC, 'memo_deproc', 'DEPROC')
    adicionar_tag(driver, registro, TAG_MEMO_DEPROC_COPARTICIPACAO)


def _avaliar_mantis_e_criar_memos(  # noqa: PLR0913, PLR0917
    driver: webdriver.Remote,
    registro: RegistroMain,
    tds_docs: list[dict],
    dados_ui: DadosUI,
    avaliacao_disa: AvaliacaoDisa,
    bases_mantis: BasesMantis,
) -> RegistroMain:
    uso_disa = avaliacao_disa.uso
    avaliacao_mantis = avaliar_uso_rede_propria_mantis(uso_disa.matricula_titular, avaliacao_disa.dependentes, dados_ui.periodo_titular, bases_mantis)
    _registrar_uso_mantis(registro, avaliacao_mantis)
    alem_disa = usos_mantis_alem_disa(uso_disa, avaliacao_mantis.rede_propria)
    registro.mats_uso_mantis_alem_disa = alem_disa

    if alem_disa:
        logger.warning(f'MANTIS com uso da rede própria que a base DISA marca como não uso: {alem_disa}')
        memo_validar = MemoDisaValidarUsosMantis(nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO, matriculas=alem_disa)
        tags = [TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, TAG_MEMO_DISA_VALIDAR_USOS_MANTIS]
    else:
        # Sem usos além da DISA, o uso do MANTIS está contido no da DISA
        alguem_usou = uso_disa.alguem_usou or avaliacao_mantis.rede_propria.alguem_usou
        tags = [TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS] + ([TAG_MEMO_DISA_USO_REDE_PROPRIA] if alguem_usou else []) + [TAG_MEMO_DEPROC_COPARTICIPACAO]
    garantir_marcadores_no_sei(driver, tags)

    adicionar_tag_se_ausente(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)
    if alem_disa:
        return _tratar_usos_mantis_alem_disa(driver, registro, tds_docs, memo_validar)

    if alguem_usou:
        logger.info('Alguém usou a rede própria: memos DISA e DEPROC')
        _incluir_memo_disa(driver, registro, dados_ui, avaliacao_disa)
    else:
        logger.info('Ninguém usou a rede própria: somente memo DEPROC')
    _incluir_memo_deproc(driver, registro, dados_ui)
    return _finalizar(driver, registro, tds_docs, ProxAcao.ASSINAR_DISA_DEPROC if alguem_usou else ProxAcao.ASSINAR_DEPROC)


# ---------------------------------------------------------------------------
# Fluxo normal
# ---------------------------------------------------------------------------


def processar_novo(
    driver: webdriver.Remote,
    registro: RegistroMain,
    tds_docs: list[dict],
    bases: BasesUso,
    bases_mantis: BasesMantis,
) -> RegistroMain:
    """Fluxo normal de processos NOVOS.

    Termina em um destes pontos:
    - sem memo da APIS para a GEACS: memo à APIS (sem memorando);
    - memo da APIS em formato inválido: memo à APIS (formato inválido);
    - matrícula fora da base geral: 1.2.1 e memo à APIS;
    - período variável para dependentes: 1.1 e memo à APIS;
    - MANTIS com uso da rede própria que a DISA não tem: memo à DISA;
    - memo DISA (se alguém usou a rede própria) e memo DEPROC.

    Em todos os casos o marcador do memo só é adicionado depois que ele
    está no bloco.
    """
    registro.fluxo = 'NOVO - fluxo normal'
    try:
        dados_ui = obter_dados_ui(driver, registro, tds_docs)
    except MemoApisNaoEncontrado:
        return _tratar_sem_memo_apis(driver, registro, tds_docs)
    except FormatoMemorandoInvalido as e:
        return _tratar_formato_invalido(driver, registro, tds_docs, e)

    avaliacao_disa = _avaliar_disa(driver, registro, dados_ui, bases)
    if avaliacao_disa.nao_encontradas_geral:
        return _tratar_nao_encontradas_base_geral(driver, registro, tds_docs, avaliacao_disa)

    if dados_ui.periodo_dependentes:
        return _tratar_periodo_variavel(driver, registro, tds_docs, avaliacao_disa)

    return _avaliar_mantis_e_criar_memos(driver, registro, tds_docs, dados_ui, avaliacao_disa, bases_mantis)
