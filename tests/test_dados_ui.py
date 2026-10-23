import pytest

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI, iniciais_nome


@pytest.mark.parametrize(
    ('nome', 'esperado'),
    [
        ('José da Silva e Souza', 'J.S.S.'),
        ('MARIA DOS SANTOS DE OLIVEIRA', 'M.S.O.'),
        ('  ana   do  carmo ', 'A.C.'),
        ("Joana D'Arc Pereira", 'J.A.P.'),
        ('Ana Clara Lima-Souza', 'A.C.L.S.'),
        ('Ênio das Dores', 'Ê.D.'),
    ],
)
def test_iniciais_nome(nome, esperado):
    assert iniciais_nome(nome) == esperado


def test_memo_usa_iniciais_e_nao_o_nome():
    dados = DadosUI(nome_titular='José da Silva', matricula_titular='1289612', periodo_titular='01/2024 a 06/2024', periodo_dependentes=False)

    html = dados.texto_levantamento_html()

    assert dados.nome_titular_iniciais == 'J.S.'
    assert 'J.S.' in html
    assert 'José' not in html
