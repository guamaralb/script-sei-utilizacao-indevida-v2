import traceback
from dataclasses import dataclass, field, fields
from datetime import datetime

from docs_processo import filtrar_docs_geacs, filtrar_memos_geacs
from tags import colunas_tags

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


class ProxAcao:
    """Valores padronizados da coluna prox_acao (facilitam o filtro e o
    resumo do log). Detalhes ficam nas demais colunas e no log."""

    # Fluxo normal
    ASSINAR_DEPROC = 'Assinar memo DEPROC e encaminhar'
    ASSINAR_MEMO_DISA_VALIDAR_CONSTA = 'Assinar memo à DISA (validar e complementar) e encaminhar'
    ASSINAR_MEMO_DISA_VALIDAR_NAO_CONSTA = 'Assinar memo à DISA (validar; não consta na base DISA) e encaminhar'
    ASSINAR_MEMO_DISA_SEM_MANTIS_RELATORIO = 'Assinar memo à DISA (sem MANTIS: solicita relatório) e encaminhar'
    # Concluído na versão anterior do fluxo
    ASSINAR_DISA_DEPROC = 'Assinar memos DISA e DEPROC e encaminhar'

    # VELHOS (enviados à DISA e à DEPROC antes da avaliação)
    VELHO_AGUARDAR_DEFINICAO = 'VELHO: não processado (fluxo ainda não definido)'
    FORA_DO_ESCOPO = 'Fora do escopo (tratado manualmente)'

    # Verificações manuais
    VERIFICAR_FORMATO_MEMO = 'Verificar formato do memo da APIS'
    ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS = 'Assinar memo à APIS (matrículas não encontradas) e encaminhar'
    ASSINAR_MEMO_APIS_SEM_MEMO = 'Assinar memo à APIS (sem memorando para a GEACS) e encaminhar'
    ASSINAR_MEMO_APIS_FORMATO_INVALIDO = 'Assinar memo à APIS (formato do memorando inválido) e encaminhar'
    ASSINAR_MEMO_APIS_PERIODO_DEPS = 'Assinar memo à APIS (período dos dependentes) e encaminhar'
    ASSINAR_MEMO_APIS_SEM_USO = 'Assinar memo à APIS (nenhum uso nas bases) e encaminhar'
    AGUARDAR_RESPOSTA_MEMO = 'Aguardar resposta ao memo enviado (processo parado)'
    VERIFICAR_MARCADORES = 'Verificar marcadores inconsistentes (corrigir no SEI)'
    VERIFICAR_ERRO = 'Verificar erro'


