from dataclasses import dataclass

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


@dataclass
class RegistroSepararProecessarNovos:
    num_processo: str

    prox_acao: str | None = None

    qnt_docs_geacs_na_arvore: int = -1
    marcador_processo_novo: bool = False
    marcador_processo_velho: bool = False

    ult_memo_obtido: bool = False
    conteudo_ult_memo_obtido: bool = False
    dados_ui: DadosUI | None = None
    marcador_periodo_var_deps: bool = False

    memo_disa_criado: bool = False
    memo_disa_inserido_bloco: bool = False

    memo_deproc_criado: bool = False
    memo_deproc_inserido_bloco: bool = False

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
            'marcador_processo_novo': self.marcador_processo_novo,
            'marcador_processo_velho': self.marcador_processo_velho,
            'ult_memo_obtido': self.ult_memo_obtido,
            'conteudo_ult_memo_obtido': self.conteudo_ult_memo_obtido,
            'marcador_periodo_variavel_deps': self.marcador_periodo_var_deps,
            'memo_disa_criado': self.memo_disa_criado,
            'memo_disa_inserido_bloco': self.memo_disa_inserido_bloco,
            'memo_deproc_criado': self.memo_deproc_criado,
            'memo_deproc_inserido_bloco': (self.memo_deproc_inserido_bloco),
            'erro': self.erro,
        }
