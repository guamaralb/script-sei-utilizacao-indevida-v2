import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto a partir do modelo Memorando 2019 (SEI 150646384) e
# trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = 'Inclusão de solicitação de levantamento direcionada à GEACS'

# O script procura o memo por este padrão antes de criar (retomada)
PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = re.compile(re.escape(ASSUNTO_MEMO_APIS_FORMATO_INVALIDO), flags=re.IGNORECASE)


class MemoApisFormatoInvalido(Memorando):
    """Memo à APIS-Utilização: o memorando da APIS destinado à GEACS não
    está no modelo esperado."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, memo_apis_sei: str):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (formato inválido)')
        super().__init__(
            destinatario_nome=(
                'IPSEMG/APIS-Utilização'
                'Assessoria de Políticas e Informações em Saúde - APIS'
            ),
            assunto=ASSUNTO_MEMO_APIS_FORMATO_INVALIDO,
            vocativo='Prezada Assessora',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
    paragrafos=[
                'Retornamos o processo por não constar memorando direcionado à Gerência de Auditoria e Contas da Saúde - GEACS com a solicitação do levantamento a ser realizado.',
                '<strong>Caso a demanda esteja vinculada ao levantamento tratado no processo 2010.01.0058549/2026-56</strong>, solicita-se a inclusão de memorando de solicitação no modelo padronizado atualmente utilizado, contendo todos os dados necessários à apuração, especialmente a identificação do titular, as matrículas completas do titular e dos dependentes e os respectivos períodos de apuração, com datas de início e término.',
                'Para viabilizar a rotina de automatização, a demanda deverá estar integralmente apresentada nesse documento, <strong>não sendo suficiente o encaminhamento de despacho ou resposta a este memorando com informações parciais ou remissão a documentos anteriores</strong>.',
                'Após a inclusão, solicita-se o reencaminhamento do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>. Caso se trate de demanda diversa daquele levantamento, solicita-se sua formalização e encaminhamento à unidade <strong>IPSEMG/GEACS</strong>.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
