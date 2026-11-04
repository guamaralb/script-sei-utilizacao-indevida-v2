from datetime import date

import pytest
from mantis import Atendimento, BaseMantis, BasesMantis, avaliar_uso_rede_propria_mantis
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
