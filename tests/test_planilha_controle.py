import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import planilha_controle
import processos_a_processar
import pytest
from openpyxl import load_workbook
from planilha_controle import HistoricoCsv, PlanilhaControleGeral, arquivo_historico
from Registro import ProxAcao
from sessao_sei import sessao_encerrada


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    monkeypatch.setattr(planilha_controle, 'DIR_BACKUP_CONTROLE', tmp_path / 'backup')
    return tmp_path / 'controle_geral_de_processos.xlsx'


def _passagem(num, hora, **colunas):
    return {'num_processo': num, 'data_execucao': 'exec', 'ultima_passagem': datetime(2026, 10, 21, hora), 'erro': None, **colunas}


def _ler(arquivo):
    return pd.read_excel(arquivo, sheet_name=None)


def _historico(arquivo) -> list[dict]:
    return HistoricoCsv(arquivo_historico(arquivo)).ler()


def test_grava_a_cada_processo(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9, prox_acao='A'))
    assert len(_ler(arquivo)['processos']) == 1

    controle.registrar(_passagem('P2', 10, prox_acao='B'))
    abas = _ler(arquivo)
    assert list(abas['processos']['num_processo']) == ['P1', 'P2']
    assert 'historico' not in abas
    assert list(abas['processos'].columns[:6]) == ['num_processo', 'BUSCA', 'ERROS VERIFICADOS MANUALMENTE', 'primeira_passagem', 'ultima_passagem', 'script']
    historico = _historico(arquivo)
    assert [h['num_processo'] for h in historico] == ['P1', 'P2']
    assert list(historico[0])[:3] == ['script', 'num_processo', 'data_execucao']
    assert historico[0]['ultima_passagem'] == '21/10/2026 09:00:00'


def test_nova_passagem_atualiza_linha_e_mantem_primeira_passagem(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A', caso_disa_mantis='111'))
    PlanilhaControleGeral('correcao_rede_propria', 'exec2', arquivo).registrar(_passagem('P1', 15, prox_acao='B'))

    abas = _ler(arquivo)
    linha = abas['processos'].iloc[0]
    assert len(abas['processos']) == 1
    assert linha['primeira_passagem'] == datetime(2026, 10, 21, 9)
    assert linha['ultima_passagem'] == datetime(2026, 10, 21, 15)
    assert linha['prox_acao'] == 'B'
    assert linha['script'] == 'correcao_rede_propria'
    # Coluna que a segunda passagem não grava é mantida
    assert str(linha['caso_disa_mantis']) == '111'
    assert [h['prox_acao'] for h in _historico(arquivo)] == ['A', 'B']


def test_cor_da_linha_erro_parado_e_concluido(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('ERRO', 9, prox_acao=ProxAcao.VERIFICAR_ERRO, tipo_erro='ErroAvaliacao', erro='falhou'))
    controle.registrar(_passagem('PARADO', 10, prox_acao=ProxAcao.AGUARDAR_RESPOSTA_MEMO, tipo_erro='ErroAvaliacao', erro='Processamento parado: memo enviado'))
    controle.registrar(_passagem('CONCLUIDO', 11, prox_acao=ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO, tipo_erro='ErroAvaliacao', erro='erro antigo'))
    controle.registrar(_passagem('NO_BLOCO', 12, prox_acao=ProxAcao.ASSINAR_DEPROC))

    processos = load_workbook(arquivo)['processos']
    colunas = [c.value for c in processos[1]]
    cor = {linha[0].value: linha[colunas.index('ultima_passagem')].fill for linha in processos.iter_rows(min_row=2)}
    assert cor['ERRO'].start_color.rgb == 'FFF4CCCC'
    assert cor['PARADO'].fill_type is None
    assert cor['CONCLUIDO'].start_color.rgb == 'FFD9D9D9'
    assert cor['NO_BLOCO'].fill_type is None


def test_backup_uma_vez_por_execucao(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9))
    controle = PlanilhaControleGeral('geacs_inicial', 'exec2', arquivo)
    controle.registrar(_passagem('P2', 10))
    controle.registrar(_passagem('P3', 11))

    backups = sorted(p.name for p in planilha_controle.DIR_BACKUP_CONTROLE.iterdir())
    assert backups == ['controle_geral_de_processos_exec2.xlsx']


