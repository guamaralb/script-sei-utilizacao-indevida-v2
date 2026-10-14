"""Consulta à planilha de beneficiários atendidos na rede própria e à
base geral (listagem de todos os beneficiários).

Compartilhado entre o fluxo normal (main.py) e o fluxo de correção
(main_add_memo_nao_usou_rede_propria.py).
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from constantes import VALOR_MATRICULA_DEPENDENTE_AVERIGUAR

from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    UsoRedeBeneficiarios,
)

logger = logging.getLogger(__name__)

_COLUNA_UTILIZOU = 'UTILIZOU A REDE PRÓPRIA?'
_RESPOSTAS_UTILIZOU = {'SIM': True, 'NÃO': False, 'NAO': False}

_ABA_TITULARES = ('UI 2025 EX-TITULARES', 'MATRICULAS TITULARES')
_ABA_DEPENDENTES = ('UI 2025 EX-DEPENDENTES', 'MATRICULAS DEPENDENTES - SEM DV')

# Base geral: titulares e dependentes com DV. Nos processos, os dependentes
# vêm sem DV, então o DV (último dígito) é retirado dos dependentes da base.
_ABA_GERAL_TITULARES = ('UI 2025 EX-TITULARES', 'MATRICULAS TITULARES')
_ABA_GERAL_DEPENDENTES = ('UI 2025 EX-DEPENDENTES', 'MATRICULAS DEPENDENTES')

# Número lido do Excel como float e convertido para texto: "123456789.0"
_PADRAO_FLOAT_EXCEL = re.compile(r'^(\d+)\.0+$')
_PADRAO_SEPARADORES = re.compile(r'[-.\s]')


class ErroAvaliacao(Exception):
    """Problema esperado nos dados de um processo (não é falha do script)."""


@dataclass(frozen=True)
class NaoEncontradas:
    """Matrículas não encontradas em uma base."""

    titular: str | None = None
    dependentes: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.titular or self.dependentes)

    def descrever(self) -> str:
        partes = []
        if self.titular:
            partes.append(f'titular {self.titular}')
        if self.dependentes:
            partes.append(f'dependente(s) {", ".join(self.dependentes)}')
        return '; '.join(partes)


class MatriculasNaoEncontradas(ErroAvaliacao):
    """Matrícula(s) não encontrada(s) na base geral e/ou na base da rede
    própria. O processamento do processo deve ser parado."""

    def __init__(self, base_geral: NaoEncontradas, base_rede: NaoEncontradas):
        self.base_geral = base_geral
        self.base_rede = base_rede
        partes = []
        if base_geral:
            partes.append(f'base geral: {base_geral.descrever()}')
        if base_rede:
            partes.append(f'base da rede própria: {base_rede.descrever()}')
        super().__init__(f'Matrícula(s) não encontrada(s) | {" | ".join(partes)}')


@dataclass(frozen=True)
class BasesUso:
    """Mapeia matrícula -> utilizou a rede própria.

    O valor é None quando a coluna de uso tem resposta diferente de
    SIM/NÃO para aquela matrícula.
    """

    titulares: dict[str, bool | None]
    dependentes: dict[str, bool | None]
    # Base geral (sem resposta de uso). Dependentes sem DV.
    geral_titulares: frozenset[str]
    geral_dependentes: frozenset[str]


def normalizar_matricula(valor) -> str | None:
    """Padroniza a matrícula no formato da planilha de rede própria:
    com dígito verificador, sem hífen e sem zeros à esquerda."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, float):
        valor = int(valor)

    mat = str(valor).strip()
    match_float = _PADRAO_FLOAT_EXCEL.match(mat)
    if match_float:
        mat = match_float.group(1)

    mat = _PADRAO_SEPARADORES.sub('', mat).lstrip('0')
    return mat or None


def _combinar_respostas(atual: bool | None, nova: bool | None) -> bool | None:
    """Combina respostas de linhas repetidas da mesma matrícula.

    Qualquer SIM prevalece; resposta inválida prevalece sobre NÃO.
    """
    if atual is True or nova is True:
        return True
    if atual is None or nova is None:
        return None
    return False


