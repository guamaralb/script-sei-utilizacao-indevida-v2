"""Planilha de controle geral (dados/controle/controle_geral_de_processos.xlsx).

Gravada por main_geacs_inicial.py depois de cada processo (PlanilhaControleGeral). A
coluna "script" distingue as passagens antigas do script de correção
(correcao_rede_propria), que foi removido:
    - aba "processos": uma linha por processo, com a última passagem pelo
      fluxo. As colunas que o script grava são sobrescritas (o processo é
      reavaliado a cada passagem); as demais e primeira_passagem são
      mantidas;
    - histórico: uma linha por passagem, acrescentada a um CSV ao lado da
      planilha (controle_geral_de_processos_historico.csv, HistoricoCsv). Até
      18/11/2026 era a aba "historico", regravada inteira a cada processo; na
      primeira leitura, a aba é copiada para o CSV e sai da planilha.

A primeira aba, "resumo", traz a quantidade de processos (aba "processos")
por prox_acao, regravada a cada gravação.

As outras abas (ex.: "BUSCA", preenchida à mão) são mantidas. Na aba
"processos", as colunas BUSCA (fórmula que procura o processo na aba BUSCA;
#N/D se não estiver lá) e ERROS VERIFICADOS MANUALMENTE (anotações) vêm
logo depois de num_processo. A fórmula é regravada a cada gravação.

Antes da primeira gravação da execução, a planilha anterior é copiada para
dados/controle/backup.
Se não for possível ler ou gravar a planilha (ex.: aberta no Excel), a
execução é salva em um arquivo à parte, para ser conferida e incorporada
manualmente.

Formatação:
    - cabeçalho congelado e com filtro;
    - largura das colunas ajustada ao conteúdo;
    - colunas dos marcadores (o nome inteiro do marcador, tags.COLUNAS_TAGS)
      no fim, na ordem da numeração, com largura fixa e o nome quebrado em
      até 3 linhas; estado_atual logo depois da prox_acao;
    - linha com erro destacada em vermelho claro;
    - células de matrículas não encontradas destacadas em amarelo;
    - ação sugerida, inconsistência e erro do fluxo GEACS VERIFICAR
      MARCADORES em amarelo (com a prox_acao da linha), logo depois de erro.

A gravação é atômica: o arquivo é gravado em uma cópia temporária, que só
então substitui a planilha. Uma interrupção no meio da gravação (ex.:
sistema operacional encerrando o processo) não corrompe a planilha.

Uma execução por vez: a planilha fica travada (~em_uso_<nome>.lock, trava do
sistema operacional, liberada quando o processo termina) do início ao fim da
execução. Outra execução, de qualquer fluxo, para antes do login
(PlanilhaEmUso). Em 18/11/2026, duas execuções gravaram juntas a mesma cópia
temporária e corromperam a planilha.
"""

import csv
import logging
import math
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import IO

import pandas as pd
from constantes import ARQ_CONTROLE_GERAL, DIR_BACKUP_CONTROLE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from tags import (
    COLUNA_DEMAIS_MARCADORES,
    COLUNA_ESTADO_ATUAL,
    COLUNA_ESTADO_ATUAL_DEPROC,
    COLUNA_POR_COLUNA_ANTIGA,
    COLUNAS_TAGS,
    COLUNAS_TAGS_VALIDOS,
    TAGS_ESTADO_DEPROC,
    demais_marcadores,
    descrever_estado,
    eh_coluna_tag,
)

logger = logging.getLogger(__name__)

_ABA_PROCESSOS = 'processos'
_ABA_HISTORICO = 'historico'
_ABA_RESUMO = 'resumo'
_SEM_PROX_ACAO = '(sem prox_acao)'
_COLUNAS_INICIAIS = ('num_processo', 'primeira_passagem', 'ultima_passagem', 'script')
# Mantida pelo usuário: os processos a procurar na aba "processos" (coluna A)
_ABA_BUSCA = 'BUSCA'
_COLUNA_BUSCA = 'BUSCA'
_COLUNA_ERROS_MANUAIS = 'ERROS VERIFICADOS MANUALMENTE'
_COLUNAS_INICIAIS_PROCESSOS = ('num_processo', _COLUNA_BUSCA, _COLUNA_ERROS_MANUAIS, 'primeira_passagem', 'ultima_passagem', 'script')
_BACKUPS_MANTIDOS = 30

