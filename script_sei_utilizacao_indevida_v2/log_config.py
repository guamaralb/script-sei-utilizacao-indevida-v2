"""Configuração de logging compartilhada pelos scripts.

- Cada linha de log traz o número do processo em andamento (via
  contexto_processo), inclusive as mensagens emitidas pelos módulos
  auxiliares (rede_propria, docs_processo etc.).
- Arquivo: nível DEBUG (detalhado). Console: nível INFO.
- Bibliotecas ruidosas (selenium, urllib3) ficam em WARNING.
"""

import contextvars
import logging
from collections import Counter
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

_LIMITE_DURACAO = 60
_SEM_PROCESSO = '-'
_processo_atual = contextvars.ContextVar('processo_atual', default=_SEM_PROCESSO)

_FORMATO = '%(asctime)s | %(levelname)-7s | %(processo)-25s | %(name)-21s | %(message)s'
_FORMATO_DATA = '%Y-%m-%d %H:%M:%S'

_LOGGERS_RUIDOSOS = ('selenium', 'urllib3', 'WDM', 'webdriver_manager')


def _adicionar_processo(record: logging.LogRecord) -> bool:
    """Filtro de logging: injeta o processo atual no record."""
    record.processo = _processo_atual.get()
    return True


def configurar_logging(arq_log: Path) -> None:
    formatador = logging.Formatter(_FORMATO, _FORMATO_DATA)

    handler_arquivo = logging.FileHandler(arq_log, encoding='utf-8')
    handler_arquivo.setLevel(logging.DEBUG)

    handler_console = logging.StreamHandler()
    handler_console.setLevel(logging.INFO)

    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG)
    raiz.handlers.clear()

    for handler in (handler_arquivo, handler_console):
        handler.setFormatter(formatador)
        handler.addFilter(_adicionar_processo)
        raiz.addHandler(handler)

    for nome in _LOGGERS_RUIDOSOS:
        logging.getLogger(nome).setLevel(logging.WARNING)

    logging.captureWarnings(True)


@contextmanager
def contexto_processo(num_processo):
    """Associa as mensagens de log emitidas dentro do bloco ao processo."""
    token = _processo_atual.set(str(num_processo))
    try:
        yield
    finally:
        _processo_atual.reset(token)


def formatar_duracao(duracao: timedelta) -> str:
    total = duracao.total_seconds()
    if total < _LIMITE_DURACAO:
        return f'{total:.1f}s'
    minutos, segundos = divmod(int(total), 60)
    horas, minutos = divmod(minutos, 60)
    return f'{horas:d}h{minutos:02d}m{segundos:02d}s'


def log_fim_processo(logger: logging.Logger, registro, duracao: timedelta) -> None:
    if registro.erro:
        logger.warning(f'FIM COM ERRO ({formatar_duracao(duracao)}) | {registro.tipo_erro}: {registro.erro}')
    else:
        logger.info(f'FIM ({formatar_duracao(duracao)}) | Próxima ação: {registro.prox_acao or "-"}')


def log_resumo(logger: logging.Logger, registros: list[dict]) -> None:
    total = len(registros)
    com_erro = [r for r in registros if r.get('erro')]
    sem_erro = [r for r in registros if not r.get('erro')]

    logger.info('------------------------ RESUMO ------------------------')
    logger.info(f'Processos: {total} | Sem erro: {len(sem_erro)} | Com erro: {len(com_erro)}')

    contagem = Counter(r.get('prox_acao') or '(sem próxima ação)' for r in sem_erro)
    for acao, qtd in contagem.most_common():
        logger.info(f'{qtd:>5} | {acao}')

    for registro in com_erro:
        logger.info(f'ERRO  | {registro["num_processo"]} | {registro.get("tipo_erro")}: {registro["erro"]}')
