"""Memos à DISA, um por caso da comparação base DISA x MANTIS (rede
própria), decidida pelo processo inteiro (alguém usou):

- base DISA sim, MANTIS sim: validar os atendimentos do MANTIS e complementar
  com os dados da DISA (MemoDisaValidarConsta);
- base DISA não, MANTIS sim: validar, informando que não consta na planilha
  (MemoDisaValidarNaoConsta);
- base DISA sim, MANTIS não: sem atendimento no MANTIS, solicita o
  relatório com os dados da DISA (MemoDisaSemMantisSolicitaRelatorio).

Os relatórios do MANTIS (PDF) de quem usou são anexados antes.
"""

import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import (
    REFERENCIA_PLANILHA_REDE_PROPRIA,
    UsoRedeBeneficiarios,
)

# TODO: revisar os textos (rascunhos adaptados do memo DISA anterior) e
# trocar para True
TEXTO_DEFINIDO = False

# Não altere os assuntos depois de criar memos: é por eles que o script os
# encontra na árvore. Nenhum pode conter outro, e todos são diferentes do
# assunto do memo DISA da versão anterior ("Levantamento de atendimentos da
# rede própria..."), que está nos processos VELHOS.
# TODO: confirmar os assuntos antes de criar o primeiro memo
ASSUNTO_MEMO_DISA_VALIDAR_CONSTA = 'Validação e complementação de atendimentos da rede própria - utilização indevida da assistência à saúde'
ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA = 'Validação de atendimentos da rede própria - utilização indevida da assistência à saúde'
ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO = 'Relatório de atendimentos da rede própria - utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA = re.compile(re.escape(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA), flags=re.IGNORECASE)
PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA = re.compile(re.escape(ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA), flags=re.IGNORECASE)
PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO = re.compile(re.escape(ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO), flags=re.IGNORECASE)

_CLASSE_PARAGRAFO = 'Texto_Justificado_Recuo_Primeira_Linha'
_COMPETENCIA_DISA = 'Solicita-se à Diretoria de Saúde - DISA, no âmbito de suas competências institucionais previstas nos arts. 68 e 73 do Decreto Estadual nº 48.823, de 16 de maio de 2024,'
_CAMPOS_LEVANTAMENTO = '<strong>identificação do beneficiário, data do atendimento, natureza do atendimento, procedimentos realizados e respectivos valores</strong>, observadas as regras de faturamento aplicáveis e a tabela da rede própria vigente à época da realização'


def _p(conteudo: str) -> str:
    return f'<p class="{_CLASSE_PARAGRAFO}">{conteudo}</p>'


def _situacao_disa(usou: bool) -> str:
    return 'consta' if usou else 'NÃO consta'


def _beneficiarios(titular: str | None, dependentes: tuple[str, ...], situacao) -> str:
    """Um parágrafo por beneficiário: "TITULAR: matrícula 123 (<situação>)"."""
    itens = [f'TITULAR: matrícula {titular}{situacao(titular, True)}'] if titular else []
    itens += [f'DEPENDENTE: matrícula {m}{situacao(m, False)}' for m in dependentes]
    return ''.join(_p(i) for i in itens)


def _usos_mantis(uso_disa: UsoRedeBeneficiarios, tit_usou_mantis: bool, deps_que_usaram_mantis: tuple[str, ...]) -> str:
    """Beneficiários com atendimento na rede própria do MANTIS, com a
    situação de cada um na base DISA."""

    def situacao(matricula: str, titular: bool) -> str:
        usou = uso_disa.tit_usou if titular else matricula in uso_disa.deps_que_usaram
        return f' ({_situacao_disa(usou)} na planilha)'

    return _beneficiarios(uso_disa.matricula_titular if tit_usou_mantis else None, deps_que_usaram_mantis, situacao)


def _usos_so_disa(uso_disa: UsoRedeBeneficiarios, tit_usou_mantis: bool, deps_que_usaram_mantis: tuple[str, ...]) -> str:
    """Beneficiários atendidos segundo a base DISA, sem atendimento na rede
    própria do MANTIS no período."""
    titular = uso_disa.matricula_titular if uso_disa.tit_usou and not tit_usou_mantis else None
    dependentes = tuple(m for m in uso_disa.deps_que_usaram if m not in deps_que_usaram_mantis)
    return _beneficiarios(titular, dependentes, lambda matricula, titular: '')


def _par_levantamento_complementar():
    return f'Solicita-se, ainda, caso existam atendimentos não relacionados nos relatórios, o respectivo levantamento, contemplando, no mínimo, a {_CAMPOS_LEVANTAMENTO}.'


def _par_padronizacao():
    return 'Para subsidiar a padronização do retorno, poderão ser observados, no que couber, os campos dos modelos de relatório encaminhados por meio do Memorando IPSEMG/GEACS nº 96/2026. O retorno deverá conter os elementos necessários à posterior consolidação, pela GEACS, das informações da rede própria com aquelas referentes à rede contratada e à coparticipação, para composição do demonstrativo final por beneficiário.'


def _par_lgpd():
    return 'O tratamento e o compartilhamento das informações deverão observar os princípios e as disposições da Lei nº 13.709, de 14 de agosto de 2018 - Lei Geral de Proteção de Dados Pessoais - LGPD, especialmente quanto à finalidade, à necessidade e à segurança dos dados.'


