"""Correção dos processos NOVOS encaminhados à DISA e à DEPROC sem a
avaliação do uso da rede própria.

Usado por main.py e por main_add_memo_nao_usou_rede_propria.py.

Ordem das ações (para permitir retomar após falha):
    1. avalia o uso (sem alterar nada no SEI);
    2. reabre o processo;
    3. se alguém NÃO usou: cria o memo, insere no bloco e coloca o
       marcador de memo no bloco;
    4. coloca o marcador de avaliado.
"""

import logging

from constantes import (
    BLOCO_MEMO_USO_REDE_PROPRIA,
    CARGO_SIGNATARIO,
    NOME_SIGNATARIO,
)
from docs_processo import encontrar_memo_uso_rede
from matriculas_nao_encontradas import marcar_matriculas_nao_encontradas
from rede_propria import (
    BasesUso,
    ErroAvaliacao,
    MatriculasNaoEncontradas,
    avaliar_uso,
    registrar_uso,
)
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.processo import (
    adicionar_marcador,
    incluir_doc_sei_memo,
    reabrir_processo,
)
from selenium import webdriver
from tags import (
    TAG_AVALIADO_USO_REDE_PROPRIA,
    TAG_MAT_NAO_ENCONTRADAS_NOVO,
    TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    MemoDisaUsoRede,
)

logger = logging.getLogger(__name__)


def verificar_memo_uso_rede(driver: webdriver.Remote, registro, tds_docs: list[dict]) -> None:
    """Confere se o memo de uso da rede própria existe na árvore."""
    memo = encontrar_memo_uso_rede(driver, tds_docs)
    if memo is None:
        raise ErroAvaliacao(f'Marcador "{TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO}" presente, mas o memo de uso da rede própria não foi encontrado na árvore')
    registro.memo_uso_rede_na_arvore = True
    registro.prox_acao = f'Memo de uso da rede própria encontrado ({memo["numero_sei"]})'


def _marcar_avaliado(driver: webdriver.Remote, registro) -> None:
    adicionar_marcador(driver, TAG_AVALIADO_USO_REDE_PROPRIA)
    registro.tag_avaliado_se_usou_rede_propria = True
    logger.info(f'Marcador adicionado: "{TAG_AVALIADO_USO_REDE_PROPRIA}"')


def _reabrir(driver: webdriver.Remote) -> None:
    reabrir_processo(driver)
    logger.info('Processo reaberto na unidade')


def corrigir_uso_rede_propria(
    driver: webdriver.Remote,
    registro,
    tds_docs: list[dict],
    matricula_titular,
    matriculas_dependentes,
    bases: BasesUso,
) -> None:
    # Retomada: memo já foi para o bloco, mas faltou o marcador de avaliado
    if registro.tag_memo_nao_usou_rede_propria_no_bloco:
        logger.info('Retomada: memo de uso da rede própria já está no bloco; falta apenas o marcador de avaliado')
        verificar_memo_uso_rede(driver, registro, tds_docs)
        _reabrir(driver)
        _marcar_avaliado(driver, registro)
        return

    logger.info('Iniciando correção: avaliação do uso da rede própria')
    try:
        uso = avaliar_uso(matricula_titular, matriculas_dependentes, bases)
    except MatriculasNaoEncontradas as e:
        # Os marcadores são adicionados com o processo reaberto
        _reabrir(driver)
        marcar_matriculas_nao_encontradas(driver, registro, e, TAG_MAT_NAO_ENCONTRADAS_NOVO)
        raise
    registrar_uso(registro, uso)

    if not uso.alguem_nao_usou:
        logger.info('Todos os beneficiários usaram a rede própria: memo dispensado')
        _reabrir(driver)
        _marcar_avaliado(driver, registro)
        registro.prox_acao = 'Todos usaram a rede própria. Memo dispensado.'
        return

    memo_existente = encontrar_memo_uso_rede(driver, tds_docs)
    if memo_existente is not None:
        registro.memo_uso_rede_na_arvore = True
        raise ErroAvaliacao(
            f'Memo de uso da rede própria ({memo_existente["numero_sei"]}) já existe na árvore, mas o processo não tem os marcadores. Verificar se está no bloco e adicionar os marcadores manualmente.'
        )

    _reabrir(driver)

    memo = MemoDisaUsoRede(
        nome_signatario=NOME_SIGNATARIO,
        cargo_signatario=CARGO_SIGNATARIO,
        uso=uso,
    )
    incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
    registro.memo_uso_rede_criado = True
    logger.info('Memo de uso da rede própria criado')

    inserir_bloco_ass(driver, BLOCO_MEMO_USO_REDE_PROPRIA)
    registro.memo_uso_rede_inserido_bloco = True
    logger.info(f'Memo de uso da rede própria inserido no bloco {BLOCO_MEMO_USO_REDE_PROPRIA}')

    adicionar_marcador(driver, TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO)
    registro.tag_memo_nao_usou_rede_propria_no_bloco = True
    logger.info(f'Marcador adicionado: "{TAG_MEMO_NAO_USOU_REDE_PROPRIA_NO_BLOCO}"')

    _marcar_avaliado(driver, registro)
    registro.prox_acao = 'Assinar memo de uso da rede própria e encaminhar'
