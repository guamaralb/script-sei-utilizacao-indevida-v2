import re
from dataclasses import dataclass

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, identificar_doc

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES = 'Retorno do levantamento de utilização da assistência à saúde e respectiva coparticipação'

PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES = re.compile(re.escape(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES), flags=re.IGNORECASE)

# Atributos da tabela criada pelo editor do SEI
_ATRIBUTOS_TABELA = 'border="1" cellpadding="4" style="border-collapse:collapse;margin-left:auto;margin-right:auto;width:500px;"'


@dataclass(frozen=True)
class ValoresBeneficiario:
    """Uma linha das tabelas: valores e demonstrativos do beneficiário."""

    identificacao: str
    valor_rede_credenciada: float
    valor_rede_propria: float
    coparticipacao: float
    doc_rede_credenciada: str | None = None
    doc_rede_propria: str | None = None

    @property
    def total(self) -> float:
        return self.valor_rede_credenciada + self.valor_rede_propria


def formatar_reais(valor: float) -> str:
    """formatar_reais(1234.5) -> 'R$ 1.234,50'."""
    return 'R$ ' + f'{valor:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def _linha(celulas: list[str], *, negrito: bool = False) -> str:
    conteudo = (f'<strong>{c}</strong>' if negrito else c for c in celulas)
    return f'<tr>{"".join(f"<td>{c}</td>" for c in conteudo)}</tr>'


def _tabela(cabecalho: list[str], linhas: list[list[str]], *, ultima_em_negrito: bool = False) -> str:
    corpo = ''.join(_linha(linha, negrito=ultima_em_negrito and i == len(linhas) - 1) for i, linha in enumerate(linhas))
    return f'<table {_ATRIBUTOS_TABELA}><tbody>{_linha(cabecalho, negrito=True)}{corpo}</tbody></table>'


def _tabela_valores(beneficiarios: tuple[ValoresBeneficiario, ...]) -> str:
    def _valores(b: ValoresBeneficiario) -> list[str]:
        return [formatar_reais(v) for v in (b.valor_rede_credenciada, b.valor_rede_propria, b.total, b.coparticipacao)]

    total = ValoresBeneficiario(
        identificacao='Total',
        valor_rede_credenciada=sum(b.valor_rede_credenciada for b in beneficiarios),
        valor_rede_propria=sum(b.valor_rede_propria for b in beneficiarios),
        coparticipacao=sum(b.coparticipacao for b in beneficiarios),
    )
    return _tabela(
        ['Beneficiário / matrícula', 'Utilização da rede credenciada', 'Utilização da rede própria', 'Total dos serviços utilizados', 'Coparticipação apurada'],
        [[b.identificacao, *_valores(b)] for b in (*beneficiarios, total)],
        ultima_em_negrito=True,
    )


def _documento(doc: str | None) -> str:
    return f'Documento {doc}' if doc else '–'


def _tabela_demonstrativos(beneficiarios: tuple[ValoresBeneficiario, ...]) -> str:
    return _tabela(
        ['Beneficiário / matrícula', 'Demonstrativo da rede credenciada', 'Demonstrativo da rede própria'],
        [[b.identificacao, _documento(b.doc_rede_credenciada), _documento(b.doc_rede_propria)] for b in beneficiarios],
    )


def _resultado_rede_propria(doc_levantamento_disa: str | None) -> str:
    if doc_levantamento_disa:
        return f'o levantamento apresentado ou validado pela DISA, conforme documento {doc_levantamento_disa}'
    return 'a ausência de atendimento identificado na Planilha BENEFICIÁRIOS ATENDIDOS NA REDE PRÓPRIA (149768791) e na base de faturamento do SADS consultada pela GEACS'


class MemoApisComTodasAsInformacoes(Memorando):
    """Memo à APIS-Utilização: retorno final, com os valores da utilização e
    da coparticipação em tabelas. Sem doc_levantamento_disa, informa que não
    houve atendimento na rede própria."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        memo_apis: DocArvore,
        beneficiarios: tuple[ValoresBeneficiario, ...],
        doc_coparticipacao: str,
        nome_signatario: str,
        cargo_signatario: str,
        doc_levantamento_disa: str | None = None,
    ):
        if not beneficiarios:
            raise ValueError('Memorando de retorno à APIS criado sem beneficiários')

        super().__init__(
            # Duas linhas: <br>, pois o texto entra no HTML do memo (um \n vira espaço)
            destinatario_nome='Fernanda de Moura Galantini<br>Assessoria de Políticas e Informações em Saúde – APIS',
            assunto=ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES,
            vocativo='Prezada Assessora',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'Em atendimento à solicitação constante do <strong>{identificar_doc(memo_apis)}</strong>, encaminhamos o resultado do levantamento dos serviços assistenciais utilizados e da respectiva coparticipação, referente aos beneficiários e períodos abaixo indicados:',
                dados.texto_levantamento_html() + dados.periodo_dependentes_html(),
                f'O levantamento da rede credenciada foi realizado a partir dos registros de faturamento constantes do Sistema de Assistência Descentralizada à Saúde – SADS, extraídos pela ASGE no Mantis 0011156. Quanto à rede própria, o resultado considera {_resultado_rede_propria(doc_levantamento_disa)}.',
                'A coparticipação correspondente aos atendimentos identificados foi apurada pelo Departamento de Processamento de Contas e Coparticipação – DEPROC, conforme relatórios extraídos e consolidados pela ASGE no Mantis 0011281.',
                'Os valores apurados estão sintetizados a seguir:',
                _tabela_valores(beneficiarios),
                '',
                'O detalhamento dos serviços utilizados consta dos demonstrativos individualizados do titular e de cada dependente, separados por rede assistencial, conforme os documentos relacionados abaixo:',
                _tabela_demonstrativos(beneficiarios),
                '',
                'Os demonstrativos apresentam a discriminação dos procedimentos, datas de realização, natureza dos atendimentos e valores individuais, sendo os da rede própria apresentados no mesmo formato.',
                f'O detalhamento da respectiva coparticipação consta do documento {doc_coparticipacao}, conforme apuração do DEPROC. Eventuais quantias já descontadas em folha estão discriminadas no retorno do DEPROC.',
                'Dessa forma, retornamos o processo à APIS com os demonstrativos e o resumo dos valores apurados, para subsidiar a notificação dos beneficiários e o prosseguimento das providências sob sua competência.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis

    def texto_principal(self) -> str:
        """Memorando.texto_principal põe cada parágrafo em um <p>; a tabela
        fica fora dele (tabela dentro de <p> é HTML inválido)."""
        return super().texto_principal().replace(f'<p class="{self.css_paragrafo}"><table', '<table').replace('</table></p>', '</table>')
