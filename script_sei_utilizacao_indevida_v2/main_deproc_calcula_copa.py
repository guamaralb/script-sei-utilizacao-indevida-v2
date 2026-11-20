"""Fluxo DEPROC (task run_deproc_calcula_copa), na unidade da DEPROC: confere que o memo
DEPROC da GEACS está assinado, apura a coparticipação na base do MANTIS
(coparticipacao_deproc.py), anexa o relatório em PDF (relatorio_deproc.py) e
cria o memo de resultado da DEPROC à GEACS, no bloco próprio.

Usa os marcadores da unidade da DEPROC (TAG_DEPROC_*, em tags.py, com o
mesmo prefixo "v2: " dos da GEACS): 01 (tratado), 01.01 (relatório anexado,
estado de retomada), 01.02 (memo no bloco, aguarda assinatura) e 01.02.1
(manual: memo encaminhado à GEACS, conclusão). Dentro de cada etapa,
a retomada é pelo nome do PDF e pelo assunto do memo, na rodada (depois do
último memo da APIS destinado à GEACS).

O ano de cada processo escolhe a base DEPROC e a data de geração dela, citada
no memo de resultado (constantes.BASES_DEPROC). Vem da planilha de controle
(coluna ano_processo, gravada pelo geacs_inicial, ou ano_base_deproc, de uma
apuração anterior). O -a só é exigido se algum processo da lista não tiver o
ano na planilha, e vale só para esses:
poetry run task run_deproc_calcula_copa [-a 2019]
"""

import argparse
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from constantes import (
    BASES_DEPROC,
    BLOCO_MEMO_GEACS_CALCULO_COPA,
    CARGO_SIGNATARIO_DEPROC,
    DIR_CONTROLE,
    DIR_FLUXO_DEPROC_PDF,
    DIR_INPUTS,
    DIR_LOG,
    NOME_SIGNATARIO,
    NOME_SIGNATARIO_DEPROC,
    PADRAO_ASSINATURA_MEMO_DEPROC,
    UNIDADE_DEPROC,
    UNIDADE_GEACS,
)
from coparticipacao_deproc import BasesDeprocPorAno, MatriculasDivergentes, ResultadoDeproc, apurar_coparticipacao, carregar_base_deproc
from docs_processo import encontrar_memo_por_assunto
from extrator_dados_ui import FormatoMemorandoInvalido
from log_config import (
    configurar_logging,
    contexto_processo,
    formatar_duracao,
    log_fim_processo,
    log_resumo,
)
from marcadores_disponiveis import garantir_marcadores_no_sei
from memos_sei import incluir_memo, registrar_numeros_memos
from planilha_controle import PlanilhaControleGeral, texto_celula
from processar_novo import obter_dados_ui
from processo_fechado import ProcessoFechadoNoSetor, tem_incluir_documento
from processos_a_processar import ler_processos_a_processar
from rede_propria import ErroAvaliacao
from Registro import ProxAcao, RegistroDeproc, registrar_erro, registrar_sem_acesso
from relatorio_deproc import incluir_relatorio_deproc
from sei_automacao.exceptions import UnidadeSemAcessoException
from sei_automacao.processo import acessar_processo, listar_documentos_arvore, listar_marcadores
from selenium import webdriver
from sessao_sei import abrir_sei, restaurar_navegador, sessao_encerrada
from tags import (
    TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA,
    TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA,
    TAG_DEPROC_RELATORIO_ANEXADO,
    TAG_DEPROC_TRATADO,
    TAGS_DEPROC,
    TAGS_ESTADO_DEPROC,
    MarcadoresInconsistentes,
    adicionar_tag,
    adicionar_tag_se_ausente,
    conferir_marcadores_deproc,
    estado_atual,
    registrar_tags,
)

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import PADRAO_ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA, MemoGeacsCalculoCopa
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import TextoMemoPendente

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'deproc_calcula_copa'
FLUXO = 'DEPROC - COPARTICIPAÇÃO'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_deproc_calcula_copa.log'

_PADRAO_ASSINATURA = re.compile(PADRAO_ASSINATURA_MEMO_DEPROC, re.IGNORECASE)

logger = logging.getLogger(__name__)