def test_falha_ao_gravar_salva_a_parte_e_depois_volta(arquivo, monkeypatch):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
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
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9))

    assert arquivo.read_text() == 'não é um xlsx'
    assert arquivo.with_name('controle_geral_de_processos_exec1_NAO_INCORPORADO.xlsx').exists()


def test_mantem_outras_abas_formula_de_busca_e_anotacoes(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A'))

    # O usuário preenche a aba BUSCA, cria outra aba e anota um erro
    wb = load_workbook(arquivo)
    wb['BUSCA']['A1'] = 'P1'
    wb.create_sheet('ERROS')['A1'] = 'nota'
    wb['processos']['C2'] = 'erro visto na execução'
    wb.save(arquivo)

    controle = PlanilhaControleGeral('geacs_inicial', 'exec2', arquivo)
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
    assert 'BUSCA' not in _historico(arquivo)[0]


def test_primeira_aba_e_o_resumo_por_prox_acao(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
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
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A'))
    wb = load_workbook(arquivo)
    wb.create_sheet('ERROS', 0)
    wb.save(arquivo)

    PlanilhaControleGeral('geacs_inicial', 'exec2', arquivo).registrar(_passagem('P2', 10, prox_acao='B'))

    wb = load_workbook(arquivo)
    assert wb.sheetnames[0] == 'resumo'
    assert {'processos', 'BUSCA', 'ERROS'} <= set(wb.sheetnames)


def test_historico_em_csv_acrescenta_sem_regravar(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9, prox_acao='A', valor=1.5, ok=True))
    csv = arquivo_historico(arquivo)
    antes = csv.read_bytes()
    # Mesmas colunas: só acrescenta a linha no fim
    controle.registrar(_passagem('P2', 10, prox_acao='B', valor=2.0, ok=False))
    assert csv.read_bytes().startswith(antes)
    # BOM só no começo, separador ";" e valores como o Excel em português lê
    texto = csv.read_text(encoding='utf-8')
    assert texto.count('\ufeff') == 1
    assert ';1,5;VERDADEIRO' in texto
    assert ';2,0;FALSO' in texto

    # Coluna nova: regrava o arquivo com o cabeçalho maior
    controle.registrar(_passagem('P3', 11, prox_acao='C', nova='x'))
    historico = _historico(arquivo)
    assert [h['prox_acao'] for h in historico] == ['A', 'B', 'C']
    assert [h['nova'] for h in historico] == ['', '', 'x']
    assert not list(arquivo.parent.glob('~gravando_*'))


def test_historico_pendente_quando_o_csv_nao_pode_ser_gravado(arquivo, monkeypatch):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9))
    gravar = HistoricoCsv._gravar_pendentes

    def falhar(self):
        raise PermissionError('CSV aberto no Excel')

    monkeypatch.setattr(HistoricoCsv, '_gravar_pendentes', falhar)
    controle.registrar(_passagem('P2', 10))
    # A planilha continua sendo gravada
    assert list(_ler(arquivo)['processos']['num_processo']) == ['P1', 'P2']

    monkeypatch.setattr(HistoricoCsv, '_gravar_pendentes', gravar)
    controle.registrar(_passagem('P3', 11))
    assert [h['num_processo'] for h in _historico(arquivo)] == ['P1', 'P2', 'P3']


def _planilha_com_aba_historico(arquivo, historico: list[dict]) -> None:
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame([historico[-1]]).to_excel(writer, sheet_name='processos', index=False)
        pd.DataFrame(historico).to_excel(writer, sheet_name='historico', index=False)
        pd.DataFrame({'A': ['P1']}).to_excel(writer, sheet_name='BUSCA', index=False)


