"""Fluxo DEPROC (main_deproc_calcula_copa.py, coparticipacao_deproc.py e
relatorio_deproc.py), com o SEI simulado e uma base DEPROC gerada no teste."""

from datetime import datetime
from pathlib import Path

import main_deproc_calcula_copa
import pandas as pd
import pytest
import relatorio_deproc
from constantes import UNIDADE_DEPROC, UNIDADE_GEACS
from coparticipacao_deproc import (
    COL_VALOR,
    SITUACAO_NAO_DESCONTADO_SALDO_NAO_QUITADO,
    SITUACAO_RATEIO_SALDO_NAO_QUITADO,
    MatriculasDivergentes,
    apurar_coparticipacao,
    carregar_base_deproc,
)
from rede_propria import ErroAvaliacao
from Registro import ProxAcao
from tags import TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA, TAG_DEPROC_RELATORIO_ANEXADO, TAG_DEPROC_TRATADO, TAGS_DEPROC

from script_sei_utilizacao_indevida_v2.memorandos import MemoGeacsCalculoCopa
from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import ASSUNTO_MEMO_GEACS_CALCULO_COPA
from tests.sei_falso import DriverFalso, SEIFalso

PROCESSO = 'PROC'
# Base com DV; o memo da APIS (sei_falso.MEMO_APIS) tem o titular com DV
# ("1234567 / 8") e o dependente sem (555)
TITULAR = 12345678
DEPENDENTE = 5559

ASSINATURA = 'Documento assinado eletronicamente por Bruna Miiller Lavarini, Gerente, em 01/11/2026'


def _linha(beneficiario, categoria, data, *, sei=PROCESSO, titular=TITULAR, **valores):
    return {
        'SEI': sei,
        'MATRICULA_TITULAR': titular,
        'NOME_TITULAR': 'FULANO',
        'MATRICULA_BENEFICIARIO': beneficiario,
        'NOME_BENEFICIARIO': 'FULANO' if categoria == 'TITULAR' else 'BELTRANO',
        'TITULAR_DEPENDENTE': categoria,
        'DATA_ATENDIMENTO': datetime.fromisoformat(data),
        'COD_PRESTADOR': 123.0,
        'NOME_PRESTADOR': 'HOSPITAL & CIA',
        'QUANTIDADE': 1,
        'GRUPO_COPARTICIPACAO': 'CONSULTAS',
        'VALOR_APURADO_SISTEMA': valores.get('apurado'),
        'VALOR_DESCONTADO_FOLHA': valores.get('descontado'),
        'SALDO_APOS_COMPETENCIA': valores.get('saldo'),
        'CALCULO_COPARTICIPACAO': valores.get('calculado'),
        'SITUACAO': valores.get('situacao', 'NAO APURADO PELO SISTEMA, CALCULADO'),
    }


LINHAS = [
    # Titular: dentro do período (01/2024 a 06/2024) e fora dele
    _linha(TITULAR, 'TITULAR', '2024-03-01', calculado=8.5),
    _linha(TITULAR, 'TITULAR', '2024-04-10', apurado=10.0, descontado=4.0, saldo=6.0, situacao=SITUACAO_RATEIO_SALDO_NAO_QUITADO),
    _linha(TITULAR, 'TITULAR', '2023-01-01', calculado=100.0),
    # Dependente: saldo não quitado e isento (sem valor)
    _linha(DEPENDENTE, 'DEPENDENTE', '2024-02-01', apurado=3.5, descontado=0.0, saldo=3.5, situacao=SITUACAO_NAO_DESCONTADO_SALDO_NAO_QUITADO),
    _linha(DEPENDENTE, 'DEPENDENTE', '2024-02-02', situacao='ISENTO NO SADS: SEM VALOR'),
    # Outro processo
    _linha(999, 'TITULAR', '2024-03-01', sei='OUTRO', titular=999, calculado=1.0),
]


