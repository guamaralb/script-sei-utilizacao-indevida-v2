"""Memos à DISA, um por caso da comparação base DISA x MANTIS (rede
própria), decidida pelo processo inteiro (alguém usou):

- base DISA sim, MANTIS sim: validar os atendimentos dos relatórios e
  complementar com os dados da DISA (MemoDisaValidarConsta);
- base DISA não, MANTIS sim: validar os atendimentos dos relatórios, que
  não constam na planilha (MemoDisaValidarNaoConsta);
- base DISA sim, MANTIS não: sem relatório, solicita o levantamento à DISA
  (MemoDisaSemMantisSolicitaRelatorio).

Os relatórios do MANTIS (PDF) de quem usou são anexados antes, e os da
rede própria são citados pelo número SEI (docs_relatorio_rp).
"""

import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, citar_documentos, identificar_doc
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido
from script_sei_utilizacao_indevida_v2.memorandos.UsoRede import UsoRedeBeneficiarios

TEXTO_DEFINIDO = True

# Não altere os assuntos depois de criar memos: é por eles que o script os
# encontra na árvore. Nenhum pode conter outro, e todos são diferentes do
# assunto do memo DISA da versão anterior ("Levantamento de atendimentos da
# rede própria..."), que está nos processos VELHOS.
ASSUNTO_MEMO_DISA_VALIDAR_CONSTA = 'Validação e complementação do levantamento de atendimentos da rede própria'
ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA = 'Validação de atendimentos da rede própria identificados pela GEACS'
ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO = 'Solicitação de levantamento dos atendimentos e valores da rede própria'

PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA = re.compile(re.escape(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA), flags=re.IGNORECASE)
PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA = re.compile(re.escape(ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA), flags=re.IGNORECASE)
PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO = re.compile(re.escape(ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO), flags=re.IGNORECASE)


def _memo_apis(memo_apis: DocArvore) -> str:
    return f'<strong>{identificar_doc(memo_apis)}</strong>'


def _par_abertura_validar(memo_apis: DocArvore) -> str:
    return (
        f'Em atendimento à solicitação constante do {_memo_apis(memo_apis)}, encaminhamos o processo para '
        '<strong>validação do levantamento dos atendimentos da rede própria e respectivos valores</strong>, referente aos seguintes beneficiários e períodos:'
    )


def _par_registros_nao_consta(docs: tuple[str, ...]) -> str:
    return (
        'Embora a Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791) não indique atendimento para as matrículas relacionadas, '
        f'a GEACS identificou registros de faturamento nas remessas exportadas ao SADS, consolidados <strong>{citar_documentos(docs, "no", "nos")}</strong>.'
    )


def _par_validacao_nao_consta(docs: tuple[str, ...]) -> str:
    return (
        'Solicita-se a <strong>validação dos atendimentos e valores apresentados e a verificação da existência de outros atendimentos nos períodos indicados</strong>. '
        'Caso o relatório seja confirmado integralmente e não haja outros atendimentos a acrescentar, solicita-se manifestação expressa de que poderá ser utilizado na consolidação do retorno à APIS. '
        'Se identificadas inconsistências ou atendimentos adicionais, solicita-se o envio de '
        f'<strong>novo relatório consolidado com a relação completa dos atendimentos e valores validados, em substituição {citar_documentos(docs, "ao", "aos")}</strong>, evitando duplicidades.'
    )


def _par_abertura_levantamento(memo_apis: DocArvore) -> str:
    return (
        f'Em atendimento à solicitação constante do {_memo_apis(memo_apis)}, encaminhamos o processo para '
        '<strong>levantamento dos atendimentos realizados na rede própria e dos respectivos valores</strong>, referente aos seguintes beneficiários e períodos:'
    )


def _par_registros_consta(docs: tuple[str, ...]) -> str:
    return (
        f'A Gerência de Auditoria e Contas da Saúde - GEACS identificou registros de faturamento da rede própria nas remessas exportadas ao SADS, consolidados <strong>{citar_documentos(docs, "no", "nos")}</strong>. '
        'Esses registros podem corresponder à totalidade dos atendimentos identificados por essa Diretoria ou representar apenas parte deles, sendo necessária a verificação de outros atendimentos, '
        '<strong>especialmente internações e atendimentos no Serviço Médico de Urgência - SMU do Hospital Governador Israel Pinheiro - HGIP</strong>, '
        'conforme detalhado no processo <strong>2010.01.0058549/2026-56</strong>.'
    )


def _par_validacao_consta(docs: tuple[str, ...]) -> str:
    return f'Assim, solicita-se a <strong>validação dos atendimentos e respectivos valores constantes {citar_documentos(docs, "do", "dos")} e a verificação da existência de outros atendimentos nos períodos solicitados</strong>.'


def _par_novo_relatorio_consta(docs: tuple[str, ...]) -> str:
    return (
        'Caso o relatório seja confirmado integralmente e não haja outros atendimentos a acrescentar, solicita-se manifestação expressa de que poderá ser utilizado na consolidação do retorno à APIS. '
        'Se identificadas inconsistências ou atendimentos adicionais, solicita-se o envio de '
        '<strong>novo relatório consolidado com a relação completa de todos os atendimentos e valores validados, incluindo os registros da GEACS confirmados e os demais identificados pela DISA, '
        f'em substituição {citar_documentos(docs, "ao", "aos")}</strong>, evitando duplicidades.'
    )


