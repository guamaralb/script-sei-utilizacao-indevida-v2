"""Argumentos -a (ano dos processos) e -d (data de geração da planilha da base
DEPROC) do geacs_inicial e do deproc_calcula_copa. Os dois escolhem o arquivo
da base (constantes.BaseDeproc):
-a 2019 -d 06/11/2026 -> copa-MANTIS11281-base_2019-06_11_2026.xlsx."""

import argparse
import re
from datetime import datetime

from constantes import BaseDeproc, bases_deproc_na_pasta


def tipo_ano(texto: str) -> str:
    ano = texto.strip()
    if not re.fullmatch(r'(19|20)\d\d', ano):
        raise argparse.ArgumentTypeError(f'ano inválido: {texto!r} (use AAAA, ex.: 2019)')
    return ano


def tipo_data(texto: str) -> str:
    """DD/MM/AAAA, com data válida (dia e mês com dois dígitos)."""
    data = texto.strip()
    try:
        if not re.fullmatch(r'\d\d/\d\d/\d{4}', data):
            raise ValueError
        datetime.strptime(data, '%d/%m/%Y')
    except ValueError:
        raise argparse.ArgumentTypeError(f'data inválida: {texto!r} (use DD/MM/AAAA, ex.: 06/11/2026)') from None
    return data


def adicionar_argumentos(parser: argparse.ArgumentParser, obrigatorios: bool, uso: str) -> None:
    parser.add_argument('-a', '--ano', required=obrigatorios, type=tipo_ano, help=f'ano dos processos (AAAA): {uso}')
    parser.add_argument(
        '-d',
        '--data',
        required=obrigatorios,
        type=tipo_data,
        help='data de geração da planilha da base DEPROC (DD/MM/AAAA), que está no nome do arquivo: -a 2019 -d 06/11/2026 -> copa-MANTIS11281-base_2019-06_11_2026.xlsx',
    )


def _bases_disponiveis() -> str:
    return ', '.join(f'-a {b.ano} -d {b.data_geracao}' for b in bases_deproc_na_pasta()) or 'nenhuma'


def base_dos_argumentos(parser: argparse.ArgumentParser, args: argparse.Namespace) -> BaseDeproc | None:
    """A base do -a e do -d (None sem os dois). Só um dos dois, ou sem o
    arquivo da base na pasta: o argparse mostra o erro e encerra (código 2),
    antes do log, do login e de qualquer ação no SEI."""
    if args.ano is None and args.data is None:
        return None
    if args.ano is None or args.data is None:
        parser.error('os argumentos -a/--ano e -d/--data são usados juntos')
    base = BaseDeproc(args.ano, args.data)
    if not base.existe():
        parser.error(f'base DEPROC não encontrada: {base.arquivo} (bases na pasta: {_bases_disponiveis()})')
    return base
