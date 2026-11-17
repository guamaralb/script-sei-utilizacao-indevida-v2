"""Fluxo de verificar os marcadores (main_geacs_verificar_marcadores.py): colunas
de marcadores, conferência da prox_acao com os marcadores e os memorandos
(conferencia_prox_acao.py) e a migração das colunas de marcadores da planilha
de controle."""

from datetime import datetime

import conferencia_prox_acao
import docs_processo
import main_geacs_verificar_marcadores as fluxo
import processo_fechado
import pytest
import sei_automacao.processo
import tags
from conferencia_prox_acao import AcaoSugerida
from constantes import UNIDADE_DEPROC, UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral, migrar_colunas_marcadores
from Registro import PROX_ACOES_A_VERIFICAR, ProxAcao, RegistroMain

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import ASSUNTO_MEMO_APIS_SEM_MEMO
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import ASSUNTO_MEMO_GEACS_CALCULO_COPA
from tests.sei_falso import DISA_USOU_RP_ANTIGO, MANTIS_USOU_RC_ANTIGO, SEIFalso

# Marcadores válidos na GEACS (lista de 11/11/2026, mais os dois do fluxo GEACS
# TODAS INFOS, a cadastrar no SEI): uma coluna tag_* para cada
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
    'v2: 01.12 - No Bloco APIS: Todas as Infos',
    'v2: 01.12.1 - Encaminhado APIS: Todas as Infos',
)


def _passar(monkeypatch, marcadores, sei: SEIFalso | None = None, linha: dict | None = None, *, aberto: bool = True):
    """Uma passagem pelo fluxo. sei: árvore e textos (sem ele, árvore vazia);
    linha: a linha do processo na planilha de controle (None: planilha não
    lida); aberto: o processo tem "Incluir Documento" na GEACS."""
    sei = sei or SEIFalso()
    removidos = []

    def arvore(driver):
        return [dict(doc) for doc in sei.docs]

    def texto(driver, doc):
        return sei.textos[doc['numero_sei']]

    monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(marcadores))
    monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
    monkeypatch.setattr(fluxo, 'tem_incluir_documento', lambda driver: aberto)
    monkeypatch.setattr(conferencia_prox_acao, 'listar_documentos_arvore', arvore)
    monkeypatch.setattr(conferencia_prox_acao, 'ler_texto_doc', texto)
    monkeypatch.setattr(docs_processo, 'ler_texto_doc', texto)
    monkeypatch.setattr(tags, 'remover_marcador', lambda driver, lista: removidos.extend(lista))
    monkeypatch.setattr(tags, 'adicionar_marcador', lambda driver, tag: pytest.fail('o fluxo não adiciona marcadores'))
    # O fluxo não reabre processos (fechado no setor continua fechado)
    for modulo in (processo_fechado, sei_automacao.processo):
        monkeypatch.setattr(modulo, 'reabrir_processo', lambda *a, **k: pytest.fail('o fluxo não reabre processos'))
    registro = fluxo._processar_linha(object(), 'PROC', linha)
    assert removidos == []
    return registro


def _inconsistencia(registro) -> str | None:
    return registro.to_dict()['verificar_marcadores_inconsistencia']


def _acao(registro) -> str | None:
    return registro.to_dict()['verificar_marcadores_acao_sugerida']


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
    # Planilha não lida (linha None): a prox_acao não é conferida
    assert dados['verificar_marcadores_inconsistencia'] is not None
    assert 'prox_acao' not in dados['verificar_marcadores_inconsistencia']


def test_nao_reabre_processo_fechado(monkeypatch):
    # Confere o Incluir Documento só para informar: lê marcadores e árvore sem reabrir
    for modulo in (fluxo, conferencia_prox_acao):
        codigo = open(modulo.__file__, encoding='utf-8').read()
        assert 'reabrir' not in codigo.lower()
    assert 'processo_reaberto' not in fluxo.RegistroVerificarMarcadores(num_processo='PROC').to_dict()

    dados = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False).to_dict()
    assert dados['verificar_marcadores_aberto_na_geacs'] is False
    assert dados['verificar_marcadores_inconsistencia'] is None
    assert _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC}).to_dict()['verificar_marcadores_aberto_na_geacs'] is True


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


