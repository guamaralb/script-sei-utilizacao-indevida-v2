import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import (
    REFERENCIA_PLANILHA_REDE_PROPRIA,
    UsoRedeBeneficiarios,
)

# TODO: revisar o texto (rascunho adaptado do memo DISA anterior) e trocar
# para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore. É diferente do assunto do memo DISA anterior
# ("Levantamento de atendimentos da rede própria..."), que continua nos
# processos VELHOS.
ASSUNTO_MEMO_DISA = 'Validação de atendimentos da rede própria - utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_DISA = re.compile(re.escape(ASSUNTO_MEMO_DISA), flags=re.IGNORECASE)

_CLASSE_PARAGRAFO = 'Texto_Justificado_Recuo_Primeira_Linha'


def _p(conteudo: str) -> str:
    return f'<p class="{_CLASSE_PARAGRAFO}">{conteudo}</p>'


def _situacao_disa(usou: bool) -> str:
    return 'consta' if usou else 'NÃO consta'


def _par_1():
    return 'Solicita-se à Diretoria de Saúde - DISA, no âmbito de suas competências institucionais previstas nos arts. 68 e 73 do Decreto Estadual nº 48.823, de 16 de maio de 2024, a <strong>validação dos atendimentos realizados na Rede Própria</strong> pelos beneficiários indicados abaixo, no período de apuração informado, conforme os relatórios de utilização extraídos do sistema MANTIS e anexados a este processo.'


def _par_2(dados: DadosUI):
    return dados.texto_levantamento_html()


def _par_intro_uso():
    return f'Os relatórios anexos indicam atendimentos na Rede Própria dos beneficiários abaixo. Para cada um, indica-se se consta como atendido na {REFERENCIA_PLANILHA_REDE_PROPRIA}:'


def _par_situacao(uso_disa: UsoRedeBeneficiarios, tit_usou_mantis: bool, deps_que_usaram_mantis: tuple[str, ...]):
    itens = []
    if tit_usou_mantis:
        itens.append(f'TITULAR: matrícula {uso_disa.matricula_titular} ({_situacao_disa(uso_disa.tit_usou)} na planilha)')
    itens += [f'DEPENDENTE: matrícula {m} ({_situacao_disa(m in uso_disa.deps_que_usaram)} na planilha)' for m in deps_que_usaram_mantis]
    return ''.join(_p(i) for i in itens)


def _par_3():
    return 'Solicita-se a confirmação dos atendimentos relacionados nos relatórios e, caso existam atendimentos neles não relacionados, o respectivo levantamento, contemplando, no mínimo, a <strong>identificação do beneficiário, data do atendimento, natureza do atendimento, procedimentos realizados e respectivos valores</strong>, observadas as regras de faturamento aplicáveis e a tabela da rede própria vigente à época da realização.'


def _par_4():
    return 'Para subsidiar a padronização do retorno, poderão ser observados, no que couber, os campos dos modelos de relatório encaminhados por meio do Memorando IPSEMG/GEACS nº 96/2026. O retorno deverá conter os elementos necessários à posterior consolidação, pela GEACS, das informações da rede própria com aquelas referentes à rede contratada e à coparticipação, para composição do demonstrativo final por beneficiário.'


def _par_5():
    return 'O tratamento e o compartilhamento das informações deverão observar os princípios e as disposições da Lei nº 13.709, de 14 de agosto de 2018 - Lei Geral de Proteção de Dados Pessoais - LGPD, especialmente quanto à finalidade, à necessidade e à segurança dos dados.'


def _par_6():
    return 'Após a validação, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para continuidade da apuração.'


def _par_7():
    return 'Atenciosamente,'


class MemoDisa(Memorando):
    """Memo à DISA para validar os atendimentos da rede própria do MANTIS
    (relatórios em PDF anexados antes do memo). Só deve existir se alguém
    tem atendimento na rede própria do MANTIS, esteja ou não na base
    DISA."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not (tit_usou_mantis or deps_que_usaram_mantis):
            raise ValueError('Memorando DISA criado sem beneficiários com atendimento na Rede Própria do MANTIS')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (validar atendimentos da rede própria)')

        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto=ASSUNTO_MEMO_DISA,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_1(),
                _par_2(dados),
                _par_intro_uso(),
                _par_situacao(uso_disa, tit_usou_mantis, deps_que_usaram_mantis),
                _par_3(),
                _par_4(),
                _par_5(),
                _par_6(),
                '',
                '',
                '',
                _par_7(),
            ],
        )
