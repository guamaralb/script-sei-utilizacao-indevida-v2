import docs_processo
import pytest
from selenium.common.exceptions import ElementClickInterceptedException

DOC = {'nome_arvore': 'Memorando 7', 'unidade': 'IPSEMG/APIS-Utilização', 'numero_sei': '123'}


class _Switch:
    @staticmethod
    def default_content():
        return None

    @staticmethod
    def frame(nome):
        return None


class _Driver:
    switch_to = _Switch

    def __init__(self):
        self.rolagens = 0

    @staticmethod
    def find_element(by, xpath):
        return 'elemento'

    def execute_script(self, script, elemento):
        self.rolagens += 1


@pytest.fixture
def driver(monkeypatch):
    monkeypatch.setattr(docs_processo, 'obter_conteudo_doc', lambda driver, formato: 'texto')
    return _Driver()


def _seleciona_na_tentativa(monkeypatch, erro: Exception | None, tentativas_com_erro: int) -> list[str]:
    chamadas: list[str] = []

    def selecionar(driver, numero_sei):
        chamadas.append('selecionar')
        if erro is not None and chamadas.count('selecionar') <= tentativas_com_erro:
            raise erro

    monkeypatch.setattr(docs_processo, 'selecionar_doc_arvore', selecionar)
    monkeypatch.setattr(docs_processo, 'listar_documentos_arvore', lambda driver: chamadas.append('listar') or [])
    return chamadas


@pytest.mark.parametrize(
    'erro',
    [
        # Pastas da árvore fechadas depois de adicionar marcador
        Exception('Documento n�o encontrado'),
        # Documento no fim da árvore
        ElementClickInterceptedException('element click intercepted'),
    ],
)
def test_reles_a_arvore_e_tenta_de_novo(monkeypatch, driver, erro):
    chamadas = _seleciona_na_tentativa(monkeypatch, erro, tentativas_com_erro=1)

    assert docs_processo.ler_texto_doc(driver, DOC) == 'texto'
    assert chamadas == ['selecionar', 'listar', 'selecionar']
    assert driver.rolagens == 1


def test_segunda_falha_propaga(monkeypatch, driver):
    _seleciona_na_tentativa(monkeypatch, ElementClickInterceptedException('x'), tentativas_com_erro=2)

    with pytest.raises(ElementClickInterceptedException):
        docs_processo.ler_texto_doc(driver, DOC)


def test_outro_erro_nao_tenta_de_novo(monkeypatch, driver):
    chamadas = _seleciona_na_tentativa(monkeypatch, RuntimeError('outro'), tentativas_com_erro=1)

    with pytest.raises(RuntimeError):
        docs_processo.ler_texto_doc(driver, DOC)
    assert chamadas == ['selecionar']
