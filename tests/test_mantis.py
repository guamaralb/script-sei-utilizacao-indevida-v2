from datetime import date

import pytest
from mantis import Atendimento, BaseMantis, BasesMantis, Intervalo, avaliar_uso_rede_propria_mantis, interpretar_periodo
from rede_propria import ErroAvaliacao

_VAZIA = BaseMantis('vazia', {}, {})
_EM_2023 = Atendimento(date(2023, 1, 15), 10.0)
BASES = BasesMantis(BaseMantis('rede própria', {}, {'555': (_EM_2023,), '666': (_EM_2023,)}), _VAZIA)


def test_sem_periodos_por_dependente_vale_o_periodo_do_titular():
    uso = avaliar_uso_rede_propria_mantis('12345678', ('555', '666'), '01/2024 a 06/2024', BASES).rede_propria

    assert not uso.alguem_usou


def test_periodo_proprio_do_dependente():
    # O 555 tem o seu período (com a matrícula como no memo); o 666 usa o do titular
    uso = avaliar_uso_rede_propria_mantis('12345678', ('555', '666'), '01/2024 a 06/2024', BASES, {'0.555': '01/2023 a 02/2023'}).rede_propria

    assert uso.deps_que_usaram == ('555',)
    assert uso.deps_valor_total == 10.0


def test_periodo_do_dependente_invalido():
    with pytest.raises(ErroAvaliacao, match='do dependente 555'):
        avaliar_uso_rede_propria_mantis('12345678', ('555',), '01/2024 a 06/2024', BASES, {'555': 'janeiro de 2023'})


@pytest.mark.parametrize(
    ('texto', 'inicio', 'fim'),
    [
        ('01/04/2019 a12/06/2024', date(2019, 4, 1), date(2024, 6, 12)),
        ('01/04/2019a 12/06/2024', date(2019, 4, 1), date(2024, 6, 12)),
        ('01/05/2019 A 12/06/2024', date(2019, 5, 1), date(2024, 6, 12)),
        ('11/2019 A 06/2024', date(2019, 11, 1), date(2024, 6, 30)),
        ('02 A 06/2024.', date(2024, 2, 1), date(2024, 6, 30)),
    ],
)
def test_periodo_com_a_maiusculo_ou_sem_espaco(texto, inicio, fim):
    assert interpretar_periodo(texto) == (Intervalo(inicio, fim),)


def test_varios_intervalos_com_a_maiusculo():
    assert len(interpretar_periodo('(01/05/2019 A 31/12/2019) e (01/02/2020 a12/06/2024)')) == 2


@pytest.mark.parametrize('texto', ['01/112019 a 12/06/2024', '01/12/20219 a 12/06/2024', '01/07/2019 a 12/06/202024', '01/08/2026 a 12/06/2024', '2019 a 2024'])
def test_periodo_com_erro_de_digitacao_e_recusado(texto):
    with pytest.raises(ErroAvaliacao):
        interpretar_periodo(texto)
