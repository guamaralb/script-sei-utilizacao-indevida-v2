"""Fluxo de verificar os marcadores (main_geacs_verificar_marcadores.py) e a
migração das colunas de marcadores da planilha de controle."""

from datetime import datetime

import main_geacs_verificar_marcadores as fluxo
import pytest
import tags
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral, migrar_colunas_marcadores
from Registro import RegistroMain

from tests.sei_falso import DISA_USOU_RP_ANTIGO, MANTIS_USOU_RC_ANTIGO

# Marcadores válidos na GEACS (lista de 11/11/2026): uma coluna tag_* para cada
VALIDOS_NO_SEI = (
    'v2: 00 - Processo VELHO',
    'v2: 01 - Tratado pelo Script',
    'v2: 01.00 - Aguarda Script: Fluxo Normal',
    'v2: 01.01 - Período Variável p/ Dependentes',
    'v2: 01.02.1 - Mat. N Encontradas Base APIS',
    'v2: 01.05 - No Bloco APIS: Formato Inválido',
    'v2: 01.05 - No Bloco APIS: Sem Memo p/ GEACS',
    'v2: 01.05.1 - Aguarda APIS: Formato Inválido',
    'v2: 01.05.1 - Aguarda APIS: Sem Memo p/ GEACS',
    'v2: 01.06 - Avaliado Uso Rede Própria DISA',
    'v2: 01.06.1 - No Bloco APIS: Matrículas',
    'v2: 01.06.1.1 - Aguarda APIS: Matrículas',
    'v2: 01.07 - No Bloco APIS: Período Deps',
    'v2: 01.07.1 - Aguarda APIS: Período Deps',
    'v2: 01.08 - Avaliado Uso Rede Própria MANTIS',
    'v2: 01.08.1 - Memo DISA Validar Usos MANTIS',
    'v2: 01.09 - Memo DISA Uso Rede Própria',
    'v2: 01.09 - No Bloco DISA: Relat. s/ MANTIS',
    'v2: 01.09 - No Bloco DISA: Validar (Consta)',
    'v2: 01.09 - No Bloco DISA: Validar (N Consta)',
    'v2: 01.09.1 - Aguarda DISA: Relat. s/ MANTIS',
    'v2: 01.09.1 - Aguarda DISA: Validar (Consta)',
    'v2: 01.09.1 - Aguarda DISA: Validar (N Consta)',
    'v2: 01.10 - Concluído: Memos DISA e DEPROC',
    'v2: 01.10 - No Bloco APIS: Sem Uso',
    'v2: 01.10 - No Bloco DEPROC: Coparticipação',
    'v2: 01.10.1 - Aguarda APIS: Sem Uso',
    'v2: 01.10.1 - Aguarda DEPROC: Coparticipação',
    'v2: 01.11 - VELHO Concluído: Memo DEPROC',
    'v2: 01.11 - VELHO Concluído: Memo DISA',
)


def _passar(monkeypatch, marcadores):
    removidos = []
    monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(marcadores))
    monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
    monkeypatch.setattr(tags, 'remover_marcador', lambda driver, lista: removidos.extend(lista))
    registro = fluxo._processar_linha(object(), 'PROC')
    assert removidos == []
    return registro


def _colunas_tag(dados: dict) -> dict:
    return {c: v for c, v in dados.items() if c.startswith('tag_')}


def test_validos_sao_os_marcadores_cadastrados_na_geacs():
    assert tags.TAGS_VALIDOS_GEACS == frozenset(VALIDOS_NO_SEI)


def test_uma_coluna_por_marcador_valido_e_os_demais_juntos(monkeypatch):
    marcadores = [tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, 'PLANILHADO', tags.TAG_PROCESSO_NOVO, 'v2: 02 - Processo VELHO', 'v2v: 01.03 - Memos DISA e DEPROC no Bloco', DISA_USOU_RP_ANTIGO, 'MANUAL']
    dados = _passar(monkeypatch, marcadores).to_dict()

    colunas = _colunas_tag(dados)
    assert len(colunas) == len(VALIDOS_NO_SEI)
    assert {c for c, v in colunas.items() if v} == {'tag_processo_novo', 'tag_aguarda_disa_validar_consta'}
    assert dados['demais_marcadores'] == '; '.join(sorted(['PLANILHADO', 'v2: 02 - Processo VELHO', 'v2v: 01.03 - Memos DISA e DEPROC no Bloco', DISA_USOU_RP_ANTIGO, 'MANUAL']))
    assert dados['marcadores_finais'] == '; '.join(marcadores)
    assert dados['verificar_marcadores_erro'] is None


def test_sem_demais_marcadores(monkeypatch):
    dados = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO]).to_dict()

    assert dados['demais_marcadores'] is None