_LARGURA_MAXIMA = 60
# Colunas dos marcadores: o nome mais longo ("DEPROC | v2: 01.02.1 -
# Encaminhado GEACS: Memo Cálculo COPA") cabe em 3 linhas de 20 caracteres
# (há teste); a folga é do negrito
_LARGURA_COLUNA_MARCADOR = 22
CARACTERES_POR_LINHA_MARCADOR = 20
_ALTURA_CABECALHO_MARCADORES = 48
_PREENCHIMENTO_ERRO = PatternFill(fill_type='solid', start_color='FFF4CCCC', end_color='FFF4CCCC')
_PREENCHIMENTO_NAO_ENCONTRADA = PatternFill(fill_type='solid', start_color='FFFFE599', end_color='FFFFE599')

# Coluna de marcadores que não existe mais: os marcadores do processo ficam
# nas colunas dos marcadores válidos (tags.COLUNAS_TAGS) e em demais_marcadores
_COLUNAS_MARCADORES_OBSOLETAS = frozenset({'verificar_marcadores'})

_COLUNAS_NAO_ENCONTRADAS = (
    'titular_nao_encontrado_base_geral',
    'deps_nao_encontrados_base_geral',
    'deps_nao_encontrados_ignorados',
)

# Fluxo GEACS VERIFICAR MARCADORES: ação sugerida, inconsistência encontrada
# (prox_acao, marcadores e memorandos) e erro da passagem. Ficam logo depois
# de "erro" e, preenchidas, em amarelo (com a prox_acao da linha)
COLUNA_VERIFICAR_ACAO_SUGERIDA = 'verificar_marcadores_acao_sugerida'
COLUNA_VERIFICAR_INCONSISTENCIA = 'verificar_marcadores_inconsistencia'
COLUNA_VERIFICAR_ERRO = 'verificar_marcadores_erro'
_COLUNAS_VERIFICAR = (COLUNA_VERIFICAR_ACAO_SUGERIDA, COLUNA_VERIFICAR_INCONSISTENCIA, COLUNA_VERIFICAR_ERRO)
# Logo depois da prox_acao
_COLUNAS_ESTADO = (COLUNA_ESTADO_ATUAL, COLUNA_ESTADO_ATUAL_DEPROC)

# Histórico (uma linha por passagem): CSV ao lado da planilha. Separador ";"
# e UTF-8 com BOM, para o Excel em português abrir direto
_SEPARADOR_CSV = ';'
_CODIFICACAO_CSV = 'utf-8-sig'


# ---------------------------------------------------------------------------
# Leitura e atualização
# ---------------------------------------------------------------------------


def _ler_aba(planilhas: dict[str, pd.DataFrame], aba: str) -> list[dict]:
    if aba not in planilhas:
        return []
    df = planilhas[aba].astype(object).where(planilhas[aba].notna(), None)
    return df.to_dict('records')


def _coluna_marcador_obsoleta(coluna) -> bool:
    """Coluna tag_* de marcador que não é mais válido (o marcador vai para
    demais_marcadores) ou coluna de marcadores que não existe mais."""
    coluna = str(coluna)
    return (eh_coluna_tag(coluna) and coluna not in COLUNAS_TAGS_VALIDOS) or coluna in _COLUNAS_MARCADORES_OBSOLETAS


def _migrar_nomes(linha: dict) -> dict:
    """Colunas tag_* dos marcadores válidos -> o nome do marcador (até
    18/11/2026 tinham nomes curtos, alguns diferentes do marcador). Com as
    duas na linha, vale a atual."""
    nova = {}
    for coluna, valor in linha.items():
        atual = COLUNA_POR_COLUNA_ANTIGA.get(coluna)
        if atual is None:
            nova[coluna] = valor
        elif atual not in linha:
            nova[atual] = valor
    return nova


