"""Fluxo dos processos NOVOS (main.py e processar_novo.py) em várias
passagens, com o SEI simulado."""

from Registro import ProxAcao
from tags import TAG_MEMOS_DISA_DEPROC_NO_BLOCO, TAG_PROCESSO_NOVO

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import ASSUNTO_MEMO_DISA
from tests.sei_falso import MANTIS_DEPENDENTE_USOU, bases, curto

NOVO = '1 - Processo NOVO'
DISA = '1.6 - Avaliado Uso Rede Própria DISA'
MANTIS = '1.8 - Avaliado Uso Rede Própria MANTIS'
MEMO_DISA = '1.9 - Memo DISA Uso Rede Própria'
CONCLUIDO_DISA_DEPROC = '1.10 - Memos DISA e DEPROC no Bloco'
CONCLUIDO_DEPROC = '1.10 - Memo DEPROC Coparticipação'


def test_alguem_usou_conclui_com_um_estado(sei):
    sei.novo_processo()
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]
    assert sei.qnt_memos_geacs == 2
    assert registro.prox_acao == ProxAcao.ASSINAR_DISA_DEPROC
    assert [curto(t) for t in registro.marcadores_removidos] == [DISA, MANTIS, MEMO_DISA]
    assert registro.memo_disa_sei
    assert registro.memo_deproc_sei


def test_concluido_e_conferido_na_passagem_seguinte(sei):
    sei.novo_processo()
    sei.passar(bases())
    registro = sei.passar(bases())

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DISA_DEPROC
    assert registro.qnt_memos_geacs_esperada == 2
    assert sei.qnt_memos_geacs == 2


def test_ninguem_usou_so_memo_deproc(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False))

    assert sei.tags_curtas == [NOVO, CONCLUIDO_DEPROC]
    assert sei.qnt_memos_geacs == 1
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC


def test_titular_fora_da_base_disa_mantem_informativo(sei):
    sei.novo_processo()
    sei.passar(bases(tit_na_disa=False))

    assert sei.tags_curtas == [NOVO, '1.2.2 - Mat. N Encontradas Base DISA', CONCLUIDO_DEPROC]


def test_falha_ao_criar_deproc_retoma_pelo_estado(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 2
    registro = sei.passar(bases())
    assert sei.tags_curtas == [NOVO, MEMO_DISA]
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO

    sei.falhar_memo_n = None
    registro = sei.passar(bases())
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]
    assert sei.qnt_memos_geacs == 2
    assert registro.memos_criados == ['memo_deproc']


def test_base_geral_para_com_memo_a_apis(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_na_geral=False))
    assert sei.tags_curtas == [NOVO, '1.2.1 - Mat. N Encontradas Base Geral', '1.6.1 - Memo APIS Mat. N Encontradas']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS

    registro = sei.passar(bases(tit_na_geral=False))
    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
    assert sei.qnt_memos_geacs == 1


def test_sem_memo_da_apis(sei):
    sei.novo_processo(com_memo_apis=False)
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Memo APIS Sem Memo p/ GEACS']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO


def test_periodo_variavel_para_dependentes(sei):
    sei.novo_processo(extra='Dependente 555: 01/02/2024 a 01/03/2024')
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.1 - Período Variável p/ Dependentes', '1.7 - Memo APIS Período Dependentes']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_PERIODO_DEPS


def test_uso_no_mantis_alem_da_disa(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)

    assert sei.tags_curtas == [NOVO, '1.8.1 - Memo DISA Validar Usos MANTIS']
    assert registro.mats_uso_mantis_alem_disa == ['555 (dependente)']


def test_memo_a_mais_sem_assunto_conhecido_gera_erro(sei):
    sei.novo_processo()
    sei.passar(bases(tit_usou=False))
    sei.memo_geacs('Outro assunto')

    registro = sei.passar(bases(tit_usou=False))
    assert registro.prox_acao == ProxAcao.VERIFICAR_QNT_MEMOS
    assert 'indica 1 memorando(s)' in registro.erro


def test_falha_na_remocao_deixa_dois_estados_e_gera_erro(sei):
    sei.novo_processo()
    sei.falhar_remocao = True
    sei.passar(bases())
    assert sei.tags_curtas == [NOVO, DISA, MANTIS]

    sei.falhar_remocao = False
    registro = sei.passar(bases())
    assert 'mais de um marcador de estado' in registro.erro


# --- Retomada pelo assunto (memo criado sem marcador) -------------------------


def test_memo_deproc_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MEMO_DISA]
    sei.memo_geacs(ASSUNTO_MEMO_DISA)
    numero_deproc = sei.memo_geacs(ASSUNTO_MEMO_DEPROC)

    registro = sei.passar(bases())
    assert registro.erro is None
    assert sei.qnt_memos_geacs == 2
    assert registro.memo_deproc_na_arvore
    assert registro.memo_deproc_sei == numero_deproc
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]


def test_memo_disa_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MANTIS]
    sei.memo_geacs(ASSUNTO_MEMO_DISA)

    registro = sei.passar(bases())
    assert registro.erro is None
    assert registro.memo_disa_na_arvore
    assert registro.memos_criados == ['memo_deproc']
    assert sei.qnt_memos_geacs == 2
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]


def test_memo_a_apis_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + DISA, 'Script v2 - 1.2.1 - Mat. N Encontradas Base Geral']
    sei.memo_geacs(ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS)

    registro = sei.passar(bases(tit_na_geral=False))
    assert registro.erro is None
    assert registro.memo_apis_mat_nao_encontradas_na_arvore
    assert sei.qnt_memos_geacs == 1
    assert sei.tags_curtas[-1] == '1.6.1 - Memo APIS Mat. N Encontradas'


def test_memo_sem_marcador_de_outra_etapa_gera_erro(sei):
    # Estado 1.9: o memo seguinte só pode ser o DEPROC
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MEMO_DISA]
    sei.memo_geacs(ASSUNTO_MEMO_DISA)
    sei.memo_geacs(ASSUNTO_MEMO_DISA)

    registro = sei.passar(bases())
    assert registro.prox_acao == ProxAcao.VERIFICAR_QNT_MEMOS


# --- Versão anterior do fluxo -------------------------------------------------


def test_versao_anterior_sem_avaliacao_passa_pela_correcao(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMOS_DISA_DEPROC_NO_BLOCO]
    sei.memo_geacs('disa (versão anterior)')
    sei.memo_geacs('deproc (versão anterior)')

    registro = sei.passar(bases())
    assert registro.prox_acao == ProxAcao.ASSINAR_USO_REDE
    assert registro.memo_uso_rede_sei
    assert sei.qnt_memos_geacs == 3

    registro = sei.passar(bases())
    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DISA_DEPROC
    assert registro.qnt_memos_geacs_esperada == 3
