"""Fluxo GEACS CORRIGE ENVIO DISA (task run_geacs_corrige_envio_disa), na
unidade da GEACS: corrige os processos enviados à DISA com o memo "Validar (N
Consta)" (uso da rede própria só no MANTIS, sem constar na base DISA). Pela
regra atual (geacs_inicial), esses processos vão direto à DEPROC.

Para cada processo da aba geacs_corrige_envio_disa de processos_a_processar.xlsx:

1. lê os marcadores e confere a combinação (tags.conferir_marcadores). O
   estado precisa ser um marcador de memo à DISA (No Bloco ou Aguarda, os
   três casos); senão, para com erro, sem ação;
2. sem "Incluir Documento" (fechado no setor), para sem reabrir;
3. lê o último memo da APIS destinado à GEACS (define a rodada) e procura,
   nos memos da GEACS da rodada, o memo à DISA "Validar (N Consta)", pelo
   trecho TRECHO_MEMO_DISA_N_CONSTA. Nenhum (e o estado não é o N Consta):
   nada a corrigir, sem ação;
4. recalcula o caso base DISA x MANTIS (como no geacs_inicial) e procura os
   relatórios do MANTIS na rodada. O caso precisa ser "DISA não" com uso no
   MANTIS; senão, ou sem algum relatório, para com erro, sem ação. O memo
   DEPROC é montado antes de qualquer ação no SEI;
5. exclui o(s) memo(s) à DISA (excluir_doc da sei_automacao). Algum não
   excluído (ex.: assinado): para com erro, prox_acao = Verificar o que
   fazer: memo à DISA (não consta) não excluído, sem criar o memo DEPROC;
6. cria o memo DEPROC (retomada: o memo já na rodada, pelo assunto, não é
   recriado), insere no bloco BLOCO_MEMO_DEPROC e adiciona o 01.10 - No Bloco
   DEPROC: Coparticipação, que remove o marcador da DISA (estado). O 01 e os
   informativos ficam. prox_acao = Assinar memo DEPROC e encaminhar.

Retomada: se uma passagem excluiu o memo à DISA e falhou antes do memo DEPROC,
o processo continua com o marcador N Consta e sem o memo; a próxima passagem
segue do passo 4.
"""

import logging
import re
import time
from datetime import datetime

from constantes import (
    ARQ_BASE_APIS,
    ARQ_MANTIS_REDE_CREDENCIADA,
    ARQ_MANTIS_REDE_CREDENCIADA_DEPS_NAO_ENCONTRADOS,
    ARQ_MANTIS_REDE_PROPRIA,
    ARQ_MANTIS_REDE_PROPRIA_DEPS_NAO_ENCONTRADOS,
    ARQ_USO_REDE_PROPRIA,
    BLOCO_MEMO_DEPROC,
    DIR_CONTROLE,
    DIR_INPUTS,
    DIR_LOG,
    UNIDADE_GEACS,
)
from docs_processo import filtrar_memos_geacs, ler_texto_doc, selecionar_doc
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from mantis import BasesMantis, carregar_bases_mantis
from marcadores_disponiveis import garantir_marcadores_no_sei
from memos_sei import incluir_memo, registrar_numeros_memos
from planilha_controle import PlanilhaControleGeral
from processar_novo import montar_memo_deproc, obter_dados_ui
from processo_fechado import ProcessoFechadoNoSetor, tem_incluir_documento
from processos_a_processar import ler_processos_a_processar
from rede_propria import BasesUso, ErroAvaliacao, avaliar_uso_rede_propria_disa, carregar_bases
from Registro import PROX_ACAO_POR_NO_BLOCO, ProxAcao, RegistroCorrigeEnvioDisa, registrar_erro, registrar_sem_acesso
from relatorios_mantis import REDE_CREDENCIADA, REDE_PROPRIA
from sei_automacao.documento import excluir_doc
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore, listar_marcadores
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import (
    AGUARDA_POR_NO_BLOCO,
    TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO,
    TAG_NO_BLOCO_DISA_VALIDAR_CONSTA,
    TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA,
    MarcadoresInconsistentes,
    adicionar_tag,
    conferir_marcadores,
    estado_atual,
    registrar_tags,
)
from todas_infos import recalcular_mantis, relatorios_da_rede

from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_corrige_envio_disa'
FLUXO = 'CORRIGE ENVIO DISA - MEMO À DISA (N CONSTA) TROCADO PELO MEMO DEPROC'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_corrige_envio_disa.log'

