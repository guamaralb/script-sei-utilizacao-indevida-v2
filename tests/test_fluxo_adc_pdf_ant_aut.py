"""Fluxo alternativo ADC PDF ANT AUT (main_geacs_adc_pdf_ant_aut.py e planilhas_adc_pdf_ant_aut.py), com o SEI
simulado e planilhas geradas nos testes."""

from datetime import datetime
from pathlib import Path

import main_geacs_adc_pdf_ant_aut
import pandas as pd
import planilhas_adc_pdf_ant_aut
import processo_fechado
import pytest
import relatorios_mantis
import transformar_xls_em_pdf
from constantes import UNIDADE_APIS
from openpyxl import load_workbook
from planilhas_adc_pdf_ant_aut import ANEXO, DEPENDENTES, TITULAR, encontrar_planilhas, ler_planilha, nome_pdf, tipo_da_planilha
from rede_propria import ErroAvaliacao
from Registro import ProxAcao, RegistroAdcPdfAnt, registrar_erro
from selenium.common.exceptions import InvalidSessionIdException, StaleElementReferenceException, TimeoutException
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

    @staticmethod
    def refresh():
        return None


@pytest.fixture
def alt(sei, monkeypatch, tmp_path):
    falso = DownloadFalso(tmp_path)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'DIR_ADC_PDF_ANT_AUT_PLANILHAS', tmp_path)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'DIR_ADC_PDF_ANT_AUT_PDF', tmp_path / 'pdfs')
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'TIMEOUT_DOWNLOAD', 0.1)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, '_ESPERA_NOVA_TENTATIVA', 0)
    monkeypatch.setattr(processo_fechado, '_ESPERA_REABERTURA', 0)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in sei.docs])
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'selecionar_doc_arvore', falso.selecionar)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'tem_incluir_documento', lambda driver: True)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'transformar_xls_em_pdf', falso.transformar)
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in sei.docs])
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'listar_marcadores', lambda driver: list(sei.tags))
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'garantir_marcadores_no_sei', lambda driver, lista: None)
    return falso


def planilha(sei, alt, nome: str, linhas: list[dict]) -> str:
    numero = sei.novo_doc(nome, UNIDADE_APIS, '')
    alt.planilhas[numero] = linhas
    return numero


def passar() -> RegistroAdcPdfAnt:
    return main_geacs_adc_pdf_ant_aut._processar_linha(DriverFalso(), 'PROC')


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
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL
    assert registro.fluxo == 'ADC PDF ANT AUT - PLANILHA ANTIGA BAIXADA DO SEI'
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
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL


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


def test_processo_com_so_um_dos_pdfs_recebe_o_que_falta(sei, alt):
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    dep = planilha(sei, alt, f'Planilha Utilização Dependentes - {MATRICULA}', [{**BASE, **DEPENDENTE}])
    pdf_tit = sei.novo_doc(f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}', UNIDADE_APIS, '')

    registro = passar()

    assert alt.abertas == [dep]
    assert registro.pdfs_incluidos == [f'Utilização Dep. - {MATRICULA} - SEI {dep}']
    assert registro.pdfs_na_arvore == [pdf_tit]
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]


def _falhar_ao_anexar(monkeypatch, sei, falhas: list[bool]):
    """Cada item é uma tentativa com tempo esgotado: True se o documento entra
    mesmo assim (tempo esgotado depois de salvar)."""

    def incluir(driver, *, tipo_doc, num, **kwargs):
        if num.startswith('Utilização Dep.') and falhas:
            if falhas.pop(0):
                sei.novo_doc(f'{tipo_doc} {num}', UNIDADE_APIS, '')
            raise TimeoutException
        sei.novo_doc(f'{tipo_doc} {num}', UNIDADE_APIS, '')

    monkeypatch.setattr(relatorios_mantis, 'incluir_doc_externo', incluir)


def _titular_e_dependentes(sei, alt) -> tuple[str, str]:
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    dep = planilha(sei, alt, f'Planilha Utilização Dependentes - {MATRICULA}', [{**BASE, **DEPENDENTE}])
    return tit, dep