def _base(tmp_path: Path, linhas=LINHAS) -> pd.DataFrame:
    arquivo = tmp_path / 'base_deproc.xlsx'
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame(linhas).to_excel(writer, sheet_name='Resultado', index=False)
        pd.DataFrame({'DE': ['MATRÍCULA']}).to_excel(writer, sheet_name='DE-PARA', index=False)
    return carregar_base_deproc(arquivo)


def _dados(**kwargs) -> DadosUI:
    padrao = {
        'nome_titular': 'FULANO',
        'matricula_titular': '1234567 / 8',
        'periodo_titular': '(01/2024 a 06/2024)',
        'periodo_dependentes': False,
        'matriculas_dependentes': '555',
    }
    return DadosUI(**{**padrao, **kwargs})


# --- apuração ---------------------------------------------------------------


def test_apura_linhas_do_processo_no_periodo(tmp_path):
    resultado = apurar_coparticipacao(_base(tmp_path), PROCESSO, _dados())

    assert resultado.linhas_processo == 5
    assert resultado.linhas_fora_periodo == 1
    atendimentos = resultado.atendimentos
    assert list(atendimentos.columns) == ['MATRÍCULA', 'NOME BENEFICIÁRIO', 'CATEGORIA', 'DATA ATENDIMENTO', 'PRESTADOR', 'PROCEDIMENTO', 'QTDE', 'VALOR DA COPARTICIPAÇÃO']
    # Titular primeiro; valor = U + AI; prestador = código - nome
    assert list(atendimentos['MATRÍCULA']) == ['12345678', '12345678', '5559', '5559']
    assert list(atendimentos[COL_VALOR]) == [8.5, 10.0, 3.5, 0.0]
    assert atendimentos['PRESTADOR'].iloc[0] == '123 - HOSPITAL & CIA'
    assert [(s.matricula, s.atendimentos, s.valor) for s in resultado.subtotais] == [('12345678', 2, 18.5), ('5559', 2, 3.5)]


def test_totais_seguem_a_formula_da_de_para(tmp_path):
    totais = apurar_coparticipacao(_base(tmp_path), PROCESSO, _dados()).totais

    assert totais.coparticipacao == 22.0
    # Só a parte descontada do rateio não quitado (4): o apurado das linhas
    # com saldo não quitado não entra inteiro
    assert totais.descontado == 4.0
    # CALCULO_COPARTICIPACAO (8,5) + saldo das duas situações não quitadas (6 + 3,5)
    assert totais.em_aberto == 18.0
    assert totais.descontado + totais.em_aberto == totais.coparticipacao


def test_periodo_proprio_do_dependente(tmp_path):
    dados = _dados(periodos_por_dependente={'555': '01/02/2024 a 01/02/2024'})
    resultado = apurar_coparticipacao(_base(tmp_path), PROCESSO, dados)

    assert list(resultado.atendimentos['DATA ATENDIMENTO'].dt.strftime('%d/%m')) == ['01/03', '10/04', '01/02']


def test_matricula_da_base_fora_do_memo(tmp_path):
    with pytest.raises(MatriculasDivergentes) as erro:
        apurar_coparticipacao(_base(tmp_path), PROCESSO, _dados(matriculas_dependentes='777'))
    assert erro.value.divergentes == ['5559 (dependente)']

    with pytest.raises(MatriculasDivergentes) as erro:
        apurar_coparticipacao(_base(tmp_path), PROCESSO, _dados(matricula_titular='7654321'))
    assert erro.value.divergentes == ['12345678 (titular)']


def test_processo_fora_da_base(tmp_path):
    with pytest.raises(ErroAvaliacao, match='não consta na base DEPROC'):
        apurar_coparticipacao(_base(tmp_path), 'NENHUM', _dados())