# Trecho do memo à DISA "Validar (N Consta)" (MemoDisaValidarNaoConsta).
# Espaços, quebras de linha e maiúsculas são ignorados
TRECHO_MEMO_DISA_N_CONSTA = 'Embora a Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791) não indique atendimento para as matrículas relacionadas'
_PADRAO_MEMO_DISA_N_CONSTA = re.compile(r'\s+'.join(re.escape(palavra) for palavra in TRECHO_MEMO_DISA_N_CONSTA.split()), re.IGNORECASE)

# Marcadores de memo à DISA: No Bloco (não assinado) e Aguarda (assinado)
_NO_BLOCO_DISA = (TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, TAG_NO_BLOCO_DISA_SEM_MANTIS_RELATORIO)
TAGS_MEMO_DISA = (*_NO_BLOCO_DISA, *(AGUARDA_POR_NO_BLOCO[tag] for tag in _NO_BLOCO_DISA))
_TAGS_N_CONSTA = (TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA)

# Logo depois da exclusão, a árvore ainda mostra o documento: a conferência
# reabre o processo e relê a árvore por até este tempo (segundos)
TEMPO_CONFERENCIA = 15

# Navegador fechado: para o processo (e o loop)
_SESSAO_ENCERRADA = (InvalidSessionIdException, NoSuchWindowException)

logger = logging.getLogger(__name__)


class SemMarcadorDisa(ErroAvaliacao):
    """O processo não está com um marcador de memo à DISA."""


class CasoNaoCorrigivel(ErroAvaliacao):
    """O caso base DISA x MANTIS recalculado não é o do memo DEPROC (DISA
    não, com uso no MANTIS), ou falta relatório do MANTIS na rodada."""


class MemoDisaNaoExcluido(ErroAvaliacao):
    """Memo à DISA que o SEI não deixou excluir (ex.: assinado)."""


def _descrever(doc: dict) -> str:
    return f'{doc["nome_arvore"]} (SEI {doc["numero_sei"]})'


def eh_memo_disa_n_consta(texto: str) -> bool:
    return _PADRAO_MEMO_DISA_N_CONSTA.search(texto) is not None


