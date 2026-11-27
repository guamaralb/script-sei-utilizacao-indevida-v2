"""Fluxo de verificar os marcadores (main_geacs_verificar_marcadores.py): colunas
de marcadores, conferência da prox_acao com os marcadores e os memorandos
(conferencia_prox_acao.py), prox_acao e erro com o prefixo "VERIFICAR
MARCADORES: " e a verificação na unidade da DEPROC."""

from datetime import datetime
from types import SimpleNamespace

import conferencia_prox_acao
import docs_processo
import main_geacs_verificar_marcadores as fluxo
import pandas as pd
import processo_fechado
import pytest
import sei_automacao.processo
import tags
from conferencia_prox_acao import AcaoSugerida
from constantes import UNIDADE_DEPROC, UNIDADE_GEACS
from openpyxl import load_workbook
from planilha_controle import PlanilhaControleGeral, migrar_colunas
from rede_propria import ErroAvaliacao
from Registro import PREFIXO_VERIFICAR_MARCADORES, PROX_ACOES_A_VERIFICAR, ProxAcao, RegistroMain, RegistroVerificarMarcadores

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemMemo import ASSUNTO_MEMO_APIS_SEM_MEMO
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import ASSUNTO_MEMO_GEACS_CALCULO_COPA
from tests.sei_falso import DISA_USOU_RP_ANTIGO, MANTIS_USOU_RC_ANTIGO, SEIFalso

# Marcadores válidos na GEACS (lista de 11/11/2026, mais os dois do fluxo GEACS
# TODAS INFOS, a cadastrar no SEI)
VALIDOS_NO_SEI = (
    'v2: 00 - Processo VELHO',
    'v2: 01 - Tratado pelo Script',
    'v2: 01.00 - Aguarda Script: Fluxo Normal',
    'v2: 01.01 - Período Variável p/ Dependentes',
    'v2: 01.02.1 - Mat. N Encontradas Base APIS',
    'v2: 01.05.A - No Bloco APIS: Formato Inválido',
    'v2: 01.05.B - No Bloco APIS: Sem Memo p/ GEACS',
    'v2: 01.05.A.1 - Aguarda APIS: Formato Inválido',
    'v2: 01.05.B.1 - Aguarda APIS: Sem Memo p/ GEACS',
    'v2: 01.06 - Avaliado Uso Rede Própria DISA',
    'v2: 01.06.1 - No Bloco APIS: Matrículas',
    'v2: 01.06.1.1 - Aguarda APIS: Matrículas',
    'v2: 01.07 - No Bloco APIS: Período Deps',
    'v2: 01.07.1 - Aguarda APIS: Período Deps',
    'v2: 01.08 - Avaliado Uso Rede Própria MANTIS',
    'v2: 01.08.1 - Memo DISA Validar Usos MANTIS',
    'v2: 01.09 - Memo DISA Uso Rede Própria',
    'v2: 01.09.A - No Bloco DISA: Relat. s/ MANTIS',
    'v2: 01.09.B - No Bloco DISA: Validar (Consta)',
    'v2: 01.09.C - No Bloco DISA: Validar (N Consta)',
    'v2: 01.09.A.1 - Aguarda DISA: Relat. s/ MANTIS',
    'v2: 01.09.B.1 - Aguarda DISA: Validar (Consta)',
    'v2: 01.09.C.1 - Aguarda DISA: Validar (N Consta)',
    'v2: 01.10 - Concluído: Memos DISA e DEPROC',
    'v2: 01.10.A - No Bloco APIS: Sem Uso',
    'v2: 01.10.B - No Bloco DEPROC: Coparticipação',
    'v2: 01.10.A.1 - Aguarda APIS: Sem Uso',
    'v2: 01.10.B.1 - Aguarda DEPROC: Coparticipação',
    'v2: 01.11 - VELHO Concluído: Memo DEPROC',
    'v2: 01.11 - VELHO Concluído: Memo DISA',
    'v2: 01.12 - No Bloco APIS: Todas as Infos',
    'v2: 01.12.1 - Encaminhado APIS: Todas as Infos',
)


def _passar(
    monkeypatch,
    marcadores,
    sei: SEIFalso | None = None,
    linha: dict | None = None,
    *,
    aberto: bool = True,
    cadastrados: set[str] | None = None,
    eventos: list | None = None,
    reabre: bool = True,
    conclui: bool = True,
):
    """Uma passagem pelo fluxo. sei: árvore e textos (sem ele, árvore vazia);
    linha: a linha do processo na planilha de controle (None: planilha não
    lida); aberto: o processo tem "Incluir Documento" na GEACS; cadastrados:
    os marcadores cadastrados no SEI (None: todos); eventos: recebe as ações no
    SEI, em ordem (reabrir, adicionar/remover marcador, concluir); reabre /
    conclui: reabrir / concluir o processo funciona."""
    sei = sei or SEIFalso()
    eventos = [] if eventos is None else eventos
    removidos = []
    adicionados = []

    def adicionar(driver, tag):
        adicionados.append(tag)
        eventos.append(('adicionar', tag))

    def remover(driver, lista):
        removidos.extend(lista)
        eventos.extend(('remover', tag) for tag in lista)

    def reabrir(driver, registro):
        eventos.append('reabrir')
        if not reabre:
            raise processo_fechado.ProcessoFechadoNoSetor('não foi possível reabrir')
        eventos.append('reaberto')

    def concluir(driver):
        eventos.append('concluir')
        if not conclui:
            raise RuntimeError('falhou ao concluir')

    def garantir(driver, lista):
        faltando = [tag for tag in lista if cadastrados is not None and tag not in cadastrados]
        if faltando:
            raise ErroAvaliacao(f'Marcador(es) não cadastrado(s) no SEI: {faltando}')

    def arvore(driver):
        return [dict(doc) for doc in sei.docs]

    def texto(driver, doc):
        return sei.textos[doc['numero_sei']]

    monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(marcadores))
    monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
    monkeypatch.setattr(conferencia_prox_acao, 'tem_incluir_documento', lambda driver: aberto)
    monkeypatch.setattr(conferencia_prox_acao, 'listar_documentos_arvore', arvore)
    monkeypatch.setattr(conferencia_prox_acao, 'ler_texto_doc', texto)
    monkeypatch.setattr(docs_processo, 'ler_texto_doc', texto)
    monkeypatch.setattr(tags, 'remover_marcador', remover)
    monkeypatch.setattr(tags, 'adicionar_marcador', adicionar)
    monkeypatch.setattr(conferencia_prox_acao, 'garantir_marcadores_no_sei', garantir)
    monkeypatch.setattr(conferencia_prox_acao, 'reabrir_processo_fechado', reabrir)
    monkeypatch.setattr(conferencia_prox_acao, 'concluir_processo', concluir)
    monkeypatch.setattr(conferencia_prox_acao, 'acessar_processo', lambda driver, num: None)
    # Só pelo reabrir_processo_fechado (acima), e só para trocar o marcador
    for modulo in (processo_fechado, sei_automacao.processo):
        monkeypatch.setattr(modulo, 'reabrir_processo', lambda *a, **k: pytest.fail('reabre só pelo reabrir_processo_fechado'))
    registro = fluxo._processar_linha(object(), 'PROC', linha)
    # Só a troca do "No Bloco" mexe nos marcadores, sempre por adicionar_tag
    assert adicionados == registro.marcadores_adicionados
    assert removidos == registro.marcadores_removidos
    # Processo reaberto é sempre concluído de novo, por último
    if 'reaberto' in eventos:
        assert eventos[:2] == ['reabrir', 'reaberto']
        assert eventos[-1] == 'concluir'
    else:
        assert 'concluir' not in eventos
    return registro


