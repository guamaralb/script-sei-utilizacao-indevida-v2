from dataclasses import asdict, dataclass, field

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


@dataclass
class RegistroMain:
    num_processo: str

    prox_acao: str | None = None

    qnt_docs_geacs_na_arvore: int = -1
    tag_processo_novo: bool = False
    tag_processo_velho: bool = False

    tag_planilhado: bool = False
    tag_ui_inserida: bool = False

    # NOVOS
    ult_memo_obtido: bool = False
    conteudo_ult_memo_obtido: bool = False
    dados_ui: DadosUI | None = None
    tag_periodo_var_deps: bool = False

    memo_disa_criado: bool = False
    memo_disa_inserido_bloco: bool = False

    memo_deproc_criado: bool = False
    memo_deproc_inserido_bloco: bool = False

    tag_memos_no_bloco: bool = False

    tag_rel_ui_transformado_pdf: bool = False
    tag_novo_rel_ui_gerado: bool = False

    erro: str | None = None

    def to_dict(self) -> dict:
        dados_ui = self.dados_ui

        return {
            'num_processo': self.num_processo,
            'prox_acao': self.prox_acao,
            'matricula_titular': (
                dados_ui.matricula_titular if dados_ui else None
            ),
            'nome_titular': dados_ui.nome_titular if dados_ui else None,
            'periodo_titular': (
                dados_ui.periodo_titular if dados_ui else None
            ),
            'matriculas_dependentes': (
                dados_ui.matriculas_dependentes if dados_ui else None
            ),
            'periodo_dependentes': (
                dados_ui.periodo_dependentes if dados_ui else None
            ),
            'qnt_docs_geacs_na_arvore': self.qnt_docs_geacs_na_arvore,
            'tag_processo_novo': self.tag_processo_novo,
            'tag_processo_velho': self.tag_processo_velho,
            'tag_planilhado': self.tag_planilhado,
            'tag_ui_inserida': self.tag_ui_inserida,
            'ult_memo_obtido': self.ult_memo_obtido,
            'conteudo_ult_memo_obtido': self.conteudo_ult_memo_obtido,
            'tag_periodo_variavel_deps': self.tag_periodo_var_deps,
            'memo_disa_criado': self.memo_disa_criado,
            'memo_disa_inserido_bloco': self.memo_disa_inserido_bloco,
            'memo_deproc_criado': self.memo_deproc_criado,
            'memo_deproc_inserido_bloco': (self.memo_deproc_inserido_bloco),
            'tag_memos_no_bloco': (self.tag_memos_no_bloco),
            'tag_rel_ui_transformado_pdf': (self.tag_rel_ui_transformado_pdf),
            'tag_novo_rel_ui_gerado': (self.tag_novo_rel_ui_gerado),
            'erro': self.erro,
        }


@dataclass
class RegistroMainAddMemoNaoUsouRedePropria:
    num_processo: str
    matricula_titular: str | None = None
    matriculas_dependentes: str | None = None

    tag_processo_novo: bool = False
    tag_processo_velho: bool = False
    tag_avaliado_se_usou_rede_propria: bool = False

    # Titular: ambos False => não encontrado na base
    tit_usou: bool = False
    tit_nao_usou: bool = False
    deps_que_usaram: list[str] = field(default_factory=list)
    deps_que_nao_usaram: list[str] = field(default_factory=list)

    tag_memo_nao_usou_rede_propria_add: bool = False

    erro: str | None = None

    def to_dict(self) -> dict:
        dados = asdict(self)
        for campo in (
            'deps_que_usaram',
            'deps_que_nao_usaram',
        ):
            dados[campo] = '; '.join(getattr(self, campo))
        return dados