def test_aba_historico_antiga_vai_para_o_csv(arquivo):
    _planilha_com_aba_historico(arquivo, [_passagem('P1', 8, prox_acao='X', script='geacs', tag_processo_novo=True), _passagem('P1', 9, prox_acao='A', script='geacs')])

    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 10, prox_acao='B'))

    assert 'historico' not in load_workbook(arquivo).sheetnames
    historico = _historico(arquivo)
    assert [h['prox_acao'] for h in historico] == ['X', 'A', 'B']
    # O histórico vai inteiro para o CSV, com as colunas que tinha
    assert historico[0]['tag_processo_novo'] == 'VERDADEIRO'
    # Backup da planilha com a aba, antes de tirá-la
    assert 'historico' in load_workbook(next(planilha_controle.DIR_BACKUP_CONTROLE.iterdir())).sheetnames


def test_migracao_restaura_o_ultimo_fluxo_que_agiu(arquivo):
    """Até 18/11/2026, o verificar marcadores gravava script e ultima_passagem
    na aba processos: na migração, voltam os do último fluxo que agiu."""
    historico = [
        _passagem('P1', 8, prox_acao='A', script='geacs_inicial', data_execucao='exec_inicial'),
        _passagem('P1', 9, prox_acao='A', script='geacs_verificar_marcadores'),
        _passagem('P2', 9, script='geacs_verificar_marcadores'),
    ]
    _planilha_com_aba_historico(arquivo, historico)
    with pd.ExcelWriter(arquivo, mode='a', if_sheet_exists='replace') as writer:
        pd.DataFrame([historico[1], historico[2]]).to_excel(writer, sheet_name='processos', index=False)

    controle = PlanilhaControleGeral('geacs_verificar_marcadores', 'exec2', arquivo)
    p1, p2 = controle.linha_processo('P1'), controle.linha_processo('P2')

    assert p1['script'] == 'geacs_inicial'
    assert p1['ultima_passagem'] == datetime(2026, 10, 21, 8)
    assert p1['data_execucao'] == 'exec_inicial'
    assert p1['verificar_marcadores_em'] == datetime(2026, 10, 21, 9)
    # Só passou pelo verificar: fica como está
    assert p2['script'] == 'geacs_verificar_marcadores'


def test_aba_historico_ja_copiada_so_sai_da_planilha(arquivo):
    passagens = [_passagem('P1', 9, prox_acao='A')]
    _planilha_com_aba_historico(arquivo, passagens)
    # Execução anterior copiou a aba e parou antes de gravar a planilha
    HistoricoCsv(arquivo_historico(arquivo)).acrescentar(passagens)

    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 10, prox_acao='B'))

    assert 'historico' not in load_workbook(arquivo).sheetnames
    assert [h['prox_acao'] for h in _historico(arquivo)] == ['A', 'B']


def test_aba_historico_maior_que_o_csv_fica_na_planilha(arquivo):
    _planilha_com_aba_historico(arquivo, [_passagem('P1', 8, prox_acao='X'), _passagem('P1', 9, prox_acao='A')])
    HistoricoCsv(arquivo_historico(arquivo)).acrescentar([_passagem('P9', 7, prox_acao='Z')])

    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 10, prox_acao='B'))

    assert 'historico' in load_workbook(arquivo).sheetnames
    assert [h['prox_acao'] for h in _historico(arquivo)] == ['Z', 'B']


def test_migracao_gravada_sem_nenhum_processo(arquivo):
    """Execução sem processos (ex.: lista vazia) também deixa a planilha
    migrada: a aba historico vai para o CSV e as colunas dos marcadores saem
    da aba processos, logo na leitura. O backup é feito uma vez só."""
    _planilha_com_aba_historico(arquivo, [_passagem('P1', 9, prox_acao='A', tag_processo_novo=True, marcadores_finais='v2: 01 - Tratado pelo Script')])

    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)

    livro = load_workbook(arquivo)
    assert 'historico' not in livro.sheetnames
    colunas = [c.value for c in livro['processos'][1]]
    assert 'tag_processo_novo' not in colunas
    assert 'v2: 01 - Tratado pelo Script' not in colunas
    assert 'marcadores_finais' not in colunas
    assert 'marcadores_pos_fluxo' in colunas
    assert [h['prox_acao'] for h in _historico(arquivo)] == ['A']

    controle.registrar(_passagem('P1', 10, prox_acao='B'))
    assert len(list(planilha_controle.DIR_BACKUP_CONTROLE.iterdir())) == 1
    assert [h['prox_acao'] for h in _historico(arquivo)] == ['A', 'B']