def _memo_deproc_assinado(driver: webdriver.Remote, registro: RegistroDeproc) -> DocArvore:
    """O memo DEPROC da GEACS na rodada, assinado (PADRAO_ASSINATURA_MEMO_DEPROC). Sem o memo ou
    sem a assinatura: ErroAvaliacao, sem ação no SEI."""
    encontrado = encontrar_memo_por_assunto(driver, registro.docs_rodada, PADRAO_ASSUNTO_MEMO_DEPROC, 'DEPROC (da GEACS)', UNIDADE_GEACS)
    if encontrado is None:
        raise ErroAvaliacao('Memo DEPROC da GEACS não encontrado depois do último memo da APIS destinado à GEACS')

    memo, texto = encontrado
    registro.memo_deproc_geacs_sei = memo['numero_sei']
    registro.memo_deproc_assinado = _PADRAO_ASSINATURA.search(texto) is not None
    if not registro.memo_deproc_assinado:
        raise ErroAvaliacao(f'Memo DEPROC da GEACS ({memo["numero_sei"]}) ainda não assinado por {NOME_SIGNATARIO} (ou Bruna Miiller Lavarini)')
    logger.info(f'Memo DEPROC da GEACS assinado: {memo["numero_sei"]}')
    return memo


def _registrar_resultado(registro: RegistroDeproc, resultado: ResultadoDeproc) -> None:
    registro.linhas_base_deproc = resultado.linhas_processo
    registro.linhas_fora_periodo_deproc = resultado.linhas_fora_periodo
    registro.linhas_base_copa_zero_deproc = resultado.linhas_base_copa_zero
    registro.atendimentos_deproc = len(resultado.atendimentos)
    registro.valor_total_coparticipacao = resultado.totais.coparticipacao
    registro.valor_total_descontado = resultado.totais.descontado
    registro.valor_total_em_aberto = resultado.totais.em_aberto


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='poetry run task run_deproc_calcula_copa',
        description='Fluxo DEPROC: apura a coparticipação, anexa o relatório e cria o memo de resultado à GEACS.',
    )
    parser.add_argument(
        '-a',
        '--ano',
        type=str.strip,
        choices=sorted(BASES_DEPROC),
        help=(
            'ano dos processos sem ano na planilha de controle (colunas ano_processo e ano_base_deproc): escolhe a base DEPROC '
            'e a data de geração dela, citada no memo de resultado (constantes.BASES_DEPROC). Obrigatório se algum processo não tiver o ano'
        ),
    )
    return parser


