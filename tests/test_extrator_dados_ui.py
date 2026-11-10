import pytest
from extrator_dados_ui import FormatoMemorandoInvalido, eh_modelo_periodo_por_dependente, extrair_dados_ui, validar_template

from tests.sei_falso import MEMO_APIS, MEMO_APIS_PERIODO_POR_DEPENDENTE

MEMO_NOVO_NOVO = MEMO_APIS.format(extra='')
LINHAS_DEPENDENTE_666 = 'Matrícula do dependente: 666\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.'
MEMO_POR_DEPENDENTE = MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra=LINHAS_DEPENDENTE_666)


def test_modelo_periodo_por_dependente_e_procurado_antes_do_novo_novo():
    assert validar_template(MEMO_POR_DEPENDENTE) == 'periodo_por_dependente'

    dados = extrair_dados_ui(MEMO_POR_DEPENDENTE)

    assert dados.periodos_por_dependente == {'555': '01/01/2023 a 28/02/2023', '666': '01/03/2024 a 30/04/2024'}
    assert dados.matriculas_dependentes == '555; 666'
    assert dados.periodo_titular == '(01/2024 a 06/2024)'
    assert dados.nome_titular == 'FULANO'
    assert dados.matricula_titular == '1234567 / 8'
    assert not dados.periodo_dependentes


def test_memorandos_trazem_o_periodo_de_cada_dependente():
    dados = extrair_dados_ui(MEMO_POR_DEPENDENTE)

    assert 'Período de apuração do dependente 666:</strong> 01/03/2024 a 30/04/2024' in dados.texto_levantamento_html()
    # Não pode dizer que o período do titular vale para os dependentes
    assert not dados.periodo_dependentes_html()


def test_dependente_com_varios_intervalos():
    extra = 'Matrícula do dependente: 666\nPeríodo de apuração do dependente: (01/03/2024 a 30/04/2024) e (01/06/2024 a 30/06/2024).'
    dados = extrair_dados_ui(MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra=extra))

    assert dados.periodos_por_dependente['666'] == '(01/03/2024 a 30/04/2024) e (01/06/2024 a 30/06/2024)'


def test_resumo_das_matriculas_e_ignorado_quando_ha_duplas():
    # O 777 só está no resumo: valem as duplas
    texto = MEMO_POR_DEPENDENTE.replace('Nome completo: FULANO', 'Nome completo: FULANO\nMatrículas dos dependentes: 555; 666; 777')
    dados = extrair_dados_ui(texto)

    assert dados.matriculas_dependentes == '555; 666'


@pytest.mark.parametrize(
    ('campo', 'esperado'),
    [
        ('1234567-8; 7654321-0', '1234567-8; 7654321-0'),
        ('1234567 / 8, 7654321/0', '1234567 / 8; 7654321/0'),
        ('1234567 e 76543210', '1234567; 76543210'),
    ],
)
def test_matriculas_dos_dependentes_com_ou_sem_dv(campo, esperado):
    texto = MEMO_NOVO_NOVO.replace('Matrícula dos dependentes: 555', f'Matrícula dos dependentes: {campo}')

    assert extrair_dados_ui(texto).matriculas_dependentes == esperado


def test_dupla_com_dv_separado():
    extra = 'Matrícula do dependente: 1234567 / 8\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.'
    dados = extrair_dados_ui(MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra=extra))

    assert dados.periodos_por_dependente['12345678'] == '01/03/2024 a 30/04/2024'


def test_sem_a_linha_do_periodo_o_memo_e_analisado_como_hoje():
    assert not eh_modelo_periodo_por_dependente(MEMO_NOVO_NOVO)
    assert validar_template(MEMO_NOVO_NOVO) == 'novo_novo'
    assert extrair_dados_ui(MEMO_NOVO_NOVO).periodos_por_dependente is None


def test_periodo_sem_a_matricula_do_dependente_e_periodo_variavel():
    # Fora do padrão: continua parando com memo à APIS (1.1 e 1.7)
    texto = MEMO_APIS.format(extra='Período de apuração dos dependentes: 01/02/2024 a 01/03/2024')

    assert validar_template(texto) == 'novo_novo'
    assert extrair_dados_ui(texto).periodo_dependentes


@pytest.mark.parametrize(
    ('extra', 'mensagem'),
    [
        ('Matrícula do dependente: 666', 'fora de dupla'),
        ('Período de apuração do dependente: 01/03/2024 a 30/04/2024.', 'fora de dupla'),
        ('Matrícula do dependente: 666\nMatrícula do dependente: 777\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.', 'fora de dupla'),
        ('Matrícula do dependente: 666; 777\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.', 'única matrícula'),
        ('Matrícula do dependente: 666 777\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.', 'única matrícula'),
        ('Matrícula do dependente:\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024.', 'única matrícula'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente:', 'número par'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente: 01/03/2024.', 'número par'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente: 01/03/2024 a 30/04/2024 e 01/05/2024.', 'número par'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente: 03/2024 a 04/2024.', 'número par'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente: 01/03/2024 e 30/04/2024.', 'formato não reconhecido'),
        ('Matrícula do dependente: 666\nPeríodo de apuração do dependente: 30/04/2024 a 01/03/2024.', 'início depois do fim'),
        ('Matrícula do dependente: 555\nPeríodo de apuração do dependente: 01/05/2024 a 30/06/2024.', 'dois períodos'),
    ],
)
def test_dependentes_inconsistentes_sao_formato_invalido(extra, mensagem):
    with pytest.raises(FormatoMemorandoInvalido, match=mensagem):
        extrair_dados_ui(MEMO_APIS_PERIODO_POR_DEPENDENTE.format(extra=extra))


def test_campo_do_titular_ausente_e_formato_invalido():
    texto = MEMO_POR_DEPENDENTE.replace('Nome completo: FULANO\n', '')
    with pytest.raises(FormatoMemorandoInvalido, match='período por dependente'):
        validar_template(texto)


@pytest.mark.parametrize('memo', [MEMO_APIS, MEMO_APIS_PERIODO_POR_DEPENDENTE])
@pytest.mark.parametrize('periodo', ['01/112019 a 12/06/2024', '01/08/2019 a 12/06/2019'])
def test_periodo_do_titular_invalido_e_formato_invalido(memo, periodo):
    texto = memo.format(extra='').replace('(01/2024 a 06/2024)', periodo)
    with pytest.raises(FormatoMemorandoInvalido, match='Período de apuração do titular'):
        extrair_dados_ui(texto)


def test_periodo_do_titular_com_a_maiusculo_e_aceito():
    texto = MEMO_APIS.format(extra='').replace('(01/2024 a 06/2024)', '01/05/2019 A 12/06/2024')
    assert extrair_dados_ui(texto).periodo_titular == '01/05/2019 A 12/06/2024'