def test_planilha_ja_migrada_nao_e_regravada_na_leitura(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9, prox_acao='A'))
    gravada = arquivo.stat().st_mtime_ns

    PlanilhaControleGeral('geacs_inicial', 'exec2', arquivo)

    assert arquivo.stat().st_mtime_ns == gravada


def test_processos_da_planilha(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    for passagem in (_passagem('P2', 9), _passagem('P1', 9), _passagem('P2', 10)):
        controle.registrar(passagem)

    assert PlanilhaControleGeral('geacs_inicial', 'exec2', arquivo).processos_da_planilha() == ['P2', 'P1']


def test_le_a_aba_do_fluxo_em_processos_a_processar(tmp_path, monkeypatch):
    arquivo = tmp_path / 'processos_a_processar.xlsx'
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame({'num_sei': ['P1', None, ' P2 ']}).to_excel(writer, sheet_name='geacs_inicial', index=False)
        pd.DataFrame({'num_sei': []}).to_excel(writer, sheet_name='deproc_calcula_copa', index=False)
    monkeypatch.setattr(processos_a_processar, 'ARQ_PROCESSOS_A_PROCESSAR', arquivo)

    assert processos_a_processar.ler_processos_a_processar('geacs_inicial') == ['P1', 'P2']
    assert processos_a_processar.ler_processos_a_processar('deproc_calcula_copa') == []
    with pytest.raises(ValueError, match='Aba "geacs_adc_pdf_ant_man" não encontrada'):
        processos_a_processar.ler_processos_a_processar('geacs_adc_pdf_ant_man')


def test_outra_execucao_nao_usa_a_planilha_travada(arquivo):
    """Duas execuções gravando juntas corrompem a planilha (18/11/2026): a
    segunda para antes do login."""
    PlanilhaControleGeral('geacs_verificar_marcadores', 'exec1', arquivo).registrar(_passagem('P1', 9))
    raiz = Path(planilha_controle.__file__).parent
    codigo = (
        'import sys; from pathlib import Path; '
        'import planilha_controle as p\n'
        'try:\n'
        '    p.PlanilhaControleGeral("geacs_inicial", "exec2", Path(sys.argv[1]))\n'
        'except p.PlanilhaEmUso as e:\n'
        '    print(e); sys.exit(3)\n'
    )
    resultado = subprocess.run([sys.executable, '-c', codigo, str(arquivo)], cwd=raiz, capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(raiz)}, check=False)
    assert resultado.returncode == 3, resultado.stderr
    assert 'geacs_verificar_marcadores' in resultado.stdout
    # A execução que tem a trava continua gravando
    PlanilhaControleGeral('geacs_verificar_marcadores', 'exec1', arquivo).registrar(_passagem('P2', 10))
    assert list(_ler(arquivo)['processos']['num_processo']) == ['P1', 'P2']


