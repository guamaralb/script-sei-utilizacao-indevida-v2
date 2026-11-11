import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, citar_documentos

# Não altere os assuntos: é por eles que o script encontra memos já criados
ASSUNTO_MEMO_DEPROC = 'Levantamento de coparticipação – utilização indevida da assistência à saúde na rede credenciada'
ASSUNTO_MEMO_DEPROC_DUAS_REDES = 'Levantamento de coparticipação – utilização indevida da assistência à saúde nas redes credenciada e própria'

# Início comum aos dois assuntos. Aceita também o assunto anterior
# ("Levantamento de coparticipação - utilização indevida da assistência à
# saúde"), dos memos já criados
PADRAO_ASSUNTO_MEMO_DEPROC = re.compile(r'Levantamento de coparticipação\s*[-–]\s*utilização indevida da assistência à saúde', flags=re.IGNORECASE)


def _par_rede_credenciada(docs_relatorio_rc: tuple[str, ...]) -> str:
    return f'<strong>Rede credenciada:</strong> relatórios de utilização extraídos do SADS, constantes {citar_documentos(docs_relatorio_rc, "do", "dos")}.'


def _par_rede_propria(doc_relatorio_disa: str, doc_manifestacao_disa: str) -> str:
    return f'<strong>Rede própria:</strong> relatório de atendimentos e respectivos valores apresentado ou validado pela DISA, constante do documento {doc_relatorio_disa}, conforme manifestação no documento {doc_manifestacao_disa}.'


class MemoDeproc(Memorando):
    """Memo à DEPROC, sempre com todos os beneficiários. Os relatórios da
    rede credenciada são anexados antes e citados pelo número SEI.

    Com doc_relatorio_disa e doc_manifestacao_disa, o levantamento abrange as
    duas redes. Sem eles (sem uso da rede própria na base DISA e no SADS), só
    a credenciada."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        docs_relatorio_rc: tuple[str, ...],
        memo_apis: DocArvore,
        nome_signatario: str,
        cargo_signatario: str,
        doc_relatorio_disa: str | None = None,
        doc_manifestacao_disa: str | None = None,
    ):
        if not docs_relatorio_rc:
            raise ValueError('Memorando DEPROC exige o número SEI dos relatórios da rede credenciada')
        if bool(doc_relatorio_disa) != bool(doc_manifestacao_disa):
            raise ValueError('Memorando DEPROC exige o relatório e a manifestação da DISA juntos')

        duas_redes = bool(doc_relatorio_disa)
        atendimentos = 'nas redes credenciada e própria' if duas_redes else 'na rede credenciada'
        contemplar = 'de ambas as redes' if duas_redes else 'da rede credenciada'
        super().__init__(
            destinatario_nome='IPSEMG/DEPROC-Utilização',
            assunto=ASSUNTO_MEMO_DEPROC_DUAS_REDES if duas_redes else ASSUNTO_MEMO_DEPROC,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'Solicita-se ao Departamento de Processamento de Contas e Coparticipação – DEPROC, no âmbito de suas competências institucionais previstas no art. 66 do Decreto Estadual nº 48.823, de 16 de maio de 2024, o levantamento dos <strong>valores de coparticipação</strong> referentes aos atendimentos efetivamente realizados {atendimentos} pelo titular e seus dependentes abaixo indicados, nos respectivos períodos informados pela Assessoria de Políticas e Informações em Saúde – APIS:',
                dados.texto_levantamento_html() + dados.periodo_dependentes_html(),
                'Para subsidiar a apuração, constam deste processo:',
                _par_rede_credenciada(docs_relatorio_rc),
                *([_par_rede_propria(doc_relatorio_disa, doc_manifestacao_disa)] if duas_redes else []),
                f'Solicita-se que o levantamento contemple os atendimentos {contemplar}, com os valores de coparticipação individualizados por beneficiário e atendimento, de modo a permitir sua incorporação ao demonstrativo consolidado a ser encaminhado à APIS.',
                'Caso não sejam identificados valores de coparticipação no período, solicita-se o registro dessa informação no processo.',
                'Após o levantamento, solicita-se o retorno do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