def _carregar_aba(arquivo: Path, aba: str, coluna_matricula: str) -> dict[str, bool | None]:
    df = pd.read_excel(
        io=arquivo,
        sheet_name=aba,
        dtype={coluna_matricula: str, _COLUNA_UTILIZOU: str},
    )

    uso: dict[str, bool | None] = {}
    repetidas = 0
    sem_matricula = 0
    for matricula, resposta in zip(df[coluna_matricula], df[_COLUNA_UTILIZOU], strict=True):
        mat = normalizar_matricula(matricula)
        if not mat:
            sem_matricula += 1
            continue
        chave = str(resposta).strip().upper() if pd.notna(resposta) else ''
        valor = _RESPOSTAS_UTILIZOU.get(chave)
        if mat in uso:
            repetidas += 1
            uso[mat] = _combinar_respostas(uso[mat], valor)
        else:
            uso[mat] = valor

    qtd_sim = sum(1 for v in uso.values() if v is True)
    qtd_nao = sum(1 for v in uso.values() if v is False)
    qtd_invalida = sum(1 for v in uso.values() if v is None)

    logger.info(f'Aba "{aba}" carregada | {len(df)} linha(s) | {len(uso)} matrícula(s) única(s) | SIM: {qtd_sim} | NÃO: {qtd_nao} | resposta inválida: {qtd_invalida}')
    if repetidas:
        logger.info(f'Aba "{aba}": {repetidas} linha(s) com matrícula repetida (respostas combinadas; SIM prevalece)')
    if sem_matricula:
        logger.warning(f'Aba "{aba}": {sem_matricula} linha(s) sem matrícula ignorada(s)')
    return uso


def _carregar_aba_geral(arquivo: Path, aba: str, coluna_matricula: str, *, retirar_dv: bool) -> frozenset[str]:
    df = pd.read_excel(io=arquivo, sheet_name=aba, dtype=str)
    # A planilha tem cabeçalho com espaço sobrando ("MATRICULAS TITULARES ")
    df.columns = df.columns.str.strip()

    matriculas = set()
    for valor in df[coluna_matricula]:
        mat = normalizar_matricula(valor)
        if mat and retirar_dv:
            mat = mat[:-1].lstrip('0')
        if mat:
            matriculas.add(mat)

    logger.info(f'Base geral, aba "{aba}" carregada | {len(df)} linha(s) | {len(matriculas)} matrícula(s) única(s)')
    return frozenset(matriculas)


def carregar_bases(arquivo_uso: Path, arquivo_geral: Path) -> BasesUso:
    logger.info(f'Carregando planilha de uso da rede própria: {arquivo_uso.name}')
    titulares = _carregar_aba(arquivo_uso, *_ABA_TITULARES)
    dependentes = _carregar_aba(arquivo_uso, *_ABA_DEPENDENTES)

    logger.info(f'Carregando base geral de beneficiários: {arquivo_geral.name}')
    return BasesUso(
        titulares=titulares,
        dependentes=dependentes,
        geral_titulares=_carregar_aba_geral(arquivo_geral, *_ABA_GERAL_TITULARES, retirar_dv=False),
        geral_dependentes=_carregar_aba_geral(arquivo_geral, *_ABA_GERAL_DEPENDENTES, retirar_dv=True),
    )


def separar_matriculas_dependentes(valor) -> list[str]:
    """Converte "123; 456" em lista de matrículas normalizadas.

    Dependentes citados sem matrícula explícita ("AVERIGUAR") geram erro.
    """
    if valor is None or pd.isna(valor):
        return []

    texto = str(valor).strip()
    if not texto:
        return []

    if texto.upper() == VALOR_MATRICULA_DEPENDENTE_AVERIGUAR:
        raise ErroAvaliacao('O memorando da APIS cita dependentes sem informar explicitamente as matrículas')

    matriculas = (normalizar_matricula(p) for p in texto.split(';'))
    return list(dict.fromkeys(m for m in matriculas if m))


def _validar_formato(matriculas: list[str], descricao: str) -> None:
    invalidas = [m for m in matriculas if not m.isdigit()]
    if invalidas:
        raise ErroAvaliacao(f'Matrícula(s) de {descricao} em formato inválido: {", ".join(invalidas)}')


def _consultar(
    matriculas: list[str],
    base: dict[str, bool | None],
    descricao: str,
) -> tuple[list[str], list[str]]:
    """Retorna (usaram, nao_usaram). As matrículas já devem ter sido
    encontradas na base (ver _verificar_encontradas)."""
    invalidas = [m for m in matriculas if m in base and base[m] is None]
    if invalidas:
        raise ErroAvaliacao(f'Matrícula(s) de {descricao} com resposta inválida em "{_COLUNA_UTILIZOU}": {", ".join(invalidas)}')

    usaram = [m for m in matriculas if base[m] is True]
    nao_usaram = [m for m in matriculas if base[m] is not True]
    return usaram, nao_usaram


def _nao_encontradas(titular: str, dependentes: list[str], base_titulares, base_dependentes) -> NaoEncontradas:
    return NaoEncontradas(
        titular=titular if titular not in base_titulares else None,
        dependentes=tuple(m for m in dependentes if m not in base_dependentes),
    )


