"""Fluxo alternativo ALT 1 (main_alt_1.py e planilhas_alt_1.py), com o SEI
simulado e planilhas geradas nos testes."""

from datetime import datetime
from pathlib import Path

import main_alt_1
import pandas as pd
import planilhas_alt_1
import pytest
import transformar_xls_em_pdf
from constantes import UNIDADE_APIS
from planilhas_alt_1 import ANEXO, DEPENDENTES, TITULAR, encontrar_planilhas, ler_planilha, nome_pdf, tipo_da_planilha
from rede_propria import ErroAvaliacao
from Registro import ProxAcao, RegistroAlt1
from tags import (
    TAG_AGUARDA_DISA_VALIDAR_CONSTA,
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_DISA_USOU_RP,
    TAG_MANTIS_USOU_RC,
    TAG_MANTIS_USOU_RP,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_PROCESSO_NOVO,
    TAG_PROCESSO_VELHO,
)

MATRICULA = 3542985
BASE = {
    'REFERENCIA': datetime(2024, 3, 1),
    'COD_PRESTADOR': 1,
    'NOME_PRESTADOR': 'CLINICA & CIA',
    'NUM_REMESSA': 2,
    'MATRICULA_BENEFICIARIO': MATRICULA,
    'NOME_BENEFICIARIO': 'Fulano de Tal',
    'DAT_ATENDIMENTO': '15/03/2024',
    'ITEM_SERVICO': 3,
    'PROCEDIMENTO': 'CONSULTA',
    'VAL_PAGAR': 10.5,
}
DEPENDENTE = {'MATRICULA_DEPENDENTE': 555, 'NOME_DEPENDENTE': 'Beltrano'}


def gravar(caminho: Path, linhas: list[dict]) -> Path:
    pd.DataFrame(linhas).to_excel(caminho, index=False)
    return caminho


class DownloadFalso:
    """Abrir a planilha na árvore a "baixa" para a pasta de downloads, com um
    nome que não identifica o documento (como no SEI)."""

    def __init__(self, pasta: Path):
        self.pasta = pasta
        self.planilhas: dict[str, list[dict]] = {}
        self.abertas: list[str] = []
        self.pdfs: list[dict] = []

    def selecionar(self, driver, numero_sei):
        self.abertas.append(numero_sei)
        gravar(self.pasta / 'Utilizacao_3542985 (1).xlsx', self.planilhas[numero_sei])

    def transformar(self, **kwargs):
        self.pdfs.append(kwargs)
        return kwargs['path_destino'] / 'relatorio.pdf'


class _SwitchFalso:
    @staticmethod
    def default_content():
        return None


class DriverFalso:
    switch_to = _SwitchFalso


@pytest.fixture
def alt(sei, monkeypatch, tmp_path):
    falso = DownloadFalso(tmp_path)
    monkeypatch.setattr(planilhas_alt_1, 'DIR_ALT_1_PLANILHAS', tmp_path)
    monkeypatch.setattr(planilhas_alt_1, 'DIR_ALT_1_PDF', tmp_path / 'pdfs')
    monkeypatch.setattr(planilhas_alt_1, 'TIMEOUT_DOWNLOAD', 0.1)
    monkeypatch.setattr(planilhas_alt_1, '_ESPERA_PROCESSO', 0)
    monkeypatch.setattr(planilhas_alt_1, 'selecionar_doc_arvore', falso.selecionar)
    monkeypatch.setattr(planilhas_alt_1, 'clicar_num_processo', lambda driver: None)
    monkeypatch.setattr(planilhas_alt_1, 'transformar_xls_em_pdf', falso.transformar)
    monkeypatch.setattr(main_alt_1, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(main_alt_1, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in sei.docs])
    monkeypatch.setattr(main_alt_1, 'listar_marcadores', lambda driver: list(sei.tags))
    monkeypatch.setattr(main_alt_1, 'garantir_marcadores_no_sei', lambda driver, lista: None)
    return falso


def planilha(sei, alt, nome: str, linhas: list[dict]) -> str:
    numero = sei.novo_doc(nome, UNIDADE_APIS, '')
    alt.planilhas[numero] = linhas
    return numero


def passar() -> RegistroAlt1:
    return main_alt_1._processar_linha(DriverFalso(), 'PROC')


# --- Fluxo --------------------------------------------------------------------


