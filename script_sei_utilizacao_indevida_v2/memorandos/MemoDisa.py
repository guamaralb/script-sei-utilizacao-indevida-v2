from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisaUsoRede import (
    REFERENCIA_PLANILHA_REDE_PROPRIA,
    UsoRedeBeneficiarios,
)


def _par_1():
    return 'Solicita-se à Diretoria de Saúde - DISA, no âmbito de suas competências institucionais previstas nos arts. 68 e 73 do Decreto Estadual nº 48.823, de 16 de maio de 2024, e conforme fluxo de apuração formalizado nos Memorandos IPSEMG/APIS-UTILIZAÇÃO nº. 467/2026 (142545421) e nº 468/2026 (142545891), o levantamento dos valores de utilização indevida da assistência à saúde referentes aos <strong>beneficiários que utilizaram a Rede Própria</strong>, indicados abaixo, na forma e nas etapas ali definidas, abrangendo <strong>os atendimentos de internação e de pronto atendimento realizados na Rede Própria</strong>, no período de apuração informado.'


def _par_2(dados: DadosUI):
    return dados.texto_levantamento_html()


def _par_intro_uso():
    return f'Conforme a {REFERENCIA_PLANILHA_REDE_PROPRIA}, verificou-se a seguinte situação quanto ao uso da Rede Própria:'


def _par_situacao_uso(uso: UsoRedeBeneficiarios):
    return uso.situacao_uso_html()


def _par_3():
    return 'Não sendo identificado atendimento dessa natureza, solicita-se que essa informação seja registrada no processo para prosseguimento da apuração pela GEACS.'


def _par_4():
    return 'Caso sejam identificados atendimentos, solicita-se o levantamento e a apuração das respectivas contas, contemplando, no mínimo, a <strong>identificação do beneficiário, data do atendimento, natureza do atendimento, procedimentos realizados e respectivos valores</strong>, observadas as regras de faturamento aplicáveis e a tabela da rede própria vigente à época da realização.'


def _par_5():
    return 'Para subsidiar a padronização do retorno, poderão ser observados, no que couber, os campos dos modelos de relatório encaminhados por meio do Memorando IPSEMG/GEACS nº 96/2026. O retorno deverá conter os elementos necessários à posterior consolidação, pela GEACS, das informações da rede própria com aquelas referentes à rede contratada e à coparticipação, para composição do demonstrativo final por beneficiário.'


def _par_6():
    return 'O tratamento e o compartilhamento das informações deverão observar os princípios e as disposições da Lei nº 13.709, de 14 de agosto de 2018 - Lei Geral de Proteção de Dados Pessoais - LGPD, especialmente quanto à finalidade, à necessidade e à segurança dos dados.'


def _par_7():
    return 'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para continuidade da apuração.'


def _par_8():
    return 'Atenciosamente,'


class MemoDisa(Memorando):
    """Memo do fluxo normal. Só deve existir se alguém usou a rede
    própria."""

    def __init__(
        self,
        dados: DadosUI,
        uso: UsoRedeBeneficiarios,
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not uso.alguem_usou:
            raise ValueError('Memorando DISA criado sem beneficiários que utilizaram a Rede Própria')

        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto='Levantamento de atendimentos da rede própria - utilização indevida da assistência à saúde',
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                _par_1(),
                _par_2(dados),
                _par_intro_uso(),
                _par_situacao_uso(uso),
                _par_3(),
                _par_4(),
                _par_5(),
                _par_6(),
                _par_7(),
                '',
                '',
                '',
                _par_8(),
            ],
        )
