from extrator_dados_ui import FormatoMemorandoInvalido, extrair_dados_ui
from Registro import RegistroSepararProecessarNovos
from sei_automacao.documento import inserir_bloco_ass, obter_conteudo_doc
from sei_automacao.processo import adicionar_marcador, incluir_doc_sei_memo
from sei_automacao.processo.arvore import (
    selecionar_doc_arvore,
)
from selenium import webdriver

from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import MemoDeproc
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import MemoDisa


def processar_novo(
    driver: webdriver.Remote,
    registro: RegistroSepararProecessarNovos,
    tds_docs: list[dict],
    marcador_periodo_var_dep: str,
) -> dict:
    try:
        memos = [doc for doc in tds_docs if 'Memorando' in doc['nome_arvore']]

        ultimo_doc = memos[-1]
        registro.ult_memo_obtido = True

        selecionar_doc_arvore(driver, numero_sei=ultimo_doc['numero_sei'])
        doc_text = obter_conteudo_doc(driver, formato='texto')
        registro.conteudo_ult_memo_obtido = True

        try:
            dados_ui = extrair_dados_ui(doc_text)
            registro.matricula_titular = dados_ui.matricula_titular
            registro.nome_titular = dados_ui.nome_titular
            registro.periodo_titular = dados_ui.periodo_titular
            registro.matriculas_dependentes = dados_ui.matriculas_dependentes
            registro.periodo_dependentes = dados_ui.periodo_dependentes

        except FormatoMemorandoInvalido:
            registro.prox_acao = 'Verificar erro no formato do memo'
            raise

        registro.dados_ui = dados_ui

        if dados_ui.periodo_dependentes:
            adicionar_marcador(driver, marcador_periodo_var_dep)
            registro.marcador_periodo_variavel_deps = True

        # Memorando DISA
        memo_disa = MemoDisa(
            dados=dados_ui,
            nome_signatario='Bruna Miiller Lavarini',
            cargo_signatario='Gerência de Auditoria e Contas da Saúde',
        )
        incluir_doc_sei_memo(driver, **memo_disa.para_kwargs_inserir_doc())
        registro.memo_disa_criado = True

        inserir_bloco_ass(driver, 7697744)
        registro.memo_disa_inserido_bloco = True

        # Memorando DEPROC
        memo_deproc = MemoDeproc(
            dados=dados_ui,
            nome_signatario='Bruna Miiller Lavarini',
            cargo_signatario='Gerência de Auditoria e Contas da Saúde',
        )
        incluir_doc_sei_memo(driver, **memo_deproc.para_kwargs_inserir_doc())
        registro.memo_deproc_criado = True

        inserir_bloco_ass(driver, 7697744)
        registro.memo_deproc_inserido_bloco = True

        registro.prox_acao = 'Assinar memorandos e encaminhar'

        return registro

    except Exception as e:
        registro.erro = f'{type(e).__name__}: {e}'
        return registro