def test_erro_nao_apaga_as_colunas_de_marcadores(monkeypatch):
    def falhar(driver):
        raise RuntimeError('tela presa')

    monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo, 'listar_marcadores', falhar)
    monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
    dados = fluxo._processar_linha(object(), 'PROC').to_dict()

    assert dados['verificar_marcadores_erro'] == 'RuntimeError: tela presa'
    assert not _colunas_tag(dados)
    assert 'demais_marcadores' not in dados
    assert 'marcadores_finais' not in dados


@pytest.mark.parametrize('coluna', ['prox_acao', 'fluxo', 'tipo_erro', 'erro', 'marcadores_sei', 'marcadores_adicionados', 'marcadores_removidos'])
def test_nao_grava_as_colunas_dos_outros_fluxos(monkeypatch, coluna):
    assert coluna not in _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO]).to_dict()


def test_outros_fluxos_tambem_gravam_demais_marcadores():
    registro = RegistroMain(num_processo='PROC')
    tags.registrar_tags(registro, [tags.TAG_PROCESSO_NOVO, MANTIS_USOU_RC_ANTIGO])
    dados = registro.to_dict()

    assert dados['demais_marcadores'] == MANTIS_USOU_RC_ANTIGO
    assert set(_colunas_tag(dados)) == {coluna for coluna in tags.COLUNAS_TAGS_VALIDOS if not coluna.startswith('tag_deproc_')}


def test_migracao_remove_colunas_obsoletas_e_preenche_demais_marcadores():
    linhas = [
        {
            'num_processo': 'P1',
            'prox_acao': 'Assinar',
            'tit_usou': True,
            'marcadores_finais': f'{tags.TAG_PROCESSO_NOVO}; {DISA_USOU_RP_ANTIGO}; PLANILHADO',
            'tag_processo_novo': True,
            'tag_base_disa_usou_rp': True,
            'tag_planilhado': True,
            'tag_deproc_tratado': False,
            'verificar_marcadores': '11/11/2026 | ...',
        },
        # Já migrada: demais_marcadores não é recalculada
        {'num_processo': 'P2', 'marcadores_finais': 'PLANILHADO', 'demais_marcadores': 'MANUAL'},
        # Sem marcadores_finais (ex.: só passou pelo cancelamento do memo)
        {'num_processo': 'P3', 'canc_memo_deproc_ant_cancelado': True},
    ]
    p1, p2, p3 = migrar_colunas_marcadores(linhas)

    assert p1 == {
        'num_processo': 'P1',
        'prox_acao': 'Assinar',
        'tit_usou': True,
        'marcadores_finais': f'{tags.TAG_PROCESSO_NOVO}; {DISA_USOU_RP_ANTIGO}; PLANILHADO',
        'tag_processo_novo': True,
        'tag_deproc_tratado': False,
        'demais_marcadores': f'PLANILHADO; {DISA_USOU_RP_ANTIGO}',
    }
    assert p2['demais_marcadores'] == 'MANUAL'
    assert p3 == {'num_processo': 'P3', 'canc_memo_deproc_ant_cancelado': True}


def test_planilha_de_controle_mantem_o_resto_e_migra_os_marcadores(monkeypatch, tmp_path):
    arquivo = tmp_path / 'controle.xlsx'
    anterior = {
        'num_processo': 'PROC',
        'data_execucao': 'exec1',
        'ultima_passagem': datetime(2026, 11, 1, 9),
        'fluxo': 'NOVO',
        'prox_acao': 'Assinar memo DEPROC e encaminhar',
        'tipo_erro': None,
        'erro': None,
        'tit_usou': True,
        'marcadores_finais': f'{tags.TAG_PROCESSO_NOVO}; {DISA_USOU_RP_ANTIGO}',
        'tag_processo_novo': True,
        'tag_base_disa_usou_rp': True,
    }
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(anterior)

    PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo).registrar(_passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_SEM_USO, 'PLANILHADO']).to_dict())

    livro = load_workbook(arquivo)
    for aba in ('processos', 'historico'):
        assert 'tag_base_disa_usou_rp' not in [c.value for c in livro[aba][1]]
    processos = livro['processos']
    linha = {c.value: v.value for c, v in zip(processos[1], processos[2], strict=True)}
    assert linha['prox_acao'] == 'Assinar memo DEPROC e encaminhar'
    assert linha['fluxo'] == 'NOVO'
    assert linha['tit_usou'] is True
    assert linha['script'] == fluxo.SCRIPT
    assert linha['tag_processo_novo'] is True
    assert linha['tag_aguarda_apis_sem_uso'] is True
    assert linha['demais_marcadores'] == 'PLANILHADO'
    historico = livro['historico']
    primeira = {c.value: v.value for c, v in zip(historico[1], historico[2], strict=True)}
    assert primeira['demais_marcadores'] == DISA_USOU_RP_ANTIGO