def test_tempo_esgotado_ao_anexar_tenta_de_novo(sei, alt, monkeypatch):
    tit, dep = _titular_e_dependentes(sei, alt)
    _falhar_ao_anexar(monkeypatch, sei, [False, False])

    registro = passar()

    assert registro.erro is None
    assert sei.nomes[-2:] == [f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}', f'PDF Utilização Dep. - {MATRICULA} - SEI {dep}']
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]


def test_elemento_obsoleto_ao_anexar_tenta_de_novo(sei, alt, monkeypatch):
    # A tela recarregou entre achar o ícone e clicar
    tit, dep = _titular_e_dependentes(sei, alt)
    falhas = [StaleElementReferenceException]

    def incluir(driver, *, tipo_doc, num, **kwargs):
        if num.startswith('Utilização Dep.') and falhas:
            raise falhas.pop()
        sei.novo_doc(f'{tipo_doc} {num}', UNIDADE_APIS, '')

    monkeypatch.setattr(relatorios_mantis, 'incluir_doc_externo', incluir)

    registro = passar()

    assert registro.erro is None
    assert sei.nomes[-2:] == [f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}', f'PDF Utilização Dep. - {MATRICULA} - SEI {dep}']


def _sem_incluir_documento(monkeypatch, *, reabre: bool = True) -> list[str]:
    """Só depois de reaberto o processo tem "Incluir Documento"."""
    reaberturas: list[str] = []

    def reabrir(driver):
        if not reabre:
            raise ValueError('Não há como concluir nem reabrir o processo')
        reaberturas.append('reabriu')

    monkeypatch.setattr(processo_fechado, 'reabrir_processo', reabrir)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'tem_incluir_documento', lambda driver: bool(reaberturas))
    monkeypatch.setattr(processo_fechado, 'tem_incluir_documento', lambda driver: bool(reaberturas))
    return reaberturas


def test_processo_sem_incluir_documento_e_reaberto_e_recebe_os_pdfs(sei, alt, monkeypatch):
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    reaberturas = _sem_incluir_documento(monkeypatch)

    registro = passar()

    assert reaberturas == ['reabriu']
    assert registro.processo_reaberto is True
    assert registro.to_dict()['processo_reaberto'] is True
    assert registro.erro is None
    assert sei.nomes[-1] == f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}'


def test_processo_que_nao_reabre_para_antes_de_baixar(sei, alt, monkeypatch):
    planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    _sem_incluir_documento(monkeypatch, reabre=False)

    registro = passar()

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert 'não foi possível reabrir' in registro.erro
    assert registro.processo_reaberto is False
    assert alt.abertas == []
    assert sei.tags == []


def test_processo_que_continua_sem_incluir_documento_e_erro(sei, alt, monkeypatch):
    planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    monkeypatch.setattr(processo_fechado, 'reabrir_processo', lambda driver: None)
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'tem_incluir_documento', lambda driver: False)
    monkeypatch.setattr(processo_fechado, 'tem_incluir_documento', lambda driver: False)

    registro = passar()

    assert 'depois de reabrir' in registro.erro
    assert registro.processo_reaberto is False
    assert alt.abertas == []


def test_processo_com_todos_os_pdfs_nao_e_reaberto(sei, alt, monkeypatch):
    tit = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    sei.novo_doc(f'PDF Utilização Tit. - {MATRICULA} - SEI {tit}', UNIDADE_APIS, '')
    reaberturas = _sem_incluir_documento(monkeypatch)

    registro = passar()

    assert reaberturas == []
    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL


def test_tempo_esgotado_depois_de_salvar_nao_duplica(sei, alt, monkeypatch):
    _, dep = _titular_e_dependentes(sei, alt)
    _falhar_ao_anexar(monkeypatch, sei, [True])

    registro = passar()

    assert registro.erro is None
    assert sei.nomes.count(f'PDF Utilização Dep. - {MATRICULA} - SEI {dep}') == 1