def ler_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Com ano sem base cadastrada em BASES_DEPROC, o argparse mostra o erro
    e encerra (código 2) antes do log, do login e de qualquer ação no SEI."""
    return _criar_parser().parse_args(argv)


def ano_na_planilha(linha_controle: dict | None) -> str:
    """Ano do processo na planilha de controle: ano_processo (geacs_inicial)
    ou, sem ela, ano_base_deproc (apuração anterior). '' se não houver."""
    if not linha_controle:
        return ''
    return texto_celula(linha_controle.get('ano_processo')) or texto_celula(linha_controle.get('ano_base_deproc'))


@dataclass(frozen=True)
class AnoProcesso:
    ano: str
    # Veio do -a (a planilha não tinha): vai para a coluna ano_processo
    do_argumento: bool = False


def anos_dos_processos(processos: list, linha_processo: Callable[[str], dict | None], ano_argumento: str | None) -> tuple[dict[str, AnoProcesso], list[str]]:
    """O ano de cada processo: o da planilha de controle ou, sem ele, o do
    -a. Devolve também os processos sem ano (nem na planilha nem no -a). Com
    o -a diferente do da planilha, vale o da planilha (aviso no log)."""
    anos: dict[str, AnoProcesso] = {}
    sem_ano: list[str] = []
    for num_processo in processos:
        ano = ano_na_planilha(linha_processo(num_processo))
        if ano:
            if ano_argumento and ano_argumento != ano:
                logger.warning(f'{num_processo}: ano {ano} na planilha de controle, diferente do -a {ano_argumento}; usado o da planilha')
            anos[num_processo] = AnoProcesso(ano)
        elif ano_argumento:
            anos[num_processo] = AnoProcesso(ano_argumento, do_argumento=True)
        else:
            sem_ano.append(num_processo)
    return anos, sem_ano


def _montar_memo(resultado: ResultadoDeproc, memo_deproc_geacs: DocArvore, doc_relatorio: str | None, data_geracao_base: str) -> MemoGeacsCalculoCopa:
    return MemoGeacsCalculoCopa(
        resultado=resultado,
        doc_relatorio=doc_relatorio,
        memo_deproc_geacs=memo_deproc_geacs,
        data_geracao_bases=data_geracao_base,
        nome_signatario=NOME_SIGNATARIO_DEPROC,
        cargo_signatario=CARGO_SIGNATARIO_DEPROC,
    )


def _conferir_configuracao(data_geracao_base: str | None) -> None:
    """Antes de qualquer documento: sem bloco, signatário ou data de geração
    da base, o memo não pode ser criado, e o relatório ficaria sem memo."""
    if BLOCO_MEMO_GEACS_CALCULO_COPA is None:
        raise ErroAvaliacao('Bloco do memo de resultado da DEPROC não configurado (BLOCO_MEMO_GEACS_CALCULO_COPA)')
    if NOME_SIGNATARIO_DEPROC is None:
        raise ErroAvaliacao('Signatário do memo de resultado da DEPROC não configurado (NOME_SIGNATARIO_DEPROC)')
    if not data_geracao_base:
        raise ErroAvaliacao('Data de geração da base DEPROC não configurada (BASES_DEPROC): o memo de resultado não é criado')


def _conferir_marcadores(registro: RegistroDeproc, momento: str) -> None:
    try:
        conferir_marcadores_deproc(registro)
    except MarcadoresInconsistentes:
        logger.error(f'Marcadores inconsistentes {momento}: {registro.marcadores_atuais}')
        registro.prox_acao = ProxAcao.VERIFICAR_MARCADORES
        raise


def processar_deproc(driver: webdriver.Remote, registro: RegistroDeproc, base: pd.DataFrame | None, data_geracao_base: str | None, ano: str | None = None) -> None:
    registrar_tags(registro, listar_marcadores(driver))
    logger.info(f'Marcadores: {registro.marcadores_sei or "nenhum"}')
    _conferir_marcadores(registro, 'no início da passagem')

    estado = estado_atual(registro, TAGS_ESTADO_DEPROC)
    if estado == TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA:
        # Quem assina coloca o 01.02.1 e remove o 01.02
        logger.info('Memo de resultado da DEPROC no bloco: aguarda assinatura')
        registro.prox_acao = ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO
        return
    if estado == TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA:
        logger.info('Concluído: memo de resultado da DEPROC encaminhado à GEACS')
        registro.prox_acao = ProxAcao.DEPROC_MEMO_ENCAMINHADO
        return

    # Ano sem base cadastrada: a base não pode ser usada (nenhuma ação no SEI)
    if base is None:
        raise ErroAvaliacao(f'Ano {ano} sem base DEPROC cadastrada em BASES_DEPROC (coluna ano_processo da planilha de controle)')

    # Na DEPROC, o processo precisa estar aberto na unidade (enviado pela
    # GEACS); não é reaberto
    if not tem_incluir_documento(driver):
        raise ProcessoFechadoNoSetor('Processo sem "Incluir Documento" na unidade da DEPROC: não está aberto na unidade (não reaberto)')
    # Antes de listar a árvore: a conferência recarrega a página e fecha as
    # pastas. Sem os marcadores cadastrados na DEPROC, nada é feito
    garantir_marcadores_no_sei(driver, list(TAGS_DEPROC))
    registro.registrar_arvore(listar_documentos_arvore(driver))
    logger.info(f'Árvore: {len(registro.tds_docs)} documento(s)')

    dados = obter_dados_ui(driver, registro)
    memo_deproc_geacs = _memo_deproc_assinado(driver, registro)

    try:
        resultado = apurar_coparticipacao(base, registro.num_processo, dados)
    except MatriculasDivergentes as e:
        registro.matriculas_divergentes_deproc = e.divergentes
        raise
    _registrar_resultado(registro, resultado)
    # A base foi usada: o fluxo GEACS TODAS INFOS confere a coparticipação
    # na base deste ano (coluna ano_base_deproc)
    registro.ano_base_deproc = ano
    registro.data_geracao_base_deproc = data_geracao_base

    # Memo montado antes do relatório só para conferir texto, bloco e
    # signatário: nada é anexado se o memo não puder ser criado
    _conferir_configuracao(data_geracao_base)
    _montar_memo(resultado, memo_deproc_geacs, '<relatório a anexar>', data_geracao_base)

    adicionar_tag_se_ausente(driver, registro, TAG_DEPROC_TRATADO)
    doc_relatorio = None
    if resultado.tem_coparticipacao:
        # Com o 1.1 (retomada), o relatório é encontrado pelo nome
        doc_relatorio = incluir_relatorio_deproc(driver, registro, resultado, dados)
        if estado != TAG_DEPROC_RELATORIO_ANEXADO:
            adicionar_tag(driver, registro, TAG_DEPROC_RELATORIO_ANEXADO)
    memo = _montar_memo(resultado, memo_deproc_geacs, doc_relatorio, data_geracao_base)
    incluir_memo(
        driver,
        registro,
        memo,
        BLOCO_MEMO_GEACS_CALCULO_COPA,
        'memo_deproc_resultado',
        'de resultado da DEPROC',
        PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA,
        unidade=UNIDADE_DEPROC,
    )
    adicionar_tag(driver, registro, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA)
    registrar_numeros_memos(driver, registro, UNIDADE_DEPROC)
    registro.prox_acao = ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO


def _processar_linha(
    driver: webdriver.Remote,
    num_processo,
    base: pd.DataFrame | None,
    data_geracao_base: str | None,
    ano: str | None = None,
    ano_do_argumento: bool = False,
) -> RegistroDeproc:
    registro = RegistroDeproc(num_processo=num_processo, data_execucao=AGORA, fluxo=FLUXO)
    if ano_do_argumento:
        # A planilha não tinha o ano: fica registrado para as próximas execuções
        registro.ano_processo = ano

    try:
        acessar_processo(driver, num_processo)
        processar_deproc(driver, registro, base, data_geracao_base, ano)
        _conferir_marcadores(registro, 'no fim da passagem')

    except UnidadeSemAcessoException as e:
        # Unidade sem acesso ao processo: nenhuma ação no SEI
        registrar_sem_acesso(registro, e)

    except (ErroAvaliacao, FormatoMemorandoInvalido, TextoMemoPendente) as e:
        # Problema esperado nos dados: sem traceback
        registrar_erro(registro, e)

    except Exception as e:
        registrar_erro(registro, e)
        logger.exception('Erro inesperado durante o processamento')
        restaurar_navegador(driver)

    return registro


def _logar_anos(anos: dict[str, AnoProcesso]) -> None:
    for ano in sorted({a.ano for a in anos.values()}):
        quantidade = sum(a.ano == ano for a in anos.values())
        base_ano = BASES_DEPROC.get(ano)
        if base_ano is None:
            logger.error(f'Ano {ano}: {quantidade} processo(s), sem base DEPROC cadastrada em BASES_DEPROC (não serão apurados)')
        else:
            logger.info(f'Ano {ano}: {quantidade} processo(s) | Base DEPROC: {base_ano.arquivo.name} | Data de geração: {base_ano.data_geracao}')


def _anos_ou_encerrar(parser: argparse.ArgumentParser, processos: list, controle: PlanilhaControleGeral, ano_argumento: str | None) -> dict[str, AnoProcesso]:
    """O ano de cada processo. Faltando o de algum (na planilha e no -a), o
    argparse mostra o erro e encerra (código 2), antes do login."""
    anos, sem_ano = anos_dos_processos(processos, controle.linha_processo, ano_argumento)
    if sem_ano:
        lista = ', '.join(map(str, sem_ano))
        logger.error(f'{len(sem_ano)} processo(s) sem ano na planilha de controle (ano_processo / ano_base_deproc): {lista}')
        parser.error(f'o argumento -a/--ano é obrigatório: {len(sem_ano)} processo(s) sem ano na planilha de controle ({lista})')
    _logar_anos(anos)
    return anos


def _processar_com_ano(driver: webdriver.Remote, num_processo, bases: BasesDeprocPorAno, ano: AnoProcesso) -> RegistroDeproc:
    """Ano sem base cadastrada: base None (erro no processo, sem ação no SEI)."""
    base_ano = BASES_DEPROC.get(ano.ano)
    base = bases.do_ano(ano.ano) if base_ano else None
    data_geracao = base_ano.data_geracao if base_ano else None
    return _processar_linha(driver, num_processo, base, data_geracao, ano.ano, ano.do_argumento)


def main(argv: list[str] | None = None):
    # Antes de tudo: com ano sem base cadastrada, nada é feito (nem log)
    parser = _criar_parser()
    ano_argumento = parser.parse_args(argv).ano

    for diretorio in [DIR_INPUTS, DIR_CONTROLE, DIR_LOG, DIR_FLUXO_DEPROC_PDF]:
        diretorio.mkdir(parents=True, exist_ok=True)
    configurar_logging(ARQ_LOG)

    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info(f'================= INÍCIO DA EXECUÇÃO ({FLUXO}) =================')
        logger.info(f'Log: {ARQ_LOG}')
        logger.info(f'Ano informado (-a): {ano_argumento or "nenhum"}')

        processos = ler_processos_a_processar(SCRIPT)
        total = len(processos)

        controle = PlanilhaControleGeral(SCRIPT, AGORA)
        anos = _anos_ou_encerrar(parser, processos, controle, ano_argumento)

        bases = BasesDeprocPorAno(carregar_base_deproc)
        driver = abrir_sei(UNIDADE_DEPROC)

        for i, num_processo in enumerate(processos, start=1):
            with contexto_processo(num_processo):
                t_ini = datetime.now()
                logger.info(f'INÍCIO [{i}/{total}]')

                registro = _processar_com_ano(driver, num_processo, bases, anos[num_processo])
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