def _marcadores(texto) -> list[str] | None:
    """Os marcadores de marcadores_finais (separados por ";"); None se vazia."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    return [tag.strip() for tag in texto.split(';')]


def migrar_colunas_marcadores(linhas: list[dict]) -> list[dict]:
    """Renomeia as colunas tag_* dos marcadores válidos para o nome do marcador
    e remove as colunas de marcadores obsoletas. Os marcadores delas não se
    perdem: sem demais_marcadores, ela é calculada a partir de
    marcadores_finais (todos os marcadores do processo no fim da passagem).
    Sem estado_atual (estado_atual_deproc), ela também é calculada, de
    marcadores_finais (marcadores_deproc_finais). As outras colunas ficam como
    estão."""
    migradas = []
    for linha in linhas:
        nova = {coluna: valor for coluna, valor in _migrar_nomes(linha).items() if not _coluna_marcador_obsoleta(coluna)}
        finais = _marcadores(linha.get('marcadores_finais'))
        if finais is not None:
            if nova.get(COLUNA_DEMAIS_MARCADORES) is None:
                nova[COLUNA_DEMAIS_MARCADORES] = demais_marcadores(finais) or None
            if nova.get(COLUNA_ESTADO_ATUAL) is None:
                nova[COLUNA_ESTADO_ATUAL] = descrever_estado(finais)
        finais_deproc = _marcadores(linha.get('marcadores_deproc_finais'))
        if finais_deproc is not None and nova.get(COLUNA_ESTADO_ATUAL_DEPROC) is None:
            nova[COLUNA_ESTADO_ATUAL_DEPROC] = descrever_estado(finais_deproc, TAGS_ESTADO_DEPROC)
        migradas.append(nova)
    return migradas


def _tem_colunas_a_migrar(planilhas: dict[str, pd.DataFrame]) -> bool:
    """A aba processos tem colunas que a migração renomeia ou remove."""
    if _ABA_PROCESSOS not in planilhas:
        return False
    colunas = [str(coluna) for coluna in planilhas[_ABA_PROCESSOS].columns]
    sem_estado = 'marcadores_finais' in colunas and COLUNA_ESTADO_ATUAL not in colunas
    return sem_estado or any(coluna in COLUNA_POR_COLUNA_ANTIGA or _coluna_marcador_obsoleta(coluna) for coluna in colunas)


def _ler(arquivo: Path) -> tuple[list[dict], list[dict] | None, bool]:
    """As linhas da aba processos, as da aba historico (None: a planilha não
    tem mais a aba, que virou o CSV) e se a aba processos tinha colunas a
    migrar (migrar_colunas_marcadores)."""
    if not arquivo.exists():
        logger.info(f'Planilha de controle geral ainda não existe; será criada: {arquivo}')
        return [], None, False
    planilhas = pd.read_excel(arquivo, sheet_name=None, dtype=object)
    historico = migrar_colunas_marcadores(_ler_aba(planilhas, _ABA_HISTORICO)) if _ABA_HISTORICO in planilhas else None
    return migrar_colunas_marcadores(_ler_aba(planilhas, _ABA_PROCESSOS)), historico, _tem_colunas_a_migrar(planilhas)


def _atualizar_processos(processos: list[dict], passagens: list[dict], so_historico: frozenset[str] = frozenset()) -> list[dict]:
    """so_historico: colunas das passagens que não vão para a aba processos
    (ex.: script e ultima_passagem do verificar marcadores)."""
    por_processo = {str(linha['num_processo']).strip(): dict(linha) for linha in processos}
    for passagem in passagens:
        linha = por_processo.setdefault(str(passagem['num_processo']).strip(), {})
        primeira = linha.get('primeira_passagem') or passagem['ultima_passagem']
        linha.update({coluna: valor for coluna, valor in passagem.items() if coluna not in so_historico})
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
        celula.alignment = Alignment(vertical='top')

    for indice, coluna in enumerate(colunas, start=1):
        letra = get_column_letter(indice)
        if eh_coluna_tag(coluna):
            # Largura fixa e o nome do marcador quebrado em até 3 linhas
            planilha.column_dimensions[letra].width = _LARGURA_COLUNA_MARCADOR
            planilha.cell(row=1, column=indice).alignment = Alignment(wrap_text=True, vertical='top')
            continue
        valores = [str(c.value) for c in planilha[letra] if c.value is not None]
        largura = max((len(v) for v in valores), default=len(coluna))
        planilha.column_dimensions[letra].width = min(largura + 2, _LARGURA_MAXIMA)
    if any(eh_coluna_tag(coluna) for coluna in colunas):
        planilha.row_dimensions[1].height = _ALTURA_CABECALHO_MARCADORES

    idx_erro = colunas.index('erro') if 'erro' in colunas else None
    idx_nao_encontradas = [colunas.index(c) for c in _COLUNAS_NAO_ENCONTRADAS if c in colunas]
    idx_verificar = [colunas.index(c) for c in _COLUNAS_VERIFICAR if c in colunas]
    idx_prox_acao = colunas.index('prox_acao') if 'prox_acao' in colunas else None

    for linha in planilha.iter_rows(min_row=2):
        if idx_erro is not None and linha[idx_erro].value:
            for celula in linha:
                celula.fill = _PREENCHIMENTO_ERRO
        for idx in idx_nao_encontradas:
            if linha[idx].value:
                linha[idx].fill = _PREENCHIMENTO_NAO_ENCONTRADA
        verificar = [idx for idx in idx_verificar if linha[idx].value]
        if verificar and idx_prox_acao is not None:
            verificar.append(idx_prox_acao)
        for idx in verificar:
            linha[idx].fill = _PREENCHIMENTO_NAO_ENCONTRADA


def _inserir_depois(colunas: list[str], ancora: str, novas: list[str]) -> list[str]:
    posicao = colunas.index(ancora) + 1 if ancora in colunas else len(colunas)
    return colunas[:posicao] + novas + colunas[posicao:]


def _ordenar_colunas(colunas: list[str]) -> list[str]:
    """estado_atual (e estado_atual_deproc) logo depois da prox_acao; as do
    fluxo GEACS VERIFICAR MARCADORES logo depois de erro; no fim,
    demais_marcadores e as colunas dos marcadores, na ordem de
    tags.COLUNAS_TAGS (as antigas que sobrarem, depois)."""
    marcadores = [c for c in COLUNAS_TAGS if c in colunas] + [c for c in colunas if eh_coluna_tag(c) and c not in COLUNAS_TAGS_VALIDOS]
    fim = [COLUNA_DEMAIS_MARCADORES] * (COLUNA_DEMAIS_MARCADORES in colunas) + marcadores
    estados = [c for c in _COLUNAS_ESTADO if c in colunas]
    verificar = [c for c in _COLUNAS_VERIFICAR if c in colunas]
    resto = [c for c in colunas if c not in {*fim, *estados, *verificar}]
    resto = _inserir_depois(resto, 'prox_acao', estados)
    resto = _inserir_depois(resto, 'erro', verificar)
    return resto + fim


def _dataframe(linhas: list[dict], colunas_iniciais: tuple[str, ...] = _COLUNAS_INICIAIS) -> pd.DataFrame:
    colunas = list(colunas_iniciais)
    for linha in linhas:
        colunas += [c for c in linha if c not in colunas]
    return pd.DataFrame(linhas, columns=_ordenar_colunas(colunas))


def _dataframe_processos(linhas: list[dict]) -> pd.DataFrame:
    df = _dataframe(linhas, _COLUNAS_INICIAIS_PROCESSOS)
    # O pandas lê o valor calculado, não a fórmula: ela é regravada.
    # num_processo é a coluna A; a linha 1 é o cabeçalho
    df[_COLUNA_BUSCA] = [f'=MATCH(A{linha},{_ABA_BUSCA}!$A:$A,0)' for linha in range(2, len(df) + 2)]
    return df


def _dataframe_resumo(processos: list[dict]) -> pd.DataFrame:
    """Quantidade de processos por prox_acao, da maior para a menor, com o
    total na última linha."""
    contagem = pd.Series([linha.get('prox_acao') or _SEM_PROX_ACAO for linha in processos], dtype=object).value_counts()
    resumo = pd.DataFrame({'prox_acao': contagem.index, 'quantidade': contagem.to_numpy()})
    total = pd.DataFrame({'prox_acao': ['TOTAL'], 'quantidade': [len(processos)]})
    return pd.concat([resumo, total], ignore_index=True)


def _gravar_resumo(writer: pd.ExcelWriter, processos: list[dict]) -> None:
    """Aba resumo, a primeira da planilha (é a que abre no Excel)."""
    df = _dataframe_resumo(processos)
    df.to_excel(writer, sheet_name=_ABA_RESUMO, index=False)
    book = writer.book
    book.move_sheet(_ABA_RESUMO, offset=-book.sheetnames.index(_ABA_RESUMO))
    for aba in book.worksheets:
        aba.sheet_view.tabSelected = False
    book.active = 0
    book.active.sheet_view.tabSelected = True
    try:
        planilha = writer.sheets[_ABA_RESUMO]
        for celula in (*planilha[1], *planilha[planilha.max_row]):
            celula.font = Font(bold=True)
        planilha.column_dimensions['A'].width = min(max(len(str(v)) for v in df['prox_acao']) + 2, _LARGURA_MAXIMA * 2)
        planilha.column_dimensions['B'].width = 12
    except Exception:
        logger.exception('Falha ao formatar a aba "resumo" da planilha de controle')


def _gravar(arquivo: Path, abas: dict[str, list[dict]], remover: tuple[str, ...] = ()) -> None:
    """Grava em uma cópia temporária e só então substitui o arquivo
    (os.replace é atômico): se o processo for encerrado no meio da gravação,
    a planilha anterior continua inteira."""
    # Com o pid, uma cópia temporária nunca é a de outro processo
    temporario = arquivo.with_name(f'~gravando_{os.getpid()}_{arquivo.name}')
    try:
        if arquivo.exists():
            shutil.copy2(arquivo, temporario)
        else:
            temporario.unlink(missing_ok=True)
        _gravar_arquivo(temporario, abas, remover)
        # No Windows, o fsync exige o arquivo aberto para escrita ('rb' dá
        # EBADF)
        with temporario.open('r+b') as gravado:
            os.fsync(gravado.fileno())
        os.replace(temporario, arquivo)
    finally:
        temporario.unlink(missing_ok=True)


def _gravar_arquivo(arquivo: Path, abas: dict[str, list[dict]], remover: tuple[str, ...] = ()) -> None:
    """remover: abas que saem da planilha (a aba historico, depois de copiada
    para o CSV)."""
    # Com o arquivo existente, só as abas do script são substituídas: as
    # demais (ex.: BUSCA) são mantidas
    modo = {'mode': 'a', 'if_sheet_exists': 'replace'} if arquivo.exists() else {'mode': 'w'}
    with pd.ExcelWriter(arquivo, engine='openpyxl', **modo) as writer:
        for aba in remover:
            if aba in writer.book.sheetnames and aba not in abas:
                writer.book.remove(writer.book[aba])
        for aba, linhas in abas.items():
            df = _dataframe_processos(linhas) if aba == _ABA_PROCESSOS else _dataframe(linhas)
            df.to_excel(writer, sheet_name=aba, index=False)
            # A formatação é opcional: se falhar, a aba fica sem ela
            try:
                _formatar(writer.sheets[aba], list(df.columns))
            except Exception:
                logger.exception(f'Falha ao formatar a aba "{aba}" da planilha de controle')
        # Sem a aba, a fórmula da coluna BUSCA daria erro de referência
        if _ABA_BUSCA not in writer.book.sheetnames:
            writer.book.create_sheet(_ABA_BUSCA)
        if _ABA_PROCESSOS in abas:
            _gravar_resumo(writer, abas[_ABA_PROCESSOS])


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


class PlanilhaEmUso(RuntimeError):
    """Outra execução está usando a planilha de controle geral."""


# Travas deste processo, por arquivo: abertas até o processo terminar. Várias
# PlanilhaControleGeral do mesmo arquivo no mesmo processo (ex.: testes)
# compartilham a trava
_TRAVAS: dict[Path, IO] = {}


def _arquivo_trava(arquivo: Path) -> Path:
    return arquivo.with_name(f'~em_uso_{arquivo.stem}.lock')


#: No Windows, a trava é de um byte depois do texto da trava (a parte travada
#: não pode ser lida pela outra execução, que precisa dizer quem está rodando)
_POSICAO_TRAVA_WINDOWS = 1 << 20


def _travar_sem_esperar(trava: IO) -> None:
    """Trava exclusiva do sistema operacional; OSError se outra execução já a
    tem. É liberada quando o processo termina, mesmo encerrado à força."""
    if sys.platform == 'win32':
        import msvcrt  # noqa: PLC0415

        trava.seek(_POSICAO_TRAVA_WINDOWS)
        msvcrt.locking(trava.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl  # noqa: PLC0415

        fcntl.flock(trava.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def travar_planilha(arquivo: Path, script: str) -> None:
    """Uma execução por vez na planilha de controle: levanta PlanilhaEmUso se
    outro processo a está usando (o arquivo da trava diz qual)."""
    chave = arquivo.resolve()
    if chave in _TRAVAS:
        return
    caminho = _arquivo_trava(arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # 'a+': não apaga o que a outra execução escreveu antes de travar
    trava = caminho.open('a+', encoding='utf-8')
    try:
        _travar_sem_esperar(trava)
    except OSError:
        try:
            trava.seek(0)
            dono = trava.read().strip() or 'desconhecida'
        except OSError:
            # No Windows, a parte travada não pode ser lida
            dono = f'veja {caminho.name}'
        trava.close()
        raise PlanilhaEmUso(
            f'A planilha de controle geral está sendo usada por outra execução ({dono}). '
            f'Espere ela terminar (ou encerre-a) antes de rodar outro fluxo: duas execuções gravando juntas corrompem a planilha'
        ) from None
    trava.seek(0)
    trava.truncate()
    trava.write(f'script {script}, pid {os.getpid()}, início {datetime.now():%d/%m/%Y %H:%M:%S}')
    trava.flush()
    _TRAVAS[chave] = trava


# ---------------------------------------------------------------------------
# Histórico em CSV
# ---------------------------------------------------------------------------


def arquivo_historico(arquivo: Path) -> Path:
    """O CSV do histórico, ao lado da planilha de controle."""
    return arquivo.with_name(f'{arquivo.stem}_historico.csv')


def _valor_csv(valor) -> str:
    """Como o Excel em português lê: VERDADEIRO / FALSO, data DD/MM/AAAA e
    decimal com vírgula."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor is pd.NaT:
        return ''
    if isinstance(valor, bool):
        return 'VERDADEIRO' if valor else 'FALSO'
    if isinstance(valor, datetime):
        return valor.strftime('%d/%m/%Y %H:%M:%S')
    if isinstance(valor, float):
        return repr(valor).replace('.', ',')
    return str(valor)


