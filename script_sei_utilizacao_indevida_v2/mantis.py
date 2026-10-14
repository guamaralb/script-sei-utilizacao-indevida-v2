"""Consulta às bases de utilização do MANTIS (rede própria e rede
credenciada).

Cada arquivo tem as abas TITULARES e DEPENDENTES, com uma linha por item
atendido. Conta como uso o atendimento com data dentro do período de
apuração do titular (o fluxo normal para antes do MANTIS quando há período
variável para dependentes, então o período do titular vale para todos).

A rede própria entra na decisão do fluxo normal; a rede credenciada só é
registrada na planilha de controle.
"""

import calendar
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from rede_propria import ErroAvaliacao, normalizar_matricula

from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    UsoRedeBeneficiarios,
)

logger = logging.getLogger(__name__)

_ABA_TITULARES = ('TITULARES', 'MATRICULA_BENEFICIARIO')
_ABA_DEPENDENTES = ('DEPENDENTES', 'MATRICULA_DEPENDENTE')
_COLUNA_DATA = 'DAT_ATENDIMENTO'
_COLUNA_VALOR = 'VAL_PAGAR'

# TODO: confirmar com as planilhas completas. No exemplo, o titular vem SEM
# DV (2362911 corresponde a 23629118). Para os dependentes ainda não há
# confirmação; assume-se sem DV, como nos processos.
TITULAR_MANTIS_COM_DV = False
DEPENDENTE_MANTIS_COM_DV = False

# Datas do Excel guardadas como número de série
_ORIGEM_DATA_EXCEL = datetime(1899, 12, 30)


@dataclass(frozen=True)
class Atendimento:
    data: date | None
    valor: float


@dataclass(frozen=True)
class BaseMantis:
    """Atendimentos por matrícula, sempre sem DV."""

    nome: str
    titulares: dict[str, tuple[Atendimento, ...]]
    dependentes: dict[str, tuple[Atendimento, ...]]


@dataclass(frozen=True)
class BasesMantis:
    rede_propria: BaseMantis
    rede_credenciada: BaseMantis


def _sem_dv(matricula: str) -> str | None:
    return matricula[:-1].lstrip('0') or None