PREFIXO = PREFIXO_VERIFICAR_MARCADORES


def _inconsistencia(registro) -> str | None:
    """As inconsistências da passagem (vão para a coluna erro, com o prefixo)."""
    return ' | '.join(registro.inconsistencias) or None


def _acao(registro) -> str | None:
    """As ações sugeridas, sem repetição (vão para a prox_acao, com o prefixo)."""
    return ' | '.join(dict.fromkeys(registro.acoes_sugeridas)) or None


def _colunas_tag(dados: dict) -> dict:
    return {c: v for c, v in dados.items() if tags.eh_coluna_tag(c)}


def test_validos_sao_os_marcadores_cadastrados_na_geacs():
    assert tags.TAGS_VALIDOS_GEACS == frozenset(VALIDOS_NO_SEI)


def test_colunas_dos_marcadores_antes_e_depois_da_passagem(monkeypatch):
    marcadores = [tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA, 'PLANILHADO', tags.TAG_PROCESSO_NOVO, 'v2: 02 - Processo VELHO', 'v2v: 01.03 - Memos DISA e DEPROC no Bloco', DISA_USOU_RP_ANTIGO, 'MANUAL']
    registro = _passar(monkeypatch, marcadores)
    dados = registro.to_dict()

    # Sem uma coluna por marcador nem demais_marcadores
    assert not _colunas_tag(dados)
    assert 'demais_marcadores' not in dados
    assert 'marcadores_finais' not in dados
    assert dados['marcadores_pre_fluxo'] == '; '.join(marcadores)
    assert dados['marcadores_pos_fluxo'] == '; '.join(marcadores)
    assert dados['estado_atual'] == tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA
    assert registro.erro is None
    # Planilha não lida (linha None): a prox_acao não é conferida
    assert _inconsistencia(registro) is not None
    assert 'prox_acao' not in _inconsistencia(registro)
    # A inconsistência vai para tipo_erro e erro, com o prefixo
    assert dados['tipo_erro'] == f'{PREFIXO}Inconsistencia'
    assert dados['erro'] == f'{PREFIXO}{_inconsistencia(registro)}'
    assert dados['prox_acao'] == f'{PREFIXO}{_acao(registro)}'
    assert 'verificar_marcadores_inconsistencia' not in dados
    assert 'verificar_marcadores_acao_sugerida' not in dados


def test_nao_confere_se_aberto_sem_troca(monkeypatch):
    # Sem marcador a trocar, nem confere o "Incluir Documento" (o fechado é
    # lido como está, sem reabrir)
    assert 'processo_reaberto' not in fluxo.RegistroVerificarMarcadores(num_processo='PROC').to_dict()

    eventos = []
    dados = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, eventos=eventos).to_dict()
    assert eventos == []
    assert 'verificar_marcadores_aberto_na_geacs' not in dados
    assert 'erro' not in dados
    assert 'prox_acao' not in dados


def test_erro_nao_apaga_as_colunas_de_marcadores(monkeypatch):
    def falhar(driver):
        raise RuntimeError('tela presa')

    monkeypatch.setattr(fluxo, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo, 'listar_marcadores', falhar)
    monkeypatch.setattr(fluxo, 'restaurar_navegador', lambda driver: None)
    dados = fluxo._processar_linha(object(), 'PROC').to_dict()

    assert dados['tipo_erro'] == f'{PREFIXO}RuntimeError'
    assert dados['erro'] == f'{PREFIXO}tela presa'
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_ERRO}'
    assert 'marcadores_pos_fluxo' not in dados
    assert 'estado_atual' not in dados


@pytest.mark.parametrize('coluna', ['prox_acao', 'fluxo', 'tipo_erro', 'erro', 'marcadores_sei', 'marcadores_adicionados', 'marcadores_removidos'])
def test_nao_grava_as_colunas_dos_outros_fluxos(monkeypatch, coluna):
    assert coluna not in _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO]).to_dict()


def test_outros_fluxos_gravam_os_marcadores_antes_e_depois():
    registro = RegistroMain(num_processo='PROC')
    tags.registrar_tags(registro, [tags.TAG_PROCESSO_NOVO, MANTIS_USOU_RC_ANTIGO])
    dados = registro.to_dict()

    assert dados['marcadores_pre_fluxo'] == dados['marcadores_pos_fluxo'] == f'{tags.TAG_PROCESSO_NOVO}; {MANTIS_USOU_RC_ANTIGO}'
    assert not _colunas_tag(dados)
    assert 'demais_marcadores' not in dados


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
    # Planilha de antes de 18/11/2026: colunas tag_* e aba historico
    with pd.ExcelWriter(arquivo) as writer:
        pd.DataFrame([{**anterior, 'script': 'geacs_inicial'}]).to_excel(writer, sheet_name='processos', index=False)
        pd.DataFrame([{**anterior, 'script': 'geacs_inicial'}]).to_excel(writer, sheet_name='historico', index=False)

    controle = PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo, colunas_so_historico=RegistroVerificarMarcadores.COLUNAS_SO_HISTORICO)
    controle.registrar(_passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_SEM_USO, 'PLANILHADO']).to_dict())

    livro = load_workbook(arquivo)
    # A aba historico foi para o CSV
    assert 'historico' not in livro.sheetnames
    processos = livro['processos']
    assert 'tag_base_disa_usou_rp' not in [c.value for c in processos[1]]
    assert 'tag_processo_novo' not in [c.value for c in processos[1]]
    assert not [c.value for c in processos[1] if tags.eh_coluna_tag(c.value)]
    linha = {c.value: v.value for c, v in zip(processos[1], processos[2], strict=True)}
    # Sem o memo à APIS na árvore: o que fazer vai para a prox_acao
    assert linha['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_MANUALMENTE}'
    assert linha['fluxo'] == 'NOVO'
    assert linha['tit_usou'] is True
    # script e ultima_passagem são os do último fluxo que agiu no processo
    assert linha['script'] == 'geacs_inicial'
    assert linha['ultima_passagem'] == datetime(2026, 11, 1, 9)
    assert linha['data_execucao'] == 'exec1'
    assert linha['verificar_marcadores_em'] is not None
    assert linha['marcadores_pos_fluxo'] == f'{tags.TAG_PROCESSO_NOVO}; {tags.TAG_NO_BLOCO_APIS_SEM_USO}; PLANILHADO'
    assert linha['estado_atual'] == tags.TAG_NO_BLOCO_APIS_SEM_USO
    assert 'demais_marcadores' not in linha
    assert 'marcadores_finais' not in linha
    historico = controle.historico.ler()
    assert [h['script'] for h in historico] == ['geacs_inicial', fluxo.SCRIPT]
    # O histórico antigo vai para o CSV como estava
    assert historico[0]['tag_processo_novo'] == 'VERDADEIRO'
    assert historico[1]['ultima_passagem']


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
    assert registro.erros() == []
    assert 'erro' not in registro.to_dict()


def test_prox_acao_de_outro_memo_e_corrigida_pela_arvore(monkeypatch):
    # No Bloco com o memo da rodada não assinado: o verificar corrige a prox_acao
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA})

    assert registro.to_dict()['prox_acao'] == ProxAcao.ASSINAR_DEPROC
    assert _inconsistencia(registro) is None