class HistoricoCsv:
    """Histórico das passagens (uma linha por passagem), em CSV. A linha é
    acrescentada no fim do arquivo, sem regravar o resto (a aba historico era
    regravada inteira a cada processo). O arquivo só é regravado quando
    aparece uma coluna nova (cabeçalho maior), em uma cópia temporária que
    então o substitui.

    Se não for possível gravar (ex.: CSV aberto no Excel), as linhas ficam
    pendentes e vão na gravação seguinte."""

    def __init__(self, arquivo: Path):
        self.arquivo = arquivo
        self._pendentes: list[dict] = []

    def _colunas(self) -> list[str]:
        if not self.arquivo.exists():
            return []
        with self.arquivo.open(encoding=_CODIFICACAO_CSV, newline='') as entrada:
            return next(csv.reader(entrada, delimiter=_SEPARADOR_CSV), [])

    def ler(self) -> list[dict]:
        if not self.arquivo.exists():
            return []
        with self.arquivo.open(encoding=_CODIFICACAO_CSV, newline='') as entrada:
            return list(csv.DictReader(entrada, delimiter=_SEPARADOR_CSV))

    def quantidade(self) -> int:
        return len(self.ler())

    def acrescentar(self, linhas: list[dict]) -> bool:
        """Grava as linhas (e as pendentes). False se não conseguiu (ficam
        pendentes)."""
        self._pendentes += linhas
        try:
            self._gravar_pendentes()
        except Exception:
            logger.exception(f'Falha ao gravar o histórico: {self.arquivo}. {len(self._pendentes)} passagem(ns) pendente(s), gravada(s) na próxima vez')
            return False
        return True

    def _gravar_pendentes(self) -> None:
        if not self._pendentes:
            return
        colunas = self._colunas()
        novas = [c for c in dict.fromkeys(c for linha in self._pendentes for c in linha) if c not in colunas]
        linhas = [{c: _valor_csv(v) for c, v in linha.items()} for linha in self._pendentes]
        if novas or not colunas:
            self._regravar(_ordenar_colunas([*colunas, *novas]), [*self.ler(), *linhas])
        else:
            with self.arquivo.open('a', encoding=_CODIFICACAO_CSV, newline='') as saida:
                csv.DictWriter(saida, colunas, delimiter=_SEPARADOR_CSV).writerows(linhas)
                saida.flush()
                os.fsync(saida.fileno())
        self._pendentes = []

    def _regravar(self, colunas: list[str], linhas: list[dict]) -> None:
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_name(f'~gravando_{os.getpid()}_{self.arquivo.name}')
        try:
            with temporario.open('w', encoding=_CODIFICACAO_CSV, newline='') as saida:
                escritor = csv.DictWriter(saida, colunas, delimiter=_SEPARADOR_CSV)
                escritor.writeheader()
                escritor.writerows(linhas)
                saida.flush()
                os.fsync(saida.fileno())
            os.replace(temporario, self.arquivo)
        finally:
            temporario.unlink(missing_ok=True)


