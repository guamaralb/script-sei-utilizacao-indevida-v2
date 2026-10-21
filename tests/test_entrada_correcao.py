"""Entrada do script de correção: planilha de controle geral e planilha
compilada antiga."""

import main_add_memo_nao_usou_rede_propria as correcao
import pandas as pd
import pytest


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    geral = tmp_path / 'controle_geral_de_processos.xlsx'
    compilado = tmp_path / 'compilado.xlsx'
    monkeypatch.setattr(correcao, 'ARQ_CONTROLE_GERAL', geral)
    monkeypatch.setattr(correcao, 'ARQ_COMPILADO', compilado)
    pd.DataFrame([
        {'num_processo': 'A', 'matricula_titular': '111-1', 'matriculas_dependentes': None},
        {'num_processo': 'B', 'matricula_titular': '222-2', 'matriculas_dependentes': '20'},
        {'num_processo': 'C', 'matricula_titular': '333-3', 'matriculas_dependentes': None},
    ]).to_excel(compilado, sheet_name='FINAL', index=False)
    return geral


def _controle_geral(arquivo, linhas):
    pd.DataFrame(linhas).to_excel(arquivo, sheet_name='processos', index=False)


def test_sem_planilha_geral_usa_o_compilado(arquivos):
    df = correcao._ler_processos()

    assert list(df['num_processo']) == ['A', 'B', 'C']


def test_combina_planilha_geral_e_compilado(arquivos):
    _controle_geral(
        arquivos,
        [
            # Candidato sem matrícula (memo da APIS no modelo antigo): vem do compilado
            {'num_processo': 'A', 'tag_memos_no_bloco': True, 'tag_avaliado_se_usou_rede_propria': False, 'matricula_titular': None, 'matriculas_dependentes': None},
            # Já avaliado: fora
            {'num_processo': 'B', 'tag_memos_no_bloco': True, 'tag_avaliado_se_usou_rede_propria': True, 'matricula_titular': '222-2', 'matriculas_dependentes': '20'},
            # Só na planilha geral, com matrícula própria
            {'num_processo': 'D', 'tag_memos_no_bloco': True, 'tag_avaliado_se_usou_rede_propria': False, 'matricula_titular': '444-4', 'matriculas_dependentes': None},
            # Sem 1.3 Memos DISA e DEPROC: fora
            {'num_processo': 'E', 'tag_memos_no_bloco': False, 'tag_avaliado_se_usou_rede_propria': False, 'matricula_titular': '555-5', 'matriculas_dependentes': None},
        ],
    )

    df = correcao._ler_processos().set_index('num_processo')

    # C ainda não passou pela planilha geral: vem do compilado
    assert sorted(df.index) == ['A', 'C', 'D']
    assert df.loc['A', 'matricula_titular'] == '111-1'
    assert df.loc['D', 'matricula_titular'] == '444-4'