def test_prox_acao_de_outro_memo_sem_o_memo_na_arvore(monkeypatch):
    # Sem o memo na árvore a situação não é conhecida: só a inconsistência
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, None, {'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA})

    # As ações das duas inconsistências (prox_acao e memo fora da árvore)
    assert registro.to_dict()['prox_acao'] == f'{PREFIXO}{AcaoSugerida.RODAR_INICIAL} | {AcaoSugerida.VERIFICAR_MANUALMENTE}'
    assert _inconsistencia(registro).startswith(
        f'prox_acao "{ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA}" não condiz com o marcador "01.10.B - No Bloco DEPROC: Coparticipação"; '
        f'esperada: "{ProxAcao.ASSINAR_DEPROC}" (rodar o geacs_inicial atualiza a prox_acao)'
    )


def test_prox_acao_desatualizada_depois_da_assinatura():
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    problemas = conferencia_prox_acao.conferir_prox_acao(ProxAcao.ASSINAR_DEPROC, marcadores)

    assert f'esperada: "{ProxAcao.AGUARDAR_RESPOSTA_MEMO}"' in problemas[0].frase


@pytest.mark.parametrize('prox_acao', [ProxAcao.AGUARDAR_RESPOSTA_MEMO, ProxAcao.AGUARDAR_RETORNO_DEPROC])
def test_aguarda_aceita_a_prox_acao_generica_e_a_da_unidade(prox_acao):
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]

    assert conferencia_prox_acao.conferir_prox_acao(prox_acao, marcadores) == []
    # A de outra unidade não condiz
    assert conferencia_prox_acao.conferir_prox_acao(ProxAcao.AGUARDAR_RETORNO_DISA, marcadores)


def test_prox_acao_vazia_com_estado(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {})
    assert registro.to_dict()['prox_acao'] == ProxAcao.ASSINAR_DEPROC
    assert _inconsistencia(registro) is None

    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, None, {})
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
        # VELHO: corrigida pelo marcador
        ([tags.TAG_PROCESSO_VELHO], ProxAcao.ASSINAR_DEPROC, True),
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
    assert registro.to_dict()['prox_acao'] == ProxAcao.ASSINAR_DEPROC
    assert _inconsistencia(registro) is None

    # Sem o memo na árvore: só a inconsistência
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, None, {'prox_acao': ProxAcao.VERIFICAR_MARCADORES})
    assert 'mas os marcadores estão consistentes' in _inconsistencia(registro)


def test_marcador_sem_o_memo(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert _inconsistencia(registro) == 'marcador "01.10.B - No Bloco DEPROC: Coparticipação" sem o memo DEPROC (coparticipação) na árvore (procurado pelo assunto)'


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

    assert dados['erro'] == f'{PREFIXO}árvore presa'
    assert tags.TAG_MEMO_DEPROC_COPARTICIPACAO in dados['marcadores_pos_fluxo']


def test_ordem_e_formato_das_colunas_da_planilha(monkeypatch, tmp_path):
    arquivo = tmp_path / 'controle.xlsx'
    anterior = {'num_processo': 'PROC', 'ultima_passagem': datetime(2026, 11, 1, 9), 'prox_acao': ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA, 'tipo_erro': None, 'erro': None, 'tit_usou': True}
    PlanilhaControleGeral('geacs_inicial', 'exec1', arquivo).registrar({
        **anterior,
        'qnt_memos_geacs_na_arvore': 1,
        'marcadores_pre_fluxo': tags.TAG_PROCESSO_NOVO,
        'marcadores_pos_fluxo': tags.TAG_PROCESSO_NOVO,
    })

    controle = PlanilhaControleGeral(fluxo.SCRIPT, 'exec2', arquivo, colunas_so_historico=RegistroVerificarMarcadores.COLUNAS_SO_HISTORICO)
    linha = controle.linha_processo('PROC')
    assert linha['prox_acao'] == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA
    assert controle.linha_processo('OUTRO') == {}
    # Sem o memo na árvore: a prox_acao não é corrigida (fica a inconsistência)
    controle.registrar(_passar(monkeypatch, NO_BLOCO_DEPROC, None, linha).to_dict())

    assert not list(tmp_path.glob('~gravando_*'))
    processos = load_workbook(arquivo)['processos']
    colunas = [c.value for c in processos[1]]
    # estado_atual logo depois da prox_acao; sem as colunas antigas do verificar
    assert colunas[colunas.index('prox_acao') + 1] == 'estado_atual'
    assert not [c for c in colunas if c.startswith('verificar_marcadores_') and c != 'verificar_marcadores_em']
    assert 'qnt_memos_geacs_na_arvore' not in colunas
    # No fim: os marcadores antes e depois da passagem
    assert colunas[-2:] == ['marcadores_pre_fluxo', 'marcadores_pos_fluxo']
    celulas = dict(zip(colunas, processos[2], strict=True))
    assert celulas['estado_atual'].value == tags.TAG_MEMO_DEPROC_COPARTICIPACAO
    assert celulas['erro'].value.startswith(f'{PREFIXO}prox_acao "Assinar memo à DISA')
    assert celulas['tipo_erro'].value == f'{PREFIXO}Inconsistencia'
    assert celulas['prox_acao'].value.startswith(f'{PREFIXO}{AcaoSugerida.RODAR_INICIAL}')
    for coluna in ('prox_acao', 'tipo_erro', 'erro'):
        assert celulas[coluna].fill.start_color.rgb == 'FFFFE599'


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
    # Sem o memo na árvore: a prox_acao não é corrigida
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, None, linha)

    assert ('o acesso foi resolvido' not in (_inconsistencia(registro) or '')) is consistente
    if not consistente:
        assert _acao(registro).startswith(AcaoSugerida.RODAR_INICIAL)

    # Com o memo da rodada não assinado, a do acesso resolvido é corrigida
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha)
    assert _inconsistencia(registro) is None
    assert registro.to_dict().get('prox_acao') == (None if consistente else ProxAcao.ASSINAR_DEPROC)