def test_insere_um_pdf_por_planilha_e_o_marcador(sei, alt):
    sei.novo_doc('Memorando 7', UNIDADE_APIS, 'memo')
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    dep = planilha(sei, alt, f'Planilha Utilização Dependentes - {MATRICULA}', [{**BASE, **DEPENDENTE}])
    anexo = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])

    registro = passar()

    assert sei.nomes[-3:] == [
        f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}',
        f'PDF Utilização Dep. - {MATRICULA} - SEI {dep}',
        f'PDF Utilização Ben. - {MATRICULA}',
    ]
    assert [pdf['tipo'] for pdf in alt.pdfs] == ['Titular', 'Dependente(s)', 'Beneficiário(s)']
    assert not alt.pdfs[2]['tit_nome']
    assert alt.pdfs[0]['tit_nome'] == 'FULANO DE TAL'
    assert alt.pdfs[0]['tit_matricula'] == str(MATRICULA)
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]
    assert registro.prox_acao == ProxAcao.ALT_1_AGUARDA_FLUXO_NORMAL
    assert registro.fluxo == 'ALT 1 - SOMENTE INSERIR PDF'
    assert registro.erro is None
    assert registro.planilhas_sei == [tit, dep, anexo]
    assert len(registro.pdfs_incluidos) == 3


def test_planilha_baixada_fica_com_o_numero_sei_no_nome(sei, alt):
    numero = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    passar()
    assert (alt.pasta / f'{numero}_Utilizacao_3542985 (1).xlsx').exists()


def test_segunda_passagem_nao_duplica(sei, alt):
    numero = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    passar()
    pdf = sei.numero_sei('PDF Utilização')

    registro = passar()

    assert alt.abertas == [numero]
    assert sei.nomes.count(f'PDF Utilização Tit. - {MATRICULA} - SEI {numero}') == 1
    assert registro.pdfs_na_arvore == [pdf]
    assert registro.prox_acao == ProxAcao.ALT_1_AGUARDA_FLUXO_NORMAL


def test_erro_em_uma_planilha_retoma_na_passagem_seguinte(sei, alt):
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    ruim = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [{'COLUNA': 1}])

    registro = passar()

    assert registro.tipo_erro == 'ErroAvaliacao'
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO
    assert sei.tags == []

    alt.planilhas[ruim] = [BASE]
    registro = passar()

    assert registro.erro is None
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]
    assert registro.pdfs_na_arvore
    assert alt.abertas == [tit, ruim, ruim]


@pytest.mark.parametrize(
    'marcadores',
    [
        (TAG_PROCESSO_NOVO, TAG_DISA_USOU_RP, TAG_MANTIS_USOU_RP, TAG_MANTIS_USOU_RC, TAG_AGUARDA_DISA_VALIDAR_CONSTA),
        (TAG_PROCESSO_VELHO,),
        (TAG_MEMO_DEPROC_NO_BLOCO,),
    ],
)
def test_ja_no_fluxo_normal_ou_velho_recebe_pdf_e_fica_onde_esta(sei, alt, marcadores):
    sei.tags = list(marcadores)
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])

    registro = passar()

    assert sei.pdfs
    assert sei.tags == list(marcadores)
    assert registro.prox_acao == ProxAcao.ALT_1_ESTADO_MANTIDO


def test_anexo_com_varios_beneficiarios(sei, alt):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTOS', [BASE, {**BASE, 'MATRICULA_BENEFICIARIO': 999, 'NOME_BENEFICIARIO': 'Sicrano'}])

    registro = passar()

    assert registro.erro is None
    assert sei.nomes[-1] == f'PDF Utilização Ben. - {MATRICULA} e mais 1'
    assert list(alt.pdfs[0]['df']['MATRICULA BENEFICIARIO']) == [MATRICULA, 999]


def test_nome_do_pdf_do_anexo_conta_as_matriculas_distintas_e_cabe_no_sei(tmp_path):
    linhas = [BASE, BASE, *({**BASE, 'MATRICULA_BENEFICIARIO': matricula} for matricula in (1111111, 2222222, 3333333))]
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', linhas), ANEXO)

    nome = nome_pdf(ANEXO, relatorio.matricula_titular, '150644870')

    assert nome == f'Utilização Ben. - {MATRICULA} e mais 3'
    assert len(nome) <= 50


def test_anexo_ja_inserido_e_baixado_mas_nao_duplica(sei, alt):
    numero = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    passar()

    registro = passar()

    assert alt.abertas == [numero, numero]
    assert sei.nomes.count(f'PDF Utilização Ben. - {MATRICULA}') == 1
    assert registro.pdfs_incluidos == []
    assert registro.pdfs_na_arvore == [sei.numero_sei('PDF Utilização Ben.')]