# ---------------------------------------------------------------------------
# Conferência da prox_acao e dos memorandos
# ---------------------------------------------------------------------------


def _processo_disa_consta() -> SEIFalso:
    """Memo da APIS, relatório RP e memo à DISA (validar e complementar)."""
    sei = SEIFalso()
    sei.novo_processo()
    sei.novo_doc('PDF Utilização Tit. RP - 12345678 - 20261101_100000', UNIDADE_GEACS, '')
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_CONSTA)
    return sei


def _processo_deproc(*, com_relatorio: bool = True, assinado: bool = False) -> SEIFalso:
    sei = SEIFalso()
    sei.novo_processo()
    if com_relatorio:
        sei.novo_doc('PDF Utilização Tit. RC - 12345678 - 20261101_100000', UNIDADE_GEACS, '')
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=assinado)
    return sei


NO_BLOCO_CONSTA = [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA]
NO_BLOCO_DEPROC = [tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_DEPROC_COPARTICIPACAO]


def test_tudo_consistente(monkeypatch):
    linha = {'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA, 'caso_disa_mantis': 'DISA sim, MANTIS RP sim, MANTIS RC não'}
    registro = _passar(monkeypatch, NO_BLOCO_CONSTA, _processo_disa_consta(), linha)

    assert _inconsistencia(registro) is None
    assert registro.to_dict()['verificar_marcadores_erro'] is None


def test_prox_acao_de_outro_memo(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA})

    assert _inconsistencia(registro) == (
        f'prox_acao "{ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA}" não condiz com o marcador "01.10 - No Bloco DEPROC: Coparticipação"; '
        f'esperada: "{ProxAcao.ASSINAR_DEPROC}" (rodar o geacs_inicial atualiza a prox_acao)'
    )


def test_prox_acao_desatualizada_depois_da_assinatura(monkeypatch):
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    registro = _passar(monkeypatch, marcadores, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert f'esperada: "{ProxAcao.AGUARDAR_RESPOSTA_MEMO}"' in _inconsistencia(registro)


def test_prox_acao_vazia_com_estado(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {})

    assert _inconsistencia(registro).startswith('prox_acao "(vazia)" não condiz')


@pytest.mark.parametrize(
    'prox_acao',
    [
        ProxAcao.VERIFICAR_ERRO,
        ProxAcao.VERIFICAR_ACESSO_UNIDADE,
        ProxAcao.VERIFICAR_MEMO_DISA_NAO_EXCLUIDO,
        ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO,
        ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO,
        ProxAcao.DEPROC_MEMO_ENCAMINHADO,
    ],
)
def test_prox_acoes_aceitas_com_o_estado(monkeypatch, prox_acao):
    assert _inconsistencia(_passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': prox_acao})) is None


@pytest.mark.parametrize(
    ('marcadores', 'prox_acao', 'consistente'),
    [
        ([], None, True),
        ([], ProxAcao.ASSINAR_DEPROC, False),
        ([tags.TAG_PROCESSO_VELHO], ProxAcao.VELHO_AGUARDAR_DEFINICAO, True),
        ([tags.TAG_PROCESSO_VELHO, tags.TAG_MANUAL], ProxAcao.FORA_DO_ESCOPO, True),
        ([tags.TAG_PROCESSO_VELHO], ProxAcao.ASSINAR_DEPROC, False),
        ([tags.TAG_PROCESSO_NOVO], ProxAcao.ASSINAR_DEPROC, False),
        ([tags.TAG_PROCESSO_NOVO], ProxAcao.VERIFICAR_ERRO, True),
        ([tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_FLUXO_NORMAL], ProxAcao.ADC_PDF_ANT_MAN_AGUARDA_FLUXO_NORMAL, True),
        ([tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_FLUXO_NORMAL], ProxAcao.ASSINAR_DEPROC, False),
        ([tags.TAG_PROCESSO_NOVO], ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL, False),
    ],
)
def test_prox_acao_sem_memo_a_conferir(monkeypatch, marcadores, prox_acao, consistente):
    registro = _passar(monkeypatch, marcadores, linha={'prox_acao': prox_acao})

    assert (_inconsistencia(registro) is None) is consistente


def test_marcadores_inconsistentes(monkeypatch):
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_DEPROC_COPARTICIPACAO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    registro = _passar(monkeypatch, marcadores, linha={'prox_acao': ProxAcao.ASSINAR_DEPROC})

    texto = _inconsistencia(registro)
    assert texto.startswith('Marcadores inconsistentes: mais de um marcador de estado')
    assert f'esperada: "{ProxAcao.VERIFICAR_MARCADORES}"' in texto


def test_verificar_marcadores_com_marcadores_ja_corrigidos(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.VERIFICAR_MARCADORES})

    assert 'mas os marcadores estão consistentes' in _inconsistencia(registro)


def test_marcador_sem_o_memo(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert _inconsistencia(registro) == 'marcador "01.10 - No Bloco DEPROC: Coparticipação" sem o memo DEPROC (coparticipação) na árvore (procurado pelo assunto)'


def test_memo_sem_o_relatorio_que_cita(monkeypatch):
    # Sem o caso na planilha: o memo DEPROC cita algum relatório (RP ou RC)
    sei = _processo_deproc(com_relatorio=False)
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert 'sem relatório RP ou RC do MANTIS antes dele na rodada' in _inconsistencia(registro)


@pytest.mark.parametrize(
    ('caso', 'esperado'),
    [
        ('DISA não, MANTIS RP não, MANTIS RC sim', None),
        # Uso da rede própria só no MANTIS: o memo DEPROC cita também o RP
        ('DISA não, MANTIS RP sim, MANTIS RC sim', 'sem relatório RP do MANTIS antes dele na rodada'),
        ('DISA sim, MANTIS RP sim, MANTIS RC sim', 'não condiz com o memo DEPROC'),
        ('DISA não, MANTIS RP não, MANTIS RC não', 'não condiz com o memo DEPROC'),
    ],
)
def test_memo_deproc_pelo_caso(monkeypatch, caso, esperado):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC, 'caso_disa_mantis': caso})

    inconsistencia = _inconsistencia(registro)
    if esperado is None:
        assert inconsistencia is None
    else:
        assert esperado in inconsistencia