# Próximas ações definidas antes do erro que devem ser mantidas
_PROX_ACOES_DE_ERRO = frozenset({
    ProxAcao.VERIFICAR_FORMATO_MEMO,
    ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS,
    ProxAcao.AGUARDAR_RESPOSTA_MEMO,
    ProxAcao.VERIFICAR_MARCADORES,
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


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


# Dados de trabalho da passagem, fora da planilha de controle
_CAMPOS_INTERNOS = frozenset({'marcadores_atuais', 'tds_docs', 'docs_geacs', 'memos_geacs', 'docs_rodada', 'memos_criados', 'dados_ui'})


@dataclass
class RegistroBase:
    """Uma passagem de um processo pelo fluxo: dados da árvore e dos
    marcadores, o que foi feito e o resultado (uma linha da planilha de
    controle)."""

    num_processo: str
    data_execucao: str | None = None
    ultima_passagem: datetime = field(default_factory=_agora)

    fluxo: str | None = None
    prox_acao: str | None = None
    tipo_erro: str | None = None
    erro: str | None = None

    qnt_docs_geacs_na_arvore: int | None = None
    qnt_memos_geacs_na_arvore: int | None = None

    # Lidos no início, adicionados e removidos na passagem
    marcadores_sei: list[str] = field(default_factory=list)
    marcadores_adicionados: list[str] = field(default_factory=list)
    marcadores_removidos: list[str] = field(default_factory=list)

    # Uso da rede própria
    tit_usou: bool | None = None
    deps_que_usaram: list[str] = field(default_factory=list)
    deps_que_nao_usaram: list[str] = field(default_factory=list)
    # Matrículas não encontradas na base APIS (as colunas mantêm o nome
    # antigo, "base_geral")
    titular_nao_encontrado_base_geral: str | None = None
    deps_nao_encontrados_base_geral: list[str] = field(default_factory=list)
    memo_apis_mat_nao_encontradas_criado: bool = False
    memo_apis_mat_nao_encontradas_inserido_bloco: bool = False
    memo_apis_mat_nao_encontradas_na_arvore: bool = False
    memo_apis_mat_nao_encontradas_sei: str | None = None

    # Internos (ver _CAMPOS_INTERNOS)
    marcadores_atuais: list[str] = field(default_factory=list)
    tds_docs: list[dict] = field(default_factory=list)
    docs_geacs: list[dict] = field(default_factory=list)
    memos_geacs: list[dict] = field(default_factory=list)
    # Documentos da rodada atual: depois do último memo da APIS destinado à
    # GEACS (toda a árvore até ele ser encontrado). É onde memos e
    # relatórios já criados são procurados (retomada)
    docs_rodada: list[dict] = field(default_factory=list)
    # Memos criados na passagem, na ordem de criação (prefixo dos atributos
    # <memo>_sei), para obter o número SEI relendo a árvore
    memos_criados: list[str] = field(default_factory=list)

    def registrar_arvore(self, tds_docs: list[dict]) -> None:
        self.tds_docs = tds_docs
        self.docs_rodada = tds_docs
        self.docs_geacs = filtrar_docs_geacs(tds_docs)
        self.memos_geacs = filtrar_memos_geacs(tds_docs)
        self.qnt_docs_geacs_na_arvore = len(self.docs_geacs)
        self.qnt_memos_geacs_na_arvore = len(self.memos_geacs)

    def to_dict(self) -> dict:
        dados = {}
        for campo in fields(self):
            if campo.name in _CAMPOS_INTERNOS:
                continue
            valor = getattr(self, campo.name)
            dados[campo.name] = _juntar(valor) if isinstance(valor, list) else valor
        dados['marcadores_finais'] = _juntar(self.marcadores_atuais)
        dados.update(colunas_tags(self.marcadores_atuais))
        return dados


@dataclass
class RegistroMain(RegistroBase):
    # Enviado à DISA e à DEPROC antes da avaliação da rede própria
    velho: bool | None = None
    # Memos da GEACS à DISA e à DEPROC que identificaram o VELHO (número SEI)
    memos_velho_sei: list[str] = field(default_factory=list)

    # Instruções da APIS
    ult_memo_obtido: bool = False
    conteudo_ult_memo_obtido: bool = False
    memo_apis_sei: str | None = None
    memos_apis_geacs_sei: list[str] = field(default_factory=list)
    modelo_memo_apis: str | None = None
    motivo_formato_invalido: str | None = None
    dados_ui: DadosUI | None = None

    # Memos à APIS que param o fluxo normal
    memo_apis_sem_memo_criado: bool = False
    memo_apis_sem_memo_inserido_bloco: bool = False
    memo_apis_sem_memo_na_arvore: bool = False
    memo_apis_sem_memo_sei: str | None = None
    memo_apis_formato_invalido_criado: bool = False
    memo_apis_formato_invalido_inserido_bloco: bool = False
    memo_apis_formato_invalido_na_arvore: bool = False
    memo_apis_formato_invalido_sei: str | None = None
    memo_apis_periodo_deps_criado: bool = False
    memo_apis_periodo_deps_inserido_bloco: bool = False
    memo_apis_periodo_deps_na_arvore: bool = False
    memo_apis_periodo_deps_sei: str | None = None
    memo_apis_sem_uso_criado: bool = False
    memo_apis_sem_uso_inserido_bloco: bool = False
    memo_apis_sem_uso_na_arvore: bool = False
    memo_apis_sem_uso_sei: str | None = None

    # Uso da rede própria e da rede credenciada no MANTIS (período do titular)
    tit_usou_mantis_rede_propria: bool | None = None
    tit_valor_total_uso_mantis_rede_propria: float | None = None
    deps_que_usaram_mantis_rede_propria: list[str] = field(default_factory=list)
    deps_valor_total_uso_mantis_rede_propria: float | None = None
    tit_usou_mantis_rede_credenciada: bool | None = None
    tit_valor_total_uso_mantis_rede_credenciada: float | None = None
    deps_que_usaram_mantis_rede_credenciada: list[str] = field(default_factory=list)
    deps_valor_total_uso_mantis_rede_credenciada: float | None = None
    # Uso da rede própria no MANTIS que a base DISA marca como não uso
    mats_uso_mantis_alem_disa: list[str] = field(default_factory=list)
    # Comparação base DISA x MANTIS, ex.: "DISA sim, MANTIS RP não, MANTIS RC sim"
    caso_disa_mantis: str | None = None
    # Relatórios em PDF do MANTIS: anexados na passagem (nome na árvore) e
    # já na árvore (número SEI, retomada)
    relatorios_incluidos: list[str] = field(default_factory=list)
    relatorios_na_arvore: list[str] = field(default_factory=list)

    # Memos DISA (um dos três casos) e DEPROC. <memo>_na_arvore: o memo já
    # estava na árvore sem marcador e foi reaproveitado (retomada)
    memo_disa_criado: bool = False
    memo_disa_inserido_bloco: bool = False
    memo_disa_na_arvore: bool = False
    memo_disa_sei: str | None = None
    memo_deproc_criado: bool = False
    memo_deproc_inserido_bloco: bool = False
    memo_deproc_na_arvore: bool = False
    memo_deproc_sei: str | None = None

    def to_dict(self) -> dict:
        dados = super().to_dict()
        dados_ui = self.dados_ui
        periodo_deps = dados_ui.periodo_dependentes if dados_ui else None
        colunas_ui = {
            'matricula_titular': dados_ui.matricula_titular if dados_ui else None,
            'nome_titular': dados_ui.nome_titular if dados_ui else None,
            'periodo_titular': dados_ui.periodo_titular if dados_ui else None,
            'matriculas_dependentes': dados_ui.matriculas_dependentes if dados_ui else None,
            # Só indica se há período variável (sem as datas)
            'tem_periodo_var_deps': bool(periodo_deps) if dados_ui else None,
        }
        # Logo depois das colunas de resultado (até "erro")
        itens = list(dados.items())
        posicao = list(dados).index('erro') + 1
        return dict(itens[:posicao] + list(colunas_ui.items()) + itens[posicao:])
