import pytest
from rede_propria import BasesUso, ErroAvaliacao, avaliar_uso_rede_propria_disa, verificar_base_apis


def _bases(*, apis_titulares=('12345678',), apis_dependentes=('5559',)) -> BasesUso:
    return BasesUso(
        titulares={'12345678': True},
        dependentes={'555': True},
        apis_titulares=frozenset(apis_titulares),
        apis_dependentes=frozenset(apis_dependentes),
    )


@pytest.mark.parametrize('titular', ['12345678', '1234567', '1234567 / 8', '1234567-8'])
@pytest.mark.parametrize('dependente', ['555', '5559', '555-9', '0555'])
def test_memo_com_ou_sem_dv_encontra_a_mesma_matricula(titular, dependente):
    matriculas = verificar_base_apis(titular, dependente, _bases())

    assert not matriculas.nao_encontradas_apis
    # Titular com DV (base DISA) e dependente sem DV (base DISA e MANTIS)
    assert matriculas.titular == '12345678'
    assert matriculas.dependentes == ('555',)

    uso = avaliar_uso_rede_propria_disa(matriculas, _bases())
    assert uso.tit_usou
    assert uso.deps_que_usaram == ('555',)


def test_dv_errado_nao_e_encontrado():
    matriculas = verificar_base_apis('12345670', '5550', _bases())

    assert matriculas.nao_encontradas_apis.titular == '12345670'
    assert matriculas.nao_encontradas_apis.dependentes == ('5550',)


def test_dependente_citado_com_e_sem_dv_conta_uma_vez():
    assert verificar_base_apis('1234567', '555; 5559', _bases()).dependentes == ('555',)


@pytest.mark.parametrize('base', [('1234567', '12345678'), ('12345678', '12345679')])
def test_matricula_ambigua_na_base_apis_e_erro(base):
    with pytest.raises(ErroAvaliacao, match='ambígua'):
        verificar_base_apis('1234567', None, _bases(apis_titulares=base))


def test_periodos_usam_a_matricula_sem_dv():
    matriculas = verificar_base_apis('1234567', '5559', _bases())

    assert matriculas.periodos_dos_dependentes({'5559': '01/2024 a 02/2024'}) == {'555': '01/2024 a 02/2024'}
    assert matriculas.periodos_dos_dependentes(None) is None


def test_mesmo_dependente_com_e_sem_dv_e_periodos_diferentes_e_erro():
    matriculas = verificar_base_apis('1234567', '555; 5559', _bases())

    with pytest.raises(ErroAvaliacao, match='com e sem DV'):
        matriculas.periodos_dos_dependentes({'555': '01/2024 a 02/2024', '5559': '03/2024 a 04/2024'})
