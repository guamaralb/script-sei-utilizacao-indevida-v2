"""Fluxo GEACS TODAS INFOS (main_geacs_todas_infos.py e todas_infos.py): retorno
final à APIS (MemoApisComTodasAsInformacoes), com o SEI simulado."""

from pathlib import Path

import main_geacs_todas_infos as fluxo
import pandas as pd
import pytest
import todas_infos
from constantes import UNIDADE_DEPROC, UNIDADE_GEACS
from coparticipacao_deproc import apurar_coparticipacao
from Registro import ProxAcao
from tags import (
    TAG_AGUARDA_DEPROC_COPARTICIPACAO,
    TAG_ENCAMINHADO_APIS_TODAS_INFOS,
    TAG_NO_BLOCO_APIS_TODAS_INFOS,
    TAG_PROCESSO_NOVO,
)
from transformar_xls_em_pdf import transformar_xls_em_pdf

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import ASSUNTO_MEMO_DISA_VALIDAR_CONSTA
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import MemoGeacsCalculoCopa
from tests.sei_falso import MANTIS_CREDENCIADA_TITULAR_USOU, MANTIS_DUAS_REDES, DriverFalso, SEIFalso, bases
from tests.test_fluxo_deproc_calcula_copa import LINHAS, _base, _linha

PROCESSO = 'PROC'
ASSINATURA = 'Documento assinado eletronicamente por Danúbia Lacerda Gomes de Oliveira, Diretora, em 12/11/2026'
NOME_PDF_RC_TIT = 'PDF Utilização Tit. RC - 12345678 - 20261110_101010'


def _dados() -> DadosUI:
    return DadosUI(nome_titular='FULANO', matricula_titular='1234567 / 8', periodo_titular='(01/2024 a 06/2024)', periodo_dependentes=False, matriculas_dependentes='555')


class SEITodasInfos(SEIFalso):
    def __init__(self):
        super().__init__()
        # Total da linha TOTAL de cada PDF do MANTIS (pelo número SEI)
        self.totais_pdf: dict[str, float] = {}

    def pdf_rc_titular(self, total: float = 10.0) -> str:
        numero = self.novo_doc(NOME_PDF_RC_TIT, UNIDADE_GEACS, '')
        self.totais_pdf[numero] = total
        return numero

    def memo_deproc_geacs(self) -> str:
        return self.novo_doc('Memorando 2', UNIDADE_GEACS, f'Assunto: {ASSUNTO_MEMO_DEPROC}\nPara: IPSEMG/DEPROC-Utilização')

    def memo_calculo_copa(self, base: pd.DataFrame, *, assinado: bool = True, texto: str | None = None) -> str:
        """Memo de resultado da DEPROC (e o relatório, com coparticipação),
        com o texto do MemoGeacsCalculoCopa."""
        resultado = apurar_coparticipacao(base, PROCESSO, _dados())
        relatorio = self.novo_doc('PDF Coparticipação - 12345678 - 20261112_101500', UNIDADE_DEPROC, '') if resultado.tem_coparticipacao else None
        memo_deproc = {'numero_sei': '1', 'nome_arvore': 'Memorando 2348', 'unidade': UNIDADE_GEACS}
        if texto is None:
            memo = MemoGeacsCalculoCopa(resultado=resultado, doc_relatorio=relatorio, memo_deproc_geacs=memo_deproc, data_geracao_bases='06/11/2026', nome_signatario='D.', cargo_signatario='DEPROC')
            texto = f'Assunto: {memo.assunto}\n{memo.texto_principal()}'
        return self.novo_doc('Memorando 120', UNIDADE_DEPROC, f'{texto}\n{ASSINATURA if assinado else ""}')

    def processo_pronto(self, base: pd.DataFrame, *, total_pdf: float = 10.0) -> None:
        """Retorno da DEPROC no caminho direto: 01 e 01.10.1, relatório RC e
        memo DEPROC da GEACS, memo de resultado da DEPROC."""
        self.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_DEPROC_COPARTICIPACAO]
        self.pdf_rc_titular(total_pdf)
        self.memo_deproc_geacs()
        self.memo_calculo_copa(base)

    def instalar(self, monkeypatch) -> None:
        super().instalar(monkeypatch)
        monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(self.tags))
        monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(fluxo, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in self.docs])
        monkeypatch.setattr(fluxo, 'garantir_marcadores_no_sei', lambda driver, lista: None)
        monkeypatch.setattr(todas_infos, 'ler_texto_doc', lambda driver, doc: self.textos[doc['numero_sei']])
        monkeypatch.setattr(todas_infos, 'baixar_pdf', lambda driver, doc: doc['numero_sei'].encode())
        monkeypatch.setattr(todas_infos, 'total_do_pdf', lambda conteudo: self.totais_pdf[conteudo.decode()])


