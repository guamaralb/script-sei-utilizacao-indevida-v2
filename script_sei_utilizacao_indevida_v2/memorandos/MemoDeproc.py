import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore

# Não altere o assunto: é por ele que o script encontra memos já criados
ASSUNTO_MEMO_DEPROC = 'Levantamento de coparticipação - utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_DEPROC = re.compile(re.escape(ASSUNTO_MEMO_DEPROC), flags=re.IGNORECASE)


def _par_rede_credenciada(usou_rede_credenciada: bool) -> str:
    if usou_rede_credenciada:
        return 'Seguem anexos a este processo os relatórios de utilização da <strong>rede credenciada</strong> extraídos do sistema MANTIS, referentes ao período de apuração.'
    return 'Não foram identificados no sistema MANTIS atendimentos na <strong>rede credenciada</strong> no período de apuração.'


class MemoDeproc(Memorando):
    """Memo do processo sem uso da rede própria (base DISA e MANTIS): sempre
    com todos os beneficiários. Os relatórios da rede credenciada (se alguém
    usou) são anexados antes."""

    def __init__(self, dados: DadosUI, usou_rede_credenciada: bool, nome_signatario: str, cargo_signatario: str, *, memo_apis: DocArvore):
        super().__init__(
            destinatario_nome='IPSEMG/DEPROC',
            assunto=ASSUNTO_MEMO_DEPROC,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                'Solicita-se ao Departamento de Processamento de Contas e Coparticipação - Deproc, no âmbito de suas competências institucionais previstas no art. 66 do Decreto Estadual nº 48.823, de 16 de maio de 2024, o levantamento dos <strong>valores de coparticipação</strong> referentes aos atendimentos efetivamente realizados pelo titular e seus dependentes abaixo indicados, nos respectivos períodos informados pela Assessoria de Políticas e Informações em Saúde - APIS:',
                dados.texto_levantamento_html(),
                _par_rede_credenciada(usou_rede_credenciada),
                'Caso não sejam identificados valores de coparticipação no período, solicita-se o registro dessa informação no processo.',
                'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