def test_prox_acao_da_deproc_so_com_o_memo_deproc(monkeypatch):
    linha = {'prox_acao': ProxAcao.DEPROC_MEMO_ENCAMINHADO}
    assert _inconsistencia(_passar(monkeypatch, AGUARDA_DEPROC, _processo_deproc(assinado=True), linha)) is None

    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES)
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_TODAS_INFOS], sei, linha)
    # Desatualizada com o 01.12: corrigida pelo memo da rodada não assinado
    assert registro.to_dict()['prox_acao'] == ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS
    assert _inconsistencia(registro) is None

    # Sem o memo na árvore: só a inconsistência
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_TODAS_INFOS], None, linha)
    assert f'esperada: "{ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS}"' in _inconsistencia(registro)
    assert _acao(registro).startswith(AcaoSugerida.RODAR_INICIAL)


def test_no_bloco_com_memo_ja_assinado(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(assinado=True), {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert _inconsistencia(registro).endswith('troque pelo "01.10.B.1 - Aguarda DEPROC: Coparticipação"')
    assert _acao(registro) == AcaoSugerida.TROCAR_MARCADOR_ASSINADO


def test_aguarda_com_memo_nao_assinado(monkeypatch):
    registro = _passar(monkeypatch, AGUARDA_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO})

    assert 'não está assinado' in _inconsistencia(registro)
    assert _acao(registro) == AcaoSugerida.ASSINAR_MEMO
    dados = registro.to_dict()
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.ASSINAR_MEMO}'
    assert dados['tipo_erro'] == f'{PREFIXO}Inconsistencia'
    assert 'memo_deproc_sei' not in dados


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


# ---------------------------------------------------------------------------
# Memo do "Aguarda" assinado (começo do fluxo)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'signatario',
    ['Gustavo Amaral Bernardino', 'Bruna Miiller Lavarini', 'Bruna Miller Lavarini', 'Danúbia Lacerda Gomes de Oliveira'],
)
def test_aguarda_com_memo_assinado_atualiza_a_planilha(monkeypatch, signatario):
    sei = SEIFalso()
    sei.novo_processo()
    sei.novo_doc('PDF Utilização Tit. RC - 12345678 - 20261101_100000', UNIDADE_GEACS, '')
    numero = sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=True, signatario=signatario)
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    dados = registro.to_dict()
    assert dados['prox_acao'] == ProxAcao.AGUARDAR_RETORNO_DEPROC
    # Aguardando resposta: sem erro
    assert dados['tipo_erro'] is None
    assert dados['erro'] is None
    assert 'memo_deproc_sei' not in dados
    # Só no histórico
    assert dados['verificar_marcadores_memo_aguarda_assinado'] == f'01.10.B.1 - Aguarda DEPROC: Coparticipação: {numero} ({signatario})'
    # A prox_acao conferida é a atualizada
    assert _inconsistencia(registro) is None


def test_aguarda_com_memo_assinado_por_outra_pessoa_tambem_atualiza(monkeypatch):
    sei = _processo_deproc(assinado=True)  # Fulano de Tal
    numero = sei.docs[-1]['numero_sei']
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    dados = registro.to_dict()
    assert dados['prox_acao'] == ProxAcao.AGUARDAR_RETORNO_DEPROC
    assert dados['verificar_marcadores_memo_aguarda_assinado'] == f'01.10.B.1 - Aguarda DEPROC: Coparticipação: {numero} (Fulano de Tal)'
    assert _inconsistencia(registro) is None


def test_aguarda_sem_memo_e_erro_e_pede_criar_o_memo(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    dados = registro.to_dict()
    # A prox_acao da planilha (do No Bloco) também está desatualizada
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.RODAR_INICIAL} | {AcaoSugerida.CRIAR_MEMO}'
    assert dados['tipo_erro'] == f'{PREFIXO}Inconsistencia'
    assert dados['erro'].startswith(f'{PREFIXO}prox_acao "{ProxAcao.ASSINAR_DEPROC}" não condiz')
    assert ' | marcador "01.10.B.1 - Aguarda DEPROC: Coparticipação" sem o memo DEPROC' in dados['erro']
    assert 'sem o memo DEPROC' in _inconsistencia(registro)
    assert AcaoSugerida.CRIAR_MEMO in _acao(registro).split(' | ')


@pytest.mark.parametrize(
    ('marcador', 'assunto', 'prox_acao'),
    [
        (tags.TAG_AGUARDA_APIS_SEM_MEMO, ASSUNTO_MEMO_APIS_SEM_MEMO, ProxAcao.AGUARDAR_RETORNO_APIS),
        (tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA, ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, ProxAcao.AGUARDAR_RETORNO_DISA),
        (tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS, ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO),
    ],
)
def test_memo_assinado_da_a_prox_acao_da_unidade_ou_concluido(monkeypatch, marcador, assunto, prox_acao):
    sei = SEIFalso()
    sei.novo_processo()
    # O memo à DISA de validação cita o relatório RP
    sei.novo_doc('PDF Utilização Tit. RP - 12345678 - 20261101_100000', UNIDADE_GEACS, '')
    sei.memo_geacs(assunto, assinado=True, signatario=GUSTAVO)
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, marcador], sei, {'prox_acao': ProxAcao.VERIFICAR_ERRO})

    dados = registro.to_dict()
    assert dados['prox_acao'] == prox_acao
    # A prox_acao de erro trocada: o erro sai
    assert dados['tipo_erro'] is None
    assert dados['erro'] is None


@pytest.mark.parametrize(('assinado', 'frase'), [(False, 'não está assinado'), (None, 'sem o memo à APIS (todas as informações)')])
@pytest.mark.parametrize('prox_acao', [ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO, ProxAcao.VERIFICAR_CRIAR_MEMO_DO_MARCADOR, ProxAcao.VERIFICAR_ERRO])
def test_encaminhado_apis_sem_memo_assinado_e_erro_mas_concluido(monkeypatch, assinado, frase, prox_acao):
    sei = SEIFalso()
    sei.novo_processo()
    if assinado is not None:
        sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, assinado=assinado)
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS]
    registro = _passar(monkeypatch, marcadores, sei, {'prox_acao': prox_acao})

    dados = registro.to_dict()
    # Com o Encaminhado, a prox_acao é sempre a de concluído
    assert dados['prox_acao'] == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert dados['tipo_erro'] == f'{PREFIXO}Inconsistencia'
    assert frase in dados['erro']


