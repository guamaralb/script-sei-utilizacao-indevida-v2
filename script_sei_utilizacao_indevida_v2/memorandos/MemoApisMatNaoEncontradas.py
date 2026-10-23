import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore

PROCESSO_PLANILHA_MATRICULAS = '2010.01.0058549/2026-56'
PLANILHA_MATRICULAS = 'Planilha de Matrículas – Titulares e Dependentes U.I (144739371)'

# Não altere o assunto: é por ele que o script encontra memos já criados
ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = 'Matrículas Não Encontradas na Planilha de Matrículas U.I'

PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = re.compile(
    r'Matr[íi]culas\s+N[ãa]o\s+Encontradas\s+na\s+Planilha\s+de\s+Matr[íi]culas',
    flags=re.IGNORECASE,
)


def _listar_matriculas(titular: str | None, dependentes: tuple[str, ...]) -> list[str]:
    itens = [f'{titular} (titular)'] if titular else []
    itens += [f'{m} (dependente)' for m in dependentes]
    return itens


def _juntar(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ', '.join(itens[:-1]) + f' e {itens[-1]}'


def _par_nao_localizadas(itens: list[str]) -> str:
    base = (
        f'dentre as matrículas constantes da {PLANILHA_MATRICULAS}, disponibilizada no processo nº {PROCESSO_PLANILHA_MATRICULAS}, '
        'que constitui a base de referência para tratamento das demandas pela unidade IPSEMG/GEACS-Utilização.'
    )
    if len(itens) == 1:
        return f'A matrícula {itens[0]}, informada no presente processo, não foi localizada {base}'
    return f'As matrículas {_juntar(itens)}, informadas no presente processo, não foram localizadas {base}'


def _par_conferencia(plural: bool) -> str:
    matricula = 'das matrículas informadas' if plural else 'da matrícula informada'
    return f'Dessa forma, retornamos o processo para conferência {matricula} e verificação de sua correspondência com os beneficiários abrangidos pela referida planilha.'


def _par_correcao(plural: bool) -> str:
    matricula = 'de alguma das matrículas' if plural else 'da matrícula'
    return f'Caso seja identificada necessidade de correção {matricula} e confirmada sua inclusão na base, solicitamos a retificação da informação e o reencaminhamento à IPSEMG/GEACS-Utilização.'


def _par_encaminhamento(plural: bool) -> str:
    condicao = 'Caso as matrículas estejam corretas e os beneficiários não integrem' if plural else 'Caso a matrícula esteja correta e o beneficiário não integre'
    return (
        f'{condicao} a base da demanda de utilização indevida tratada no processo nº {PROCESSO_PLANILHA_MATRICULAS}, '
        'o presente processo deverá ser encaminhado à unidade IPSEMG/GEACS, para o tratamento pertinente.'
    )


def _par_fecho():
    return 'Atenciosamente,'


class MemoApisMatNaoEncontradas(Memorando):
    """Memo à APIS-Utilização: matrícula(s) não localizada(s) na base APIS
    (Planilha de Matrículas - Titulares e Dependentes U.I).

    Devolve o processo para conferência da matrícula (possível erro de
    digitação) e, se estiver correta, pede o encaminhamento à IPSEMG/GEACS.
    """

    def __init__(
        self,
        *,
        nome_signatario: str,
        cargo_signatario: str,
        titular: str | None,
        dependentes: tuple[str, ...],
        memo_apis: DocArvore,
    ):
        itens = _listar_matriculas(titular, dependentes)
        if not itens:
            raise ValueError('Memorando de matrículas não encontradas criado sem matrículas')
        plural = len(itens) > 1

        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_nao_localizadas(itens),
                _par_conferencia(plural),
                _par_correcao(plural),
                _par_encaminhamento(plural),
                '',
                '',
                '',
                _par_fecho(),
            ],
        )
        self.memo_apis = memo_apis