def test_memo_deproc_com_rp_do_mantis(monkeypatch):
    sei = _processo_deproc(com_relatorio=False)
    sei.docs.insert(len(sei.docs) - 1, {'numero_sei': '9001', 'nome_arvore': 'PDF Utilização Dep. RP - 12345678 - 20261101_100000', 'unidade': UNIDADE_GEACS})
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC, 'caso_disa_mantis': 'DISA não, MANTIS RP sim, MANTIS RC não'})

    assert _inconsistencia(registro) is None


def test_memo_no_bloco_de_pedido_anterior(monkeypatch):
    sei = _processo_deproc()
    sei.memo_apis()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert 'é de antes do último memo da APIS destinado à GEACS' in _inconsistencia(registro)


def test_aguarda_com_novo_memo_da_apis_depois(monkeypatch):
    sei = _processo_deproc(assinado=True)
    sei.memo_apis()
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]

    assert _inconsistencia(_passar(monkeypatch, marcadores, sei, {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO})) is None


def test_numero_sei_da_planilha_fora_da_arvore(monkeypatch):
    sei = _processo_deproc()
    numero = sei.numero_sei('Memorando 1')
    linha = {'prox_acao': ProxAcao.ASSINAR_DEPROC, 'memo_deproc_sei': int(numero)}
    assert _inconsistencia(_passar(monkeypatch, NO_BLOCO_DEPROC, sei, linha)) is None

    linha['memo_deproc_sei'] = 999
    assert _inconsistencia(_passar(monkeypatch, NO_BLOCO_DEPROC, sei, linha)) == 'memo_deproc_sei = 999 na planilha, mas o documento não está na árvore'


def test_caso_disa_mantis_de_outro_memo(monkeypatch):
    linha = {'prox_acao': ProxAcao.ASSINAR_DEPROC, 'caso_disa_mantis': 'DISA sim, MANTIS RP não, MANTIS RC sim'}
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha)

    assert _inconsistencia(registro).startswith('caso_disa_mantis "DISA sim, MANTIS RP não, MANTIS RC sim" não condiz com o memo DEPROC')