def test_anexo_com_matricula_que_comeca_igual_nao_e_o_mesmo_pdf(sei, alt):
    sei.novo_doc(f'PDF Utilização Ben. - {MATRICULA}9', 'IPSEMG/GEACS - Utilização', '')
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])

    registro = passar()

    assert registro.pdfs_incluidos == [f'Utilização Ben. - {MATRICULA}']


def test_anexos_com_o_mesmo_nome_de_pdf_param_antes_de_inserir(sei, alt):
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTOS', [BASE])

    registro = passar()

    assert 'mesmo nome de PDF' in registro.erro
    assert sei.pdfs == [f'PDF Utilização Tit. - {MATRICULA}']
    assert sei.tags == []
    assert tit in alt.abertas


def test_anexo_com_pdf_no_modelo_antigo_insere_o_novo_e_aponta_o_antigo(sei, alt):
    numero = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    antigo = sei.novo_doc(f'PDF Utilização Tit. - {MATRICULA} - SEI {numero}', 'IPSEMG/GEACS - Utilização', '')

    registro = passar()

    assert registro.pdfs_incluidos == [f'Utilização Ben. - {MATRICULA}']
    assert registro.pdfs_antigos_a_excluir == [antigo]
    assert antigo in {doc['numero_sei'] for doc in sei.docs}

    registro = passar()

    assert registro.pdfs_incluidos == []
    assert registro.pdfs_antigos_a_excluir == [antigo]


def test_processo_sem_planilha_nao_recebe_marcador(sei, alt):
    sei.novo_doc('Memorando 7', UNIDADE_APIS, 'memo')

    registro = passar()

    assert registro.prox_acao == ProxAcao.ALT_1_SEM_PLANILHAS
    assert registro.erro is None
    assert sei.tags == []


def test_download_que_nao_chega_e_erro(sei, alt, monkeypatch):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    monkeypatch.setattr(planilhas_alt_1, 'selecionar_doc_arvore', lambda driver, numero_sei: None)

    registro = passar()

    assert 'não foi baixada' in registro.erro
    assert sei.pdfs == []


def test_controle_nao_apaga_as_colunas_do_fluxo_principal(sei, alt):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    colunas = passar().to_dict()

    assert colunas['fluxo'] == 'ALT 1 - SOMENTE INSERIR PDF'
    assert colunas['tag_aguarda_fluxo_normal'] is True
    assert 'tit_usou' not in colunas
    assert 'memo_apis_mat_nao_encontradas_criado' not in colunas


# --- Identificação ------------------------------------------------------------


@pytest.mark.parametrize(
    ('nome', 'tipo'),
    [
        ('Planilha Utilização Titular - 3542985', TITULAR),
        ('Planilha Utilização Titular - 3542985 (SEI nº', TITULAR),
        ('Planilha Utilização Dependentes - 35429850', DEPENDENTES),
        ('Anexo RELAÇÃO ATENDIMENTO', ANEXO),
        ('Anexo Relação Atendimento', ANEXO),
        ('Anexo RELAÇÃO ANTENDIMENTO', ANEXO),
        ('Anexo RELACAO ATENDIMENTOS', ANEXO),
        ('Anexo RELAÇÃO ATENDIMENTOS', ANEXO),
        ('Anexo RELAÇÃO DE ATENDIMENTOS', ANEXO),
        ('Anexo RELAÇÕES ATENDIMENTO', ANEXO),
        ('Anexo  RELACÃO   ATENDIMENTO - Fulano', ANEXO),
        ('Planilha Utilizacao Titular - 123', TITULAR),
        ('Planilha Utilização Tit. - 3549507 - 10/12/2025', TITULAR),
        ('Planilha Utilização Titular - #####3', TITULAR),
        ('Planilha Utilização Dep. - 3549507 - 10/12/2025', DEPENDENTES),
        ('Planilha Utilização Dependente - #####3', DEPENDENTES),
        ('Planilha Utilização Dependentes - #####3', DEPENDENTES),
        ('Planilha Utilização Dependente - 123', DEPENDENTES),
        ('Anexo RELAÇÃO PAGAMENTO', None),
        ('Anexo RELAÇÃO ATESTADOS', None),
        ('Anexo RELAÇÃO', None),
        ('Anexo Atendimento', None),
        ('Memorando 7', None),
        ('PDF Utilização Tit. - 3542985 - SEI 123', None),
        ('Planilha Outra - 123', None),
        ('Anexo', None),
    ],
)
def test_tipo_da_planilha(nome, tipo):
    assert tipo_da_planilha({'nome_arvore': nome}) is tipo