def _conferir_marcadores(registro: RegistroCorrigeEnvioDisa, momento: str) -> None:
    try:
        conferir_marcadores(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def _prox_acao_do_estado(estado: str) -> str:
    """A prox_acao que o geacs_inicial daria: assinar (No Bloco) ou aguardar
    a resposta (Aguarda)."""
    return PROX_ACAO_POR_NO_BLOCO.get(estado, ProxAcao.AGUARDAR_RESPOSTA_MEMO)


def _memos_disa_n_consta(driver: webdriver.Remote, registro: RegistroCorrigeEnvioDisa) -> list[dict]:
    """Memos da GEACS na rodada com o trecho do memo à DISA (N Consta)."""
    memos = [memo for memo in filtrar_memos_geacs(registro.docs_rodada) if eh_memo_disa_n_consta(ler_texto_doc(driver, memo))]
    registro.memos_disa_n_consta_sei = [memo['numero_sei'] for memo in memos]
    return memos


def _relistar_arvore(driver: webdriver.Remote, registro: RegistroCorrigeEnvioDisa) -> None:
    """Relê a árvore e refaz a rodada (depois do memo da APIS já lido)."""
    registro.registrar_arvore(listar_documentos_arvore(driver))
    indice = next(i for i, doc in enumerate(registro.tds_docs) if doc['numero_sei'] == registro.memo_apis_sei)
    registro.docs_rodada = registro.tds_docs[indice + 1 :]


def _memos_restantes(driver: webdriver.Remote, registro: RegistroCorrigeEnvioDisa, numeros: list[str]) -> list[str]:
    """Dos memos excluídos, os que continuam na árvore. A árvore demora a
    refletir a exclusão: reabre o processo e relê até eles sumirem ou passar
    TEMPO_CONFERENCIA."""
    acessar_processo(driver, registro.num_processo)
    limite = time.monotonic() + TEMPO_CONFERENCIA
    while True:
        restantes = [doc['numero_sei'] for doc in listar_documentos_arvore(driver) if doc['numero_sei'] in numeros]
        if not restantes or time.monotonic() >= limite:
            return restantes
        logger.debug(f'Excluído(s) ainda na árvore: {restantes}; relendo')
        time.sleep(1)


def excluir_memos_disa(driver: webdriver.Remote, registro: RegistroCorrigeEnvioDisa, memos: list[dict]) -> None:
    """Exclui os memos à DISA, do último para o primeiro, e confere na
    árvore. Algum não excluído: MemoDisaNaoExcluido, com a prox_acao de
    verificar o que fazer."""
    for memo in reversed(memos):
        try:
            selecionar_doc(driver, memo)
            excluir_doc(driver)
        except _SESSAO_ENCERRADA:
            raise
        except Exception:
            logger.warning(f'Memo à DISA não excluído: {_descrever(memo)} (assinado, já enviado ou sem permissão?)', exc_info=True)
            registro.memos_disa_nao_excluidos_sei.append(memo['numero_sei'])
            restaurar_navegador(driver)
            continue
        registro.memos_disa_excluidos_sei.append(memo['numero_sei'])
        logger.info(f'Memo à DISA excluído: {_descrever(memo)}')

    if registro.memos_disa_excluidos_sei:
        for numero in _memos_restantes(driver, registro, registro.memos_disa_excluidos_sei):
            # A exclusão não deu erro, mas o memo continua na árvore
            registro.memos_disa_excluidos_sei.remove(numero)
            registro.memos_disa_nao_excluidos_sei.append(numero)
    if registro.memos_disa_nao_excluidos_sei:
        registro.prox_acao = ProxAcao.VERIFICAR_MEMO_DISA_NAO_EXCLUIDO
        raise MemoDisaNaoExcluido(f'Memo(s) à DISA (não consta) não excluído(s): {", ".join(registro.memos_disa_nao_excluidos_sei)}; memo DEPROC não criado')


def _montar_memo_deproc(registro: RegistroCorrigeEnvioDisa, bases: BasesUso, bases_mantis: BasesMantis):
    """Recalcula o caso base DISA x MANTIS (como no geacs_inicial) e monta o
    memo DEPROC com os relatórios do MANTIS da rodada."""
    dados_memo, matriculas, avaliacao = recalcular_mantis(registro.dados_ui, bases, bases_mantis)
    uso_disa = avaliar_uso_rede_propria_disa(matriculas, bases)
    usou_rp, usou_rc = avaliacao.rede_propria.alguem_usou, avaliacao.rede_credenciada.alguem_usou
    registro.caso_disa_mantis = f'DISA {"sim" if uso_disa.alguem_usou else "não"}, MANTIS RP {"sim" if usou_rp else "não"}, MANTIS RC {"sim" if usou_rc else "não"}'
    logger.info(f'Base DISA x MANTIS: {registro.caso_disa_mantis}')
    if uso_disa.alguem_usou:
        raise CasoNaoCorrigivel(f'{registro.caso_disa_mantis}: com uso na base DISA o processo vai à DISA; nada foi alterado')
    if not (usou_rp or usou_rc):
        raise CasoNaoCorrigivel(f'{registro.caso_disa_mantis}: sem uso no MANTIS não há memo DEPROC (memo à APIS sem uso); nada foi alterado')

    rp, faltando_rp = relatorios_da_rede(registro, avaliacao.rede_propria, REDE_PROPRIA, matriculas.titular)
    rc, faltando_rc = relatorios_da_rede(registro, avaliacao.rede_credenciada, REDE_CREDENCIADA, matriculas.titular)
    registro.relatorios_rp_sei, registro.relatorios_rc_sei = rp.numeros, rc.numeros
    if faltando_rp or faltando_rc:
        raise CasoNaoCorrigivel(f'Relatórios do MANTIS da rodada não conferem com o recálculo: {"; ".join(faltando_rp + faltando_rc)}; nada foi alterado')
    logger.info(f'Relatórios do MANTIS citados no memo DEPROC: RP {rp.numeros or "-"} | RC {rc.numeros or "-"}')
    return montar_memo_deproc(registro, dados_memo, tuple(rp.numeros), tuple(rc.numeros))


def corrigir_envio_disa(driver: webdriver.Remote, registro: RegistroCorrigeEnvioDisa, bases: BasesUso, bases_mantis: BasesMantis) -> None:
    registrar_tags(registro, listar_marcadores(driver))
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
    _conferir_marcadores(registro, 'no início da passagem')

    estado = estado_atual(registro)
    if estado not in TAGS_MEMO_DISA:
        raise SemMarcadorDisa(f'Processo sem marcador de memo à DISA (estado atual: {estado or "nenhum"}); nada foi alterado')

    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da GEACS: nada foi alterado (não reaberto)')
    garantir_marcadores_no_sei(driver, [TAG_MEMO_DEPROC_COPARTICIPACAO])

    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')
    obter_dados_ui(driver, registro)

    memos_disa = _memos_disa_n_consta(driver, registro)
    if memos_disa:
        logger.info(f'Memo(s) à DISA (não consta) na rodada: {[_descrever(m) for m in memos_disa]}')
    elif estado in _TAGS_N_CONSTA:
        # Retomada: o memo à DISA foi excluído numa passagem anterior, que
        # falhou antes do memo DEPROC
        logger.warning(f'Marcador "{estado}" sem o memo à DISA (não consta) na rodada: excluído numa passagem anterior? Segue para o memo DEPROC')
    else:
        logger.info('Nenhum memo à DISA (não consta) na rodada: nada a corrigir')
        registro.corrige_envio_disa = f'{datetime.now():%d/%m/%Y %H:%M}: nenhum memo à DISA (não consta) na rodada; nada a corrigir'
        registro.prox_acao = _prox_acao_do_estado(estado)
        return

    if BLOCO_MEMO_DEPROC is None:
        raise ErroAvaliacao('Bloco do memo DEPROC não configurado (BLOCO_MEMO_DEPROC): nada foi alterado')
    # Montado antes de qualquer ação no SEI
    memo = _montar_memo_deproc(registro, bases, bases_mantis)

    if memos_disa:
        excluir_memos_disa(driver, registro, memos_disa)
        _relistar_arvore(driver, registro)

    incluir_memo(driver, registro, memo, BLOCO_MEMO_DEPROC, 'memo_deproc', 'DEPROC', padrao_assunto=PADRAO_ASSUNTO_MEMO_DEPROC)
    # Estado: remove o marcador da DISA
    adicionar_tag(driver, registro, TAG_MEMO_DEPROC_COPARTICIPACAO)
    registrar_numeros_memos(driver, registro)
    registro.fluxo = f'{FLUXO} ({registro.caso_disa_mantis})'
    registro.prox_acao = ProxAcao.ASSINAR_DEPROC
    excluidos = ', '.join(registro.memos_disa_excluidos_sei) or 'nenhum (já excluído antes)'
    registro.corrige_envio_disa = f'{datetime.now():%d/%m/%Y %H:%M}: memo à DISA excluído: {excluidos}; memo DEPROC: {registro.memo_deproc_sei or "criado"}'


def _resumo_erro(registro: RegistroCorrigeEnvioDisa) -> None:
    if registro.erro:
        excluidos = f'; memo à DISA excluído: {", ".join(registro.memos_disa_excluidos_sei)}' if registro.memos_disa_excluidos_sei else ''
        registro.corrige_envio_disa = f'{datetime.now():%d/%m/%Y %H:%M}: ERRO ({registro.tipo_erro}): {registro.erro}{excluidos}'


def _processar_linha(driver: webdriver.Remote, num_processo, bases: BasesUso, bases_mantis: BasesMantis) -> RegistroCorrigeEnvioDisa:
    registro = RegistroCorrigeEnvioDisa(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)

    try:
        acessar_processo(driver, num_processo)
        corrigir_envio_disa(driver, registro, bases, bases_mantis)
        _conferir_marcadores(registro, 'no fim da passagem')

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except (ErroAvaliacao, FormatoMemorandoInvalido) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    _resumo_erro(registro)
    return registro


def main():
    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')

        processos = ler_processos_a_processar(SCRIPT)
        total = len(processos)

        bases = carregar_bases(ARQ_USO_REDE_PROPRIA, ARQ_BASE_APIS)
        bases_mantis = carregar_bases_mantis(
            ARQ_MANTIS_REDE_PROPRIA,
            ARQ_MANTIS_REDE_CREDENCIADA,
            ARQ_MANTIS_REDE_PROPRIA_DEPS_NAO_ENCONTRADOS,
            ARQ_MANTIS_REDE_CREDENCIADA_DEPS_NAO_ENCONTRADOS,
        )

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        # Login e troca para a unidade da GEACS
        driver = abrir_sei(UNIDADE_GEACS)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_linha(driver, num_processo, bases, bases_mantis)
                registros_processados.append(registro.to_dict())
                controle.registrar(registros_processados[-1])

                log_fim_processo(logger, registro, datetime.now() - t_ini)

                if sessao_encerrada(registro):
                    logger.warning(f'Navegador fechado: execução interrompida em {i} de {total} processo(s)')
                    break

    except Exception:
        logger.exception(f'Erro crítico na execução ({FLUXO})')
        raise

    finally:
        if driver is not None:
            driver.quit()
        log_resumo(logger, registros_processados)
        logger.info(f'Duração total da execução: {formatar_duracao(datetime.now() - t_ini_geral)}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