@pytest.mark.parametrize(
    'prox_acao',
    [None, ProxAcao.VERIFICAR_ERRO, ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS, ProxAcao.DEPROC_MEMO_ENCAMINHADO, ProxAcao.VERIFICAR_MARCADORES, ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO],
)
def test_encaminhado_apis_sempre_da_a_prox_acao_de_concluido(monkeypatch, prox_acao):
    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, assinado=True, signatario=GUSTAVO)
    registro = _passar(monkeypatch, [tags.TAG_PROCESSO_NOVO, tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS], sei, {'prox_acao': prox_acao})

    dados = registro.to_dict()
    assert dados['prox_acao'] == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert dados['erro'] is None
    assert _inconsistencia(registro) is None


def test_prox_acao_de_erro_de_outro_fluxo_fica(monkeypatch):
    # Verificar erro (ex.: falha do geacs_todas_infos) não é escondida
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.VERIFICAR_ERRO})
    assert 'prox_acao' not in registro.to_dict()
    # A da DEPROC fica com o memo DEPROC na GEACS
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO})
    assert 'prox_acao' not in registro.to_dict()


def test_sem_planilha_a_prox_acao_pela_situacao_nao_muda(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), None)
    assert 'prox_acao' not in registro.to_dict()


@pytest.mark.parametrize('prox_acao', [ProxAcao.AGUARDAR_RETORNO_DEPROC, 'DEPROC: assinar memo de resultado'])
def test_aguarda_com_memo_assinado_mantem_prox_acao_ja_certa_ou_da_deproc(monkeypatch, prox_acao):
    sei = _processo_deproc()
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=True, signatario='Gustavo Amaral Bernardino')
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': prox_acao})

    dados = registro.to_dict()
    assert 'prox_acao' not in dados
    assert dados['verificar_marcadores_memo_aguarda_assinado'] is not None


def test_aguarda_com_marcadores_inconsistentes_so_registra_o_memo(monkeypatch):
    sei = _processo_deproc()
    numero = sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=True, signatario='Gustavo Amaral Bernardino')
    # Sem o 01: combinação impossível
    registro = _passar(monkeypatch, [tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO], sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    dados = registro.to_dict()
    assert registro.prox_acao_atualizada is None
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.CORRIGIR_MARCADORES}'
    assert numero in dados['verificar_marcadores_memo_aguarda_assinado']


def test_aguarda_com_memo_assinado_e_erro_depois(monkeypatch):
    sei = _processo_deproc()
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=True, signatario='Gustavo Amaral Bernardino')

    def falha(*args, **kwargs):
        raise RuntimeError('falhou')

    monkeypatch.setattr(fluxo, 'conferir_processo', falha)
    registro = _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    # A atualização pelo memo não se perde, mas o erro vai para a prox_acao
    assert registro.prox_acao_atualizada == ProxAcao.AGUARDAR_RETORNO_DEPROC
    dados = registro.to_dict()
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_ERRO}'
    assert dados['tipo_erro'] == f'{PREFIXO}RuntimeError'
    assert dados['erro'] == f'{PREFIXO}falhou'


# ---------------------------------------------------------------------------
# "No Bloco" com o memo assinado: troca pelo marcador de assinado
# ---------------------------------------------------------------------------

GUSTAVO = 'Gustavo Amaral Bernardino'


def _deproc_assinado_por(signatario: str = GUSTAVO) -> tuple[SEIFalso, str]:
    sei = SEIFalso()
    sei.novo_processo()
    sei.novo_doc('PDF Utilização Tit. RC - 12345678 - 20261101_100000', UNIDADE_GEACS, '')
    return sei, sei.memo_geacs(ASSUNTO_MEMO_DEPROC, assinado=True, signatario=signatario)


@pytest.mark.parametrize('signatario', [GUSTAVO, 'Bruna Miiller Lavarini', 'Danúbia Lacerda Gomes de Oliveira'])
def test_no_bloco_com_memo_assinado_troca_pelo_aguarda(monkeypatch, signatario):
    sei, numero = _deproc_assinado_por(signatario)
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert registro.marcadores_adicionados == [tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO]
    assert registro.marcadores_removidos == [tags.TAG_MEMO_DEPROC_COPARTICIPACAO]
    assert registro.marcadores_atuais == AGUARDA_DEPROC
    dados = registro.to_dict()
    assert dados['marcadores_adicionados'] == tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO
    assert dados['marcadores_removidos'] == tags.TAG_MEMO_DEPROC_COPARTICIPACAO
    assert dados['prox_acao'] == ProxAcao.AGUARDAR_RETORNO_DEPROC
    assert 'memo_deproc_sei' not in dados
    assert dados['verificar_marcadores_marcador_trocado'] == (f'01.10.B - No Bloco DEPROC: Coparticipação -> 01.10.B.1 - Aguarda DEPROC: Coparticipação: {numero} ({signatario})')
    # Depois da troca, tudo condiz
    assert _inconsistencia(registro) is None


def test_no_bloco_todas_infos_assinado_troca_pelo_encaminhado(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, assinado=True, signatario='Danúbia Lacerda Gomes de Oliveira')
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_TODAS_INFOS]
    registro = _passar(monkeypatch, marcadores, sei, {'prox_acao': ProxAcao.ASSINAR_MEMO_APIS_TODAS_INFOS})

    assert registro.marcadores_atuais == [tags.TAG_PROCESSO_NOVO, tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS]
    assert registro.to_dict()['prox_acao'] == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert _inconsistencia(registro) is None


def test_no_bloco_com_memo_nao_assinado_nao_troca(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert registro.marcadores_adicionados == []
    assert 'prox_acao' not in registro.to_dict()
    assert 'verificar_marcadores_marcador_trocado' not in registro.to_dict()


def test_no_bloco_assinado_por_outra_pessoa_nao_troca(monkeypatch):
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(assinado=True), {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert registro.marcadores_adicionados == []
    assert _acao(registro) == AcaoSugerida.TROCAR_MARCADOR_ASSINADO


def test_no_bloco_assinado_em_processo_fechado_reabre_troca_e_conclui(monkeypatch):
    sei, numero = _deproc_assinado_por()
    eventos = []
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, eventos=eventos)

    assert eventos == [
        'reabrir',
        'reaberto',
        ('adicionar', tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO),
        ('remover', tags.TAG_MEMO_DEPROC_COPARTICIPACAO),
        'concluir',
    ]
    dados = registro.to_dict()
    assert dados['verificar_marcadores_marcador_trocado'].endswith(f'{numero} ({GUSTAVO}) (processo reaberto e concluído de novo)')
    assert dados['prox_acao'] == ProxAcao.AGUARDAR_RETORNO_DEPROC
    assert dados['erro'] is None
    assert _inconsistencia(registro) is None


def test_processo_fechado_com_manual_nao_reabre(monkeypatch):
    sei, _ = _deproc_assinado_por()
    eventos = []
    registro = _passar(monkeypatch, [*NO_BLOCO_DEPROC, 'MANUAL'], sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, eventos=eventos)

    assert eventos == []
    assert _acao(registro) == AcaoSugerida.TROCAR_MARCADOR_ASSINADO


def test_processo_fechado_que_nao_reabre_nao_troca(monkeypatch):
    sei, _ = _deproc_assinado_por()
    eventos = []
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, eventos=eventos, reabre=False)

    assert eventos == ['reabrir']
    assert registro.marcadores_adicionados == []
    assert 'não pôde ser reaberto' in _inconsistencia(registro)


