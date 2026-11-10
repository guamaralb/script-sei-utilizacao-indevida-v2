import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, identificar_doc
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import formatar_reais
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto final do memo (modelo provisório, baseado no
# MemoDeproc e no MemoApisSemUso) e só então passar para True. Enquanto for
# False, o fluxo DEPROC para antes de anexar o relatório e criar o memo
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore. É diferente do assunto do memo da GEACS à DEPROC
# ("Levantamento de coparticipação - ...")
ASSUNTO_MEMO_DEPROC_RESULTADO = 'Coparticipação apurada – utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_DEPROC_RESULTADO = re.compile(r'Coparticipação apurada\s*[-–]\s*utilização indevida da assistência à saúde', flags=re.IGNORECASE)

_CSS = 'Texto_Justificado_Recuo_Primeira_Linha'
_CATEGORIAS = {'TITULAR': 'titular', 'DEPENDENTE': 'dependente'}


def _subtotais_html(subtotais) -> str:
    """Valor por beneficiário, pela matrícula (sem o nome: LGPD)."""
    return ''.join(
        f'<p class="{_CSS}"><strong>Matrícula {s.matricula} ({_CATEGORIAS.get(s.categoria, s.categoria.lower())}):</strong> {s.atendimentos} atendimento(s), {formatar_reais(s.valor)}</p>'
        for s in subtotais
    )


def _totais_html(totais) -> str:
    return (
        f'<p class="{_CSS}"><strong>Valor total da coparticipação:</strong> {formatar_reais(totais.coparticipacao)}</p>'
        f'<p class="{_CSS}"><strong>Valor total descontado:</strong> {formatar_reais(totais.descontado)}</p>'
        f'<p class="{_CSS}"><strong>Valor total em aberto:</strong> {formatar_reais(totais.em_aberto)}</p>'
    )


class MemoDeprocResultado(Memorando):
    """Memo da DEPROC à GEACS com o resultado do levantamento da
    coparticipação (fluxo DEPROC): resumo por beneficiário, totais e o
    relatório em PDF anexado antes, citado pelo número SEI.

    resultado: coparticipacao_deproc.ResultadoDeproc. Sem atendimento no
    período, não há relatório (doc_relatorio=None) e o memo informa que não
    há coparticipação."""

    def __init__(
        self,
        *,
        dados: DadosUI,
        resultado,
        doc_relatorio: str | None,
        memo_apis: DocArvore,
        memo_deproc_geacs: DocArvore,
        nome_signatario: str,
        cargo_signatario: str,
    ):
        verificar_texto_definido(TEXTO_DEFINIDO, 'da DEPROC (resultado da coparticipação)')
        tem_atendimentos = not resultado.atendimentos.empty
        if tem_atendimentos and not doc_relatorio:
            raise ValueError('Memo de resultado da DEPROC com atendimentos exige o número SEI do relatório')

        if tem_atendimentos:
            resultado_html = [
                f'Foram identificados <strong>{len(resultado.atendimentos)} atendimento(s)</strong> no período de apuração, detalhados por beneficiário e atendimento no relatório constante do documento {doc_relatorio}. Valores de coparticipação por beneficiário:',
                _subtotais_html(resultado.subtotais),
                'Totais apurados:',
                _totais_html(resultado.totais),
            ]
        else:
            resultado_html = ['<strong>Não foram identificados atendimentos</strong> com coparticipação no período de apuração informado.']

        super().__init__(
            destinatario_nome='Bruna Miiller Lavarini<br>Gerência de Auditoria e Contas da Saúde - GEACS',
            assunto=ASSUNTO_MEMO_DEPROC_RESULTADO,
            vocativo='Prezada',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'Em atenção ao {identificar_doc(memo_deproc_geacs)}, que solicitou o levantamento dos valores de coparticipação referentes aos atendimentos do titular e de seus dependentes abaixo indicados, nos períodos informados no {identificar_doc(memo_apis)}, informa-se o resultado apurado por este Departamento:',
                dados.texto_levantamento_html() + dados.periodo_dependentes_html(),
                *resultado_html,
                'Dessa forma, retorna-se o processo à <strong>IPSEMG/GEACS - Utilização</strong>, para consolidação da apuração e prosseguimento do fluxo.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
