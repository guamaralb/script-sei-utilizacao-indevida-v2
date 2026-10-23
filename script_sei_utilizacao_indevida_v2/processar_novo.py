"""Fluxo dos processos (colunas 3 e 4 do docs/fluxo.drawio). O processo
VELHO é separado antes, em main._tratar, e não passa por aqui.

Cada memo criado recebe o seu marcador logo depois de entrar no bloco.
Os marcadores são a memória entre execuções: o marcador de estado diz até
onde o processo chegou e, ao retomar, as etapas já feitas são puladas (ver
main._tratar). Cada novo estado substitui o anterior no SEI.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from constantes import (
    BLOCO_MEMO_APIS_FORMATO_INVALIDO,
    BLOCO_MEMO_APIS_PERIODO_DEPENDENTES,
    BLOCO_MEMO_APIS_SEM_MEMO,
    BLOCO_MEMO_APIS_SEM_USO,
    BLOCO_MEMO_DEPROC,
    BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    BLOCO_MEMO_DISA_VALIDAR_CONSTA,
    BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import obter_memos_apis_para_geacs
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui, validar_template
from mantis import AvaliacaoMantis, BasesMantis, UsoMantis, avaliar_uso_rede_propria_mantis, usos_mantis_alem_disa
from marcadores_disponiveis import garantir_marcadores_no_sei
from matriculas_nao_encontradas import incluir_memo_apis_mat_nao_encontradas
from memos_sei import incluir_memo, registrar_numeros_memos
from rede_propria import (
    BasesUso,
    ErroAvaliacao,
    MatriculasProcesso,
    avaliar_uso_rede_propria_disa,
    registrar_uso,
    verificar_base_apis,
)
from Registro import ProxAcao, RegistroMain
from relatorios_mantis import REDE_CREDENCIADA, REDE_PROPRIA, incluir_relatorios
from sei_automacao.classes.Memorando import Memorando
from selenium import webdriver
from tags import (
    TAG_AGUARDA_APIS_SEM_USO,
    TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO,
    TAG_AGUARDA_DISA_VALIDAR_CONSTA,
    TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    TAG_AVALIADO_USO_REDE_PROPRIA_DISA,
    TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS,
    TAG_DISA_NAO_USOU_RP,
    TAG_DISA_USOU_RP,
    TAG_MANTIS_NAO_USOU_RC,
    TAG_MANTIS_NAO_USOU_RP,
    TAG_MANTIS_USOU_RC,
    TAG_MANTIS_USOU_RP,
    TAG_MAT_NAO_ENCONTRADAS_APIS,
    TAG_MEMO_APIS_FORMATO_INVALIDO,
    TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    TAG_MEMO_APIS_SEM_MEMO,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_PERIODO_VAR_DEP,
    TAGS_RETOMADA_NOVO,
    adicionar_tag,
    adicionar_tag_se_ausente,
    estado_atual,
    remover_tag,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisFormatoInvalido import PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO, MemoApisFormatoInvalido
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisPeriodoDependentes import PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES, MemoApisPeriodoDependentes
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO, MemoApisSemMemo
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemUso import PADRAO_ASSUNTO_MEMO_APIS_SEM_USO, MemoApisSemUso
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC, MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
    MemoDisaSemMantisSolicitaRelatorio,
    MemoDisaValidarConsta,
    MemoDisaValidarNaoConsta,
)
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import UsoRedeBeneficiarios

logger = logging.getLogger(__name__)


class MemoApisNaoEncontrado(ErroAvaliacao):
    """Não há memorando da APIS destinado à GEACS na árvore."""


def obter_dados_ui(driver: webdriver.Remote, registro: RegistroMain) -> DadosUI:
    """Extrai as instruções do último memorando da APIS-Utilização
    destinado à GEACS. Os documentos depois dele são a rodada atual
    (registro.docs_rodada).

    Levanta MemoApisNaoEncontrado (nenhum) ou FormatoMemorandoInvalido
    (qualquer modelo diferente do novo_novo)."""
    memos_para_geacs = obter_memos_apis_para_geacs(driver, registro.tds_docs)
    registro.memos_apis_geacs_sei = [memo['numero_sei'] for memo, _ in memos_para_geacs]
    if not memos_para_geacs:
        raise MemoApisNaoEncontrado('Não foi encontrado memorando da APIS-Utilização destinado à GEACS na árvore')

    memo_apis, doc_text = memos_para_geacs[-1]
    if len(memos_para_geacs) > 1:
        logger.info(f'{len(memos_para_geacs)} memorandos da APIS destinados à GEACS: usado o último ({memo_apis["numero_sei"]})')
    registro.ult_memo_obtido = True
    registro.memo_apis = memo_apis
    registro.memo_apis_sei = memo_apis['numero_sei']
    registro.conteudo_ult_memo_obtido = True
    indice = next(i for i, doc in enumerate(registro.tds_docs) if doc['numero_sei'] == memo_apis['numero_sei'])
    registro.docs_rodada = registro.tds_docs[indice + 1 :]

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


def _etapa_feita(registro: RegistroMain, etapa: str) -> bool:
    """O estado do processo é esta etapa ou uma posterior (retomada)."""
    estado = estado_atual(registro)
    feita = estado in TAGS_RETOMADA_NOVO and TAGS_RETOMADA_NOVO.index(estado) >= TAGS_RETOMADA_NOVO.index(etapa)
    if feita:
        logger.info(f'Retomada: etapa "{etapa}" já feita (estado "{estado}")')
    return feita


def _finalizar(driver: webdriver.Remote, registro: RegistroMain, prox_acao: str) -> None:
    registro.prox_acao = prox_acao
    registrar_numeros_memos(driver, registro)


# ---------------------------------------------------------------------------
# Memos que param o processo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Parada:
    """Memo que para o processo até a resposta do destinatário."""

    fluxo: str
    descricao: str
    prefixo_registro: str
    # None: bloco ainda não configurado (o processo para antes do memo)
    bloco: int | None
    tag: str
    prox_acao: str
    padrao_assunto: re.Pattern


_SEM_MEMO_APIS = _Parada(
    fluxo='sem memo da APIS',
    descricao='à APIS (sem memorando)',
    prefixo_registro='memo_apis_sem_memo',
    bloco=BLOCO_MEMO_APIS_SEM_MEMO,
    tag=TAG_MEMO_APIS_SEM_MEMO,
    prox_acao=ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO,
)
_FORMATO_INVALIDO = _Parada(
    fluxo='memo da APIS em formato inválido',
    descricao='à APIS (formato inválido)',
    prefixo_registro='memo_apis_formato_invalido',
    bloco=BLOCO_MEMO_APIS_FORMATO_INVALIDO,
    tag=TAG_MEMO_APIS_FORMATO_INVALIDO,
    prox_acao=ProxAcao.ASSINAR_MEMO_APIS_FORMATO_INVALIDO,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO,
)
_PERIODO_VARIAVEL = _Parada(
    fluxo='período variável para dependentes',
    descricao='à APIS (período dos dependentes)',
    prefixo_registro='memo_apis_periodo_deps',
    bloco=BLOCO_MEMO_APIS_PERIODO_DEPENDENTES,
    tag=TAG_MEMO_APIS_PERIODO_DEPENDENTES,
    prox_acao=ProxAcao.ASSINAR_MEMO_APIS_PERIODO_DEPS,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES,
)
# Memos à DISA (comparação base DISA x MANTIS, rede própria). O processo
# fica parado até o retorno da DISA e não vai para a DEPROC
_DISA_VALIDAR_CONSTA = _Parada(
    fluxo='DISA sim, MANTIS sim: memo à DISA (validar e complementar)',
    descricao='à DISA (validar e complementar)',
    prefixo_registro='memo_disa',
    bloco=BLOCO_MEMO_DISA_VALIDAR_CONSTA,
    tag=TAG_AGUARDA_DISA_VALIDAR_CONSTA,
    prox_acao=ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
)
_DISA_VALIDAR_NAO_CONSTA = _Parada(
    fluxo='DISA não, MANTIS sim: memo à DISA (validar, não consta)',
    descricao='à DISA (validar, não consta na base DISA)',
    prefixo_registro='memo_disa',
    bloco=BLOCO_MEMO_DISA_VALIDAR_NAO_CONSTA,
    tag=TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    prox_acao=ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_NAO_CONSTA,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
)
_DISA_SEM_MANTIS_RELATORIO = _Parada(
    fluxo='DISA sim, MANTIS não: memo à DISA (sem MANTIS, solicita relatório)',
    descricao='à DISA (sem MANTIS, solicita relatório)',
    prefixo_registro='memo_disa',
    bloco=BLOCO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    tag=TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO,
    prox_acao=ProxAcao.ASSINAR_MEMO_DISA_SEM_MANTIS_RELATORIO,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
)
# Nenhum uso em nenhuma base (DISA, MANTIS RP e RC): memo à APIS, sem DEPROC
_APIS_SEM_USO = _Parada(
    fluxo='DISA não, MANTIS RP não, MANTIS RC não: memo à APIS (nenhum uso)',
    descricao='à APIS (nenhum uso nas bases)',
    prefixo_registro='memo_apis_sem_uso',
    bloco=BLOCO_MEMO_APIS_SEM_USO,
    tag=TAG_AGUARDA_APIS_SEM_USO,
    prox_acao=ProxAcao.ASSINAR_MEMO_APIS_SEM_USO,
    padrao_assunto=PADRAO_ASSUNTO_MEMO_APIS_SEM_USO,
)


def _conferir_bloco(parada: _Parada) -> None:
    if parada.bloco is None:
        raise ErroAvaliacao(f'Bloco do memo {parada.descricao} não configurado (constantes): nenhum documento foi criado')


def _parar_com_memo(driver: webdriver.Remote, registro: RegistroMain, memo: Memorando, parada: _Parada, tag_antes: str | None = None) -> None:
    """tag_antes registra a verificação que levou à parada e entra antes
    do memo; o marcador do memo, depois que ele está no bloco. O memo é
    procurado pelo assunto antes de ser criado (retomada)."""
    _conferir_bloco(parada)
    registro.fluxo = f'NOVO - {parada.fluxo}'
    garantir_marcadores_no_sei(driver, [t for t in (tag_antes, parada.tag) if t])
    if tag_antes:
        adicionar_tag_se_ausente(driver, registro, tag_antes)
    incluir_memo(driver, registro, memo, parada.bloco, parada.prefixo_registro, parada.descricao, padrao_assunto=parada.padrao_assunto)
    adicionar_tag(driver, registro, parada.tag)
    _finalizar(driver, registro, parada.prox_acao)


def _parar_sem_memo_apis(driver: webdriver.Remote, registro: RegistroMain) -> None:
    logger.warning('Nenhum memorando da APIS destinado à GEACS: memo à APIS (sem memorando)')
    memo = MemoApisSemMemo(nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO)
    _parar_com_memo(driver, registro, memo, _SEM_MEMO_APIS)


def _parar_formato_invalido(driver: webdriver.Remote, registro: RegistroMain, erro: FormatoMemorandoInvalido) -> None:
    logger.warning(f'Memorando da APIS em formato inválido: memo à APIS | {erro}')
    registro.motivo_formato_invalido = str(erro).splitlines()[0]
    memo = MemoApisFormatoInvalido(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        memo_apis=registro.memo_apis,
    )
    _parar_com_memo(driver, registro, memo, _FORMATO_INVALIDO)


def _parar_periodo_variavel(driver: webdriver.Remote, registro: RegistroMain, matriculas: MatriculasProcesso) -> None:
    memo = MemoApisPeriodoDependentes(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        dependentes=matriculas.dependentes,
        memo_apis=registro.memo_apis,
    )
    _parar_com_memo(driver, registro, memo, _PERIODO_VARIAVEL, tag_antes=TAG_PERIODO_VAR_DEP)


def _parar_nao_encontradas_base_apis(driver: webdriver.Remote, registro: RegistroMain, matriculas: MatriculasProcesso) -> None:
    registro.fluxo = 'NOVO - matrículas não encontradas na base APIS'
    garantir_marcadores_no_sei(driver, [TAG_MAT_NAO_ENCONTRADAS_APIS, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS])
    adicionar_tag_se_ausente(driver, registro, TAG_MAT_NAO_ENCONTRADAS_APIS)
    incluir_memo_apis_mat_nao_encontradas(driver, registro, matriculas.nao_encontradas_apis)
    adicionar_tag(driver, registro, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS)
    _finalizar(driver, registro, ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS)


# ---------------------------------------------------------------------------
# Base APIS e base DISA
# ---------------------------------------------------------------------------


def _verificar_base_apis(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI, bases: BasesUso) -> MatriculasProcesso:
    """A existência das matrículas é conferida só na base APIS. Se todas
    estão na base e o processo tem o 1.2.1 (base corrigida depois), o
    marcador é removido e o fluxo segue."""
    matriculas = verificar_base_apis(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    registro.titular_nao_encontrado_base_geral = matriculas.nao_encontradas_apis.titular
    registro.deps_nao_encontrados_base_geral = list(matriculas.nao_encontradas_apis.dependentes)
    if not matriculas.nao_encontradas_apis and tem_tag(registro, TAG_MAT_NAO_ENCONTRADAS_APIS):
        logger.info('Matrículas agora encontradas na base APIS (base corrigida): o marcador 1.2.1 é removido e o fluxo segue')
        remover_tag(driver, registro, TAG_MAT_NAO_ENCONTRADAS_APIS)
    return matriculas


def _registrar_par(driver: webdriver.Remote, registro: RegistroMain, tag: str) -> None:
    """Marcador de um par base DISA/MANTIS: adicionar_tag remove o outro do
    par, se a base mudou desde a última passagem."""
    if not tem_tag(registro, tag):
        adicionar_tag(driver, registro, tag)


def _avaliar_disa(driver: webdriver.Remote, registro: RegistroMain, matriculas: MatriculasProcesso, bases: BasesUso) -> UsoRedeBeneficiarios:
    """Avalia o uso da rede própria na base DISA e adiciona o par base DISA
    e o marcador de avaliado (DISA)."""
    uso = avaliar_uso_rede_propria_disa(matriculas, bases)
    registrar_uso(registro, uso)

    tag_par = TAG_DISA_USOU_RP if uso.alguem_usou else TAG_DISA_NAO_USOU_RP
    garantir_marcadores_no_sei(driver, [tag_par, TAG_AVALIADO_USO_REDE_PROPRIA_DISA])
    _registrar_par(driver, registro, tag_par)
    if not _etapa_feita(registro, TAG_AVALIADO_USO_REDE_PROPRIA_DISA):
        adicionar_tag(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_DISA)
    return uso


# ---------------------------------------------------------------------------
# MANTIS, relatórios e memos DISA/DEPROC
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


def _sim_nao(valor: bool) -> str:
    return 'sim' if valor else 'não'


# Número SEI provisório dos relatórios da rede própria: o memo é montado
# com ele só para ser conferido antes de qualquer ação no SEI, e montado de
# novo depois de anexar os relatórios
_RELATORIOS_A_ANEXAR = ('<relatório a anexar>',)


def _escolher_memo(
    registro: RegistroMain,
    dados_ui: DadosUI,
    uso_disa: UsoRedeBeneficiarios,
    propria: UsoMantis,
    usou_rc: bool,
) -> tuple[_Parada | None, Callable[[tuple[str, ...]], Memorando]]:
    """A parada (None: memo DEPROC, conclusão) e uma função que monta o memo
    a partir do número SEI dos relatórios da rede própria, citados nos memos
    à DISA de validação."""
    if not (uso_disa.alguem_usou or propria.alguem_usou):
        if usou_rc:
            return None, lambda docs_rp: MemoDeproc(dados=dados_ui, usou_rede_credenciada=True, nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO, memo_apis=registro.memo_apis)
        return _APIS_SEM_USO, lambda docs_rp: MemoApisSemUso(dados=dados_ui, memo_apis=registro.memo_apis, nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO)

    argumentos = {
        'dados': dados_ui,
        'memo_apis': registro.memo_apis,
        'uso_disa': uso_disa,
        'tit_usou_mantis': propria.tit_usou,
        'deps_que_usaram_mantis': propria.deps_que_usaram,
        'nome_signatario': NOME_SIGNATARIO,
        'cargo_signatario': CARGO_SIGNATARIO,
    }
    if not propria.alguem_usou:
        return _DISA_SEM_MANTIS_RELATORIO, lambda docs_rp: MemoDisaSemMantisSolicitaRelatorio(**argumentos)
    parada, classe = (_DISA_VALIDAR_CONSTA, MemoDisaValidarConsta) if uso_disa.alguem_usou else (_DISA_VALIDAR_NAO_CONSTA, MemoDisaValidarNaoConsta)
    return parada, lambda docs_rp: classe(**argumentos, docs_relatorio_rp=docs_rp)


def _avaliar_mantis_e_criar_docs(
    driver: webdriver.Remote,
    registro: RegistroMain,
    dados_ui: DadosUI,
    uso_disa: UsoRedeBeneficiarios,
    matriculas: MatriculasProcesso,
    bases_mantis: BasesMantis,
) -> None:
    """Compara o uso da rede própria na base DISA e no MANTIS (processo
    inteiro: alguém usou) e decide o memo:

    - DISA sim, MANTIS RP sim: memo à DISA (validar e complementar);
    - DISA não, MANTIS RP sim: memo à DISA (validar, não consta);
    - DISA sim, MANTIS RP não: memo à DISA (sem MANTIS, solicita relatório);
    - DISA não, MANTIS RP não: memo DEPROC se alguém usou a rede
      credenciada; senão, memo à APIS (nenhum uso nas bases).

    Em todos os casos, os relatórios RP e RC de quem usou entram antes do
    memo. Quem vai para a DISA não vai para a DEPROC."""
    mantis = avaliar_uso_rede_propria_mantis(matriculas.titular, matriculas.dependentes, dados_ui.periodo_titular, bases_mantis)
    _registrar_uso_mantis(registro, mantis)
    registro.mats_uso_mantis_alem_disa = usos_mantis_alem_disa(uso_disa, mantis.rede_propria)
    propria, credenciada = mantis.rede_propria, mantis.rede_credenciada
    usou_disa, usou_rp, usou_rc = uso_disa.alguem_usou, propria.alguem_usou, credenciada.alguem_usou
    registro.caso_disa_mantis = f'DISA {_sim_nao(usou_disa)}, MANTIS RP {_sim_nao(usou_rp)}, MANTIS RC {_sim_nao(usou_rc)}'
    logger.info(f'Base DISA x MANTIS: {registro.caso_disa_mantis} | RP no MANTIS e fora da base DISA: {registro.mats_uso_mantis_alem_disa or "-"}')

    # O memo é montado antes de qualquer ação no SEI: texto pendente
    # (TextoMemoPendente) ou bloco não configurado param o processo aqui.
    # É montado de novo depois dos relatórios, com o número SEI deles
    parada, montar_memo = _escolher_memo(registro, dados_ui, uso_disa, propria, usou_rc)
    montar_memo(_RELATORIOS_A_ANEXAR)
    if parada is not None:
        _conferir_bloco(parada)
    tag_final = parada.tag if parada is not None else TAG_MEMO_DEPROC_COPARTICIPACAO

    tag_rp = TAG_MANTIS_USOU_RP if usou_rp else TAG_MANTIS_NAO_USOU_RP
    tag_rc = TAG_MANTIS_USOU_RC if usou_rc else TAG_MANTIS_NAO_USOU_RC
    garantir_marcadores_no_sei(driver, [tag_rp, tag_rc, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, tag_final])
    _registrar_par(driver, registro, tag_rp)
    _registrar_par(driver, registro, tag_rc)
    if not _etapa_feita(registro, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS):
        adicionar_tag(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)

    # Relatórios de quem usou (sem atendimento, nada é anexado)
    nome, matricula = dados_ui.nome_titular, matriculas.titular
    docs_rp = incluir_relatorios(driver, registro, propria, REDE_PROPRIA, nome, matricula)
    incluir_relatorios(driver, registro, credenciada, REDE_CREDENCIADA, nome, matricula)
    memo = montar_memo(docs_rp)
    if parada is not None:
        _parar_com_memo(driver, registro, memo, parada)
        return

    registro.fluxo = 'NOVO - DISA não, MANTIS RP não, MANTIS RC sim: memo DEPROC'
    incluir_memo(driver, registro, memo, BLOCO_MEMO_DEPROC, 'memo_deproc', 'DEPROC', padrao_assunto=PADRAO_ASSUNTO_MEMO_DEPROC)
    adicionar_tag(driver, registro, TAG_MEMO_DEPROC_COPARTICIPACAO)
    _finalizar(driver, registro, ProxAcao.ASSINAR_DEPROC)


# ---------------------------------------------------------------------------
# Fluxo
# ---------------------------------------------------------------------------


def processar_novo(
    driver: webdriver.Remote,
    registro: RegistroMain,
    bases: BasesUso,
    bases_mantis: BasesMantis,
) -> None:
    """Fluxo dos processos (não VELHOS), do início ou retomando pelo
    marcador de estado (1.6 ou 1.8).

    Termina em um destes pontos:
    - sem memo da APIS para a GEACS: memo à APIS (sem memorando);
    - memo da APIS em formato inválido: memo à APIS (formato inválido);
    - matrícula fora da base APIS: 1.2.1 e memo à APIS;
    - período variável para dependentes: 1.1 e memo à APIS;
    - uso da rede própria na base DISA e/ou no MANTIS: memo à DISA (um dos
      três casos);
    - sem uso da rede própria, com uso da rede credenciada: memo DEPROC;
    - nenhum uso em nenhuma base: memo à APIS.

    Em todos os casos o marcador do memo só é adicionado depois que ele
    está no bloco.
    """
    registro.fluxo = 'NOVO - fluxo normal'
    try:
        dados_ui = obter_dados_ui(driver, registro)
    except MemoApisNaoEncontrado:
        _parar_sem_memo_apis(driver, registro)
        return
    except FormatoMemorandoInvalido as e:
        _parar_formato_invalido(driver, registro, e)
        return

    matriculas = _verificar_base_apis(driver, registro, dados_ui, bases)
    if matriculas.nao_encontradas_apis:
        _parar_nao_encontradas_base_apis(driver, registro, matriculas)
        return

    uso_disa = _avaliar_disa(driver, registro, matriculas, bases)
    if dados_ui.periodo_dependentes:
        _parar_periodo_variavel(driver, registro, matriculas)
    else:
        _avaliar_mantis_e_criar_docs(driver, registro, dados_ui, uso_disa, matriculas, bases_mantis)