def test_tempo_esgotado_em_todas_as_tentativas_retoma_na_passagem_seguinte(sei, alt, monkeypatch):
    tit, dep = _titular_e_dependentes(sei, alt)
    _falhar_ao_anexar(monkeypatch, sei, [False] * 3)

    registro = passar()

    assert registro.tipo_erro == 'TimeoutException'
    assert sei.tags == []
    assert registro.pdfs_incluidos == [f'Utilização Tit. - {MATRICULA} - SEI {tit}']

    registro = passar()

    assert registro.erro is None
    assert alt.abertas == [tit, dep, dep]
    assert sei.nomes[-1] == f'PDF Utilização Dep. - {MATRICULA} - SEI {dep}'
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]


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
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO


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


def test_anexo_ja_inserido_nao_e_baixado_de_novo(sei, alt):
    numero = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    passar()

    registro = passar()

    assert alt.abertas == [numero]
    assert sei.nomes.count(f'PDF Utilização Ben. - {MATRICULA}') == 1
    assert registro.pdfs_incluidos == []
    assert registro.pdfs_na_arvore == [sei.numero_sei('PDF Utilização Ben.')]


def test_anexo_com_pdf_na_arvore_nao_depende_do_download(sei, alt, monkeypatch):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    sei.novo_doc(f'PDF Utilização Ben. - {MATRICULA} e mais 2', 'IPSEMG/GEACS - Utilização', '')
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'selecionar_doc_arvore', lambda driver, numero_sei: None)

    registro = passar()

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL


def test_dois_anexos_ja_inseridos_nao_sao_baixados_de_novo(sei, alt):
    primeiro = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    segundo = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTOS', [{**BASE, 'MATRICULA_BENEFICIARIO': 777}])
    passar()

    registro = passar()

    assert alt.abertas == [primeiro, segundo]
    assert len(registro.pdfs_na_arvore) == 2


def test_anexo_novo_depois_do_pdf_de_outro_e_baixado_e_inserido(sei, alt):
    primeiro = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    passar()
    segundo = planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTOS', [{**BASE, 'MATRICULA_BENEFICIARIO': 777}])

    registro = passar()

    assert alt.abertas == [primeiro, primeiro, segundo]
    assert registro.pdfs_incluidos == ['Utilização Ben. - 777']
    assert sei.nomes.count(f'PDF Utilização Ben. - {MATRICULA}') == 1


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

    assert registro.prox_acao == ProxAcao.ADC_PDF_ANT_AUT_SEM_PLANILHAS
    assert registro.erro is None
    assert sei.tags == []


def test_download_que_nao_chega_e_erro(sei, alt, monkeypatch):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'selecionar_doc_arvore', lambda driver, numero_sei: None)

    registro = passar()

    assert 'não foi baixada' in registro.erro
    assert sei.pdfs == []
    assert registro.tipo_erro == 'ErroAvaliacao'
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO


def test_download_demorado_e_descartado_e_a_planilha_seguinte_nao_espera(sei, alt, tmp_path, monkeypatch):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    temporario = tmp_path / 'lento.xlsx.crdownload'
    monkeypatch.setattr(planilhas_adc_pdf_ant_aut, 'selecionar_doc_arvore', lambda driver, numero_sei: temporario.touch())

    registro = passar()

    assert 'não foi baixada' in registro.erro
    assert sei.tags == []
    assert not temporario.exists()


def test_controle_nao_apaga_as_colunas_do_fluxo_principal(sei, alt):
    planilha(sei, alt, 'Anexo RELAÇÃO ATENDIMENTO', [BASE])
    colunas = passar().to_dict()

    assert colunas['fluxo'] == 'ADC PDF ANT AUT - PLANILHA ANTIGA BAIXADA DO SEI'
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


