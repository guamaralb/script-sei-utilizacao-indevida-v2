"""Fluxo dos processos (aba 3 do docs/fluxo.drawio): fluxo normal e
processo VELHO (enviado à DISA e à DEPROC antes da avaliação).

Cada memo criado recebe o seu marcador logo depois de entrar no bloco.
Os marcadores são a memória entre execuções: o marcador de estado diz até
onde o processo chegou e, ao retomar, as etapas já feitas são puladas (ver
main._tratar). Cada novo estado substitui o anterior no SEI.
"""

import logging
import re
from dataclasses import dataclass

from constantes import (
    BLOCO_MEMO_APIS_FORMATO_INVALIDO,
    BLOCO_MEMO_APIS_PERIODO_DEPENDENTES,
    BLOCO_MEMO_APIS_SEM_MEMO,
    BLOCO_MEMOS_DISA_DEPROC,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import obter_memos_apis_para_geacs
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui, validar_template
from mantis import AvaliacaoMantis, BasesMantis, avaliar_uso_rede_propria_mantis, usos_mantis_alem_disa
from marcadores_disponiveis import garantir_marcadores_no_sei
from matriculas_nao_encontradas import incluir_memo_apis_mat_nao_encontradas
from memos_sei import incluir_memo, registrar_numeros_memos
from rede_propria import (
    AvaliacaoDisa,
    BasesUso,
    ErroAvaliacao,
    avaliar_uso_rede_propria_disa,
    registrar_uso,
)
from Registro import ProxAcao, RegistroMain
from relatorios_mantis import REDE_CREDENCIADA, REDE_PROPRIA, incluir_relatorios
from sei_automacao.classes.Memorando import Memorando
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
    TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO,
    TAG_PERIODO_VAR_DEP,
    TAG_VELHO_MEMO_DEPROC,
    TAG_VELHO_MEMO_DISA,
    TAGS_RETOMADA_NOVO,
    adicionar_tag,
    adicionar_tag_se_ausente,
    estado_atual,
    tem_tag,
)

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisFormatoInvalido import PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO, MemoApisFormatoInvalido
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisPeriodoDependentes import PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES, MemoApisPeriodoDependentes
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO, MemoApisSemMemo
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC, MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeprocRedeCredenciada import PADRAO_ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA, MemoDeprocRedeCredenciada
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import PADRAO_ASSUNTO_MEMO_DISA, MemoDisa

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
    bloco: int
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


def _ramo(registro: RegistroMain) -> str:
    return 'VELHO' if registro.velho else 'NOVO'


def _parar_com_memo(driver: webdriver.Remote, registro: RegistroMain, memo: Memorando, parada: _Parada, tag_antes: str | None = None) -> None:
    """tag_antes registra a verificação que levou à parada e entra antes
    do memo; o marcador do memo, depois que ele está no bloco. O memo é
    procurado pelo assunto antes de ser criado (retomada)."""
    registro.fluxo = f'{_ramo(registro)} - {parada.fluxo}'
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
        memo_apis_sei=registro.memo_apis_sei,
    )
    _parar_com_memo(driver, registro, memo, _FORMATO_INVALIDO)


def _parar_periodo_variavel(driver: webdriver.Remote, registro: RegistroMain, avaliacao: AvaliacaoDisa) -> None:
    memo = MemoApisPeriodoDependentes(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        dependentes=avaliacao.dependentes,
    )
    _parar_com_memo(driver, registro, memo, _PERIODO_VARIAVEL, tag_antes=TAG_PERIODO_VAR_DEP)


def _parar_nao_encontradas_base_geral(driver: webdriver.Remote, registro: RegistroMain, avaliacao: AvaliacaoDisa) -> None:
    registro.fluxo = f'{_ramo(registro)} - matrículas não encontradas na base geral'
    adicionar_tag_se_ausente(driver, registro, TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO)
    incluir_memo_apis_mat_nao_encontradas(driver, registro, avaliacao.nao_encontradas_geral)
    adicionar_tag(driver, registro, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS)
    _finalizar(driver, registro, ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS)


# ---------------------------------------------------------------------------
# Base geral e base DISA
# ---------------------------------------------------------------------------


