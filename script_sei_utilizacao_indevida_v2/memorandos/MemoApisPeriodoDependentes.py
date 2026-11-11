import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, identificar_doc
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

TEXTO_DEFINIDO = True

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = 'Individualização do período de apuração dos dependentes'

# O script procura o memo por este padrão antes de criar (retomada)
PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = re.compile(re.escape(ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES), flags=re.IGNORECASE)


def _matriculas(dependentes: tuple[str, ...]) -> list[str]:
    if not dependentes:
        return []
    rotulo = '<strong>Matrículas dos dependentes</strong>' if len(dependentes) > 1 else '<strong>Matrícula do dependente</strong>'
    return [f'{rotulo}: {"; ".join(dependentes)}.']


class MemoApisPeriodoDependentes(Memorando):
    """Memo à APIS-Utilização: o memorando da APIS tem período específico
    para dependentes. Pede novo memorando com o período de cada dependente
    individualizado por matrícula."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, dependentes: tuple[str, ...], memo_apis: DocArvore):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (período dos dependentes)')
        super().__init__(
            # Duas linhas: <br>, pois o texto entra no HTML do memo (um \n vira espaço)
            destinatario_nome='Fernanda de Moura Galantini<br>Assessoria de Políticas e Informações em Saúde - APIS',
            assunto=ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES,
            vocativo='Prezada Assessora',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'Retornamos o processo porque o <strong>{identificar_doc(memo_apis)}</strong> indica período de apuração específico para dependente, distinto do período informado para o titular, referente a:',
                *_matriculas(dependentes),
                'Assim, solicita-se a <strong>emissão de novo memorando de solicitação no modelo padronizado, com o período de apuração de cada dependente apresentado em campo individualizado por matrícula</strong>, com datas de início e término.',
                'A adequação deverá contemplar a demanda completa e atualizada, em substituição à solicitação anterior. Para não comprometer a rotina de automatização, não será suficiente responder pontualmente a este memorando ou informar apenas os dados faltantes.',
                'Após o ajuste, solicita-se o reencaminhamento do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong> para realização do levantamento.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