def _verificar_encontradas(titular: str, dependentes: list[str], bases: BasesUso) -> None:
    """Busca as matrículas na base geral e na base da rede própria. As duas
    buscas são feitas antes de parar, para registrar as duas situações."""
    base_geral = _nao_encontradas(titular, dependentes, bases.geral_titulares, bases.geral_dependentes)
    base_rede = _nao_encontradas(titular, dependentes, bases.titulares, bases.dependentes)
    if base_geral or base_rede:
        raise MatriculasNaoEncontradas(base_geral, base_rede)


def _preparar_matriculas(matricula_titular, matriculas_dependentes) -> tuple[str, list[str]]:
    titular = normalizar_matricula(matricula_titular)
    if not titular:
        raise ErroAvaliacao('Não há matrícula de titular')

    dependentes = separar_matriculas_dependentes(matriculas_dependentes)

    _validar_formato([titular], 'titular')
    _validar_formato(dependentes, 'dependente')
    return titular, dependentes


def _logar_uso(uso: UsoRedeBeneficiarios) -> None:
    logger.info(
        f'Uso da rede própria | Titular {uso.matricula_titular}: '
        f'{"USOU" if uso.tit_usou else "NÃO USOU"} | '
        f'Dependentes que usaram: {list(uso.deps_que_usaram) or "-"} | '
        f'Dependentes que não usaram: {list(uso.deps_que_nao_usaram) or "-"}'
    )


def avaliar_uso(
    matricula_titular,
    matriculas_dependentes,
    bases: BasesUso,
) -> UsoRedeBeneficiarios:
    """Usada pela rotina de correção: para (MatriculasNaoEncontradas) se
    alguma matrícula não estiver nas duas bases."""
    titular, dependentes = _preparar_matriculas(matricula_titular, matriculas_dependentes)
    _verificar_encontradas(titular, dependentes, bases)

    tit_usaram, _ = _consultar([titular], bases.titulares, 'titular')
    deps_usaram, deps_nao_usaram = _consultar(dependentes, bases.dependentes, 'dependente')

    uso = UsoRedeBeneficiarios(
        matricula_titular=titular,
        tit_usou=bool(tit_usaram),
        deps_que_usaram=tuple(deps_usaram),
        deps_que_nao_usaram=tuple(deps_nao_usaram),
    )
    _logar_uso(uso)
    return uso


@dataclass(frozen=True)
class AvaliacaoDisa:
    """Resultado de avaliar_uso_rede_propria_disa (fluxo normal)."""

    uso: UsoRedeBeneficiarios
    dependentes: tuple[str, ...]
    nao_encontradas_geral: NaoEncontradas
    nao_encontradas_disa: NaoEncontradas


def _consultar_disa(matriculas: list[str], base: dict[str, bool | None], descricao: str) -> tuple[list[str], list[str]]:
    """Matrícula fora da base DISA conta como não uso."""
    usaram, _ = _consultar([m for m in matriculas if m in base], base, descricao)
    return usaram, [m for m in matriculas if m not in usaram]


def avaliar_uso_rede_propria_disa(
    matricula_titular,
    matriculas_dependentes,
    bases: BasesUso,
) -> AvaliacaoDisa:
    """Fluxo normal: procura o titular e os dependentes na base geral e na
    base DISA. Não para quando falta matrícula: quem chama decide. Quem não
    está na base DISA não usou a rede própria."""
    titular, dependentes = _preparar_matriculas(matricula_titular, matriculas_dependentes)
    nao_encontradas_geral = _nao_encontradas(titular, dependentes, bases.geral_titulares, bases.geral_dependentes)
    nao_encontradas_disa = _nao_encontradas(titular, dependentes, bases.titulares, bases.dependentes)

    tit_usaram, _ = _consultar_disa([titular], bases.titulares, 'titular')
    deps_usaram, deps_nao_usaram = _consultar_disa(dependentes, bases.dependentes, 'dependente')
    uso = UsoRedeBeneficiarios(
        matricula_titular=titular,
        tit_usou=bool(tit_usaram),
        deps_que_usaram=tuple(deps_usaram),
        deps_que_nao_usaram=tuple(deps_nao_usaram),
    )
    if nao_encontradas_geral:
        logger.warning(f'Não encontrado(s) na base geral | {nao_encontradas_geral.descrever()}')
    if nao_encontradas_disa:
        logger.warning(f'Não encontrado(s) na base DISA (contam como não uso) | {nao_encontradas_disa.descrever()}')
    _logar_uso(uso)
    return AvaliacaoDisa(
        uso=uso,
        dependentes=tuple(dependentes),
        nao_encontradas_geral=nao_encontradas_geral,
        nao_encontradas_disa=nao_encontradas_disa,
    )


def registrar_uso(registro, uso: UsoRedeBeneficiarios) -> None:
    registro.tit_usou = uso.tit_usou
    registro.deps_que_usaram = list(uso.deps_que_usaram)
    registro.deps_que_nao_usaram = list(uso.deps_que_nao_usaram)