# Fluxos que não agem no processo: até 18/11/2026 gravavam script,
# ultima_passagem e data_execucao na aba processos (hoje só no histórico)
_SCRIPTS_SO_HISTORICO = frozenset({'geacs_verificar_marcadores'})
_COLUNAS_ULTIMO_FLUXO = ('script', 'ultima_passagem', 'data_execucao')


def restaurar_ultimo_fluxo(processos: list[dict], historico: list[dict]) -> int:
    """Na migração da aba historico: a linha do processo com script de um
    fluxo que não age (_SCRIPTS_SO_HISTORICO) volta a ter script,
    ultima_passagem e data_execucao da última passagem de outro fluxo. A do
    verificar vai para verificar_marcadores_em (se vazia). Devolve a
    quantidade de processos restaurados."""
    ultima_por_processo = {}
    for passagem in historico:
        if passagem.get('script') not in _SCRIPTS_SO_HISTORICO:
            ultima_por_processo[str(passagem.get('num_processo')).strip()] = passagem
    restaurados = 0
    for linha in processos:
        passagem = ultima_por_processo.get(str(linha.get('num_processo')).strip())
        if linha.get('script') not in _SCRIPTS_SO_HISTORICO or passagem is None:
            continue
        if linha.get('verificar_marcadores_em') is None:
            linha['verificar_marcadores_em'] = linha.get('ultima_passagem')
        for coluna in _COLUNAS_ULTIMO_FLUXO:
            linha[coluna] = passagem.get(coluna)
        restaurados += 1
    return restaurados