def test_processo_reaberto_sem_o_marcador_cadastrado_e_concluido_de_novo(monkeypatch):
    sei, _ = _deproc_assinado_por()
    eventos = []
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, eventos=eventos, cadastrados=set())

    assert eventos == ['reabrir', 'reaberto', 'concluir']
    assert 'não está cadastrado no SEI' in _inconsistencia(registro)


def test_processo_reaberto_que_nao_conclui_e_erro(monkeypatch):
    sei, _ = _deproc_assinado_por()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, aberto=False, conclui=False)

    assert registro.marcadores_atuais == AGUARDA_DEPROC
    dados = registro.to_dict()
    assert 'não foi concluído de novo' in dados['erro']
    # A troca foi feita: o marcador vai para a planilha; a prox_acao pede para
    # verificar o erro
    assert registro.prox_acao_atualizada == ProxAcao.AGUARDAR_RETORNO_DEPROC
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_ERRO}'
    assert dados['estado_atual'] == tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO
    assert dados['marcadores_adicionados'] == tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO


def test_no_bloco_assinado_de_pedido_anterior_nao_troca(monkeypatch):
    sei, _ = _deproc_assinado_por()
    sei.memo_apis()  # novo pedido da APIS depois do memo
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert registro.marcadores_adicionados == []
    assert 'pedido anterior' in _inconsistencia(registro)


def test_no_bloco_assinado_com_marcadores_inconsistentes_nao_troca(monkeypatch):
    sei, _ = _deproc_assinado_por()
    registro = _passar(monkeypatch, [tags.TAG_MEMO_DEPROC_COPARTICIPACAO], sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC})

    assert registro.marcadores_adicionados == []


def test_no_bloco_assinado_sem_o_aguarda_cadastrado_nao_troca(monkeypatch):
    sei, _ = _deproc_assinado_por()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': ProxAcao.ASSINAR_DEPROC}, cadastrados=set())

    assert registro.marcadores_adicionados == []
    assert 'não está cadastrado no SEI' in _inconsistencia(registro)
    assert registro.erro is None


def test_no_bloco_assinado_mantem_prox_acao_da_deproc(monkeypatch):
    sei, _ = _deproc_assinado_por()
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, sei, {'prox_acao': 'DEPROC: assinar memo de resultado'})

    assert registro.marcadores_atuais == AGUARDA_DEPROC
    assert 'prox_acao' not in registro.to_dict()


def test_aba_vazia_verifica_todos_os_processos_da_planilha(monkeypatch, tmp_path):
    """Sem processos na aba geacs_verificar_marcadores, o fluxo verifica todos
    os processos da planilha de controle geral."""
    arquivo = tmp_path / 'controle.xlsx'
    pd.DataFrame([{'num_processo': 'P1', 'prox_acao': 'A'}, {'num_processo': 'P2', 'prox_acao': 'B'}]).to_excel(arquivo, sheet_name='processos', index=False)
    verificados = []

    def processar(driver, num_processo, linha):
        verificados.append((num_processo, linha['prox_acao']))
        return RegistroVerificarMarcadores(num_processo=num_processo, data_execucao=fluxo.AGORA, fluxo=fluxo.FLUXO)

    monkeypatch.setattr(fluxo, 'ARQ_LOG', tmp_path / 'log.log')
    monkeypatch.setattr(fluxo, 'ler_processos_a_processar', lambda aba: [])
    monkeypatch.setattr(fluxo, 'PlanilhaControleGeral', lambda *a, **k: PlanilhaControleGeral(*a, arquivo=arquivo, **k))
    monkeypatch.setattr(fluxo, 'abrir_sei', lambda unidade: SimpleNamespace(quit=lambda: verificados.append('quit')))
    monkeypatch.setattr(fluxo, '_processar_linha', processar)

    fluxo.main()

    assert verificados[:2] == [('P1', 'A'), ('P2', 'B')]
    assert verificados[-1] == 'quit'


def test_aba_e_planilha_vazias_nao_abrem_o_sei(monkeypatch, tmp_path):
    monkeypatch.setattr(fluxo, 'ARQ_LOG', tmp_path / 'log.log')
    monkeypatch.setattr(fluxo, 'ler_processos_a_processar', lambda aba: [])
    monkeypatch.setattr(fluxo, 'PlanilhaControleGeral', lambda *a, **k: PlanilhaControleGeral(*a, arquivo=tmp_path / 'controle.xlsx', **k))
    monkeypatch.setattr(fluxo, 'abrir_sei', lambda unidade: pytest.fail('sem processos, não abre o SEI'))

    fluxo.main()


def test_migracao_calcula_o_estado_atual_dos_marcadores_finais():
    """Linhas de antes da coluna estado_atual (18/11/2026): o estado vem de
    marcadores_finais (hoje marcadores_pos_fluxo), e o da DEPROC, de
    marcadores_deproc_finais."""
    linha = {
        'num_processo': 'PROC',
        'marcadores_finais': f'{tags.TAG_PROCESSO_NOVO}; {tags.TAG_NO_BLOCO_APIS_SEM_USO}; PLANILHADO',
        'marcadores_deproc_finais': f'{tags.TAG_DEPROC_TRATADO}; {tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA}',
    }
    sem_estado = {'num_processo': 'P2', 'marcadores_finais': tags.TAG_PROCESSO_NOVO}
    ja_tem = {'num_processo': 'P3', 'marcadores_finais': tags.TAG_PROCESSO_NOVO, 'estado_atual': 'X'}

    migrada, sem, tem = migrar_colunas([linha, sem_estado, ja_tem])

    assert migrada['estado_atual'] == tags.TAG_NO_BLOCO_APIS_SEM_USO
    assert migrada['estado_atual_deproc'] == tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA
    assert migrada['marcadores_pos_fluxo'] == linha['marcadores_finais']
    assert 'demais_marcadores' not in migrada
    assert sem['estado_atual'] is None
    assert tem['estado_atual'] == 'X'


# ---------------------------------------------------------------------------
# prox_acao e erro com o prefixo "VERIFICAR MARCADORES: "
# ---------------------------------------------------------------------------