def test_gera_pdf(tmp_path):
    dados = _dados()
    resultado = apurar_coparticipacao(_base(tmp_path), PROCESSO, dados)
    caminho = relatorio_deproc.gerar_pdf_deproc(resultado, dados, PROCESSO, tmp_path / 'pdf')

    assert caminho.name == 'Coparticipacao-12345678.pdf'
    assert caminho.stat().st_size > 0


def test_nome_do_relatorio_cabe_no_sei():
    nome = f'{relatorio_deproc.inicio_nome_relatorio_deproc("1234567 / 8")} - 20261110_123456'
    assert nome == 'Coparticipação - 12345678 - 20261110_123456'
    assert len(f'PDF {nome}') <= 50


# --- fluxo com o SEI simulado -----------------------------------------------


class SEIDeproc(SEIFalso):
    def memo_deproc_geacs(self, *, assinado: bool = True) -> str:
        return self.novo_doc('Memorando 2', UNIDADE_GEACS, f'Assunto: {ASSUNTO_MEMO_DEPROC}\nPara: IPSEMG/DEPROC-Utilização\n{ASSINATURA if assinado else ""}')

    def _incluir_memo_deproc(self, driver, **kwargs):
        self.memos_passagem += 1
        if self.falhar_memo_n == self.memos_passagem:
            raise RuntimeError('falha simulada ao criar memo')
        self.novo_doc('Memorando 3', UNIDADE_DEPROC, f'Assunto: {kwargs["assunto"]}\n{kwargs["texto_principal"]}')

    def _garantir(self, driver, lista):
        self.garantidos = list(lista)

    @property
    def assuntos_memos_deproc(self) -> list[str]:
        return [self.textos[d['numero_sei']].splitlines()[0].removeprefix('Assunto: ') for d in self.docs if d['unidade'] == UNIDADE_DEPROC and 'Memorando' in d['nome_arvore']]

    def instalar(self, monkeypatch) -> None:
        super().instalar(monkeypatch)
        monkeypatch.setattr(main_deproc_calcula_copa, 'acessar_processo', lambda driver, num: None)
        monkeypatch.setattr(main_deproc_calcula_copa, 'listar_marcadores', lambda driver: list(self.tags))
        monkeypatch.setattr(main_deproc_calcula_copa, 'garantir_marcadores_no_sei', self._garantir)
        monkeypatch.setattr(main_deproc_calcula_copa, 'tem_incluir_documento', lambda driver: not self.processo_fechado)
        monkeypatch.setattr(main_deproc_calcula_copa, 'listar_documentos_arvore', lambda driver: [dict(doc) for doc in self.docs])
        monkeypatch.setattr(main_deproc_calcula_copa, 'BLOCO_MEMO_GEACS_CALCULO_COPA', 1)
        monkeypatch.setattr(main_deproc_calcula_copa, 'NOME_SIGNATARIO_DEPROC', 'Signatário DEPROC')
        monkeypatch.setattr(MemoGeacsCalculoCopa, 'TEXTO_DEFINIDO', True)
        monkeypatch.setattr('memos_sei.incluir_doc_sei_memo', self._incluir_memo_deproc)
        monkeypatch.setattr(relatorio_deproc, 'anexar_pdf', lambda driver, num, caminho, data: self.novo_doc(f'PDF {num}', UNIDADE_DEPROC, ''))
        monkeypatch.setattr(relatorio_deproc, 'gerar_pdf_deproc', lambda *args: Path('relatorio.pdf'))


def _passar(sei, base):
    """Uma passagem do processo pelo main_deproc_calcula_copa.py."""
    sei.memos_passagem = 0
    return main_deproc_calcula_copa._processar_linha(DriverFalso(), PROCESSO, base)


@pytest.fixture
def sei(monkeypatch):
    sei = SEIDeproc()
    sei.instalar(monkeypatch)
    sei.novo_processo()
    return sei


