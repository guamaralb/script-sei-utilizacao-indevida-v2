"""Tratamento das matrículas não encontradas na base geral (listagem de
todos os beneficiários) e na base da rede própria (DISA).

Usado pelo fluxo normal dos NOVOS, pela rotina de correção e, no futuro,
pelo fluxo dos VELHOS (cada um com os seus marcadores).

Base geral: cria o memo à APIS-Utilização e o insere no bloco; o marcador
da base geral (1.2.1/2.1.1) só é adicionado depois disso, e também indica
que o memo está no bloco.
"""

import logging

from constantes import (
    BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import encontrar_memo_mat_nao_encontradas, memos_geacs_novos
from rede_propria import ErroAvaliacao, MatriculasNaoEncontradas, NaoEncontradas
from Registro import ProxAcao
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import incluir_doc_sei_memo
from selenium import webdriver
from tags import adicionar_tag

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import (
    MemoApisMatNaoEncontradas,
)

logger = logging.getLogger(__name__)


def _incluir_memo_apis(driver: webdriver.Remote, registro, tds_docs: list[dict], base_geral: NaoEncontradas) -> None:
    if BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS is None:
        raise ErroAvaliacao('Bloco do memo à APIS de matrículas não encontradas não configurado (constantes.BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS)')

    memo_existente = encontrar_memo_mat_nao_encontradas(driver, tds_docs)
    if memo_existente is not None:
        registro.memo_apis_mat_nao_encontradas_sei = memo_existente['numero_sei']
        raise ErroAvaliacao(
            f'Memo à APIS de matrículas não encontradas ({memo_existente["numero_sei"]}) já existe na árvore, mas o processo não tem o marcador. '
            'Verificar se está no bloco e adicionar o marcador manualmente.'
        )

    memo = MemoApisMatNaoEncontradas(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        titular=base_geral.titular,
        dependentes=base_geral.dependentes,
    )
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    registro.memo_apis_mat_nao_encontradas_criado = True
    logger.info('Memo à APIS de matrículas não encontradas criado')

    inserir_bloco_ass(driver, BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS)
    registro.memo_apis_mat_nao_encontradas_inserido_bloco = True
    logger.info(f'Memo à APIS de matrículas não encontradas inserido no bloco {BLOCO_MEMO_APIS_MAT_NAO_ENCONTRADAS}')


def _registrar_numero_memo_apis(driver: webdriver.Remote, registro, tds_docs: list[dict]) -> None:
    """Só informativo: uma falha aqui não interrompe o processo."""
    try:
        novos = memos_geacs_novos(driver, tds_docs)
    except Exception:
        logger.exception('Não foi possível obter o número SEI do memo à APIS')
        return
    if len(novos) == 1:
        registro.memo_apis_mat_nao_encontradas_sei = novos[0]['numero_sei']
    else:
        logger.warning(f'Número SEI do memo à APIS não registrado: esperado 1 memo novo na árvore, encontrado(s) {len(novos)}')


def marcar_matriculas_nao_encontradas(  # noqa: PLR0913, PLR0917
    driver: webdriver.Remote,
    registro,
    tds_docs: list[dict],
    erro: MatriculasNaoEncontradas,
    tag_base_geral: str,
    tag_base_rede: str,
) -> None:
    """Registra as matrículas, cria o memo à APIS (base geral) e adiciona o
    marcador de cada base em que houve matrícula não encontrada. Quem chama
    deve levantar o erro de novo para parar o processamento."""
    if erro.base_geral:
        registro.titular_nao_encontrado_base_geral = erro.base_geral.titular
        registro.deps_nao_encontrados_base_geral = list(erro.base_geral.dependentes)
        logger.warning(f'Não encontrado(s) na base geral | {erro.base_geral.descrever()}')
    if erro.base_rede:
        registro.titular_nao_encontrado = erro.base_rede.titular
        registro.deps_nao_encontrados = list(erro.base_rede.dependentes)
        logger.warning(f'Não encontrado(s) na base da rede própria | {erro.base_rede.descrever()}')
    registro.prox_acao = ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS

    if erro.base_geral:
        _incluir_memo_apis(driver, registro, tds_docs, erro.base_geral)
        adicionar_tag(driver, registro, tag_base_geral)
        registro.prox_acao = ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS

    if erro.base_rede:
        adicionar_tag(driver, registro, tag_base_rede)

    if registro.memo_apis_mat_nao_encontradas_criado:
        _registrar_numero_memo_apis(driver, registro, tds_docs)