def test_encontrar_planilhas_ignora_outros_documentos():
    docs = [{'nome_arvore': 'Memorando 1'}, {'nome_arvore': 'Anexo RELAÇÃO ATENDIMENTO'}]
    assert encontrar_planilhas(docs) == docs[1:]


def test_nome_do_pdf_cabe_no_campo_do_sei():
    assert len(nome_pdf(TITULAR, '12345678', '150644870')) <= 50


# --- Leitura ------------------------------------------------------------------


def test_ler_titular_com_data_em_texto(tmp_path):
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [BASE]), TITULAR)

    assert relatorio.matricula_titular == str(MATRICULA)
    assert list(relatorio.df.columns) == ['PRESTADOR', 'DATA DO ATENDIMENTO', 'PROCEDIMENTO', 'VALOR PAGO']
    assert relatorio.df.iloc[0]['DATA DO ATENDIMENTO'] == pd.Timestamp(2024, 3, 15)


def test_ler_anexo_usa_o_layout_por_beneficiario(tmp_path):
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [BASE]), ANEXO)

    assert list(relatorio.df.columns) == ['PRESTADOR', 'MATRICULA BENEFICIARIO', 'NOME BENEFICIARIO', 'DATA DO ATENDIMENTO', 'VALOR PAGO']
    assert relatorio.matricula_titular == str(MATRICULA)
    assert not relatorio.nome_titular


def test_pdf_do_anexo_tem_titulo_e_colunas_de_beneficiario(tmp_path, monkeypatch):
    textos = []
    paragrafo = transformar_xls_em_pdf.Paragraph

    def capturar(texto, *args, **kwargs):
        textos.append(texto)
        return paragrafo(texto, *args, **kwargs)

    monkeypatch.setattr(transformar_xls_em_pdf, 'Paragraph', capturar)
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [BASE]), ANEXO)

    caminho = transformar_xls_em_pdf.transformar_xls_em_pdf(tit_matricula=relatorio.matricula_titular, tit_nome=relatorio.nome_titular, tipo=ANEXO.tipo_pdf, df=relatorio.df, path_destino=tmp_path)

    assert caminho.exists()
    assert textos[0] == '<b>Relatório de Utilização Por Beneficiário(s)</b>'
    assert 'MATRICULA BENEFICIARIO' in textos
    assert 'NOME BENEFICIARIO' in textos
    assert not any('Titular' in texto for texto in textos)


def test_ler_anexo_remove_total_e_aceita_data_do_excel(tmp_path):
    linhas = [
        {**BASE, 'REFERENCIA': '03/2024', 'DAT_ATENDIMENTO': datetime(2024, 3, 15)},
        {**dict.fromkeys(BASE), 'REFERENCIA': 'TOTAL', 'VAL_PAGAR': 10.5},
    ]
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', linhas), ANEXO)

    assert len(relatorio.df) == 1
    assert relatorio.matricula_titular == str(MATRICULA)
    assert relatorio.df.iloc[0]['DATA DO ATENDIMENTO'] == pd.Timestamp(2024, 3, 15)


def test_ler_dependentes_usa_o_layout_sem_procedimento(tmp_path):
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [{**BASE, **DEPENDENTE}]), DEPENDENTES)
    assert list(relatorio.df.columns) == ['PRESTADOR', 'MATRICULA DEPENDENTE', 'NOME DEPENDENTE', 'DATA DO ATENDIMENTO', 'VALOR PAGO']


def test_valor_vazio_conta_como_zero(tmp_path):
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [{**BASE, 'VAL_PAGAR': None}]), TITULAR)
    assert relatorio.df.iloc[0]['VALOR PAGO'] == 0


@pytest.mark.parametrize(
    ('linhas', 'mensagem'),
    [
        ([{'COLUNA': 1}], 'colunas não encontradas'),
        ([{**BASE, 'DAT_ATENDIMENTO': '2024-03-15'}], 'sem data válida'),
        ([{**BASE, 'VAL_PAGAR': 'dez reais'}], 'não numérico'),
        ([{**dict.fromkeys(BASE), 'REFERENCIA': 'TOTAL'}], 'sem atendimentos'),
        ([BASE, {**BASE, 'MATRICULA_BENEFICIARIO': 999}], 'único valor'),
    ],
)
def test_planilha_invalida(tmp_path, linhas, mensagem):
    with pytest.raises(ErroAvaliacao, match=mensagem):
        ler_planilha(gravar(tmp_path / 'a.xlsx', linhas), TITULAR)


def test_formato_diferente_de_xlsx(tmp_path):
    with pytest.raises(ErroAvaliacao, match='xlsx'):
        ler_planilha(tmp_path / 'a.pdf', TITULAR)
