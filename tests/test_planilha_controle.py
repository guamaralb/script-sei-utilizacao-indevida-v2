from datetime import datetime

import pandas as pd
import planilha_controle
import processos_a_processar
import pytest
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(planilha_controle, 'DIR_BACKUP_CONTROLE', tmp_path / 'backup')
    return tmp_path / 'controle_geral_de_processos.xlsx'


def _passagem(num, hora, **colunas):
    return {'num_processo': num, 'data_execucao': 'exec', 'ultima_passagem': datetime(2026, 10, 21, hora), 'erro': None, **colunas}


def _ler(arquivo):
    return pd.read_excel(arquivo, sheet_name=None)


def test_grava_a_cada_processo(arquivo):
    controle = PlanilhaControleGeral('geacs', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9, prox_acao='A'))
    assert len(_ler(arquivo)['processos']) == 1

    controle.registrar(_passagem('P2', 10, prox_acao='B'))
    abas = _ler(arquivo)
    assert list(abas['processos']['num_processo']) == ['P1', 'P2']
    assert len(abas['historico']) == 2
    assert list(abas['processos'].columns[:6]) == ['num_processo', 'BUSCA', 'ERROS VERIFICADOS MANUALMENTE', 'primeira_passagem', 'ultima_passagem', 'script']
    assert list(abas['historico'].columns[:4]) == ['num_processo', 'primeira_passagem', 'ultima_passagem', 'script']


def test_nova_passagem_atualiza_linha_e_mantem_primeira_passagem(arquivo):
    PlanilhaControleGeral('geacs', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A', memo_disa_sei='111'))
    PlanilhaControleGeral('correcao_rede_propria', 'exec2', arquivo).registrar(_passagem('P1', 15, prox_acao='B'))

    abas = _ler(arquivo)
    linha = abas['processos'].iloc[0]
    assert len(abas['processos']) == 1
    assert linha['primeira_passagem'] == datetime(2026, 10, 21, 9)
    assert linha['ultima_passagem'] == datetime(2026, 10, 21, 15)
    assert linha['prox_acao'] == 'B'
    assert linha['script'] == 'correcao_rede_propria'
    # Coluna que a segunda passagem não grava é mantida
    assert str(linha['memo_disa_sei']) == '111'
    assert list(abas['historico']['prox_acao']) == ['A', 'B']


def test_backup_uma_vez_por_execucao(arquivo):
    PlanilhaControleGeral('geacs', 'exec1', arquivo).registrar(_passagem('P1', 9))
    controle = PlanilhaControleGeral('geacs', 'exec2', arquivo)
    controle.registrar(_passagem('P2', 10))
    controle.registrar(_passagem('P3', 11))

    backups = sorted(p.name for p in planilha_controle.DIR_BACKUP_CONTROLE.iterdir())
    assert backups == ['controle_geral_de_processos_exec2.xlsx']


def test_falha_ao_gravar_salva_a_parte_e_depois_volta(arquivo, monkeypatch):
    controle = PlanilhaControleGeral('geacs', 'exec1', arquivo)
    gravar = planilha_controle._gravar

    def gravar_falhando(destino, abas):
        if destino == arquivo:
            raise PermissionError('planilha aberta no Excel')
        gravar(destino, abas)

    monkeypatch.setattr(planilha_controle, '_gravar', gravar_falhando)
    controle.registrar(_passagem('P1', 9))
    a_parte = arquivo.with_name('controle_geral_de_processos_exec1_NAO_INCORPORADO.xlsx')
    assert a_parte.exists()
    assert not arquivo.exists()

    monkeypatch.setattr(planilha_controle, '_gravar', gravar)
    controle.registrar(_passagem('P2', 10))
    assert list(_ler(arquivo)['processos']['num_processo']) == ['P1', 'P2']


def test_falha_ao_ler_nao_sobrescreve_a_planilha(arquivo):
    arquivo.write_text('não é um xlsx')
    controle = PlanilhaControleGeral('geacs', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9))

    assert arquivo.read_text() == 'não é um xlsx'
    assert arquivo.with_name('controle_geral_de_processos_exec1_NAO_INCORPORADO.xlsx').exists()