class PlanilhaControleGeral:
    """Planilha de controle geral de uma execução.

    É lida uma vez, no início, e regravada a cada processo (registrar), para
    que uma interrupção da execução não perca os processos já tratados. O
    backup é feito uma vez por execução, antes da primeira gravação.

    Trava a planilha até o fim do processo (travar_planilha): com outra
    execução usando a planilha, levanta PlanilhaEmUso, antes do login.

    Cada passagem vai também para o histórico em CSV (HistoricoCsv).
    colunas_so_historico: colunas da passagem que não vão para a aba
    processos (ex.: script e ultima_passagem do verificar marcadores, que não
    age no processo)."""

    def __init__(self, script: str, execucao: str, arquivo: Path = ARQ_CONTROLE_GERAL, colunas_so_historico: frozenset[str] = frozenset()):
        travar_planilha(arquivo, script)
        self.script = script
        self.execucao = execucao
        self.arquivo = arquivo
        self.colunas_so_historico = colunas_so_historico
        self.historico = HistoricoCsv(arquivo_historico(arquivo))
        self._passagens: list[dict] = []
        self._backup_feito = False
        self._a_parte: Path | None = None
        # Abas que saem da planilha na próxima gravação (a historico, depois
        # de copiada para o CSV)
        self._remover: tuple[str, ...] = ()
        try:
            self._processos, aba_historico, colunas_a_migrar = _ler(arquivo)
            self._incorporar = True
        except Exception:
            logger.exception(f'Falha ao ler a planilha de controle geral: {arquivo}. Esta execução será salva à parte')
            self._processos, aba_historico, colunas_a_migrar = [], None, False
            self._incorporar = False
        restaurados = self._migrar_aba_historico(aba_historico) if aba_historico is not None else 0
        if colunas_a_migrar or self._remover or restaurados:
            self._gravar_migracao()

    def _gravar_migracao(self) -> None:
        """Grava logo a planilha migrada (colunas dos marcadores, aba historico
        no CSV, script restaurado), sem esperar o primeiro processo: a
        execução pode não ter nenhum. Se falhar, a migração vai na próxima
        gravação."""
        try:
            _fazer_backup(self.arquivo, self.execucao)
            self._backup_feito = True
            _gravar(self.arquivo, {_ABA_PROCESSOS: self._processos}, self._remover)
        except Exception:
            logger.exception(f'Falha ao gravar a planilha de controle geral migrada: {self.arquivo}; a migração vai na próxima gravação')
            return
        self._remover = ()
        logger.info(f'Planilha de controle geral migrada e gravada: {self.arquivo}')

    def processos_da_planilha(self) -> list[str]:
        """Todos os processos da aba processos, na ordem da planilha, sem
        repetição ([] se ela não pôde ser lida)."""
        if not self._incorporar:
            return []
        processos = (str(linha.get('num_processo')).strip() for linha in self._processos if linha.get('num_processo') is not None)
        return list(dict.fromkeys(numero for numero in processos if numero))

    def _migrar_aba_historico(self, linhas: list[dict]) -> int:
        """A aba historico (até 18/11/2026) vai para o CSV e sai da planilha.
        Se o CSV já tem pelo menos as linhas da aba, a cópia já foi feita (a
        execução anterior parou antes de gravar a planilha): só sai da
        planilha. Com o CSV menor, a aba fica, para conferir à mão. Devolve a
        quantidade de processos com o script restaurado."""
        try:
            existentes = self.historico.quantidade()
            if existentes == 0:
                if not self.historico.acrescentar(linhas):
                    return 0
                logger.info(f'Aba "{_ABA_HISTORICO}" copiada para o histórico em CSV ({len(linhas)} passagem(ns)): {self.historico.arquivo}')
            elif existentes < len(linhas):
                logger.warning(
                    f'A planilha ainda tem a aba "{_ABA_HISTORICO}" ({len(linhas)} linhas), maior que o histórico em CSV ({existentes} linhas): a aba fica na planilha; confira e apague-a à mão'
                )
                return 0
        except Exception:
            logger.exception(f'Falha ao copiar a aba "{_ABA_HISTORICO}" para o histórico em CSV; a aba fica na planilha')
            return 0
        self._remover = (_ABA_HISTORICO,)
        restaurados = restaurar_ultimo_fluxo(self._processos, linhas)
        if restaurados:
            logger.info(f'script e ultima_passagem restaurados pelo histórico em {restaurados} processo(s) (estavam com os do verificar marcadores)')
        return restaurados

    def linha_processo(self, num_processo) -> dict | None:
        """A linha do processo na aba "processos", com as passagens desta
        execução ({} se o processo não está na planilha). None se a planilha
        não pôde ser lida (não há como saber o que está nela)."""
        if not self._incorporar:
            return None
        chave = str(num_processo).strip()
        linha: dict = {}
        for existente in (*self._processos, *self._passagens):
            if str(existente.get('num_processo')).strip() == chave:
                linha.update(existente)
        return linha

    def registrar(self, registro: dict) -> None:
        """registro: RegistroBase.to_dict() de uma passagem."""
        passagem = {'script': self.script, **registro}
        self._passagens.append(passagem)
        self.historico.acrescentar([passagem])
        abas = {_ABA_PROCESSOS: _atualizar_processos(self._processos, self._passagens, self.colunas_so_historico)}
        if not self._incorporar:
            # O arquivo à parte leva também as passagens desta execução
            self._a_parte = _salvar_a_parte(self.arquivo, self.execucao, {**abas, _ABA_HISTORICO: self._passagens})
            return
        try:
            if not self._backup_feito:
                _fazer_backup(self.arquivo, self.execucao)
                self._backup_feito = True
            _gravar(self.arquivo, abas, self._remover)
        except Exception:
            logger.exception(f'Falha ao salvar a planilha de controle geral: {self.arquivo}')
            self._a_parte = _salvar_a_parte(self.arquivo, self.execucao, {**abas, _ABA_HISTORICO: self._passagens})
            return
        logger.debug(f'Planilha de controle geral salva: {self.arquivo} ({len(self._passagens)} passagem(ns) nesta execução)')
        if self._a_parte is not None:
            logger.info(f'Planilha de controle geral voltou a ser gravada com todas as passagens; {self._a_parte} pode ser apagado')
            self._a_parte = None