def test_prox_acao_de_passagem_anterior_do_verificar_e_recalculada(monkeypatch):
    linha = {'prox_acao': f'{PREFIXO}{AcaoSugerida.RODAR_INICIAL}', 'tipo_erro': f'{PREFIXO}Inconsistencia', 'erro': f'{PREFIXO}antiga'}
    # Situação conhecida (memo da rodada no bloco): a prox_acao dela
    registro = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha)
    dados = registro.to_dict()
    assert _inconsistencia(registro) is None
    assert dados['prox_acao'] == ProxAcao.ASSINAR_DEPROC
    # O erro de uma passagem anterior do verificar sai
    assert dados['tipo_erro'] is None
    assert dados['erro'] is None

    # Sem situação conhecida (retomada): a que o geacs_inicial daria
    sei = SEIFalso()
    sei.novo_processo()
    marcadores = [tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA]
    assert _passar(monkeypatch, marcadores, sei, linha).to_dict()['prox_acao'] == ProxAcao.VERIFICAR_ERRO


def test_aguardando_resposta_fica_sem_erro(monkeypatch):
    # Erro da passagem do geacs_inicial (até 27/11/2026 a parada era erro)
    sei = _processo_deproc(assinado=True)
    linha = {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO, 'tipo_erro': 'ErroAvaliacao', 'erro': 'Processamento parado: memo enviado, aguardando resposta'}
    dados = _passar(monkeypatch, AGUARDA_DEPROC, sei, linha).to_dict()

    assert dados['prox_acao'] == ProxAcao.AGUARDAR_RETORNO_DEPROC
    assert dados['tipo_erro'] is None
    assert dados['erro'] is None


def test_erro_de_outro_fluxo_fica_sem_problema_do_verificar(monkeypatch):
    linha = {'prox_acao': ProxAcao.VERIFICAR_ERRO, 'tipo_erro': 'ErroAvaliacao', 'erro': 'falha do geacs_todas_infos'}
    dados = _passar(monkeypatch, NO_BLOCO_DEPROC, _processo_deproc(), linha).to_dict()

    assert 'prox_acao' not in dados
    assert 'tipo_erro' not in dados
    assert 'erro' not in dados


def test_unidade_sem_acesso_na_geacs(monkeypatch):
    from sei_automacao.exceptions import UnidadeSemAcessoException  # noqa: PLC0415

    def sem_acesso(driver, num):
        raise UnidadeSemAcessoException('sem acesso')

    monkeypatch.setattr(fluxo, 'acessar_processo', sem_acesso)
    dados = fluxo._processar_linha(object(), 'PROC', {}).to_dict()

    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_ACESSO_GEACS}'
    assert dados['tipo_erro'] == f'{PREFIXO}UnidadeSemAcessoException'


# ---------------------------------------------------------------------------
# Verificação na unidade da DEPROC
# ---------------------------------------------------------------------------

DEPROC_NO_BLOCO = [tags.TAG_DEPROC_TRATADO, tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA]
DEPROC_ENCAMINHADO = [tags.TAG_DEPROC_TRATADO, tags.TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA]
ENCAMINHADO_APIS = [tags.TAG_PROCESSO_NOVO, tags.TAG_ENCAMINHADO_APIS_TODAS_INFOS]


def _na_deproc(monkeypatch, registro, marcadores_deproc, *, sem_acesso: bool = False):
    """A passagem pela DEPROC, depois da passagem pela GEACS (registro)."""

    def acessar(driver, num):
        if sem_acesso:
            from sei_automacao.exceptions import UnidadeSemAcessoException  # noqa: PLC0415

            raise UnidadeSemAcessoException('sem acesso')

    monkeypatch.setattr(fluxo, 'acessar_processo', acessar)
    monkeypatch.setattr(fluxo, 'listar_marcadores', lambda driver: list(marcadores_deproc))
    fluxo.verificar_na_deproc(object(), registro)
    return registro


def _retorno_final_encaminhado(monkeypatch):
    sei = SEIFalso()
    sei.novo_processo()
    sei.memo_geacs(ASSUNTO_MEMO_APIS_COM_TODAS_AS_INFORMACOES, assinado=True, signatario=GUSTAVO)
    return _passar(monkeypatch, ENCAMINHADO_APIS, sei, {'prox_acao': ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO})


def _aguarda_deproc(monkeypatch, *, resultado_assinado: bool | None):
    """GEACS em "Aguarda DEPROC" com o memo DEPROC assinado e, se não None, o
    memo de resultado da DEPROC na rodada."""
    sei = _processo_deproc(assinado=True)
    if resultado_assinado is not None:
        texto = f'Assunto: {ASSUNTO_MEMO_GEACS_CALCULO_COPA}' + ('\nDocumento assinado eletronicamente por Fulana' if resultado_assinado else '')
        sei.novo_doc('Memorando 3', UNIDADE_DEPROC, texto)
    return _passar(monkeypatch, AGUARDA_DEPROC, sei, {'prox_acao': ProxAcao.AGUARDAR_RESPOSTA_MEMO})


@pytest.mark.parametrize(
    ('marcadores', 'linha', 'passa'),
    [
        (AGUARDA_DEPROC, {}, True),
        ([tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_APIS_TODAS_INFOS], {}, True),
        (ENCAMINHADO_APIS, {}, True),
        # Memo DEPROC ainda no bloco: não foi à DEPROC
        (NO_BLOCO_DEPROC, {}, False),
        ([tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA], {}, False),
        # Já passou pela DEPROC (marcadores da DEPROC na planilha)
        (NO_BLOCO_DEPROC, {'estado_atual_deproc': tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA}, True),
        (NO_BLOCO_DEPROC, {'marcadores_deproc_pos_fluxo': tags.TAG_DEPROC_TRATADO}, True),
        # Marcadores da GEACS não lidos: o estado da planilha
        (None, {'estado_atual': tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO}, True),
        (None, {'estado_atual': tags.TAG_MEMO_DEPROC_COPARTICIPACAO}, False),
    ],
)
def test_processos_que_passam_pela_deproc(marcadores, linha, passa):
    registro = RegistroVerificarMarcadores(num_processo='PROC')
    if marcadores is not None:
        tags.registrar_tags(registro, marcadores)
        registro.marcadores_lidos = True

    assert conferencia_prox_acao.passa_pela_deproc(registro, linha) is passa


def test_retorno_final_com_a_deproc_encaminhada_e_consistente(monkeypatch):
    registro = _na_deproc(monkeypatch, _retorno_final_encaminhado(monkeypatch), DEPROC_ENCAMINHADO)

    dados = registro.to_dict()
    assert _inconsistencia(registro) is None
    assert dados['marcadores_deproc_pre_fluxo'] == dados['marcadores_deproc_pos_fluxo'] == '; '.join(DEPROC_ENCAMINHADO)
    assert dados['estado_atual_deproc'] == tags.TAG_DEPROC_ENCAMINHADO_MEMO_CALCULO_COPA
    assert dados['prox_acao'] == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert dados['erro'] is None