@pytest.fixture
def sei(monkeypatch):
    sei = SEITodasInfos()
    sei.instalar(monkeypatch)
    sei.novo_processo()
    return sei


def _passar(sei, base, bases_mantis=MANTIS_CREDENCIADA_TITULAR_USOU, linha_controle=None, carregadas=None):
    """base: a base DEPROC de qualquer ano; linha_controle: a linha do
    processo na planilha de controle (padrão: base de 2019)."""
    sei.memos_passagem = 0
    if linha_controle is None:
        linha_controle = {'ano_processo': '2019', 'data_geracao_base_processo': '06/11/2026'}

    def carregar(arquivo):
        if carregadas is not None:
            carregadas.append(arquivo.name)
        return base

    return fluxo._processar_linha(DriverFalso(), PROCESSO, bases(tit_usou=False), bases_mantis, fluxo.BasesDeprocPorAno(carregar), linha_controle)


def _memos_apis(sei) -> list[str]:
    return [sei.textos[d['numero_sei']] for d in sei.docs if d['unidade'] == UNIDADE_GEACS and ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES in sei.textos[d['numero_sei']]]


# --- caminho direto à DEPROC --------------------------------------------------


def test_cria_memo_a_apis_com_todas_as_informacoes(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    registro = _passar(sei, base)

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS
    assert registro.caminho_todas_infos == 'DEPROC'
    assert registro.memo_calculo_copa_assinado is True
    # O 01.12 substitui o 01.10.1 (estado)
    assert sei.tags == [TAG_PROCESSO_NOVO, TAG_NO_BLOCO_APIS_TODAS_INFOS]
    (texto,) = _memos_apis(sei)
    rc_titular = sei.numero_sei('PDF Utilização Tit. RC')
    relatorio_copart = sei.numero_sei('PDF Coparticipação')
    # Titular: RC do MANTIS (R$ 10,00) e coparticipação em aberto da DEPROC
    # (apurado R$ 18,50, dos quais R$ 4,00 já descontados em folha)
    assert '<tr><td>F. / 1234567-8</td><td>R$ 10,00</td><td>R$ 0,00</td><td>R$ 10,00</td><td>R$ 14,50</td><td>R$ 24,50</td></tr>' in texto
    # Dependente: só coparticipação (nome da base DEPROC, matrícula com DV)
    assert '<tr><td>B. / 555-9</td><td>R$ 0,00</td><td>R$ 0,00</td><td>R$ 0,00</td><td>R$ 3,50</td><td>R$ 3,50</td></tr>' in texto
    assert '<td><strong>R$ 18,00</strong></td><td><strong>R$ 28,00</strong></td></tr>' in texto
    assert 'Coparticipação em aberto' in texto
    assert f'<tr><td>F. / 1234567-8</td><td>Documento {rc_titular}</td><td>–</td></tr>' in texto
    assert f'consta do documento {relatorio_copart}' in texto
    assert 'ausência de atendimento identificado' in texto
    assert registro.doc_coparticipacao_sei == relatorio_copart
    assert registro.relatorios_rc_sei == [rc_titular]
    assert registro.valor_total_copart_todas_infos == 18.0
    assert registro.memo_apis_todas_infos_sei is not None


@pytest.mark.parametrize(
    ('linha_controle', 'arquivo'),
    [
        ({'ano_processo': '2020', 'data_geracao_base_processo': '16/11/2026'}, 'copa-MANTIS11281-base_2020-16_11_2026.xlsx'),
        # Ano lido do Excel como número
        ({'ano_processo': 2019.0, 'data_geracao_base_processo': '06/11/2026'}, 'copa-MANTIS11281-base_2019-06_11_2026.xlsx'),
        ({'ano_processo': '2021', 'data_geracao_base_processo': '23/11/2026'}, 'copa-MANTIS11281-base_2021-23_11_2026.xlsx'),
    ],
)
def test_usa_a_base_deproc_do_ano_da_planilha_de_controle(sei, tmp_path, linha_controle, arquivo):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    carregadas = []
    registro = _passar(sei, base, linha_controle=linha_controle, carregadas=carregadas)

    assert registro.erro is None
    assert carregadas == [arquivo]
    # A única coluna de ano é a ano_processo (o fluxo não a grava)
    assert 'ano_processo' not in registro.to_dict()


@pytest.mark.parametrize(
    ('linha_controle', 'mensagem'),
    [
        ({}, 'não registrada na planilha de controle'),
        ({'data_geracao_base_processo': '01/01/2026'}, 'não registrada na planilha de controle'),
        ({'ano_processo': '2018'}, 'não registrada na planilha de controle'),
        # Só o ano ou só a data: não procura a base na pasta
        ({'ano_processo': '2021'}, 'não registrada na planilha de controle'),
        ({'data_geracao_base_processo': '16/11/2026'}, 'não registrada na planilha de controle'),
        # As colunas antigas (até 27/11/2026) não são lidas: a leitura da
        # planilha as leva para ano_processo e data_geracao_base_processo
        ({'ano_base_deproc': '2019', 'data_geracao_base_deproc': '06/11/2026'}, 'não registrada na planilha de controle'),
        ({'ano_processo': '2019', 'data_geracao_base_processo': '07/11/2026'}, 'não encontrada: copa-MANTIS11281-base_2019-07_11_2026.xlsx'),
    ],
)
def test_sem_ano_da_base_deproc_para_sem_acao(sei, tmp_path, linha_controle, mensagem):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    carregadas = []
    registro = _passar(sei, base, linha_controle=linha_controle, carregadas=carregadas)

    assert registro.tipo_erro == 'SemAnoBaseDeproc'
    assert mensagem in registro.erro
    assert carregadas == []
    assert _memos_apis(sei) == []
    assert TAG_AGUARDA_DEPROC_COPARTICIPACAO in sei.tags


def test_planilha_de_controle_nao_lida(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    registro = fluxo._processar_linha(DriverFalso(), PROCESSO, bases(tit_usou=False), MANTIS_CREDENCIADA_TITULAR_USOU, fluxo.BasesDeprocPorAno(lambda arquivo: base), None)

    assert registro.tipo_erro == 'SemAnoBaseDeproc'
    assert 'Planilha de controle não lida' in registro.erro


def test_memo_no_bloco_ou_encaminhado_so_registra_a_prox_acao(sei, tmp_path):
    sei.tags = [TAG_PROCESSO_NOVO, TAG_NO_BLOCO_APIS_TODAS_INFOS]
    assert _passar(sei, _base(tmp_path)).prox_acao == ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS
    sei.tags = [TAG_PROCESSO_NOVO, TAG_ENCAMINHADO_APIS_TODAS_INFOS]
    registro = _passar(sei, _base(tmp_path))

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert _memos_apis(sei) == []


@pytest.mark.parametrize('marcadores', [[], [TAG_PROCESSO_NOVO], [TAG_PROCESSO_NOVO, 'v2: 01.10.B - No Bloco DEPROC: Coparticipação']])
def test_sem_aguarda_deproc_para_sem_acao(sei, tmp_path, marcadores):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    sei.tags = list(marcadores)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'SemAguardaDeproc'
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO
    assert _memos_apis(sei) == []
    assert sei.tags == marcadores


@pytest.mark.parametrize(
    ('preparar', 'mensagem'),
    [
        (lambda sei, base: sei.memo_calculo_copa(base, assinado=False), 'ainda não assinado'),
        (lambda sei, base: None, 'Memo de resultado da DEPROC'),
    ],
)
def test_sem_memo_de_resultado_da_deproc_assinado(sei, tmp_path, preparar, mensagem):
    base = _base(tmp_path)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    sei.pdf_rc_titular()
    preparar(sei, base)
    registro = _passar(sei, base)

    assert mensagem in registro.erro
    assert _memos_apis(sei) == []
    assert TAG_AGUARDA_DEPROC_COPARTICIPACAO in sei.tags


def test_coparticipacao_do_memo_diferente_do_recalculo(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    # A base DEPROC mudou depois do memo da DEPROC
    base_nova = _base(tmp_path, [*LINHAS, _linha(12345678, 'TITULAR', '2024-05-05', calculado=1.0)])
    registro = _passar(sei, base_nova)

    assert registro.tipo_erro == 'ValoresDivergentes'
    assert 'coparticipação de 12345678: memo da DEPROC R$ 18,50, recálculo R$ 19,50' in registro.erro
    assert 'coparticipação total' in registro.erro
    assert _memos_apis(sei) == []
    assert TAG_AGUARDA_DEPROC_COPARTICIPACAO in sei.tags


def test_memo_da_deproc_sem_valor_em_aberto_com_desconto_no_recalculo(sei, tmp_path):
    # Memo da DEPROC só com a tabela por matrícula: o recálculo tem R$ 4,00
    # descontados em folha, e o em aberto não pode ser conferido
    base = _base(tmp_path)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    sei.pdf_rc_titular()
    sei.memo_deproc_geacs()
    sei.novo_doc('PDF Coparticipação - 12345678 - 20261112_101500', UNIDADE_DEPROC, '')
    texto = 'Assunto: Retorno do levantamento de coparticipação – utilização indevida da assistência à saúde\nF. 1234567-8 Titular R$ 18,50\nB. 555-9 Dependente R$ 3,50\nTotal consolidado R$ 22,00'
    sei.memo_calculo_copa(base, texto=texto)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'ValoresDivergentes'
    assert 'coparticipação em aberto: memo da DEPROC sem o valor em aberto (considerado o total apurado) R$ 22,00, recálculo R$ 18,00' in registro.erro
    assert _memos_apis(sei) == []


def test_total_do_pdf_diferente_do_recalculo(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base, total_pdf=12.0)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'ValoresDivergentes'
    assert 'Rede Credenciada (titular)' in registro.erro
    assert 'R$ 12,00, recálculo R$ 10,00' in registro.erro
    assert registro.divergencias_todas_infos
    assert _memos_apis(sei) == []


def test_atendimento_sem_pdf_na_rodada(sei, tmp_path):
    base = _base(tmp_path)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    sei.memo_deproc_geacs()
    sei.memo_calculo_copa(base)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'ValoresDivergentes'
    assert 'sem PDF na rodada' in registro.erro


def test_uso_da_rede_propria_na_base_disa_sem_passar_pela_disa(sei, tmp_path, monkeypatch):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    monkeypatch.setattr(todas_infos, 'avaliar_uso_rede_propria_disa', lambda matriculas, bases: type('Uso', (), {'alguem_usou': True})())
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'ValoresDivergentes'
    assert 'uso da rede própria na base DISA sem passagem pela DISA' in registro.erro


def test_uso_da_rede_propria_so_no_mantis_vai_ao_memo(sei, tmp_path):
    # Processo que foi direto à DEPROC com uso da rede própria só no MANTIS
    base = _base(tmp_path)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    rp = sei.novo_doc('PDF Utilização Dep. RP - 12345678 - 20261110_101010', UNIDADE_GEACS, '')
    sei.totais_pdf[rp] = 10.0
    sei.pdf_rc_titular()
    sei.memo_deproc_geacs()
    sei.memo_calculo_copa(base)
    registro = _passar(sei, base, bases_mantis=MANTIS_DUAS_REDES)

    assert registro.erro is None
    assert registro.valor_total_rp_todas_infos == 10.0
    (texto,) = _memos_apis(sei)
    assert 'base de faturamento do SADS consultada pela GEACS, conforme os demonstrativos relacionados abaixo' in texto
    assert f'<td>Documento {rp}</td>' in texto


def test_sem_coparticipacao_cita_o_memo_da_deproc(sei, tmp_path):
    # Só atendimento fora do período: memo da DEPROC sem coparticipação
    base = _base(tmp_path, [LINHAS[2]])
    sei.processo_pronto(base)
    registro = _passar(sei, base)

    assert registro.erro is None
    assert registro.doc_coparticipacao_sei == registro.memo_calculo_copa_sei
    (texto,) = _memos_apis(sei)
    assert f'consta do documento {registro.memo_calculo_copa_sei}' in texto
    assert '<td>F. / 1234567-8</td><td>R$ 10,00</td><td>R$ 0,00</td><td>R$ 10,00</td><td>R$ 0,00</td>' in texto


def test_retomada_memo_ja_na_rodada_so_recebe_o_marcador(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES)
    registro = _passar(sei, base)

    assert registro.erro is None
    assert registro.memo_apis_todas_infos_na_arvore is True
    assert registro.memo_apis_todas_infos_criado is False
    assert sei.memos_passagem == 0
    assert TAG_NO_BLOCO_APIS_TODAS_INFOS in sei.tags


def test_processo_fechado_nao_reabre(sei, tmp_path):
    base = _base(tmp_path)
    sei.processo_pronto(base)
    sei.processo_fechado = True
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert _memos_apis(sei) == []


# --- caminho pela DISA (TODO: leitura da resposta da DISA) ---------------------


def test_memo_a_disa_sem_resposta_da_disa(sei, tmp_path):
    base = _base(tmp_path)
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA)
    sei.processo_pronto(base)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'RespostaDisaPendente'
    assert registro.caminho_todas_infos == 'DISA'
    assert registro.memo_disa_geacs_sei is not None
    assert _memos_apis(sei) == []


def test_resposta_da_disa_ainda_nao_e_lida(sei, tmp_path):
    base = _base(tmp_path)
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA)
    resposta = sei.novo_doc('Memorando 45', 'IPSEMG/DISA-UTI-INDEV', 'Levantamento da rede própria')
    sei.processo_pronto(base)
    registro = _passar(sei, base)

    assert registro.tipo_erro == 'LeituraDisaNaoImplementada'
    assert registro.resposta_disa_sei == resposta
    assert _memos_apis(sei) == []
    assert TAG_AGUARDA_DEPROC_COPARTICIPACAO in sei.tags


# --- leitura dos documentos ------------------------------------------------------


def test_le_a_coparticipacao_do_texto_do_sei():
    # Como o Selenium devolve o texto da tabela (células separadas por espaço)
    texto = (
        'Os valores apurados estão consolidados por matrícula/vínculo a seguir, de 01/2024 a 06/2024:\n'
        'Beneficiário Matrícula Vínculo Valor total de coparticipação apurado\n'
        'F.S. 1234567-8 Titular R$ 1.018,50\n'
        'B. 555-9 Dependente R$ 3,50\n'
        'Total consolidado R$ 1.022,00\n'
    )
    copart = todas_infos.ler_coparticipacao_do_memo(texto)

    assert copart.por_matricula == {'12345678': 1018.5, '5559': 3.5}
    assert copart.total == 1022.0
    # Sem a tabela de totais: nada descontado informado, em aberto = apurado
    assert copart.em_aberto == 1022.0
    assert not copart.em_aberto_no_memo

    com_totais = todas_infos.ler_coparticipacao_do_memo(
        texto + 'Descrição Valor\nValor total de coparticipação apurado R$ 1.022,00\nValor efetivamente descontado R$ 22,00\nValor total em aberto R$ 1.000,00\n'
    )
    assert com_totais.total == 1022.0
    assert com_totais.em_aberto == 1000.0
    assert com_totais.em_aberto_no_memo
    assert todas_infos.ler_coparticipacao_do_memo('Não foram identificados atendimentos com coparticipação').sem_coparticipacao


def test_le_o_total_do_pdf_do_mantis(tmp_path):
    df = pd.DataFrame([
        {'PRESTADOR': 'HOSPITAL', 'DATA DO ATENDIMENTO': pd.Timestamp('2024-03-01'), 'PROCEDIMENTO': 'CONSULTA', 'VALOR PAGO': 1234.5},
        {'PRESTADOR': 'CLÍNICA', 'DATA DO ATENDIMENTO': pd.Timestamp('2024-04-01'), 'PROCEDIMENTO': 'EXAME', 'VALOR PAGO': 10.25},
    ])
    caminho = transformar_xls_em_pdf(tit_matricula='12345678', tit_nome='FULANO', tipo='Titular', df=df, path_destino=tmp_path, rede='Rede Credenciada')

    assert todas_infos.total_do_pdf(Path(caminho).read_bytes()) == 1244.75
