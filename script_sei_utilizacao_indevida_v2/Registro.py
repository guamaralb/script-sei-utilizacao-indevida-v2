import traceback
from dataclasses import asdict, dataclass, field

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


class ProxAcao:
    """Valores padronizados da coluna prox_acao (facilitam o filtro e o
    resumo do log). Detalhes ficam nas demais colunas e no log."""

    # NOVOS
    ASSINAR_DISA_DEPROC = 'Assinar memos DISA e DEPROC e encaminhar'
    ASSINAR_DEPROC = 'Assinar memo DEPROC e encaminhar'
    ASSINAR_USO_REDE = 'Assinar memo de uso da rede própria e encaminhar'
    NADA_A_FAZER = 'Nada a fazer'
    NADA_A_FAZER_TODOS_USARAM = 'Nada a fazer: todos usaram a rede própria (memo dispensado)'
    FORA_DO_ESCOPO = 'Fora do escopo'

    # VELHOS
    PROCESSAR_VELHO = 'Processar VELHO'
    VELHO_AGUARDAR_CRITERIOS = 'VELHO: aguardar definição dos critérios das instruções'
    VELHO_TRANSFORMAR_PDF = 'VELHO: transformar Excel em PDF (não implementado)'
    VELHO_REFAZER_REL_UI = 'VELHO: refazer relatório de UI (não implementado)'
    VELHO_CONCLUIDO = 'VELHO: fluxo após conclusão (não implementado)'

    # Verificações manuais
    VERIFICAR_QNT_MEMOS = 'Verificar quantidade de memos da GEACS'
    VERIFICAR_FORMATO_MEMO = 'Verificar formato do memo da APIS'
    VERIFICAR_MAT_NAO_ENCONTRADAS = 'Verificar matrículas não encontradas'
    ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS = 'Assinar memo à APIS (matrículas não encontradas) e encaminhar'
    VERIFICAR_ERRO = 'Verificar erro'


# Próximas ações definidas antes do erro que devem ser mantidas
_PROX_ACOES_DE_ERRO = frozenset({
    ProxAcao.VERIFICAR_FORMATO_MEMO,
    ProxAcao.VERIFICAR_MAT_NAO_ENCONTRADAS,
    ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS,
})


def _mensagem_erro(erro: Exception) -> str:
    """Mensagem curta para a planilha. Erros do Selenium trazem o
    stacktrace do chromedriver no texto; fica só a primeira linha útil ou,
    sem mensagem, a função do script/biblioteca em que o erro ocorreu."""
    texto = (getattr(erro, 'msg', None) or str(erro)).strip()
    primeira_linha = texto.splitlines()[0].strip() if texto else ''
    if primeira_linha and primeira_linha != 'Message:':
        return primeira_linha

    quadros = traceback.extract_tb(erro.__traceback__)
    quadro = next((q for q in reversed(quadros) if 'selenium' not in q.filename.replace('\\', '/')), None)
    local = f' em {quadro.name}' if quadro else ''
    if type(erro).__name__ == 'TimeoutException':
        return f'Tempo esgotado esperando elemento do SEI{local} (detalhes no log)'
    return f'{type(erro).__name__} sem mensagem{local} (detalhes no log)'


def registrar_erro(registro, erro: Exception) -> None:
    registro.tipo_erro = type(erro).__name__
    registro.erro = _mensagem_erro(erro)
    if registro.prox_acao not in _PROX_ACOES_DE_ERRO:
        registro.prox_acao = ProxAcao.VERIFICAR_ERRO


def _juntar(valores: list[str]) -> str:
    return '; '.join(valores)