def _par_orientacoes_consta(memo_apis: DocArvore) -> str:
    return (
        f'Para o retorno, solicita-se observar as orientações de consolidação constantes do {_memo_apis(memo_apis)}, '
        'bem como aquelas tratadas no processo <strong>2010.01.0058549/2026-56</strong>, '
        'utilizando como referência os modelos encaminhados pelo <strong>Memorando IPSEMG/GEACS nº 96/2026 (143947926)</strong>.'
    )


class _MemoDisa(Memorando):
    def __init__(self, *, assunto: str, paragrafos: list[str], memo_apis: DocArvore, nome_signatario: str, cargo_signatario: str):
        super().__init__(
            # Duas linhas: <br>, pois o texto entra no HTML do memo (um \n vira espaço)
            destinatario_nome='Felippe Gonçalves Declie Fagioli<br>Diretor de Saúde - DISA',
            assunto=assunto,
            vocativo='Prezado Diretor',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[*paragrafos, '', '', '', 'Atenciosamente,'],
        )
        self.memo_apis = memo_apis


class MemoDisaValidarConsta(_MemoDisa):
    """Base DISA sim e MANTIS sim: validar os atendimentos dos relatórios do
    MANTIS e verificar outros atendimentos registrados pela DISA
    (especialmente internações e SMU do HGIP)."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        docs_relatorio_rp: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not (tit_usou_mantis or deps_que_usaram_mantis) or not uso_disa.alguem_usou:
            raise ValueError('Memorando DISA (validar e complementar) exige atendimento na base DISA e no MANTIS')
        if not docs_relatorio_rp:
            raise ValueError('Memorando DISA (validar e complementar) exige o número SEI dos relatórios da rede própria')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (validar e complementar)')

        super().__init__(
            assunto=ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
            paragrafos=[
                'Em atendimento à solicitação da Assessoria de Políticas e Informações em Saúde - APIS constante deste processo, e considerando a identificação de utilização na Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791), encaminhamos o processo para <strong>validação e eventual complementação do levantamento dos atendimentos da rede própria e respectivos valores</strong>, referente aos seguintes beneficiários e períodos:',
                '',
                dados.texto_levantamento_html(),
                '',
                _par_registros_consta(docs_relatorio_rp),
                _par_validacao_consta(docs_relatorio_rp),
                _par_novo_relatorio_consta(docs_relatorio_rp),
                _par_orientacoes_consta(memo_apis),
                'Após a análise, solicita-se a devolução do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong> para posterior apuração da coparticipação pelo Departamento de Processamento de Contas e Coparticipação - DEPROC.',
            ],
            memo_apis=memo_apis,
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
        )


class MemoDisaValidarNaoConsta(_MemoDisa):
    """Base DISA não e MANTIS sim: validar os atendimentos dos relatórios do
    MANTIS, que não constam na planilha, e verificar outros atendimentos."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        uso_disa: UsoRedeBeneficiarios,
        tit_usou_mantis: bool,
        deps_que_usaram_mantis: tuple[str, ...],
        docs_relatorio_rp: tuple[str, ...],
        nome_signatario: str,
        cargo_signatario: str,
    ):
        if not (tit_usou_mantis or deps_que_usaram_mantis) or uso_disa.alguem_usou:
            raise ValueError('Memorando DISA (validar, não consta) exige atendimento no MANTIS e nenhum na base DISA')
        if not docs_relatorio_rp:
            raise ValueError('Memorando DISA (validar, não consta) exige o número SEI dos relatórios da rede própria')
        verificar_texto_definido(TEXTO_DEFINIDO, 'DISA (validar, não consta na base DISA)')

        super().__init__(
            assunto=ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
            paragrafos=[
                _par_abertura_validar(memo_apis),
                '',
                dados.texto_levantamento_html(),
                _par_registros_nao_consta(docs_relatorio_rp),
                _par_validacao_nao_consta(docs_relatorio_rp),
                'Para o retorno, solicita-se observar as orientações de consolidação constantes do memorando da APIS acima identificado, bem como aquelas tratadas no processo <strong>2010.01.0058549/2026-56</strong>, utilizando como referência os modelos encaminhados pelo <strong>Memorando IPSEMG/GEACS nº 96/2026 (143947926)</strong>.',
                'Após a análise, solicita-se a devolução do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong> para consolidação dos atendimentos e posterior apuração da coparticipação pelo Departamento de Processamento de Contas e Coparticipação - DEPROC.',
            ],
            memo_apis=memo_apis,
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
        )


class MemoDisaSemMantisSolicitaRelatorio(_MemoDisa):
    """Base DISA sim e MANTIS não: sem registros no MANTIS, solicita o
    levantamento dos atendimentos e valores à DISA (não há relatório da
    rede própria para anexar)."""

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

        super().__init__(
            assunto=ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
            paragrafos=[
                _par_abertura_levantamento(memo_apis),
                '',
                dados.texto_levantamento_html(),
                '',
                'A Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791) indica utilização da rede própria, mas não foram identificados registros de faturamento correspondentes na base do SADS consultada pela GEACS.',
                'Assim, solicita-se a <strong>inclusão do relatório consolidado dos atendimentos e respectivos valores</strong>, observando as orientações constantes do memorando da APIS acima identificado, bem como aquelas tratadas no processo <strong>2010.01.0058549/2026-56</strong>, utilizando como referência os modelos encaminhados pelo <strong>Memorando IPSEMG/GEACS nº 96/2026 (143947926)</strong>. Caso não sejam identificados atendimentos nos períodos específicos solicitados, solicita-se registrar expressamente essa informação.',
                'Após a análise, solicita-se a devolução do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong> para consolidação dos atendimentos e posterior apuração da coparticipação pelo Departamento de Processamento de Contas e Coparticipação - DEPROC.',
            ],
            memo_apis=memo_apis,
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
        )
