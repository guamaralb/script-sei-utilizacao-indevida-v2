import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import iniciais_nome
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore, identificar_doc
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import formatar_reais, tabela_html
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# Texto do modelo enviado pela GEACS (12/11/2026), em validação com a DEPROC.
# A data de geração das bases (data_geracao_bases) é obrigatória: é
# informada na execução (run_deproc_calcula_copa -d DD/MM/AAAA)
TEXTO_DEFINIDO = True

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore. É diferente do assunto do memo da GEACS à DEPROC
# ("Levantamento de coparticipação – ..."), que não casa com este padrão (e
# o padrão daquele não casa com este assunto)
ASSUNTO_MEMO_GEACS_CALCULO_COPA = 'Retorno do levantamento de coparticipação – utilização indevida da assistência à saúde'

PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA = re.compile(r'Retorno do levantamento de coparticipação\s*[-–]\s*utilização indevida da assistência à saúde', flags=re.IGNORECASE)

# Documentos citados no texto (fixos no modelo)
REFERENCIA_BASES = (
    'O relatório foi elaborado a partir das bases de coparticipação disponibilizadas pela ASGE no Mantis nº 0011281, extraídas do sistema AREC, '
    'conforme informado no Memorando IPSEMG/ASGE nº 535/2026 (153361309), observada a diretriz de cálculo estabelecida no '
    'Memorando IPSEMG/DIPS nº 452/2026 (153238766).'
)

_CATEGORIAS = {'TITULAR': 'Titular', 'DEPENDENTE': 'Dependente'}


def _tabela_beneficiarios(beneficiarios, total: float) -> str:
    """Valor apurado por matrícula (iniciais no lugar do nome: LGPD). O
    vínculo é Titular ou Dependente. Beneficiário com valor apurado 0 (no
    período) não entra."""
    linhas = [[iniciais_nome(b.nome), b.matricula, _CATEGORIAS.get(b.categoria, b.categoria.title()), formatar_reais(b.valor)] for b in beneficiarios if round(b.valor, 2) != 0]
    linhas.append(['Total consolidado', '', '', formatar_reais(total)])
    return tabela_html(['Beneficiário', 'Matrícula', 'Vínculo', 'Valor total de coparticipação apurado'], linhas, ultima_em_negrito=True)


def _tabela_totais(totais) -> str:
    return tabela_html(
        ['Descrição', 'Valor'],
        [
            ['Valor total de coparticipação apurado', formatar_reais(totais.coparticipacao)],
            ['Valor efetivamente descontado', formatar_reais(totais.descontado)],
            ['Valor total em aberto', formatar_reais(totais.em_aberto)],
        ],
    )


class MemoGeacsCalculoCopa(Memorando):
    """Memo da DEPROC à GEACS com o resultado do levantamento da
    coparticipação (fluxo DEPROC): tabela com o valor por matrícula (titular
    e dependentes com linhas na base DEPROC) e tabela com o total apurado, o
    descontado e o em aberto.

    resultado: coparticipacao_deproc.ResultadoDeproc. Sem coparticipação no
    período (nenhum atendimento, ou só atendimentos de valor 0), não há
    relatório (doc_relatorio=None) e o memo informa que não há
    coparticipação, sem as tabelas.

    data_geracao_bases: data(s) de geração das bases usadas (texto, ex.:
    '06/11/2026'), citada no memo."""

    def __init__(
        self,
        *,
        resultado,
        doc_relatorio: str | None,
        memo_deproc_geacs: DocArvore,
        data_geracao_bases: str,
        nome_signatario: str,
        cargo_signatario: str,
    ):
        verificar_texto_definido(TEXTO_DEFINIDO, 'da DEPROC (resultado da coparticipação)')
        if not data_geracao_bases:
            raise ValueError('Memo de resultado da DEPROC exige a data de geração das bases')
        tem_coparticipacao = resultado.tem_coparticipacao
        if tem_coparticipacao and not doc_relatorio:
            raise ValueError('Memo de resultado da DEPROC com coparticipação exige o número SEI do relatório')

        solicitacao = (
            'referente aos atendimentos do titular e de seus respectivos dependentes, quando houver, observadas as matrículas e os períodos de '
            'utilização indevida informados pela APIS e reproduzidos na solicitação encaminhada pela GEACS a este Departamento'
        )
        em_atendimento = f'Em atendimento ao {identificar_doc(memo_deproc_geacs)}'
        if tem_coparticipacao:
            resultado_html = [
                f'{em_atendimento}, encaminhamos o Relatório de Coparticipação – Utilização Indevida da Assistência à Saúde, {solicitacao}.',
                REFERENCIA_BASES,
                'Os atendimentos estão detalhados no relatório por prestador, data de atendimento, grupo de coparticipação e valor correspondente. '
                'Os valores apurados estão consolidados por matrícula/vínculo a seguir, abrangendo os períodos indicados na solicitação:',
                _tabela_beneficiarios(resultado.beneficiarios, resultado.totais.coparticipacao),
                'Quanto ao valor total apurado, foram identificados os seguintes valores descontados e em aberto:',
                _tabela_totais(resultado.totais),
                f'Os valores apresentados refletem os registros disponíveis nas bases utilizadas, geradas em {data_geracao_bases}. '
                'Eventuais movimentações posteriores às respectivas datas de geração poderão alterar os valores descontados e o saldo em aberto.',
            ]
        else:
            # Fora do modelo: redação própria para o caso sem coparticipação
            # (nenhum atendimento ou só atendimentos de valor 0)
            resultado_html = [
                f'{em_atendimento}, informamos o resultado do levantamento de coparticipação – utilização indevida da assistência à saúde, {solicitacao}.',
                REFERENCIA_BASES.replace('O relatório foi elaborado', 'O levantamento foi realizado'),
                '<strong>Não foram identificados atendimentos com coparticipação</strong> nos períodos indicados na solicitação.',
                f'O resultado reflete os registros disponíveis nas bases utilizadas, geradas em {data_geracao_bases}.',
            ]

        super().__init__(
            destinatario_nome='Bruna Miiller Lavarini<br>Gerência de Auditoria e Contas da Saúde – GEACS',
            assunto=ASSUNTO_MEMO_GEACS_CALCULO_COPA,
            vocativo='Prezada Gerente',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                *resultado_html,
                'Retornamos o processo à unidade <strong>IPSEMG/GEACS – UTILIZAÇÃO</strong>, para incorporação das informações à consolidação da apuração e prosseguimento do fluxo de retorno à APIS.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )

    def texto_principal(self) -> str:
        """Memorando.texto_principal põe cada parágrafo em um <p>; a tabela
        fica fora dele (tabela dentro de <p> é HTML inválido)."""
        return super().texto_principal().replace(f'<p class="{self.css_paragrafo}"><table', '<table').replace('</table></p>', '</table>')