def test_sem_memo_para_geacs_mas_a_apis_mandou(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo(com_memo_apis=False)
    sei.memo_geacs(ASSUNTO_MEMO_APIS_SEM_MEMO)
    sei.memo_apis()
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_APIS_SEM_MEMO]
    registro = _passar(monkeypatch, marcadores, sei, {'prox_acao': ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO})

    texto = _inconsistencia(registro)
    assert 'o memo à APIS (sem memorando) não é mais necessário' in texto
    # O memo à APIS (sem memo) é de antes do memo da APIS: pedido anterior
    assert 'é de antes do último memo da APIS' in texto


def test_retomada_com_memo_na_rodada_sem_o_marcador(monkeypatch):
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS]
    registro = _passar(monkeypatch, marcadores, _processo_disa_consta(), {'prox_acao': ProxAcao.VERIFICAR_ERRO})

    assert _inconsistencia(registro).startswith('estado "01.08 - Avaliado Uso Rede Própria MANTIS" com o memo à DISA (validar e complementar)')


def test_retomada_sem_memo_na_rodada(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA]

    assert _inconsistencia(_passar(monkeypatch, marcadores, sei, {'prox_acao': ProxAcao.VERIFICAR_ERRO})) is None


def test_erro_ao_ler_a_arvore_mantem_os_marcadores_lidos(monkeypatch):
    def falhar(driver):
        raise RuntimeError('árvore presa')

    sei = _processo_deproc()
    monkeypatch.setattr(SEIFalso, 'docs', property(lambda self: falhar(None)), raising=False)
    dados = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}).to_dict()

    assert dados['verificar_marcadores_erro'] == 'RuntimeError: árvore presa'
    assert dados['tag_memo_deproc_coparticipacao'] is True


def test_coluna_de_inconsistencia_antes_dos_marcadores_e_em_amarelo(monkeypatch, tmp_path):
    arquivo = tmp_path / 'controle.xlsx'
    anterior = {'num_processo': 'PROC', 'ultima_passagem': datetime(2026, 11, 1, 9), 'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA, 'tit_usou': True}
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar({
        **anterior,
        'qnt_memos_geacs_na_arvore': 1,
        'marcadores_sei': tags.TAG_PROCESSO_NOVO,
        'marcadores_finais': tags.TAG_PROCESSO_NOVO,
    })

    controle = PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo)
    linha = controle.linha_processo('PROC')
    assert linha['prox_acao'] == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA
    assert controle.linha_processo('OUTRO') == {}
    controle.registrar(_passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha).to_dict())

    assert not list(tmp_path.glob('~*'))
    processos = load_workbook(arquivo)['processos']
    colunas = [c.value for c in processos[1]]
    posicao = colunas.index('marcadores_sei')
    assert colunas[posicao - 2 : posicao] == ['verificar_marcadores_inconsistencia', 'verificar_marcadores_erro']
    celulas = dict(zip(colunas, processos[2], strict=True))
    assert celulas['verificar_marcadores_inconsistencia'].value.startswith('prox_acao "Assinar memo à DISA')
    assert celulas['verificar_marcadores_inconsistencia'].fill.start_color.rgb == 'FFFFE599'
    assert celulas['prox_acao'].fill.start_color.rgb == 'FFFFE599'
    assert celulas['verificar_marcadores_erro'].fill.fill_type is None


# ---------------------------------------------------------------------------
# prox_acao de erro, acesso, DEPROC, assinatura e ação sugerida
# ---------------------------------------------------------------------------

AGUARDA_DEPROC = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]


def test_toda_prox_acao_de_verificar_vale_com_qualquer_marcador():
    # Uma prox_acao nova de erro ("Verificar ...") esquecida fora da lista
    # vira inconsistência falsa em todo processo com ela
    verificar = {v for k, v in vars(ProxAcao).items() if not k.startswith('_') and v.startswith('Verificar')}
    assert verificar - {ProxAcao.VERIFICAR_MARCADORES} <= PROX_ACOES_A_VERIFICAR