@pytest.mark.parametrize(
    ('tipo', 'colunas'),
    [
        ('Titular', {'PRESTADOR': 'A', 'DATA DO ATENDIMENTO': pd.Timestamp(2024, 3, 15), 'PROCEDIMENTO': 'B'}),
        ('Dependente(s)', {'PRESTADOR': 'A', 'MATRICULA DEPENDENTE': 1, 'NOME DEPENDENTE': 'B', 'DATA DO ATENDIMENTO': pd.Timestamp(2024, 3, 15)}),
        ('Beneficiário(s)', {'PRESTADOR': 'A', 'MATRICULA BENEFICIARIO': 1, 'NOME BENEFICIARIO': 'B', 'DATA DO ATENDIMENTO': pd.Timestamp(2024, 3, 15)}),
    ],
)
def test_pdf_termina_com_a_soma_do_valor_pago(tmp_path, monkeypatch, tipo, colunas):
    tabelas = []
    tabela = transformar_xls_em_pdf.Table

    def capturar(dados, *args, **kwargs):
        tabelas.append(dados)
        return tabela(dados, *args, **kwargs)

    monkeypatch.setattr(transformar_xls_em_pdf, 'Table', capturar)
    df = pd.DataFrame([{**colunas, 'VALOR PAGO': valor} for valor in (1000.5, 234.25, 0.0)])

    caminho = transformar_xls_em_pdf.transformar_xls_em_pdf(tit_matricula='123', tit_nome='', tipo=tipo, df=df, path_destino=tmp_path)

    assert caminho.exists()
    ultima_linha = tabelas[-1][-1]
    assert len(tabelas[-1]) == len(df) + 2
    assert ultima_linha[0] == 'TOTAL'
    assert ultima_linha[-1] == '1.234,75'


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


def test_nome_do_titular_aceita_variacoes_do_mesmo_nome(tmp_path):
    linhas = [{**BASE, 'NOME_BENEFICIARIO': nome} for nome in ('FULANO TAL', 'Fulano Tal', 'Fulano de Tál')]
    relatorio = ler_planilha(gravar(tmp_path / 'p.xlsx', linhas), TITULAR)
    assert relatorio.nome_titular == 'Fulano de Tál'


def test_nome_do_titular_com_outras_palavras_usa_o_mais_frequente(tmp_path):
    linhas = [{**BASE, 'NOME_BENEFICIARIO': 'Fulano de Souza'}, BASE, BASE]
    relatorio = ler_planilha(gravar(tmp_path / 'p.xlsx', linhas), TITULAR)
    assert relatorio.nome_titular == 'Fulano de Tal'


def test_rodape_fora_do_padrao_com_a_soma_e_removido(tmp_path):
    rodape = {**dict.fromkeys(BASE), 'REFERENCIA': 'TEXTO', 'COD_PRESTADOR': 'TOTAL', 'VAL_PAGAR': 21.0}
    relatorio = ler_planilha(gravar(tmp_path / 'a.xlsx', [BASE, BASE, rodape]), ANEXO)
    assert len(relatorio.df) == 2


def test_linha_sem_data_que_nao_e_a_soma_continua_erro(tmp_path):
    linha = {**dict.fromkeys(BASE), 'VAL_PAGAR': 99.0}
    with pytest.raises(ErroAvaliacao, match='sem data válida'):
        ler_planilha(gravar(tmp_path / 'a.xlsx', [BASE, BASE, linha]), ANEXO)


def test_planilha_com_mais_de_uma_aba_e_erro(tmp_path):
    caminho = tmp_path / 'a.xlsx'
    with pd.ExcelWriter(caminho) as escritor:
        pd.DataFrame([BASE]).to_excel(escritor, sheet_name='Planilha1', index=False)
        pd.DataFrame([BASE]).to_excel(escritor, sheet_name='Planilha2', index=False)

    with pytest.raises(ErroAvaliacao, match='2 abas'):
        ler_planilha(caminho, ANEXO)


def test_aba_oculta_tambem_conta(tmp_path):
    caminho = gravar(tmp_path / 'a.xlsx', [BASE])
    livro = load_workbook(caminho)
    livro.create_sheet('Oculta').sheet_state = 'hidden'
    livro.save(caminho)

    with pytest.raises(ErroAvaliacao, match='2 abas'):
        ler_planilha(caminho, ANEXO)


def test_anexo_acima_do_limite_de_beneficiarios_e_erro(tmp_path):
    linhas = [{**BASE, 'MATRICULA_BENEFICIARIO': MATRICULA + i} for i in range(planilhas_adc_pdf_ant_aut._MAX_BENEFICIARIOS_ANEXO + 1)]
    with pytest.raises(ErroAvaliacao, match='beneficiários'):
        ler_planilha(gravar(tmp_path / 'a.xlsx', linhas), ANEXO)


