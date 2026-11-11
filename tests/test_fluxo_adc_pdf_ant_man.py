"""Fluxo ADC PDF ANT MAN (main_geacs_adc_pdf_ant_man.py e planilhas_adc_pdf_ant_man.py), com o SEI simulado e
planilhas geradas nos testes."""

import unicodedata

import main_geacs_adc_pdf_ant_aut
import planilhas_adc_pdf_ant_aut
import planilhas_adc_pdf_ant_man
import pytest
from constantes import UNIDADE_APIS
from planilhas_adc_pdf_ant_aut import TIPO_DOC
from planilhas_adc_pdf_ant_man import arquivos_do_processo, documento_da_arvore
from rede_propria import ErroAvaliacao
from Registro import ProxAcao, RegistroAdcPdfAnt
from tags import TAG_AGUARDA_FLUXO_NORMAL, TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, TAG_PROCESSO_NOVO

from tests.sei_falso import DISA_USOU_RP_ANTIGO, MANTIS_USOU_RC_ANTIGO, MANTIS_USOU_RP_ANTIGO
from tests.test_fluxo_adc_pdf_ant_aut import BASE, DEPENDENTE, MATRICULA, DriverFalso, gravar

PROCESSO = '2010.01.0082953/2024-75'
ANEXO = 'Anexo RELAÇÃO ATENDIMENTOS'
TITULAR = f'Planilha Utilização Titular - {MATRICULA}'


def nome_arquivo(processo: str, nome: str, separador: str = '-', extensao: str = 'xlsx') -> str:
    return f'{processo.replace("/", "_")}{separador}{nome}.{extensao}'


class Pasta:
    def __init__(self, caminho):
        self.caminho = caminho
        self.pdfs: list[dict] = []

    def planilha(self, nome: str, linhas: list[dict] | None = None, processo: str = PROCESSO, separador: str = '-'):
        return gravar(self.caminho / nome_arquivo(processo, nome, separador), linhas or [BASE])

    def transformar(self, **kwargs):
        self.pdfs.append(kwargs)
        return kwargs['path_destino'] / 'relatorio.pdf'


@pytest.fixture
def pasta(sei, monkeypatch, tmp_path):
    falsa = Pasta(tmp_path)
    monkeypatch.setattr(planilhas_adc_pdf_ant_man, 'DIR_ADC_PDF_ANT_MAN_PLANILHAS', tmp_path)
    monkeypatch.setattr(planilhas_adc_pdf_ant_man, 'DIR_ADC_PDF_ANT_MAN_PDF', tmp_path / 'pdf')
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'tem_incluir_documento', lambda driver: True)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in sei.docs])
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'transformar_xls_em_pdf', falsa.transformar)
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in sei.docs])
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'listar_marcadores', lambda driver: list(sei.tags))
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'garantir_marcadores_no_sei', lambda driver, lista: None)
    return falsa


def passar() -> RegistroAdcPdfAnt:
    return main_geacs_adc_pdf_ant_aut._processar_linha(DriverFalso(), PROCESSO, 'ADC PDF ANT MAN', 'agora', planilhas_adc_pdf_ant_man.inserir_pdfs_da_pasta)


def test_insere_o_pdf_de_cada_arquivo_com_o_nome_do_adc_pdf_ant_aut_e_os_marcadores(sei, pasta):
    tit = sei.novo_doc(TITULAR, UNIDADE_APIS, '')
    anexo = sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    pasta.planilha(ANEXO)
    pasta.planilha(TITULAR)

    registro = passar()

    assert sei.nomes[-2:] == [f'{TIPO_DOC} Utilização Tit. - {MATRICULA} - SEI {tit}', f'{TIPO_DOC} Utilização Ben. - {MATRICULA}']
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_MAN_AGUARDA_FLUXO_NORMAL
    assert registro.erro is None
    assert sorted(registro.planilhas_sei) == sorted([tit, anexo])
    assert pasta.pdfs[0]['path_destino'] == pasta.caminho / 'pdf' / tit


def test_pdf_ja_inserido_pelo_adc_pdf_ant_aut_nao_duplica(sei, pasta):
    tit = sei.novo_doc(TITULAR, UNIDADE_APIS, '')
    sei.novo_doc(f'{TIPO_DOC} Utilização Tit. - {MATRICULA} - SEI {tit}', UNIDADE_APIS, '')
    pasta.planilha(TITULAR)

    registro = passar()

    assert not pasta.pdfs
    assert not registro.pdfs_incluidos
    assert len(registro.pdfs_na_arvore) == 1


def test_segunda_passagem_nao_duplica(sei, pasta):
    sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    pasta.planilha(ANEXO)
    passar()
    registro = passar()
    assert len(sei.pdfs) == 1
    assert len(registro.pdfs_na_arvore) == 1