def _par_retorno():
    return 'Após o atendimento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para continuidade da apuração.'


def _fecho() -> list[str]:
    return ['', '', '', 'Atenciosamente,']


class _MemoDisa(Memorando):
    def __init__(self, *, assunto: str, paragrafos: list[str], memo_apis: DocArvore, nome_signatario: str, cargo_signatario: str):
        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto=assunto,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[*paragrafos, _par_padronizacao(), _par_lgpd(), _par_retorno(), *_fecho()],
        )
        self.memo_apis = memo_apis


class MemoDisaValidarConsta(_MemoDisa):
    """Base DISA sim e MANTIS sim: validar os atendimentos dos relatórios do
    MANTIS e complementar com os dados da DISA (inclusive de quem consta na
    planilha sem atendimento no MANTIS)."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not (tit_usou_mantis or deps_que_usaram_mantis) or not uso_disa.alguem_usou:
            raise ValueError('Memorando DISA (validar e complementar) exige atendimento na base DISA e no MANTIS')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (validar e complementar)')

        paragrafos = [
            f'{_COMPETENCIA_DISA} a <strong>validação dos atendimentos realizados na Rede Própria</strong> pelos beneficiários indicados abaixo, no período de apuração informado, conforme os relatórios de utilização extraídos do sistema MANTIS e anexados a este processo, e a <strong>complementação com os dados de atendimento registrados por essa Diretoria</strong>.',
            dados.texto_levantamento_html(),
            f'Os relatórios anexos indicam atendimentos na Rede Própria dos beneficiários abaixo. Para cada um, indica-se se consta como atendido na {REFERENCIA_PLANILHA_REDE_PROPRIA}:',
            _usos_mantis(uso_disa, tit_usou_mantis, deps_que_usaram_mantis),
        ]
        so_disa = _usos_so_disa(uso_disa, tit_usou_mantis, deps_que_usaram_mantis)
        if so_disa:
            paragrafos += [
                'Constam ainda como atendidos na referida planilha, sem atendimentos no sistema MANTIS no período, os beneficiários abaixo:',
                so_disa,
            ]
        paragrafos.append(
            f'Solicita-se a confirmação dos atendimentos relacionados nos relatórios e a complementação com os atendimentos registrados por essa Diretoria e neles não relacionados, contemplando, no mínimo, a {_CAMPOS_LEVANTAMENTO}.'
        )
        super().__init__(assunto=ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, paragrafos=paragrafos, memo_apis=memo_apis, nome_signatario=nome_signatario, cargo_signatario=cargo_signatario)


class MemoDisaValidarNaoConsta(_MemoDisa):
    """Base DISA não e MANTIS sim: validar os atendimentos dos relatórios do
    MANTIS, informando que os beneficiários não constam na planilha."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not (tit_usou_mantis or deps_que_usaram_mantis) or uso_disa.alguem_usou:
            raise ValueError('Memorando DISA (validar, não consta) exige atendimento no MANTIS e nenhum na base DISA')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (validar, não consta na base DISA)')

        paragrafos = [
            f'{_COMPETENCIA_DISA} a <strong>validação dos atendimentos realizados na Rede Própria</strong> pelos beneficiários indicados abaixo, no período de apuração informado, conforme os relatórios de utilização extraídos do sistema MANTIS e anexados a este processo.',
            dados.texto_levantamento_html(),
            f'Os relatórios anexos indicam atendimentos na Rede Própria dos beneficiários abaixo, embora <strong>não constem como atendidos</strong> na {REFERENCIA_PLANILHA_REDE_PROPRIA}:',
            _beneficiarios(uso_disa.matricula_titular if tit_usou_mantis else None, deps_que_usaram_mantis, lambda matricula, titular: ''),
            'Solicita-se a confirmação dos atendimentos relacionados nos relatórios.',
            _par_levantamento_complementar(),
        ]
        super().__init__(assunto=ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA, paragrafos=paragrafos, memo_apis=memo_apis, nome_signatario=nome_signatario, cargo_signatario=cargo_signatario)


class MemoDisaSemMantisSolicitaRelatorio(_MemoDisa):
    """Base DISA sim e MANTIS não: relatório dos atendimentos registrados
    pela DISA (não há relatório do MANTIS para anexar)."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if tit_usou_mantis or deps_que_usaram_mantis or not uso_disa.alguem_usou:
            raise ValueError('Memorando DISA (sem MANTIS, solicita relatório) exige atendimento na base DISA e nenhum no MANTIS')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (sem MANTIS, solicita relatório)')

        paragrafos = [
            f'{_COMPETENCIA_DISA} o <strong>relatório dos atendimentos realizados na Rede Própria</strong> pelos beneficiários indicados abaixo, no período de apuração informado.',
            dados.texto_levantamento_html(),
            f'Os beneficiários abaixo constam como atendidos na {REFERENCIA_PLANILHA_REDE_PROPRIA}, mas não foram identificados atendimentos na Rede Própria no sistema MANTIS no período:',
            _usos_so_disa(uso_disa, tit_usou_mantis, deps_que_usaram_mantis),
            f'O relatório deverá contemplar, no mínimo, a {_CAMPOS_LEVANTAMENTO}.',
        ]
        super().__init__(assunto=ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO, paragrafos=paragrafos, memo_apis=memo_apis, nome_signatario=nome_signatario, cargo_signatario=cargo_signatario)