@pytest.mark.parametrize(
    ('fluxo_planilha', 'consistente'),
    [
        (None, True),
        ('DEPROC - COPARTICIPAÇÃO', True),
        ('NOVO - DISA não, MANTIS RP não, MANTIS RC sim: memo DEPROC', False),
    ],
)
def test_verificar_acesso_resolvido_pela_geacs(monkeypatch, fluxo_planilha, consistente):
    linha = {'prox_acao': ProxAcao.VERIFICAR_ACESSO_UNIDADE, 'fluxo': fluxo_planilha}
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha)

    assert (_inconsistencia(registro) is None) is consistente
    if not consistente:
        assert 'o acesso foi resolvido' in _inconsistencia(registro)
        assert _acao(registro) == AcaoSugerida.RODAR_INICIAL


def test_prox_acao_da_deproc_so_com_o_memo_deproc(monkeypatch):
    linha = {'prox_acao': ProxAcao.DEPROC_MEMO_ENCAMINHADO}
    assert _inconsistencia(_passar(monkeypatch, AGUARDA_DEPROC, _processo_deproc(assinado=True), linha)) is None

    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES)
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_TODAS_INFOS], sei, linha)
    assert f'esperada: "{ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS}"' in _inconsistencia(registro)
    assert _acao(registro) == AcaoSugerida.RODAR_INICIAL


def test_no_bloco_com_memo_ja_assinado(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(assinado=True), {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert _inconsistencia(registro).endswith('troque pelo "01.10.1 - Aguarda DEPROC: Coparticipação"')
    assert _acao(registro) == AcaoSugerida.TROCAR_MARCADOR_ASSINADO


def test_aguarda_com_memo_nao_assinado(monkeypatch):
    registro = _passar(monkeypatch, AGUARDA_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO})

    assert 'não está assinado' in _inconsistencia(registro)
    assert _acao(registro) == AcaoSugerida.VERIFICAR_MANUALMENTE


@pytest.mark.parametrize('assinado', [True, False])
def test_encaminhado_apis_confere_o_memo(monkeypatch, assinado):
    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, assinado=assinado)
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS]
    registro = _passar(monkeypatch, marcadores, sei, {'prox_acao': ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO})

    assert (_inconsistencia(registro) is None) is assinado

    sem_memo = SEIFalso()
    sem_memo.novo_processo()
    assert 'sem o memo à APIS (todas as informações)' in _inconsistencia(_passar(monkeypatch, marcadores, sem_memo, {}))


@pytest.mark.parametrize(('assinado', 'acao'), [(True, AcaoSugerida.RODAR_TODAS_INFOS), (False, None)])
def test_aguarda_deproc_com_o_resultado_da_deproc(monkeypatch, assinado, acao):
    sei = _processo_deproc(assinado=True)
    texto = f'Assunto: {ASSUNTO_MEMO_GEACS_CALCULO_COPA}' + ('\nDocumento assinado eletronicamente por Fulana' if assinado else '')
    sei.novo_doc('Memorando 3', UNIDADE_DEPROC, texto)
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO})

    assert _inconsistencia(registro) is None
    assert _acao(registro) == acao


@pytest.mark.parametrize('marcador', [tags.TAG_NO_BLOCO_DISA_VALIDAR_NAO_CONSTA, tags.TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA])
def test_n_consta_sugere_o_corrige_envio_disa(monkeypatch, marcador):
    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA, assinado=marcador == tags.TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA)
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, marcador], sei)

    assert AcaoSugerida.RODAR_CORRIGE_ENVIO_DISA in _acao(registro).split(' | ')


def test_aguarda_disa_com_resposta_da_disa(monkeypatch):
    sei = _processo_disa_consta()
    sei.textos[sei.docs[-1]['numero_sei']] += '\nDocumento assinado eletronicamente por Fulano'
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA]
    linha = {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO}
    assert _acao(_passar(monkeypatch, marcadores, sei, linha)) is None

    sei.novo_doc('Despacho 9', 'IPSEMG/DISA-UTI-INDEV', 'resposta')
    registro = _passar(monkeypatch, marcadores, sei, linha)
    assert _inconsistencia(registro) is None
    assert _acao(registro) == AcaoSugerida.TRATAR_RESPOSTA_DISA


def test_acoes_sugeridas_sem_repeticao(monkeypatch):
    # Dois problemas com a mesma ação: a ação aparece uma vez
    sei = _processo_deproc(com_relatorio=False)
    sei.memo_apis()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert len(registro.inconsistencias) == 2
    assert _acao(registro) == AcaoSugerida.VERIFICAR_MANUALMENTE