def test_cria_relatorio_e_memo_de_resultado(sei, tmp_path):
    sei.memo_deproc_geacs()
    registro = _passar(sei, _base(tmp_path))

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO
    assert registro.memo_deproc_assinado is True
    assert [nome.rsplit(' - ', 1)[0] for nome in sei.nomes if nome.startswith('PDF ')] == ['PDF Coparticipação - 12345678']
    assert sei.assuntos_memos_deproc == [ASSUNTO_MEMO_GEACS_CALCULO_COPA]
    texto = sei.textos[registro.memo_deproc_resultado_sei]
    assert f'documento {registro.relatorio_deproc_sei}' in texto
    assert 'R$ 22,00' in texto
    assert registro.atendimentos_deproc == 4
    # 1.1 entra depois do relatório e sai quando o 1.2 entra (depois do memo)
    assert registro.marcadores_adicionados == [TAG_DEPROC_TRATADO, TAG_DEPROC_RELATORIO_ANEXADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]
    assert registro.marcadores_removidos == [TAG_DEPROC_RELATORIO_ANEXADO]
    assert sei.tags == [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]
    assert sei.garantidos == list(TAGS_DEPROC)

    # Nova passagem: memo no bloco (01.02), nada é lido nem recriado
    registro = _passar(sei, _base(tmp_path))
    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO
    assert registro.memo_apis_sei is None
    assert len(sei.assuntos_memos_deproc) == 1

    # Assinado: quem assina troca o 01.02 pelo 01.02.1 (manual)
    sei.tags = [TAG_DEPROC_TRATADO, TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA]
    registro = _passar(sei, _base(tmp_path))
    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.DEPROC_MEMO_ENCAMINHADO
    assert registro.marcadores_adicionados == []
    assert len(sei.assuntos_memos_deproc) == 1


def test_retomada_pelo_relatorio_anexado(sei, tmp_path):
    sei.memo_deproc_geacs()
    sei.falhar_memo_n = 1
    registro = _passar(sei, _base(tmp_path))
    assert registro.tipo_erro == 'RuntimeError'
    assert sei.tags == [TAG_DEPROC_TRATADO, TAG_DEPROC_RELATORIO_ANEXADO]

    sei.falhar_memo_n = None
    registro = _passar(sei, _base(tmp_path))
    assert registro.erro is None
    assert registro.relatorio_deproc_na_arvore
    assert len([nome for nome in sei.nomes if nome.startswith('PDF ')]) == 1
    assert sei.tags == [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]


def test_marcadores_da_deproc_inconsistentes_param_sem_acao(sei, tmp_path):
    sei.memo_deproc_geacs()
    sei.tags = [TAG_DEPROC_RELATORIO_ANEXADO]
    registro = _passar(sei, _base(tmp_path))

    assert registro.tipo_erro == 'MarcadoresInconsistentes'
    assert registro.prox_acao == ProxAcao.VERIFICAR_MARCADORES
    assert sei.assuntos_memos_deproc == []


def test_sem_atendimento_no_periodo_memo_sem_relatorio(sei, tmp_path):
    sei.memo_deproc_geacs()
    registro = _passar(sei, _base(tmp_path, [LINHAS[2]]))

    assert registro.erro is None
    assert not any(nome.startswith('PDF ') for nome in sei.nomes)
    assert 'Não foram identificados atendimentos' in sei.textos[registro.memo_deproc_resultado_sei]
    # Sem relatório, sem o 1.1
    assert sei.tags == [TAG_DEPROC_TRATADO, TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]


@pytest.mark.parametrize(
    ('preparar', 'mensagem'),
    [
        (lambda sei: sei.memo_deproc_geacs(assinado=False), 'ainda não assinado'),
        (lambda sei: None, 'Memo DEPROC da GEACS não encontrado'),
    ],
)
def test_sem_memo_deproc_assinado_nada_e_criado(sei, tmp_path, preparar, mensagem):
    preparar(sei)
    registro = _passar(sei, _base(tmp_path))

    assert mensagem in registro.erro
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO
    assert sei.assuntos_memos_deproc == []
    assert sei.tags == []


