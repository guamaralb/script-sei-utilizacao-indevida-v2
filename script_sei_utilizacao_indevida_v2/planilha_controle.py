"""Planilha de controle geral (dados/controle/controle_geral_de_processos.xlsx).

Gravada por main.py e por main_add_memo_nao_usou_rede_propria.py depois de
cada processo (PlanilhaControleGeral):
    - aba "processos": uma linha por processo, com a última passagem pelo
      fluxo. As colunas que o script grava são sobrescritas (o processo é
      reavaliado a cada passagem); as demais e primeira_passagem são
      mantidas;
    - aba "historico": uma linha por passagem (acrescentada).

Antes da primeira gravação da execução, a planilha anterior é copiada para
dados/controle/backup.
Se não for possível ler ou gravar a planilha (ex.: aberta no Excel), a
execução é salva em um arquivo à parte, para ser conferida e incorporada
manualmente.

Formatação:
    - cabeçalho congelado e com filtro;
    - largura das colunas ajustada ao conteúdo;
    - linha com erro destacada em vermelho claro;
    - células de matrículas não encontradas destacadas em amarelo.
"""

import logging
import shutil
from pathlib import Path

import pandas as pd
from constantes import ARQ_CONTROLE_GERAL, DIR_BACKUP_CONTROLE
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

_ABA_PROCESSOS = 'processos'
_ABA_HISTORICO = 'historico'
_COLUNAS_INICIAIS = ('num_processo', 'primeira_passagem', 'ultima_passagem', 'script')
_BACKUPS_MANTIDOS = 30

_LARGURA_MAXIMA = 60
_PREENCHIMENTO_ERRO = PatternFill(fill_type='solid', start_color='FFF4CCCC', end_color='FFF4CCCC')
_PREENCHIMENTO_NAO_ENCONTRADA = PatternFill(fill_type='solid', start_color='FFFFE599', end_color='FFFFE599')

_COLUNAS_NAO_ENCONTRADAS = (
    'titular_nao_encontrado_base_geral',
    'deps_nao_encontrados_base_geral',
    'titular_nao_encontrado',
    'deps_nao_encontrados',
)


# ---------------------------------------------------------------------------
# Leitura e atualização
# ---------------------------------------------------------------------------


def _ler_aba(planilhas: dict[str, pd.DataFrame], aba: str) -> list[dict]:
    if aba not in planilhas:
        return []
    df = planilhas[aba].astype(object).where(planilhas[aba].notna(), None)
    return df.to_dict('records')


def _ler(arquivo: Path) -> tuple[list[dict], list[dict]]:
    if not arquivo.exists():
        logger.info(f'Planilha de controle geral ainda não existe; será criada: {arquivo}')
        return [], []
    planilhas = pd.read_excel(arquivo, sheet_name=None, dtype=object)
    return _ler_aba(planilhas, _ABA_PROCESSOS), _ler_aba(planilhas, _ABA_HISTORICO)


def _atualizar_processos(processos: list[dict], passagens: list[dict]) -> list[dict]:
    por_processo = {str(linha['num_processo']).strip(): dict(linha) for linha in processos}
    for passagem in passagens:
        linha = por_processo.setdefault(str(passagem['num_processo']).strip(), {})
        primeira = linha.get('primeira_passagem') or passagem['ultima_passagem']
        linha.update(passagem)
        linha['primeira_passagem'] = primeira
    return list(por_processo.values())


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


def _formatar(planilha, colunas: list[str]) -> None:
    planilha.freeze_panes = 'B2'
    planilha.auto_filter.ref = planilha.dimensions
    for celula in planilha[1]:
        celula.font = Font(bold=True)

    for indice, coluna in enumerate(colunas, start=1):
        valores = [str(c.value) for c in planilha[get_column_letter(indice)] if c.value is not None]
        largura = max((len(v) for v in valores), default=len(coluna))
        planilha.column_dimensions[get_column_letter(indice)].width = min(largura + 2, _LARGURA_MAXIMA)

    idx_erro = colunas.index('erro') if 'erro' in colunas else None
    idx_nao_encontradas = [colunas.index(c) for c in _COLUNAS_NAO_ENCONTRADAS if c in colunas]

    for linha in planilha.iter_rows(min_row=2):
        if idx_erro is not None and linha[idx_erro].value:
            for celula in linha:
                celula.fill = _PREENCHIMENTO_ERRO
        for idx in idx_nao_encontradas:
            if linha[idx].value:
                linha[idx].fill = _PREENCHIMENTO_NAO_ENCONTRADA