def test_ja_no_fluxo_normal_recebe_pdf_e_fica_onde_esta(sei, pasta):
    sei.tags.extend([TAG_PROCESSO_NOVO, DISA_USOU_RP_ANTIGO, MANTIS_USOU_RP_ANTIGO, MANTIS_USOU_RC_ANTIGO, TAG_NO_BLOCO_DISA_VALIDAR_CONSTA])
    antes = list(sei.tags)
    sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    pasta.planilha(ANEXO)

    registro = passar()

    assert sei.tags == antes
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_MAN_ESTADO_MANTIDO


def test_planilha_de_dependentes_usa_o_layout_dele(sei, pasta):
    nome = f'Planilha Utilização Dependentes - {MATRICULA}'
    sei.novo_doc(nome, UNIDADE_APIS, '')
    pasta.planilha(nome, [{**BASE, **DEPENDENTE}])
    passar()
    assert pasta.pdfs[0]['tipo'] == 'Dependente(s)'


def test_sem_arquivo_na_pasta_nao_recebe_marcador(sei, pasta):
    sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    pasta.planilha(ANEXO, processo='2010.01.0000001/2024-11')

    registro = passar()

    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_MAN_SEM_PLANILHAS
    assert registro.erro is None
    assert not sei.tags
    assert not sei.pdfs


@pytest.mark.parametrize(
    ('arquivo_extra', 'mensagem'),
    [
        ('RELAÇÃO ATENDIMENTOS', 'não é de planilha de utilização'),
        ('Anexo RELAÇÃO ATENDIMENTOS 2', 'não encontrado na árvore'),
    ],
)
def test_arquivo_invalido_para_antes_de_inserir_qualquer_pdf(sei, pasta, arquivo_extra, mensagem):
    sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    pasta.planilha(ANEXO)
    pasta.planilha(arquivo_extra)

    registro = passar()

    assert registro.tipo_erro == 'ErroAvaliacao'
    assert mensagem in registro.erro
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO
    assert not sei.pdfs
    assert not sei.tags


def test_formato_diferente_de_xlsx_e_erro(sei, pasta):
    sei.novo_doc(ANEXO, UNIDADE_APIS, '')
    (pasta.caminho / nome_arquivo(PROCESSO, ANEXO, extensao='xls')).write_bytes(b'')

    registro = passar()

    assert 'só o formato .xlsx' in registro.erro
    assert not sei.pdfs


def test_arquivos_do_processo_ignora_zone_identifier_e_outros_processos(pasta):
    caminho = pasta.planilha(ANEXO)
    pasta.planilha(ANEXO, processo='2010.01.0000001/2024-11')
    (pasta.caminho / f'{caminho.name}:Zone.Identifier').write_text('[ZoneTransfer]')

    assert arquivos_do_processo(PROCESSO) == {ANEXO: caminho}


@pytest.mark.parametrize('separador', ['-', ' - ', ' -', '- '])
def test_hifen_depois_do_processo_aceita_espacos(pasta, separador):
    caminho = pasta.planilha(ANEXO, separador=separador)
    assert arquivos_do_processo(PROCESSO) == {ANEXO: caminho}


def test_arquivo_sem_o_numero_do_processo_no_inicio_e_ignorado(pasta):
    gravar(pasta.caminho / f'Copia {nome_arquivo(PROCESSO, ANEXO)}', [BASE])
    assert not arquivos_do_processo(PROCESSO)


def test_nome_com_data_e_separador_com_espacos_acha_o_documento_com_barras(sei, pasta):
    nome_arvore = f'Planilha Utilização Tit. - {MATRICULA} - 10/12/2024'
    numero = sei.novo_doc(nome_arvore, UNIDADE_APIS, '')
    pasta.planilha(nome_arvore.replace('/', '_'), separador=' - ')

    registro = passar()

    assert registro.erro is None
    assert registro.planilhas_sei == [numero]
    assert sei.nomes[-1] == f'{TIPO_DOC} Utilização Tit. - {MATRICULA} - SEI {numero}'


def test_documento_da_arvore_ignora_forma_unicode_maiusculas_e_espacos():
    doc = {'numero_sei': '1', 'nome_arvore': ANEXO}
    assert documento_da_arvore(unicodedata.normalize('NFD', 'anexo  relação atendimentos'), [doc]) == doc


def test_dois_documentos_com_o_mesmo_nome_sao_erro():
    docs = [{'numero_sei': '1', 'nome_arvore': ANEXO}, {'numero_sei': '2', 'nome_arvore': ANEXO}]
    with pytest.raises(ErroAvaliacao, match='mais de um documento'):
        documento_da_arvore(ANEXO, docs)