@dataclass
class RegistroMain:
    num_processo: str
    data_execucao: str | None = None

    fluxo: str | None = None
    prox_acao: str | None = None
    tipo_erro: str | None = None
    erro: str | None = None

    qnt_docs_geacs_na_arvore: int = -1
    qnt_memos_geacs_na_arvore: int = -1
    qnt_memos_geacs_esperada: int | None = None

    marcadores_sei: list[str] = field(default_factory=list)
    marcadores_adicionados: list[str] = field(default_factory=list)

    tag_processo_novo: bool = False
    tag_processo_velho: bool = False

    tag_planilhado: bool = False
    tag_ui_inserida: bool = False

    # Instruções da APIS
    ult_memo_obtido: bool = False
    conteudo_ult_memo_obtido: bool = False
    memo_apis_sei: str | None = None
    modelo_memo_apis: str | None = None
    dados_ui: DadosUI | None = None
    tag_periodo_var_deps: bool = False

    # Uso da rede própria
    tag_avaliado_se_usou_rede_propria: bool = False
    tit_usou: bool | None = None
    deps_que_usaram: list[str] = field(default_factory=list)
    deps_que_nao_usaram: list[str] = field(default_factory=list)
    # Matrículas não encontradas (sem sufixo: base da rede própria/DISA)
    titular_nao_encontrado_base_geral: str | None = None
    deps_nao_encontrados_base_geral: list[str] = field(default_factory=list)
    titular_nao_encontrado: str | None = None
    deps_nao_encontrados: list[str] = field(default_factory=list)
    tag_mat_nao_encontradas_base_geral_novo: bool = False
    tag_mat_nao_encontradas_base_geral_velho: bool = False
    tag_mat_nao_encontradas_novo: bool = False
    tag_mat_nao_encontradas_velho: bool = False
    memo_apis_mat_nao_encontradas_criado: bool = False
    memo_apis_mat_nao_encontradas_inserido_bloco: bool = False
    memo_apis_mat_nao_encontradas_na_arvore: bool = False
    memo_apis_mat_nao_encontradas_sei: str | None = None

    # Fluxo normal (NOVOS)
    memo_disa_criado: bool = False
    memo_disa_inserido_bloco: bool = False
    memo_disa_sei: str | None = None
    memo_deproc_criado: bool = False
    memo_deproc_inserido_bloco: bool = False
    memo_deproc_sei: str | None = None
    tag_memos_no_bloco: bool = False
    tag_memo_deproc_no_bloco: bool = False

    # Fluxo de correção (NOVOS enviados sem avaliação)
    memo_uso_rede_criado: bool = False
    memo_uso_rede_inserido_bloco: bool = False
    memo_uso_rede_na_arvore: bool = False
    memo_uso_rede_sei: str | None = None
    tag_memo_nao_usou_rede_propria_no_bloco: bool = False

    # VELHOS
    instrucoes_velho: str | None = None
    tag_transformar_excel_em_pdf: bool = False
    tag_refazer_rel_ui: bool = False
    tag_rel_ui_transformado_pdf: bool = False
    tag_novo_rel_ui_gerado: bool = False

    def to_dict(self) -> dict:
        dados_ui = self.dados_ui
        periodo_deps = dados_ui.periodo_dependentes if dados_ui else None

        return {
            'num_processo': self.num_processo,
            'data_execucao': self.data_execucao,
            'fluxo': self.fluxo,
            'prox_acao': self.prox_acao,
            'tipo_erro': self.tipo_erro,
            'erro': self.erro,
            'matricula_titular': (dados_ui.matricula_titular if dados_ui else None),
            'nome_titular': dados_ui.nome_titular if dados_ui else None,
            'periodo_titular': (dados_ui.periodo_titular if dados_ui else None),
            'matriculas_dependentes': (dados_ui.matriculas_dependentes if dados_ui else None),
            # Modelo novo: só indica se há período variável (sem as datas).
            # Modelo velho: as datas ficam em periodo_dependentes.
            'tem_periodo_var_deps': bool(periodo_deps) if dados_ui else None,
            'periodo_dependentes': periodo_deps if isinstance(periodo_deps, str) else None,
            'memo_apis_sei': self.memo_apis_sei,
            'modelo_memo_apis': self.modelo_memo_apis,
            'qnt_docs_geacs_na_arvore': self.qnt_docs_geacs_na_arvore,
            'qnt_memos_geacs_na_arvore': self.qnt_memos_geacs_na_arvore,
            'qnt_memos_geacs_esperada': self.qnt_memos_geacs_esperada,
            'marcadores_sei': _juntar(self.marcadores_sei),
            'marcadores_adicionados': _juntar(self.marcadores_adicionados),
            'tag_processo_novo': self.tag_processo_novo,
            'tag_processo_velho': self.tag_processo_velho,
            'tag_planilhado': self.tag_planilhado,
            'tag_ui_inserida': self.tag_ui_inserida,
            'ult_memo_obtido': self.ult_memo_obtido,
            'conteudo_ult_memo_obtido': self.conteudo_ult_memo_obtido,
            'tag_periodo_variavel_deps': self.tag_periodo_var_deps,
            'tag_avaliado_se_usou_rede_propria': (self.tag_avaliado_se_usou_rede_propria),
            'tit_usou': self.tit_usou,
            'deps_que_usaram': _juntar(self.deps_que_usaram),
            'deps_que_nao_usaram': _juntar(self.deps_que_nao_usaram),
            'titular_nao_encontrado_base_geral': self.titular_nao_encontrado_base_geral,
            'deps_nao_encontrados_base_geral': _juntar(self.deps_nao_encontrados_base_geral),
            'titular_nao_encontrado': self.titular_nao_encontrado,
            'deps_nao_encontrados': _juntar(self.deps_nao_encontrados),
            'tag_mat_nao_encontradas_base_geral_novo': self.tag_mat_nao_encontradas_base_geral_novo,
            'tag_mat_nao_encontradas_base_geral_velho': self.tag_mat_nao_encontradas_base_geral_velho,
            'tag_mat_nao_encontradas_novo': self.tag_mat_nao_encontradas_novo,
            'tag_mat_nao_encontradas_velho': self.tag_mat_nao_encontradas_velho,
            'memo_apis_mat_nao_encontradas_criado': self.memo_apis_mat_nao_encontradas_criado,
            'memo_apis_mat_nao_encontradas_inserido_bloco': self.memo_apis_mat_nao_encontradas_inserido_bloco,
            'memo_apis_mat_nao_encontradas_na_arvore': self.memo_apis_mat_nao_encontradas_na_arvore,
            'memo_apis_mat_nao_encontradas_sei': self.memo_apis_mat_nao_encontradas_sei,
            'memo_disa_criado': self.memo_disa_criado,
            'memo_disa_inserido_bloco': self.memo_disa_inserido_bloco,
            'memo_disa_sei': self.memo_disa_sei,
            'memo_deproc_criado': self.memo_deproc_criado,
            'memo_deproc_inserido_bloco': self.memo_deproc_inserido_bloco,
            'memo_deproc_sei': self.memo_deproc_sei,
            'tag_memos_no_bloco': self.tag_memos_no_bloco,
            'tag_memo_deproc_no_bloco': self.tag_memo_deproc_no_bloco,
            'memo_uso_rede_criado': self.memo_uso_rede_criado,
            'memo_uso_rede_inserido_bloco': self.memo_uso_rede_inserido_bloco,
            'memo_uso_rede_na_arvore': self.memo_uso_rede_na_arvore,
            'memo_uso_rede_sei': self.memo_uso_rede_sei,
            'tag_memo_nao_usou_rede_propria_no_bloco': (self.tag_memo_nao_usou_rede_propria_no_bloco),
            'instrucoes_velho': self.instrucoes_velho,
            'tag_transformar_excel_em_pdf': self.tag_transformar_excel_em_pdf,
            'tag_refazer_rel_ui': self.tag_refazer_rel_ui,
            'tag_rel_ui_transformado_pdf': self.tag_rel_ui_transformado_pdf,
            'tag_novo_rel_ui_gerado': self.tag_novo_rel_ui_gerado,
        }