def _dataframe(linhas: list[dict]) -> pd.DataFrame:
    colunas = list(_COLUNAS_INICIAIS)
    for linha in linhas:
        colunas += [c for c in linha if c not in colunas]
    return pd.DataFrame(linhas, columns=colunas)


def _gravar(arquivo: Path, abas: dict[str, list[dict]]) -> None:
    with pd.ExcelWriter(arquivo, engine='openpyxl') as writer:
        for aba, linhas in abas.items():
            df = _dataframe(linhas)
            df.to_excel(writer, sheet_name=aba, index=False)
            # A formatação é opcional: se falhar, a aba fica sem ela
            try:
                _formatar(writer.sheets[aba], list(df.columns))
            except Exception:
                logger.exception(f'Falha ao formatar a aba "{aba}" da planilha de controle')


def _fazer_backup(arquivo: Path, execucao: str) -> None:
    if not arquivo.exists():
        return
    DIR_BACKUP_CONTROLE.mkdir(parents=True, exist_ok=True)
    destino = DIR_BACKUP_CONTROLE / f'{arquivo.stem}_{execucao}{arquivo.suffix}'
    shutil.copy2(arquivo, destino)
    logger.info(f'Backup da planilha de controle: {destino}')

    backups = sorted(DIR_BACKUP_CONTROLE.glob(f'{arquivo.stem}_*{arquivo.suffix}'))
    for antigo in backups[:-_BACKUPS_MANTIDOS]:
        antigo.unlink()


def _salvar_a_parte(arquivo: Path, execucao: str, abas: dict[str, list[dict]]) -> Path:
    a_parte = arquivo.with_name(f'{arquivo.stem}_{execucao}_NAO_INCORPORADO{arquivo.suffix}')
    try:
        _gravar(a_parte, abas)
        logger.error(f'Execução salva à parte: {a_parte}. Ela NÃO foi incorporada à planilha de controle geral; confira e incorpore manualmente')
    except Exception:
        logger.exception(f'Falha ao salvar a execução à parte: {a_parte}')
    return a_parte


class PlanilhaControleGeral:
    """Planilha de controle geral de uma execução.

    É lida uma vez, no início, e regravada a cada processo (registrar), para
    que uma interrupção da execução não perca os processos já tratados. O
    backup é feito uma vez por execução, antes da primeira gravação."""

    def __init__(self, script: str, execucao: str, arquivo: Path = ARQ_CONTROLE_GERAL):
        self.script = script
        self.execucao = execucao
        self.arquivo = arquivo
        self._passagens: list[dict] = []
        self._backup_feito = False
        self._a_parte: Path | None = None
        try:
            self._processos, self._historico = _ler(arquivo)
            self._incorporar = True
        except Exception:
            logger.exception(f'Falha ao ler a planilha de controle geral: {arquivo}. Esta execução será salva à parte')
            self._processos, self._historico = [], []
            self._incorporar = False

    def registrar(self, registro: dict) -> None:
        """registro: RegistroBase.to_dict() de uma passagem."""
        self._passagens.append({'script': self.script, **registro})
        abas = {
            _ABA_PROCESSOS: _atualizar_processos(self._processos, self._passagens),
            _ABA_HISTORICO: self._historico + self._passagens,
        }
        if not self._incorporar:
            self._a_parte = _salvar_a_parte(self.arquivo, self.execucao, abas)
            return
        try:
            if not self._backup_feito:
                _fazer_backup(self.arquivo, self.execucao)
                self._backup_feito = True
            _gravar(self.arquivo, abas)
        except Exception:
            logger.exception(f'Falha ao salvar a planilha de controle geral: {self.arquivo}')
            self._a_parte = _salvar_a_parte(self.arquivo, self.execucao, abas)
            return
        logger.debug(f'Planilha de controle geral salva: {self.arquivo} ({len(self._passagens)} passagem(ns) nesta execução)')
        if self._a_parte is not None:
            logger.info(f'Planilha de controle geral voltou a ser gravada com todas as passagens; {self._a_parte} pode ser apagado')
            self._a_parte = None
