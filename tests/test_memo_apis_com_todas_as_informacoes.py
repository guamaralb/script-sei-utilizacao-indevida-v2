import pytest

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import (
    ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES,
    PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES,
    MemoApisComTodasAsInformacoes,
    ValoresBeneficiario,
    formatar_reais,
)

MEMO_APIS = {'numero_sei': '150644870', 'nome_arvore': 'Memorando 2627', 'unidade': 'IPSEMG/APIS-Utilização'}
DADOS = DadosUI(nome_titular='José da Silva', matricula_titular='1234567', periodo_titular='01/2024 a 06/2024', periodo_dependentes=False, matriculas_dependentes='555')
BENEFICIARIOS = (
    ValoresBeneficiario('Titular – 1234567', 1000, 234.5, 100, '111', '222'),
    ValoresBeneficiario('Dependente – 555', 500.25, 0, 50.1, '333'),
)
ARGS = {'dados': DADOS, 'memo_apis': MEMO_APIS, 'beneficiarios': BENEFICIARIOS, 'doc_coparticipacao': '444', 'nome_signatario': 'x', 'cargo_signatario': 'y'}


def _html(**kwargs) -> str:
    return MemoApisComTodasAsInformacoes(**{**ARGS, **kwargs}).texto_principal()


def _linhas(html: str) -> list[list[str]]:
    """Linhas das tabelas, sem as tags, para comparar os valores."""
    linhas = []
    for linha in html.split('<tr>')[1:]:
        celulas = linha.split('</tr>')[0].split('</td>')[:-1]
        linhas.append([celula.replace('<td>', '').replace('<strong>', '').replace('</strong>', '') for celula in celulas])
    return linhas


def test_tabela_no_formato_do_editor_do_sei():
    html = _html()
    assert html.count('<table border="1" cellpadding="4" style="border-collapse:collapse;margin-left:auto;margin-right:auto;width:500px;"><tbody><tr><td>') == 2
    assert '<td><p' not in html


@pytest.mark.parametrize(('valor', 'esperado'), [(0, 'R$ 0,00'), (1234.5, 'R$ 1.234,50'), (1234567.891, 'R$ 1.234.567,89')])
def test_formatar_reais(valor, esperado):
    assert formatar_reais(valor) == esperado


def test_tabela_de_valores_com_totais():
    assert _linhas(_html())[1:4] == [
        ['Titular – 1234567', 'R$ 1.000,00', 'R$ 234,50', 'R$ 1.234,50', 'R$ 100,00'],
        ['Dependente – 555', 'R$ 500,25', 'R$ 0,00', 'R$ 500,25', 'R$ 50,10'],
        ['Total', 'R$ 1.500,25', 'R$ 234,50', 'R$ 1.734,75', 'R$ 150,10'],
    ]


def test_tabela_de_demonstrativos_sem_documento_mostra_traco():
    assert _linhas(_html())[5:] == [
        ['Titular – 1234567', 'Documento 111', 'Documento 222'],
        ['Dependente – 555', 'Documento 333', '–'],
    ]


def test_tabelas_ficam_fora_dos_paragrafos():
    html = _html()
    assert html.count('<table') == 2
    assert '<p class="Texto_Justificado_Recuo_Primeira_Linha"><table' not in html
    assert '</table></p>' not in html


def test_rede_propria_com_levantamento_da_disa():
    html = _html(doc_levantamento_disa='999')
    assert 'o levantamento apresentado ou validado pela DISA, conforme documento 999.' in html
    assert 'a ausência de atendimento' not in html


def test_rede_propria_sem_atendimento():
    assert 'a ausência de atendimento identificado na Planilha' in _html()


def test_cita_memo_da_apis_coparticipacao_e_periodo_dos_dependentes():
    html = _html().replace('<strong>', '').replace('</strong>', '')
    assert 'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 2627 (150644870)' in html
    assert 'consta do documento 444' in html
    assert 'Período de apuração dos dependentes: 01/2024 a 06/2024' in html
    assert 'José' not in html


def test_exige_beneficiarios():
    with pytest.raises(ValueError, match='sem beneficiários'):
        _html(beneficiarios=())


def test_assunto_e_encontrado_pelo_padrao():
    assert PADRAO_ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES.search(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES)