@dataclass
class RegistroMainAddMemoNaoUsouRedePropria:
    num_processo: str
    data_execucao: str | None = None

    fluxo: str | None = None
    prox_acao: str | None = None
    tipo_erro: str | None = None
    erro: str | None = None

    matricula_titular: str | None = None
    matriculas_dependentes: str | None = None

    qnt_memos_geacs_na_arvore: int | None = None
    marcadores_sei: list[str] = field(default_factory=list)
    marcadores_adicionados: list[str] = field(default_factory=list)

    tag_processo_novo: bool = False
    tag_processo_velho: bool = False
    tag_memos_no_bloco: bool = False
    tag_memo_deproc_no_bloco: bool = False
    tag_avaliado_se_usou_rede_propria: bool = False

    tit_usou: bool | None = None
    deps_que_usaram: list[str] = field(default_factory=list)
    deps_que_nao_usaram: list[str] = field(default_factory=list)
    # Matrículas não encontradas (sem sufixo: base da rede própria/DISA)
    titular_nao_encontrado_base_geral: str | None = None
    deps_nao_encontrados_base_geral: list[str] = field(default_factory=list)
    titular_nao_encontrado: str | None = None
    deps_nao_encontrados: list[str] = field(default_factory=list)
    tag_mat_nao_encontradas_base_geral_novo: bool = False
    tag_mat_nao_encontradas_novo: bool = False
    memo_apis_mat_nao_encontradas_criado: bool = False
    memo_apis_mat_nao_encontradas_inserido_bloco: bool = False
    memo_apis_mat_nao_encontradas_na_arvore: bool = False
    memo_apis_mat_nao_encontradas_sei: str | None = None

    memo_uso_rede_criado: bool = False
    memo_uso_rede_inserido_bloco: bool = False
    memo_uso_rede_na_arvore: bool = False
    memo_uso_rede_sei: str | None = None
    tag_memo_nao_usou_rede_propria_no_bloco: bool = False

    def to_dict(self) -> dict:
        dados = asdict(self)
        for campo, valor in dados.items():
            if isinstance(valor, list):
                dados[campo] = _juntar(valor)
        return dados