def test_anexo_no_limite_de_beneficiarios_e_aceito(tmp_path):
    limite = planilhas_adc_pdf_ant_aut._MAX_BENEFICIARIOS_ANEXO
    linhas = [{**BASE, 'MATRICULA_BENEFICIARIO': MATRICULA + i} for i in range(limite)]
    assert ler_planilha(gravar(tmp_path / 'a.xlsx', linhas), ANEXO).matricula_titular == f'{MATRICULA} e mais {limite - 1}'


def test_download_anterior_que_termina_nao_entra_no_proximo(sei, alt, tmp_path, monkeypatch):
    numero = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    temporario = tmp_path / 'atrasado.xlsx.crdownload'
    temporario.touch()
    dormir = planilhas_adc_pdf_ant_aut.time.sleep

    def terminar(segundos):
        # O download atrasado termina durante a espera
        if temporario.exists():
            temporario.rename(tmp_path / 'atrasado.xlsx')
        dormir(segundos)

    monkeypatch.setattr(planilhas_adc_pdf_ant_aut.time, 'sleep', terminar)

    caminho = planilhas_adc_pdf_ant_aut.baixar_planilha(DriverFalso(), {'numero_sei': numero, 'nome_arvore': 'Planilha'})

    assert caminho.name == f'{numero}_Utilizacao_3542985 (1).xlsx'
    assert (tmp_path / 'atrasado.xlsx').exists()


def test_download_preso_e_descartado_e_nao_para_o_proximo(sei, alt, tmp_path):
    numero = planilha(sei, alt, f'Planilha Utilização Titular - {MATRICULA}', [BASE])
    temporario = tmp_path / 'preso.crdownload'
    temporario.touch()

    caminho = planilhas_adc_pdf_ant_aut.baixar_planilha(DriverFalso(), {'numero_sei': numero, 'nome_arvore': 'Planilha'})

    assert not temporario.exists()
    assert caminho.name.startswith(numero)


def test_navegador_fechado_registra_o_erro_do_processo_e_para_o_loop(alt, tmp_path, monkeypatch):
    # P2 estava em andamento; P3 não é tocado
    assert _executar_ate_fechar(monkeypatch, tmp_path) == [('P1', None), ('P2', 'InvalidSessionIdException')]


def test_navegador_fechado_vira_erro_no_registro(alt, monkeypatch):
    def fechado(driver, num):
        raise InvalidSessionIdException('invalid session id')

    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'acessar_processo', fechado)

    registro = passar()

    assert registro.tipo_erro == 'InvalidSessionIdException'
    assert registro.erro.startswith('invalid session id')


def _executar_ate_fechar(monkeypatch, tmp_path) -> list[tuple]:
    gravados: list[tuple] = []

    class Controle:
        def __init__(self, *args):
            pass

        @staticmethod
        def registrar(linha):
            gravados.append((linha['num_processo'], linha['tipo_erro']))

    class DriverFechavel(DriverFalso):
        fechado = False

        def quit(self):
            self.fechado = True

    def processar(driver, num_processo, *args):
        registro = RegistroAdcPdfAnt(num_processo=num_processo, data_execucao='agora', fluxo='F')
        if num_processo != 'P1':
            registrar_erro(registro, InvalidSessionIdException('invalid session id'))
        return registro

    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'configurar_logging', lambda arquivo: None)
    abas = []
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'ler_processos_a_processar', lambda aba: abas.append(aba) or ['P1', 'P2', 'P3'])
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'PlanilhaControleGeral', Controle)
    driver = DriverFechavel()
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, 'abrir_sei', lambda unidade, download_dir=None: driver)
    monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, '_processar_linha', processar)
    for constante in ('DIR_INPUTS', 'DIR_CONTROLE', 'DIR_LOG'):
        monkeypatch.setattr(main_geacs_adc_pdf_ant_aut, constante, tmp_path)

    main_geacs_adc_pdf_ant_aut.executar('geacs_adc_pdf_ant_aut', 'F', 'agora', tmp_path / 'x.log', [], lambda driver, registro: None)

    assert driver.fechado
    assert abas == ['geacs_adc_pdf_ant_aut']
    return gravados


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
