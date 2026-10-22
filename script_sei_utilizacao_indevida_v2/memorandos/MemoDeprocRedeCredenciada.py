import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import par_rede_credenciada
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: revisar o texto (rascunho) e trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore. Precisa ser diferente do assunto do MemoDeproc, que
# já está nos processos VELHOS.
ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA = 'Relatório de utilização da rede credenciada - utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA = re.compile(re.escape(ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA), flags=re.IGNORECASE)


def _par_1():
    return 'Em complemento ao memorando desta Gerência anteriormente encaminhado a esse Departamento de Processamento de Contas e Coparticipação - Deproc, referente ao levantamento dos <strong>valores de coparticipação</strong> do titular e dos dependentes abaixo indicados, informa-se:'


def _par_3():
    return 'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.'


class MemoDeprocRedeCredenciada(Memorando):
    """Memo do processo VELHO (enviado à DISA e à DEPROC antes da
    avaliação), quando ninguém tem uso da rede própria: encaminha à DEPROC
    os relatórios da rede credenciada, sem repetir o pedido de
    coparticipação."""

    def __init__(self, dados: DadosUI, usou_rede_credenciada: bool, nome_signatario: str, cargo_signatario: str):
        verificar_texto_definido(TEXTO_DEFINIDO, 'DEPROC (rede credenciada, processo VELHO)')
        super().__init__(
            destinatario_nome='IPSEMG/DEPROC',
            assunto=ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_1(),
                dados.texto_levantamento_html(),
                par_rede_credenciada(usou_rede_credenciada),
                _par_3(),
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