def test_mantem_outras_abas_formula_de_busca_e_anotacoes(arquivo):
    PlanilhaControleGeral('geacs', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A'))

    # O usuário preenche a aba BUSCA, cria outra aba e anota um erro
    wb = load_workbook(arquivo)
    wb['BUSCA']['A1'] = 'P1'
    wb.create_sheet('ERROS')['A1'] = 'nota'
    wb['processos']['C2'] = 'erro visto na execução'
    wb.save(arquivo)

    controle = PlanilhaControleGeral('geacs', 'exec2', arquivo)
    controle.registrar(_passagem('P1', 10, prox_acao='B'))
    controle.registrar(_passagem('P2', 11, prox_acao='C'))

    wb = load_workbook(arquivo)
    assert wb['BUSCA']['A1'].value == 'P1'
    assert wb['ERROS']['A1'].value == 'nota'
    processos = wb['processos']
    assert [c.value for c in processos[1][:3]] == ['num_processo', 'BUSCA', 'ERROS VERIFICADOS MANUALMENTE']
    assert processos['B2'].value == '=MATCH(A2,BUSCA!$A:$A,0)'
    assert processos['B3'].value == '=MATCH(A3,BUSCA!$A:$A,0)'
    assert processos['C2'].value == 'erro visto na execução'
    assert processos['C3'].value is None
    assert 'BUSCA' not in [c.value for c in wb['historico'][1]]


def test_primeira_aba_e_o_resumo_por_prox_acao(arquivo):
    controle = PlanilhaControleGeral('geacs', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9, prox_acao='A'))
    controle.registrar(_passagem('P2', 10, prox_acao='B'))
    controle.registrar(_passagem('P3', 11, prox_acao='A'))
    controle.registrar(_passagem('P4', 12))
    # Nova passagem do mesmo processo: conta uma vez, pela última prox_acao
    controle.registrar(_passagem('P2', 13, prox_acao='A'))

    wb = load_workbook(arquivo)
    assert wb.sheetnames[0] == 'resumo'
    assert wb.active.title == 'resumo'
    linhas = [tuple(c.value for c in linha) for linha in wb['resumo'].iter_rows()]
    assert linhas == [('prox_acao', 'quantidade'), ('A', 3), ('(sem prox_acao)', 1), ('TOTAL', 4)]


def test_resumo_continua_primeiro_com_outras_abas(arquivo):
    PlanilhaControleGeral('geacs', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A'))
    wb = load_workbook(arquivo)
    wb.create_sheet('ERROS', 0)
    wb.save(arquivo)

    PlanilhaControleGeral('geacs', 'exec2', arquivo).registrar(_passagem('P2', 10, prox_acao='B'))

    wb = load_workbook(arquivo)
    assert wb.sheetnames[0] == 'resumo'
    assert {'processos', 'historico', 'BUSCA', 'ERROS'} <= set(wb.sheetnames)


def test_le_a_aba_do_fluxo_em_processos_a_processar(tmp_path, monkeypatch):
    arquivo = tmp_path / 'processos_a_processar.xlsx'
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame({'num_sei': ['P1', None, ' P2 ']}).to_excel(writer, sheet_name='geacs', index=False)
        pd.DataFrame({'num_sei': []}).to_excel(writer, sheet_name='deproc', index=False)
    monkeypatch.setattr(processos_a_processar, 'ARQ_PROCESSOS_A_PROCESSAR', arquivo)

    assert processos_a_processar.ler_processos_a_processar('geacs') == ['P1', 'P2']
    assert processos_a_processar.ler_processos_a_processar('deproc') == []
    with pytest.raises(ValueError, match='Aba "geacs_adc_pdf_ant_man" não encontrada'):
        processos_a_processar.ler_processos_a_processar('geacs_adc_pdf_ant_man')
