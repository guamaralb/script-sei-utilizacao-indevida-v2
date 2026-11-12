from datetime import date

import pandas as pd
import pytest
from mantis import Atendimento, BaseMantis, BasesMantis, Intervalo, avaliar_uso_rede_propria_mantis, carregar_bases_mantis, interpretar_periodo
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


def test_dependente_nao_encontrado_usa_so_o_arquivo_dele():
    # 555 está nas duas bases; fora da base APIS, vale só o arquivo dos não
    # encontrados (com atendimento em 2024)
    em_2024 = Atendimento(date(2024, 3, 1), 7.0)
    bases = BasesMantis(BaseMantis('rede própria', {}, {'555': (em_2024, em_2024)}, {'555': (em_2024,)}), _VAZIA)

    uso = avaliar_uso_rede_propria_mantis('12345678', ('555',), '01/2024 a 06/2024', bases, deps_nao_encontrados=('555',)).rede_propria
    assert uso.deps_que_usaram == ('555',)
    assert uso.deps_valor_total == 7.0

    # Encontrado na base APIS: vale a base principal
    uso = avaliar_uso_rede_propria_mantis('12345678', ('555',), '01/2024 a 06/2024', bases).rede_propria
    assert uso.deps_valor_total == 14.0


def _gravar_base(arquivo, titulares=(), dependentes=()):
    colunas_tit = ['MATRICULA_TITULAR', 'DATA_DO_ATENDIMENTO', 'VALOR_A_PAGAR', 'NOME_PRESTADOR', 'PROCEDIMENTO']
    colunas_dep = ['MATRICULA_TITULAR', 'MATRICULA_DEPENDENTE', 'NOME_DEPENDENTE', 'DATA_DO_ATENDIMENTO', 'VALOR_A_PAGAR', 'NOME_PRESTADOR', 'PROCEDIMENTO']
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame(list(titulares), columns=colunas_tit).to_excel(writer, sheet_name='TITULARES', index=False)
        pd.DataFrame(list(dependentes), columns=colunas_dep).to_excel(writer, sheet_name='DEPENDENTES', index=False)


def test_carrega_arquivo_dos_dependentes_nao_encontrados(tmp_path):
    # Só a aba DEPENDENTES, com as colunas antigas (DAT_ATENDIMENTO como
    # número de série do Excel e VAL_PAGAR)
    principal = tmp_path / 'principal.xlsx'
    _gravar_base(principal)
    nao_encontrados = tmp_path / 'nao_encontrados.xlsx'
    linhas = [[1290957, 'TITULAR', 3499186, 'STEFANI', 45352, 'HOSPITAL', 'CONSULTA', 40]]
    colunas = ['MATRICULA_BENEFICIARIO', 'NOME_BENEFICIARIO', 'MATRICULA_DEPENDENTE', 'NOME_DEPENDENTE', 'DAT_ATENDIMENTO', 'NOME_PRESTADOR', 'PROCEDIMENTO', 'VAL_PAGAR']
    pd.DataFrame(linhas, columns=colunas).to_excel(nao_encontrados, sheet_name='DEPENDENTES', index=False)

    bases = carregar_bases_mantis(principal, principal, nao_encontrados, None)

    assert bases.rede_propria.dependentes_nao_encontrados == {'3499186': (Atendimento(date(2024, 3, 1), 40.0, prestador='HOSPITAL', procedimento='CONSULTA', nome_dependente='STEFANI'),)}
    assert bases.rede_credenciada.dependentes_nao_encontrados == {}


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
