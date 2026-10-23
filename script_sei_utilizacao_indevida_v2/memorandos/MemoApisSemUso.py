import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import REFERENCIA_PLANILHA_REDE_PROPRIA

# TODO: revisar o texto (rascunho) e trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore.
# TODO: confirmar o assunto antes de criar o primeiro memo
ASSUNTO_MEMO_APIS_SEM_USO = 'Ausência de utilização da assistência à saúde - utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_APIS_SEM_USO = re.compile(re.escape(ASSUNTO_MEMO_APIS_SEM_USO), flags=re.IGNORECASE)


def _par_1():
    return 'Em atenção ao memorando dessa Assessoria, informa-se que, para os beneficiários abaixo indicados, <strong>não foram identificados atendimentos</strong> no período de apuração informado em nenhuma das bases consultadas por esta Gerência:'


def _par_bases():
    return (
        f'<strong>Rede Própria:</strong> os beneficiários não constam como atendidos na {REFERENCIA_PLANILHA_REDE_PROPRIA}, '
        'e não há registros de atendimento na Rede Própria no sistema MANTIS; '
        '<strong>Rede Credenciada:</strong> não há registros de atendimento no sistema MANTIS.'
    )


def _par_retorno():
    return 'Dessa forma, retorna-se o processo a essa Assessoria para ciência e providências que entender cabíveis.'


class MemoApisSemUso(Memorando):
    """Memo à APIS-Utilização: nenhum uso em nenhuma base (base DISA,
    MANTIS rede própria e MANTIS rede credenciada). Substitui o memo DEPROC:
    não há coparticipação a levantar."""

    def __init__(self, *, dados: DadosUI, nome_signatario: str, cargo_signatario: str):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (nenhum uso nas bases)')
        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_APIS_SEM_USO,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_1(),
                dados.texto_levantamento_html(),
                _par_bases(),
                _par_retorno(),
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
