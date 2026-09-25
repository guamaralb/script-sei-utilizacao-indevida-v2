import re

from sei_automacao.classes.Memorando import Memorando

REFERENCIA_PLANILHA_MATRICULAS = 'documento <strong>Planilha de Matrículas - Titulares e Dependentes U.I (144739371)</strong>, contida no processo 2010.01.0058549/2026-56'

ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = 'Matrículas Não Encontradas na Planilha de Matrículas U.I'

PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = re.compile(
    r'Matr[íi]culas\s+N[ãa]o\s+Encontradas\s+na\s+Planilha\s+de\s+Matr[íi]culas',
    flags=re.IGNORECASE,
)


def _listar_matriculas(titular: str | None, dependentes: tuple[str, ...]) -> list[str]:
    itens = [f'{titular} (titular)'] if titular else []
    itens += [f'{m} (dependente)' for m in dependentes]
    return itens


def _par_nao_encontradas(itens: list[str]) -> str:
    if len(itens) == 1:
        return f'A matrícula {itens[0]} não foi encontrada dentre as matrículas listadas no {REFERENCIA_PLANILHA_MATRICULAS}.'
    lista = ', '.join(itens[:-1]) + f' e {itens[-1]}'
    return f'As matrículas {lista} não foram encontradas dentre as matrículas listadas no {REFERENCIA_PLANILHA_MATRICULAS}.'


def _par_encaminhamento():
    return (
        'Considerando que a presente unidade <strong>IPSEMG/GEACS-Utilização</strong> tem como objetivo tratar somente das matrículas '
        'contidas na planilha, este processo deve ser encaminhado para a unidade <strong>IPSEMG/GEACS</strong>.'
    )


def _par_fecho():
    return 'Atenciosamente,'


class MemoApisMatNaoEncontradas(Memorando):
    """Memo à APIS-Utilização: matrícula(s) não encontrada(s) na base geral
    (Planilha de Matrículas - Titulares e Dependentes U.I)."""

    def __init__(
        self,
        *,
        nome_signatario: str,
        cargo_signatario: str,
        titular: str | None,
        dependentes: tuple[str, ...],
    ):
        itens = _listar_matriculas(titular, dependentes)
        if not itens:
            raise ValueError('Memorando de matrículas não encontradas criado sem matrículas')

        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_nao_encontradas(itens),
                _par_encaminhamento(),
                '',
                '',
                '',
                _par_fecho(),
            ],
        )
