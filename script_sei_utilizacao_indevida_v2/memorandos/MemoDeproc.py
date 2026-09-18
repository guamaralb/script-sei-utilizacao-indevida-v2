from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


def _par_1():
    return 'Solicita-se ao Departamento de Processamento de Contas e Coparticipação - Deproc, no âmbito de suas competências institucionais previstas no art. 66 do Decreto Estadual nº 48.823, de 16 de maio de 2024, o levantamento dos <strong>valores de coparticipação</strong> referentes aos atendimentos efetivamente realizados pelo titular e seus dependentes abaixo indicados, nos respectivos períodos informados pela Assessoria de Políticas e Informações em Saúde - APIS:'


def _par_2(dados: DadosUI):
    return dados.texto_levantamento_html()


def _par_3():
    return 'Caso não sejam identificados valores de coparticipação no período, solicita-se o registro dessa informação no processo.'


def _par_4():
    return 'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.'


def _par_5():
    return 'Atenciosamente,'


class MemoDeproc(Memorando):
    def __init__(
        self, dados: DadosUI, nome_signatario: str, cargo_signatario: str
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
                _par_2(dados),
                _par_3(),
                _par_4(),
                '',
                '',
                '',
                _par_5(),
            ],
        )