def test_matricula_divergente_registrada_sem_acao(sei, tmp_path):
    sei.memo_deproc_geacs()
    linhas = [*LINHAS, _linha(4444, 'DEPENDENTE', '2024-02-01', calculado=1.0)]
    registro = _passar(sei, _base(tmp_path, linhas))

    assert registro.tipo_erro == 'MatriculasDivergentes'
    assert registro.to_dict()['matriculas_divergentes_deproc'] == '4444 (dependente)'
    assert sei.assuntos_memos_deproc == []


def test_texto_pendente_ou_bloco_ausente_param_antes_do_relatorio(sei, tmp_path, monkeypatch):
    sei.memo_deproc_geacs()
    monkeypatch.setattr(MemoGeacsCalculoCopa, 'TEXTO_DEFINIDO', False)
    registro = _passar(sei, _base(tmp_path))
    assert registro.tipo_erro == 'TextoMemoPendente'

    monkeypatch.setattr(MemoGeacsCalculoCopa, 'TEXTO_DEFINIDO', True)
    monkeypatch.setattr(main_deproc_calcula_copa, 'BLOCO_MEMO_GEACS_CALCULO_COPA', None)
    registro = _passar(sei, _base(tmp_path))
    assert 'Bloco do memo de resultado' in registro.erro
    assert not any(nome.startswith('PDF ') for nome in sei.nomes)


def test_processo_fechado_na_deproc_nao_e_reaberto(sei, tmp_path):
    sei.memo_deproc_geacs()
    sei.processo_fechado = True
    registro = _passar(sei, _base(tmp_path))

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert sei.reaberturas == 0


def test_planilha_de_controle_com_colunas_dos_marcadores_da_deproc(sei, tmp_path):
    sei.memo_deproc_geacs()
    colunas = _passar(sei, _base(tmp_path)).to_dict()

    # Os marcadores da GEACS (outra unidade) ficam como estão na planilha
    assert [c for c in colunas if c.startswith(('tag_', 'marcadores_'))] == [
        'marcadores_deproc_sei',
        'marcadores_deproc_adicionados',
        'marcadores_deproc_removidos',
        'marcadores_deproc_finais',
        'tag_deproc_tratado',
        'tag_deproc_relatorio_anexado',
        'tag_deproc_concluido_memo',
        'tag_deproc_encaminhado_memo_copa',
    ]
    assert colunas['tag_deproc_concluido_memo'] is True
    assert colunas['tag_deproc_relatorio_anexado'] is False
    assert colunas['marcadores_deproc_finais'] == f'{TAG_DEPROC_TRATADO}; {TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA}'
    assert 'processo_reaberto' not in colunas
    assert colunas['memo_apis_sei'] is not None
    assert colunas['valor_total_coparticipacao'] == 22.0


def test_extrato_agrupa_por_data_prestador_e_procedimento(tmp_path):
    linhas = [*LINHAS, _linha(TITULAR, 'TITULAR', '2024-03-01', calculado=8.5)]
    atendimentos = apurar_coparticipacao(_base(tmp_path, linhas), PROCESSO, _dados()).atendimentos
    do_titular = atendimentos[atendimentos['MATRÍCULA'] == '12345678']
    resumo = relatorio_deproc.resumir_atendimentos(do_titular)

    # As duas consultas de 01/03 viram uma linha, com QTDE e valor somados
    assert list(resumo['DATA ATENDIMENTO'].dt.strftime('%d/%m')) == ['01/03', '10/04']
    assert list(resumo['QTDE']) == [2, 1]
    assert list(resumo[COL_VALOR]) == [17.0, 10.0]


def test_matricula_com_dv_no_extrato():
    assert relatorio_deproc.formatar_matricula_com_dv('33983721') == '3398372-1'