def _converter_data(valor) -> date | None:
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, datetime | pd.Timestamp):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, int | float):
        return (_ORIGEM_DATA_EXCEL + timedelta(days=int(valor))).date()
    try:
        return datetime.strptime(str(valor).strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def _converter_valor(valor) -> float | None:
    if valor is None or pd.isna(valor):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _carregar_aba(arquivo: Path, aba: str, coluna_matricula: str, *, com_dv: bool) -> dict[str, tuple[Atendimento, ...]]:
    df = pd.read_excel(io=arquivo, sheet_name=aba, dtype={coluna_matricula: str})
    df.columns = df.columns.str.strip()

    atendimentos: dict[str, list[Atendimento]] = defaultdict(list)
    sem_matricula = 0
    sem_data = 0
    sem_valor = 0
    for matricula, data_bruta, valor_bruto in zip(df[coluna_matricula], df[_COLUNA_DATA], df[_COLUNA_VALOR], strict=True):
        mat = normalizar_matricula(matricula)
        if mat and com_dv:
            mat = _sem_dv(mat)
        if not mat:
            sem_matricula += 1
            continue
        data = _converter_data(data_bruta)
        valor = _converter_valor(valor_bruto)
        sem_data += data is None
        sem_valor += valor is None
        atendimentos[mat].append(Atendimento(data=data, valor=valor or 0.0))

    logger.info(f'MANTIS, aba "{aba}" carregada | {len(df)} linha(s) | {len(atendimentos)} matrícula(s) única(s)')
    if sem_matricula:
        logger.warning(f'MANTIS, aba "{aba}": {sem_matricula} linha(s) sem matrícula ignorada(s)')
    if sem_data:
        logger.warning(f'MANTIS, aba "{aba}": {sem_data} linha(s) com data inválida (geram erro se a matrícula for consultada)')
    if sem_valor:
        logger.warning(f'MANTIS, aba "{aba}": {sem_valor} linha(s) sem valor (consideradas com valor 0)')
    return {mat: tuple(lista) for mat, lista in atendimentos.items()}


def _carregar_base(arquivo: Path, nome: str) -> BaseMantis:
    logger.info(f'Carregando base do MANTIS ({nome}): {arquivo.name}')
    return BaseMantis(
        nome=nome,
        titulares=_carregar_aba(arquivo, *_ABA_TITULARES, com_dv=TITULAR_MANTIS_COM_DV),
        dependentes=_carregar_aba(arquivo, *_ABA_DEPENDENTES, com_dv=DEPENDENTE_MANTIS_COM_DV),
    )


def carregar_bases_mantis(arquivo_rede_propria: Path, arquivo_rede_credenciada: Path) -> BasesMantis:
    return BasesMantis(
        rede_propria=_carregar_base(arquivo_rede_propria, 'rede própria'),
        rede_credenciada=_carregar_base(arquivo_rede_credenciada, 'rede credenciada'),
    )


# ---------------------------------------------------------------------------
# Período de apuração
# ---------------------------------------------------------------------------

# Formatos vistos nos memos: "01/08/2023 a 12/06/2024", "09/2023 a 06/2024"
# e "02 a 06/2024" (mês inicial sem ano), com vários intervalos separados
# por vírgula, ponto e vírgula ou ", de".
_DATA_INICIO = r'\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}|\d{1,2}'
_DATA_FIM = r'\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{4}'
_PADRAO_INTERVALO = re.compile(rf'\b({_DATA_INICIO})\s+a\s+({_DATA_FIM})\b')


@dataclass(frozen=True)
class Intervalo:
    inicio: date
    fim: date

    def contem(self, data: date) -> bool:
        return self.inicio <= data <= self.fim


def _ultimo_dia(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


_PARTES_DIA_MES_ANO = 3
_PARTES_MES_ANO = 2


def _converter_fim(texto: str) -> date:
    partes = [int(p) for p in texto.split('/')]
    if len(partes) == _PARTES_DIA_MES_ANO:
        return date(partes[2], partes[1], partes[0])
    return _ultimo_dia(partes[1], partes[0])


def _converter_inicio(texto: str, fim: date) -> date:
    partes = [int(p) for p in texto.split('/')]
    if len(partes) == _PARTES_DIA_MES_ANO:
        return date(partes[2], partes[1], partes[0])
    if len(partes) == _PARTES_MES_ANO:
        return date(partes[1], partes[0], 1)
    return date(fim.year, partes[0], 1)


def interpretar_periodo(texto: str) -> tuple[Intervalo, ...]:
    """Converte o período de apuração do memo da APIS em intervalos de
    datas. Qualquer trecho com número fora de um intervalo reconhecido
    gera ErroAvaliacao, para não deixar uso fora da consulta."""
    texto = str(texto or '')
    intervalos = []
    try:
        for match in _PADRAO_INTERVALO.finditer(texto):
            fim = _converter_fim(match.group(2))
            inicio = _converter_inicio(match.group(1), fim)
            if inicio > fim:
                raise ErroAvaliacao(f'Período de apuração do titular com início depois do fim: "{match.group(0)}"')
            intervalos.append(Intervalo(inicio, fim))
    except ValueError as e:
        raise ErroAvaliacao(f'Período de apuração do titular com data inválida: "{texto}"') from e

    restante = _PADRAO_INTERVALO.sub('', texto)
    if not intervalos or re.search(r'\d', restante):
        raise ErroAvaliacao(f'Período de apuração do titular em formato não reconhecido: "{texto}"')
    return tuple(intervalos)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UsoMantis:
    """Uso de uma rede no MANTIS dentro do período de apuração."""

    tit_usou: bool
    tit_valor_total: float
    deps_que_usaram: tuple[str, ...]
    deps_valor_total: float

    @property
    def alguem_usou(self) -> bool:
        return self.tit_usou or bool(self.deps_que_usaram)


@dataclass(frozen=True)
class AvaliacaoMantis:
    rede_propria: UsoMantis
    rede_credenciada: UsoMantis


def _no_periodo(atendimentos: tuple[Atendimento, ...], intervalos: tuple[Intervalo, ...], descricao: str) -> list[Atendimento]:
    if any(a.data is None for a in atendimentos):
        raise ErroAvaliacao(f'Atendimento do MANTIS sem data válida para {descricao}')
    return [a for a in atendimentos if any(i.contem(a.data) for i in intervalos)]


def _consultar(base: BaseMantis, titular: str, dependentes: tuple[str, ...], intervalos: tuple[Intervalo, ...]) -> UsoMantis:
    chave_titular = _sem_dv(titular)
    tit_atendimentos = _no_periodo(base.titulares.get(chave_titular, ()), intervalos, f'o titular {titular} ({base.nome})')

    deps_que_usaram = []
    deps_valor_total = 0.0
    for dependente in dependentes:
        atendimentos = _no_periodo(base.dependentes.get(dependente, ()), intervalos, f'o dependente {dependente} ({base.nome})')
        if atendimentos:
            deps_que_usaram.append(dependente)
            deps_valor_total += sum(a.valor for a in atendimentos)

    return UsoMantis(
        tit_usou=bool(tit_atendimentos),
        tit_valor_total=round(sum(a.valor for a in tit_atendimentos), 2),
        deps_que_usaram=tuple(deps_que_usaram),
        deps_valor_total=round(deps_valor_total, 2),
    )


def avaliar_uso_rede_propria_mantis(
    titular: str,
    dependentes: tuple[str, ...],
    periodo_titular: str,
    bases: BasesMantis,
) -> AvaliacaoMantis:
    """titular (com DV) e dependentes (sem DV) já normalizados."""
    intervalos = interpretar_periodo(periodo_titular)
    avaliacao = AvaliacaoMantis(
        rede_propria=_consultar(bases.rede_propria, titular, dependentes, intervalos),
        rede_credenciada=_consultar(bases.rede_credenciada, titular, dependentes, intervalos),
    )
    for nome, uso in (('rede própria', avaliacao.rede_propria), ('rede credenciada', avaliacao.rede_credenciada)):
        logger.info(
            f'MANTIS {nome} | Titular {titular}: {"USOU" if uso.tit_usou else "NÃO USOU"} (R$ {uso.tit_valor_total:.2f}) | '
            f'Dependentes que usaram: {list(uso.deps_que_usaram) or "-"} (R$ {uso.deps_valor_total:.2f})'
        )
    return avaliacao


def usos_mantis_alem_disa(disa: UsoRedeBeneficiarios, mantis: UsoMantis) -> list[str]:
    """Matrículas com uso da rede própria no MANTIS que a base DISA marca
    como não uso (ou não tem)."""
    itens = []
    if mantis.tit_usou and not disa.tit_usou:
        itens.append(f'{disa.matricula_titular} (titular)')
    itens += [f'{m} (dependente)' for m in mantis.deps_que_usaram if m not in disa.deps_que_usaram]
    return itens