def test_gravacao_nao_deixa_copia_temporaria(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(_passagem('P1', 9))
    assert [f.name for f in arquivo.parent.glob('~gravando_*')] == []


def test_navegador_sem_resposta_encerra_a_execucao():
    """Ctrl+C derruba o chromedriver junto com o navegador: os comandos
    seguintes dão MaxRetryError, e o loop tem de parar."""
    assert sessao_encerrada(SimpleNamespace(tipo_erro='MaxRetryError'))
    assert sessao_encerrada(SimpleNamespace(tipo_erro='InvalidSessionIdException'))
    assert not sessao_encerrada(SimpleNamespace(tipo_erro='TimeoutException'))


def test_migracao_das_colunas_de_27_11_2026():
    """Colunas renomeadas (marcadores antes e depois da passagem), uma só
    coluna de ano da base DEPROC e as colunas que ficam só no histórico fora
    da aba processos."""
    linhas = [
        {
            'num_processo': 'P1',
            'prox_acao': 'A',
            'tit_usou': True,
            'marcadores_sei': 'v2: 01 - Tratado pelo Script',
            'marcadores_finais': 'v2: 01 - Tratado pelo Script; v2: 01.10.B - No Bloco DEPROC: Coparticipação; PLANILHADO',
            'marcadores_deproc_sei': None,
            'marcadores_deproc_finais': 'v2: 01 - Tratado pelo Script; v2: 01.02 - No Bloco GEACS: Memo Cálculo COPA',
            'ano_base_deproc': 2019.0,
            'data_geracao_base_deproc': '06/11/2026',
            'memo_deproc_sei': '123',
            'demais_marcadores': 'PLANILHADO',
            'v2: 01 - Tratado pelo Script': True,
            'DEPROC | v2: 01 - Tratado pelo Script': True,
            'tag_processo_novo': True,
            'verificar_marcadores_acao_sugerida': 'Rodar geacs_inicial',
            'verificar_marcadores_em': datetime(2026, 11, 26, 9),
        },
        # Com o ano da base do processo: fica o dele
        {'num_processo': 'P2', 'ano_processo': '2020', 'data_geracao_base_processo': '16/11/2026', 'ano_base_deproc': '2019', 'data_geracao_base_deproc': '06/11/2026'},
        # Com a coluna nova e a antiga: vale a nova
        {'num_processo': 'P3', 'marcadores_finais': 'X', 'marcadores_pos_fluxo': 'Y'},
    ]
    p1, p2, p3 = planilha_controle.migrar_colunas(linhas)

    assert p1 == {
        'num_processo': 'P1',
        'prox_acao': 'A',
        'tit_usou': True,
        'marcadores_pre_fluxo': 'v2: 01 - Tratado pelo Script',
        'marcadores_pos_fluxo': 'v2: 01 - Tratado pelo Script; v2: 01.10.B - No Bloco DEPROC: Coparticipação; PLANILHADO',
        'marcadores_deproc_pre_fluxo': None,
        'marcadores_deproc_pos_fluxo': 'v2: 01 - Tratado pelo Script; v2: 01.02 - No Bloco GEACS: Memo Cálculo COPA',
        'ano_processo': '2019',
        'data_geracao_base_processo': '06/11/2026',
        'verificar_marcadores_em': datetime(2026, 11, 26, 9),
        'estado_atual': 'v2: 01.10.B - No Bloco DEPROC: Coparticipação',
        'estado_atual_deproc': 'v2: 01.02 - No Bloco GEACS: Memo Cálculo COPA',
    }
    assert p2 == {'num_processo': 'P2', 'ano_processo': '2020', 'data_geracao_base_processo': '16/11/2026'}
    assert p3['marcadores_pos_fluxo'] == 'Y'
    assert 'marcadores_finais' not in p3


def test_colunas_fora_da_aba_processos_ficam_no_historico(arquivo):
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar(
        _passagem('P1', 9, prox_acao='A', memo_deproc_sei='123', marcadores_adicionados='M', ano_processo='2019', tit_usou=True, data_geracao_base_processo='06/11/2026')
    )

    colunas = list(_ler(arquivo)['processos'].columns)
    assert 'memo_deproc_sei' not in colunas
    assert 'marcadores_adicionados' not in colunas
    # A data da base logo depois do ano
    assert colunas[colunas.index('ano_processo') + 1] == 'data_geracao_base_processo'
    historico = _historico(arquivo)
    assert historico[0]['memo_deproc_sei'] == '123'
    assert historico[0]['marcadores_adicionados'] == 'M'


def test_celulas_do_verificar_marcadores_em_amarelo(arquivo):
    controle = PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo)
    controle.registrar(_passagem('P1', 9, prox_acao='VERIFICAR MARCADORES: Rodar geacs_inicial', tipo_erro='VERIFICAR MARCADORES: Inconsistencia', erro='VERIFICAR MARCADORES: x'))
    controle.registrar(_passagem('P2', 9, prox_acao='A'))

    processos = load_workbook(arquivo)['processos']
    colunas = [c.value for c in processos[1]]
    p1, p2 = (dict(zip(colunas, linha, strict=True)) for linha in processos.iter_rows(min_row=2))
    assert p1['prox_acao'].fill.start_color.rgb == 'FFFFE599'
    assert p1['tipo_erro'].fill.start_color.rgb == 'FFFFE599'
    assert p1['erro'].fill.start_color.rgb == 'FFFFE599'
    assert p2['prox_acao'].fill.fill_type is None
