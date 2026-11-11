import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore

PROCESSO_PLANILHA_MATRICULAS = '2010.01.0058549/2026-56'
PLANILHA_MATRICULAS = 'Planilha de Matrículas - Titulares e Dependentes U.I (144739371)'

# Não altere o assunto: é por ele que o script encontra memos já criados
ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = 'Conferência de matrículas e do direcionamento da demanda'

# Aceita também o assunto anterior ("Matrículas Não Encontradas na Planilha de
# Matrículas U.I"), dos memos já criados
PADRAO_ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS = re.compile(
    re.escape(ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS) + r'|Matr[íi]culas\s+N[ãa]o\s+Encontradas\s+na\s+Planilha\s+de\s+Matr[íi]culas',
    flags=re.IGNORECASE,
)


def _par_nao_localizadas(plural: bool) -> str:
    verbo, matriculas = ('foram identificadas', 'as seguintes matrículas') if plural else ('foi identificada', 'a seguinte matrícula')
    return f'Na validação inicial deste processo, não {verbo} na {PLANILHA_MATRICULAS}, constante do processo {PROCESSO_PLANILHA_MATRICULAS}, {matriculas}:'


def _matriculas(titular: str | None, dependentes: tuple[str, ...]) -> list[str]:
    """Uma linha para o titular e uma para os dependentes, só as que faltaram."""
    linhas = [f'<strong>Matrícula do titular</strong>: {titular}.'] if titular else []
    if dependentes:
        rotulo = '<strong>Matrículas dos dependentes</strong>' if len(dependentes) > 1 else '<strong>Matrícula do dependente</strong>'
        linhas.append(f'{rotulo}: {"; ".join(dependentes)}.')
    return linhas


def _par_conferencia(plural: bool) -> str:
    matriculas = 'das matrículas informadas' if plural else 'da matrícula informada'
    return f'Assim, retornamos o processo para <strong>conferência {matriculas} e confirmação de que a demanda integra o levantamento abrangido pela referida planilha.</strong>'


def _par_encaminhamento(plural: bool) -> str:
    condicao = 'as matrículas estejam corretas' if plural else 'a matrícula esteja correta'
    return (
        f'Caso {condicao} e se trate de demanda de utilização diversa daquela abrangida pela planilha, solicita-se o encaminhamento à unidade IPSEMG/GEACS, '
        'uma vez que a unidade IPSEMG/GEACS-Utilização se destina ao tratamento das demandas vinculadas à relação de referência.'
    )


class MemoApisMatNaoEncontradas(Memorando):
    """Memo à APIS-Utilização: matrícula(s) não localizada(s) na base APIS
    (Planilha de Matrículas - Titulares e Dependentes U.I).

    Devolve o processo para conferência das matrículas: se houver erro, pede
    novo memorando de solicitação no modelo padronizado; se estiverem corretas
    e a demanda for diversa da planilha, o encaminhamento à IPSEMG/GEACS.
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
        if not titular and not dependentes:
            raise ValueError('Memorando de matrículas não encontradas criado sem matrículas')
        plural = len(dependentes) + bool(titular) > 1

        super().__init__(
            # Duas linhas: <br>, pois o texto entra no HTML do memo (um \n vira espaço)
            destinatario_nome='Fernanda de Moura Galantini<br>Assessoria de Políticas e Informações em Saúde - APIS',
            assunto=ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_nao_localizadas(plural),
                *_matriculas(titular, dependentes),
                _par_conferencia(plural),
                'Caso seja identificada incorreção nos dados, solicita-se a emissão de <strong>novo memorando de solicitação no modelo padronizado, contendo integralmente a demanda com os dados corrigidos</strong>, incluindo as matrículas do titular e dos dependentes e os respectivos períodos de apuração. Após o ajuste, o processo deverá ser reencaminhado à unidade IPSEMG/GEACS-Utilização.',
                _par_encaminhamento(plural),
                'Para preservar a rotina de automatização, eventual correção deverá ser incorporada ao novo memorando de solicitação, não se limitando a resposta pontual a este documento.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
