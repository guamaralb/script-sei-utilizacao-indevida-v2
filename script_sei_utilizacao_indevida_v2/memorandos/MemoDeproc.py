from memorandos.DadosProcesso import DadosProcesso
from sei_automacao.classes.Memorando import Memorando


def _par_1():
    return 'No âmbito do fluxo de apuração dos valores referentes à utilização indevida da assistência à saúde, formalizado no Processo SEI nº <strong>2010.01.0058549/2026-56,</strong>, encaminha-se o presente processo para levantamento dos <strong>valores de coparticipação</strong> referentes ao titular e aos dependentes abaixo indicados, nos respectivos períodos informados pela Assessoria de Políticas e Informações em Saúde - APIS:'


def _par_2(
    nome_titular,
    matricula_titular,
    periodo_titular,
    matriculas_dependentes,
    periodo_dependentes=None,
):

    if isinstance(matriculas_dependentes, (list, tuple)):
        dependentes_str = '; '.join(str(m) for m in matriculas_dependentes)
    else:
        dependentes_str = str(matriculas_dependentes)

    if periodo_dependentes:
        periodo_dep_html = f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração dos dependentes:</strong> {periodo_dependentes}</p>'
    else:
        periodo_dep_html = (
            '<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração dos dependentes:</strong></p>'
            '<p class="Texto_Justificado_Recuo_Primeira_Linha">[informar, quando houver período específico distinto]</p>'
        )

    return (
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Nome do titular:</strong> {nome_titular}</p>'
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrícula:</strong> {matricula_titular}</p>'
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Período de apuração do titular:</strong> {periodo_titular}</p>'
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>Matrículas dos dependentes:</strong> {dependentes_str}</p>'
        + periodo_dep_html
    )


def _par_3():
    return 'Solicita-se a consolidação dos valores de coparticipação identificados para cada beneficiário no período correspondente, de forma a subsidiar a composição do demonstrativo final solicitado pela APIS.'


def _par_4():
    return 'Caso não sejam identificados valores de coparticipação no período, solicita-se o registro dessa informação no processo.'


def _par_5():
    return 'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.'


def _par_6():
    return 'Atenciosamente'


class MemoDeproc(Memorando):
    def __init__(
        self, dados: DadosProcesso, nome_signatario: str, cargo_signatario: str
    ):
        super().__init__(
            destinatario_nome='IPSEMG/DEPROC',
            assunto='Levantamento de coparticipação - utilização indevida da assistência à saúde',
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_1(),
                _par_2(
                    dados.nome_titular,
                    dados.matricula_titular,
                    dados.periodo_titular,
                    dados.matriculas_dependentes,
                    dados.periodo_dependentes,
                ),
                _par_3(),
                _par_4(),
                _par_5(),
                _par_6(),
            ],
        )
