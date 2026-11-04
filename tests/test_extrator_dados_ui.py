import re

import extrator_dados_ui
import pytest
from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui, validar_template

from tests.sei_falso import FRASE_MODELO_PERIODO_POR_DEPENDENTE, MEMO_APIS, MEMO_APIS_PERIODO_POR_DEPENDENTE

MEMO_NOVO_NOVO = MEMO_APIS.format(extra='')
MEMO_POR_DEPENDENTE = MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra='Matrícula do dependente: 666 - Período de apuração: 03/2024 a 04/2024')


@pytest.fixture
def frases_definidas(monkeypatch):
    monkeypatch.setattr(extrator_dados_ui, '_FRASES_MODELO_PERIODO_POR_DEPENDENTE', (re.compile(FRASE_MODELO_PERIODO_POR_DEPENDENTE, flags=re.IGNORECASE),))


def test_sem_frases_definidas_o_modelo_nunca_e_identificado():
    # Enquanto o modelo não é indicado, o memo é analisado como hoje
    assert not extrator_dados_ui.eh_modelo_periodo_por_dependente(MEMO_POR_DEPENDENTE)
    assert validar_template(MEMO_POR_DEPENDENTE) == 'novo_novo'


@pytest.mark.usefixtures('frases_definidas')
def test_modelo_periodo_por_dependente_e_procurado_antes_do_novo_novo():
    assert validar_template(MEMO_POR_DEPENDENTE) == 'periodo_por_dependente'

    dados = extrair_dados_ui(MEMO_POR_DEPENDENTE)

    assert dados.periodos_por_dependente == {'555': '01/2023 a 02/2023', '666': '03/2024 a 04/2024'}
    assert dados.matriculas_dependentes == '555; 666'
    assert dados.periodo_titular == '(01/2024 a 06/2024)'
    assert not dados.periodo_dependentes
    assert 'Período de apuração do dependente 666:</strong> 03/2024 a 04/2024' in dados.texto_levantamento_html()


@pytest.mark.usefixtures('frases_definidas')
def test_sem_as_frases_o_memo_e_analisado_como_hoje():
    assert validar_template(MEMO_NOVO_NOVO) == 'novo_novo'
    assert extrair_dados_ui(MEMO_NOVO_NOVO).periodos_por_dependente is None


@pytest.mark.usefixtures('frases_definidas')
def test_modelo_periodo_por_dependente_sem_periodo_de_dependente_e_formato_invalido():
    texto = '\n'.join(linha for linha in MEMO_POR_DEPENDENTE.splitlines() if 'Matrícula do dependente' not in linha)
    with pytest.raises(FormatoMemorandoInvalido, match='período por dependente'):
        validar_template(texto)


@pytest.mark.usefixtures('frases_definidas')
def test_dependente_com_dois_periodos_e_formato_invalido():
    texto = MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra='Matrícula do dependente: 555 - Período de apuração: 05/2024 a 06/2024')
    with pytest.raises(FormatoMemorandoInvalido, match='dois períodos'):
        extrair_dados_ui(texto)
