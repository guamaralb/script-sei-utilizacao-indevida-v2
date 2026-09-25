"""Consulta à planilha de beneficiários atendidos na rede própria.

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

# Número lido do Excel como float e convertido para texto: "123456789.0"
_PADRAO_FLOAT_EXCEL = re.compile(r'^(\d+)\.0+$')
_PADRAO_SEPARADORES = re.compile(r'[-.\s]')


class ErroAvaliacao(Exception):
    """Problema esperado nos dados de um processo (não é falha do script)."""


class MatriculasNaoEncontradas(ErroAvaliacao):
    """Matrícula(s) buscada(s) e não encontrada(s) na base da rede própria.

    O processamento do processo deve ser parado.
    """

    def __init__(self, matriculas: list[str]):
        self.matriculas = matriculas
        super().__init__(f'Matrícula(s) não encontrada(s) na base da rede própria: {", ".join(matriculas)}')


@dataclass(frozen=True)
class BasesUso:
    """Mapeia matrícula -> utilizou a rede própria.

    O valor é None quando a coluna de uso tem resposta diferente de
    SIM/NÃO para aquela matrícula.
    """

    titulares: dict[str, bool | None]
    dependentes: dict[str, bool | None]


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


def carregar_bases(arquivo: Path) -> BasesUso:
    logger.info(f'Carregando planilha de uso da rede própria: {arquivo.name}')
    return BasesUso(
        titulares=_carregar_aba(arquivo, *_ABA_TITULARES),
        dependentes=_carregar_aba(arquivo, *_ABA_DEPENDENTES),
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


def _verificar_encontradas(titular: str, dependentes: list[str], bases: BasesUso) -> None:
    nao_encontradas = [titular] if titular not in bases.titulares else []
    nao_encontradas += [m for m in dependentes if m not in bases.dependentes]
    if nao_encontradas:
        raise MatriculasNaoEncontradas(nao_encontradas)


def avaliar_uso(
    matricula_titular,
    matriculas_dependentes,
    bases: BasesUso,
) -> UsoRedeBeneficiarios:
    titular = normalizar_matricula(matricula_titular)
    if not titular:
        raise ErroAvaliacao('Não há matrícula de titular')

    dependentes = separar_matriculas_dependentes(matriculas_dependentes)

    _validar_formato([titular], 'titular')
    _validar_formato(dependentes, 'dependente')
    _verificar_encontradas(titular, dependentes, bases)

    tit_usaram, _ = _consultar([titular], bases.titulares, 'titular')
    deps_usaram, deps_nao_usaram = _consultar(dependentes, bases.dependentes, 'dependente')

    uso = UsoRedeBeneficiarios(
        matricula_titular=titular,
        tit_usou=bool(tit_usaram),
        deps_que_usaram=tuple(deps_usaram),
        deps_que_nao_usaram=tuple(deps_nao_usaram),
    )
    logger.info(
        f'Uso da rede própria | Titular {titular}: '
        f'{"USOU" if uso.tit_usou else "NÃO USOU"} | '
        f'Dependentes que usaram: {list(uso.deps_que_usaram) or "-"} | '
        f'Dependentes que não usaram: {list(uso.deps_que_nao_usaram) or "-"}'
    )
    return uso


def registrar_uso(registro, uso: UsoRedeBeneficiarios) -> None:
    registro.tit_usou = uso.tit_usou
    registro.deps_que_usaram = list(uso.deps_que_usaram)
    registro.deps_que_nao_usaram = list(uso.deps_que_nao_usaram)