def test_retorno_final_com_a_deproc_no_bloco(monkeypatch):
    registro = _na_deproc(monkeypatch, _retorno_final_encaminhado(monkeypatch), DEPROC_NO_BLOCO)

    dados = registro.to_dict()
    assert _acao(registro) == AcaoSugerida.TROCAR_MARCADOR_DEPROC
    assert _inconsistencia(registro).startswith('DEPROC: GEACS em "01.12.1 - Encaminhado APIS: Todas as Infos"')
    # Concluído na GEACS: a prox_acao fica a de concluído, e o problema vai para o erro
    assert dados['prox_acao'] == ProxAcao.MEMO_APIS_TODAS_INFOS_ENCAMINHADO
    assert dados['erro'].startswith(f'{PREFIXO}DEPROC: ')
    assert dados['estado_atual_deproc'] == tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA


def test_retorno_final_sem_marcadores_na_deproc(monkeypatch):
    registro = _na_deproc(monkeypatch, _retorno_final_encaminhado(monkeypatch), [])

    assert _acao(registro) == AcaoSugerida.VERIFICAR_MANUALMENTE
    assert 'a DEPROC está sem marcador de estado' in _inconsistencia(registro)


def test_aguarda_deproc_sem_a_deproc_ter_rodado(monkeypatch):
    for marcadores_deproc in ([], [tags.TAG_DEPROC_TRATADO, tags.TAG_DEPROC_RELATORIO_ANEXADO]):
        registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=None), marcadores_deproc)

        assert _inconsistencia(registro) is None
        assert registro.to_dict()['prox_acao'] == f'{PREFIXO}{AcaoSugerida.RODAR_DEPROC_CALCULA_COPA}'


def test_aguarda_deproc_com_o_memo_de_resultado_no_bloco(monkeypatch):
    registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=False), DEPROC_NO_BLOCO)

    dados = registro.to_dict()
    assert _inconsistencia(registro) is None
    assert dados['prox_acao'] == ProxAcao.DEPROC_ASSINAR_MEMO_RESULTADO
    assert dados['erro'] is None


def test_aguarda_deproc_com_o_memo_de_resultado_assinado_e_a_deproc_no_bloco(monkeypatch):
    registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=True), DEPROC_NO_BLOCO)

    assert _acao(registro) == f'{AcaoSugerida.RODAR_TODAS_INFOS} | {AcaoSugerida.TROCAR_MARCADOR_DEPROC}'
    assert 'a DEPROC continua com "01.02 - No Bloco GEACS: Memo Cálculo COPA"' in _inconsistencia(registro)


def test_aguarda_deproc_com_a_deproc_encaminhada(monkeypatch):
    # Com o memo de resultado assinado: rodar o geacs_todas_infos
    registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=True), DEPROC_ENCAMINHADO)
    assert _inconsistencia(registro) is None
    assert registro.to_dict()['prox_acao'] == f'{PREFIXO}{AcaoSugerida.RODAR_TODAS_INFOS}'

    # Sem ele na rodada da GEACS: verificar
    registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=None), DEPROC_ENCAMINHADO)
    assert 'a GEACS não tem o memo de resultado da DEPROC assinado na rodada' in _inconsistencia(registro)


def test_marcadores_inconsistentes_na_deproc(monkeypatch):
    registro = _na_deproc(monkeypatch, _retorno_final_encaminhado(monkeypatch), [tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA])

    assert _acao(registro) == AcaoSugerida.CORRIGIR_MARCADORES_DEPROC
    assert _inconsistencia(registro).startswith('DEPROC: Marcadores inconsistentes')


def test_deproc_sem_acesso(monkeypatch):
    registro = _na_deproc(monkeypatch, _aguarda_deproc(monkeypatch, resultado_assinado=None), [], sem_acesso=True)

    dados = registro.to_dict()
    assert dados['prox_acao'] == f'{PREFIXO}{AcaoSugerida.VERIFICAR_ACESSO_DEPROC}'
    assert dados['tipo_erro'] == f'{PREFIXO}UnidadeSemAcessoException'
    assert dados['erro'].startswith(f'{PREFIXO}DEPROC: ')
    # Os marcadores da DEPROC não foram lidos: as colunas ficam como estão
    assert 'marcadores_deproc_pos_fluxo' not in dados
    # Os da GEACS, sim
    assert dados['estado_atual'] == tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO


def test_main_verifica_na_deproc_depois_da_geacs(monkeypatch, tmp_path):
    arquivo = tmp_path / 'controle.xlsx'
    pd.DataFrame([{'num_processo': 'P1', 'prox_acao': 'A'}, {'num_processo': 'P2', 'prox_acao': 'B'}]).to_excel(arquivo, sheet_name='processos', index=False)
    eventos = []
    marcadores_geacs = {'P1': AGUARDA_DEPROC, 'P2': NO_BLOCO_DEPROC}

    def processar(driver, num_processo, linha):
        eventos.append(('geacs', num_processo))
        registro = RegistroVerificarMarcadores(num_processo=num_processo, data_execucao=fluxo.AGORA, fluxo=fluxo.FLUXO)
        tags.registrar_tags(registro, marcadores_geacs[num_processo])
        registro.marcadores_lidos = True
        return registro

    def na_deproc(driver, registro):
        eventos.append(('deproc', registro.num_processo))
        registro.marcadores_deproc = list(DEPROC_NO_BLOCO)
        registro.marcadores_deproc_lidos = True

    monkeypatch.setattr(fluxo, 'ARQ_LOG', tmp_path / 'log.log')
    monkeypatch.setattr(fluxo, 'ler_processos_a_processar', lambda aba: [])
    monkeypatch.setattr(fluxo, 'PlanilhaControleGeral', lambda *a, **k: PlanilhaControleGeral(*a, arquivo=arquivo, **k))
    monkeypatch.setattr(fluxo, 'abrir_sei', lambda unidade: eventos.append(('abrir', unidade)) or SimpleNamespace(quit=lambda: eventos.append('quit')))
    monkeypatch.setattr(fluxo, 'alterar_unidade_sei', lambda driver, unidade: eventos.append(('unidade', unidade)))
    monkeypatch.setattr(fluxo, '_processar_linha', processar)
    monkeypatch.setattr(fluxo, 'verificar_na_deproc', na_deproc)

    fluxo.main()

    # Todos na GEACS e depois, na DEPROC, só os que já deveriam ter passado por ela
    assert eventos == [('abrir', UNIDADE_GEACS), ('geacs', 'P1'), ('geacs', 'P2'), ('unidade', UNIDADE_DEPROC), ('deproc', 'P1'), 'quit']
    processos = pd.read_excel(arquivo, sheet_name='processos').set_index('num_processo')
    assert processos.loc['P1', 'estado_atual_deproc'] == tags.TAG_DEPROC_NO_BLOCO_MEMO_CALCULO_COPA
    assert pd.isna(processos.loc['P2', 'estado_atual_deproc'])
    assert list(processos.columns[-4:]) == ['marcadores_pre_fluxo', 'marcadores_pos_fluxo', 'marcadores_deproc_pre_fluxo', 'marcadores_deproc_pos_fluxo']