def _avaliar_disa(driver: webdriver.Remote, registro: RegistroMain, dados_ui: DadosUI, bases: BasesUso) -> AvaliacaoDisa:
    """Avalia o uso na base DISA e adiciona 1.2.2 (se faltou matrícula na
    base DISA) e o marcador de avaliado (DISA). Os marcadores das etapas
    seguintes que dependem só desta avaliação (1.2.1 e o memo à APIS) são
    conferidos no SEI aqui também, antes de adicionar qualquer um."""
    avaliacao = avaliar_uso_rede_propria_disa(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    registro.titular_nao_encontrado_base_geral = avaliacao.nao_encontradas_geral.titular
    registro.deps_nao_encontrados_base_geral = list(avaliacao.nao_encontradas_geral.dependentes)
    registro.titular_nao_encontrado = avaliacao.nao_encontradas_disa.titular
    registro.deps_nao_encontrados = list(avaliacao.nao_encontradas_disa.dependentes)
    registrar_uso(registro, avaliacao.uso)

    tags = [TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO] if avaliacao.nao_encontradas_disa else []
    tags.append(TAG_AVALIADO_USO_REDE_PROPRIA_DISA)
    if avaliacao.nao_encontradas_geral:
        tags += [TAG_MAT_NAO_ENCONTRADAS_GERAL_NOVO, TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS]
    garantir_marcadores_no_sei(driver, tags)

    if avaliacao.nao_encontradas_disa:
        adicionar_tag_se_ausente(driver, registro, TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO)
    if not _etapa_feita(registro, TAG_AVALIADO_USO_REDE_PROPRIA_DISA):
        adicionar_tag(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_DISA)
    return avaliacao


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


def _avaliar_mantis_e_criar_docs(
    driver: webdriver.Remote,
    registro: RegistroMain,
    dados_ui: DadosUI,
    avaliacao_disa: AvaliacaoDisa,
    bases_mantis: BasesMantis,
) -> None:
    """O memo à DISA (com os relatórios da rede própria) só existe se
    alguém tem atendimento na rede própria do MANTIS; a base DISA não
    decide. Depois vêm os relatórios da rede credenciada e o memo DEPROC.

    VELHO (já enviado à DISA e à DEPROC): com uso da rede própria, vão os
    relatórios das duas redes e o memo à DISA, sem DEPROC; sem uso, os
    relatórios da rede credenciada e um memo DEPROC complementar."""
    uso_disa = avaliacao_disa.uso
    mantis = avaliar_uso_rede_propria_mantis(uso_disa.matricula_titular, avaliacao_disa.dependentes, dados_ui.periodo_titular, bases_mantis)
    _registrar_uso_mantis(registro, mantis)
    registro.mats_uso_mantis_alem_disa = usos_mantis_alem_disa(uso_disa, mantis.rede_propria)
    propria, credenciada = mantis.rede_propria, mantis.rede_credenciada

    # O memo DISA já no bloco (retomada pelo 1.9) também conta
    usou_rede_propria = propria.alguem_usou or tem_tag(registro, TAG_MEMO_DISA_USO_REDE_PROPRIA)
    # Os memos são montados antes de qualquer ação no SEI: texto pendente
    # (TextoMemoPendente) para o processo aqui
    memo_disa = None
    if propria.alguem_usou and not _etapa_feita(registro, TAG_MEMO_DISA_USO_REDE_PROPRIA):
        memo_disa = MemoDisa(
            dados=dados_ui,
            uso_disa=uso_disa,
            tit_usou_mantis=propria.tit_usou,
            deps_que_usaram_mantis=propria.deps_que_usaram,
            nome_signatario=NOME_SIGNATARIO,
            cargo_signatario=CARGO_SIGNATARIO,
        )
    memo_deproc, prefixo_deproc, padrao_deproc = None, 'memo_deproc', PADRAO_ASSUNTO_MEMO_DEPROC
    if not registro.velho:
        memo_deproc = MemoDeproc(dados=dados_ui, usou_rede_credenciada=credenciada.alguem_usou, nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO)
    elif not usou_rede_propria:
        memo_deproc = MemoDeprocRedeCredenciada(dados=dados_ui, usou_rede_credenciada=credenciada.alguem_usou, nome_signatario=NOME_SIGNATARIO, cargo_signatario=CARGO_SIGNATARIO)
        prefixo_deproc, padrao_deproc = 'memo_deproc_credenciada', PADRAO_ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA

    if registro.velho:
        tag_conclusao, prox_acao = (TAG_VELHO_MEMO_DISA, ProxAcao.VELHO_ASSINAR_DISA) if usou_rede_propria else (TAG_VELHO_MEMO_DEPROC, ProxAcao.VELHO_ASSINAR_DEPROC)
        tags = [TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, tag_conclusao]
    else:
        # O marcador de conclusão diz quantos memos ficaram no bloco
        tag_conclusao, prox_acao = (TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO, ProxAcao.ASSINAR_DISA_DEPROC) if usou_rede_propria else (TAG_MEMO_DEPROC_COPARTICIPACAO, ProxAcao.ASSINAR_DEPROC)
        tags = [TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS, *([TAG_MEMO_DISA_USO_REDE_PROPRIA] if usou_rede_propria else []), tag_conclusao]
    garantir_marcadores_no_sei(driver, tags)

    if not _etapa_feita(registro, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS):
        adicionar_tag(driver, registro, TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)

    nome, matricula = dados_ui.nome_titular, uso_disa.matricula_titular
    if memo_disa is not None:
        logger.info(f'Atendimento na rede própria do MANTIS: relatórios e memo à DISA | fora da base DISA: {registro.mats_uso_mantis_alem_disa or "-"}')
        incluir_relatorios(driver, registro, propria, REDE_PROPRIA, nome, matricula)
        if registro.velho:
            incluir_relatorios(driver, registro, credenciada, REDE_CREDENCIADA, nome, matricula)
        incluir_memo(driver, registro, memo_disa, BLOCO_MEMOS_DISA_DEPROC, 'memo_disa', 'DISA', padrao_assunto=PADRAO_ASSUNTO_MEMO_DISA)
        if not registro.velho:
            adicionar_tag(driver, registro, TAG_MEMO_DISA_USO_REDE_PROPRIA)
    elif not usou_rede_propria:
        logger.info('Nenhum atendimento na rede própria do MANTIS: sem memo à DISA')

    if memo_deproc is not None:
        incluir_relatorios(driver, registro, credenciada, REDE_CREDENCIADA, nome, matricula)
        incluir_memo(driver, registro, memo_deproc, BLOCO_MEMOS_DISA_DEPROC, prefixo_deproc, 'DEPROC', padrao_assunto=padrao_deproc)
    adicionar_tag(driver, registro, tag_conclusao)
    _finalizar(driver, registro, prox_acao)


# ---------------------------------------------------------------------------
# Fluxo
# ---------------------------------------------------------------------------


def processar_novo(
    driver: webdriver.Remote,
    registro: RegistroMain,
    bases: BasesUso,
    bases_mantis: BasesMantis,
) -> None:
    """Fluxo de todos os processos, do início ou retomando pelo marcador de
    estado (1.6, 1.8 ou 1.9). registro.velho indica o processo já enviado à
    DISA e à DEPROC antes da avaliação.

    Termina em um destes pontos:
    - sem memo da APIS para a GEACS: memo à APIS (sem memorando);
    - memo da APIS em formato inválido: memo à APIS (formato inválido);
    - VELHO com alguém na base DISA: aguarda o retorno da DISA;
    - matrícula fora da base geral: 1.2.1 e memo à APIS;
    - período variável para dependentes: 1.1 e memo à APIS;
    - relatórios e memos à DISA e/ou à DEPROC.

    Em todos os casos o marcador do memo só é adicionado depois que ele
    está no bloco.
    """
    registro.fluxo = f'{_ramo(registro)} - fluxo normal'
    try:
        dados_ui = obter_dados_ui(driver, registro)
    except MemoApisNaoEncontrado:
        _parar_sem_memo_apis(driver, registro)
        return
    except FormatoMemorandoInvalido as e:
        _parar_formato_invalido(driver, registro, e)
        return

    avaliacao_disa = _avaliar_disa(driver, registro, dados_ui, bases)
    if registro.velho and avaliacao_disa.uso.alguem_usou:
        # Atendimento na DISA desde o início: a DISA já levanta os usos
        logger.info('VELHO com beneficiário na base DISA: aguardar o retorno da DISA')
        registro.fluxo = 'VELHO - aguardando retorno da DISA'
        registro.prox_acao = ProxAcao.VELHO_AGUARDAR_DISA
    elif avaliacao_disa.nao_encontradas_geral:
        _parar_nao_encontradas_base_geral(driver, registro, avaliacao_disa)
    elif dados_ui.periodo_dependentes:
        _parar_periodo_variavel(driver, registro, avaliacao_disa)
    else:
        _avaliar_mantis_e_criar_docs(driver, registro, dados_ui, avaliacao_disa, bases_mantis)
