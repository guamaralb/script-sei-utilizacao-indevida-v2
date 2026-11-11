import logging
import traceback
from dataclasses import dataclass, field, fields
from datetime import datetime

from docs_processo import filtrar_docs_geacs, filtrar_memos_geacs
from tags import COLUNA_DEMAIS_MARCADORES, colunas_tags, colunas_tags_deproc, demais_marcadores

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI
from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore

logger = logging.getLogger(__name__)


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
    VERIFICAR_ACESSO_UNIDADE = 'Verificar acesso da unidade ao processo'

    # Fluxo alternativo ADC PDF ANT AUT
    ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL = 'ADC PDF ANT AUT: PDFs inseridos; aguarda o fluxo normal'
    ADC_PDF_ANT_AUT_ESTADO_MANTIDO = 'ADC PDF ANT AUT: PDFs inseridos; processo mantido no estado atual'
    ADC_PDF_ANT_AUT_SEM_PLANILHAS = 'ADC PDF ANT AUT: nenhuma planilha no processo (verificar)'

    # Fluxo ADC PDF ANT MAN (planilhas da pasta)
    ADC_PDF_ANT_MAN_AGUARDA_FLUXO_NORMAL = 'ADC PDF ANT MAN: PDFs inseridos; aguarda o fluxo normal'
    ADC_PDF_ANT_MAN_ESTADO_MANTIDO = 'ADC PDF ANT MAN: PDFs inseridos; processo mantido no estado atual'
    ADC_PDF_ANT_MAN_SEM_PLANILHAS = 'ADC PDF ANT MAN: nenhuma planilha na pasta (verificar)'

    # Fluxo DEPROC (coparticipação)
    DEPROC_ASSINAR_MEMO_RESULTADO = 'DEPROC: assinar memo de resultado da coparticipação e encaminhar à GEACS'
    DEPROC_MEMO_ENCAMINHADO = 'DEPROC: memo de resultado da coparticipação encaminhado à GEACS (concluído)'


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


def registrar_sem_acesso(registro, erro: Exception) -> None:
    """A unidade não tem acesso ao processo (UnidadeSemAcessoException da
    sei_automacao, levantada por acessar_processo): erro, sem nenhuma ação
    no SEI."""
    registrar_erro(registro, erro)
    registro.prox_acao = ProxAcao.VERIFICAR_ACESSO_UNIDADE
    logger.warning('Unidade sem acesso ao processo')


def _juntar(valores: list[str]) -> str:
    return '; '.join(valores)


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


# Dados de trabalho da passagem, fora da planilha de controle
_CAMPOS_INTERNOS = frozenset({'marcadores_atuais', 'tds_docs', 'docs_geacs', 'memos_geacs', 'docs_rodada', 'memos_criados', 'dados_ui', 'memo_apis', 'processo_fechado'})

# Resultados do fluxo principal: o ADC PDF ANT AUT não os avalia e não pode apagá-los da
# linha do processo na planilha de controle
_CAMPOS_SO_FLUXO_PRINCIPAL = frozenset({
    'tit_usou',
    'deps_que_usaram',
    'deps_que_nao_usaram',
    'titular_nao_encontrado_base_geral',
    'deps_nao_encontrados_base_geral',
    'memo_apis_mat_nao_encontradas_criado',
    'memo_apis_mat_nao_encontradas_inserido_bloco',
    'memo_apis_mat_nao_encontradas_na_arvore',
    'memo_apis_mat_nao_encontradas_sei',
})


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

    # Processo sem "Incluir Documento" reaberto na unidade (o script não
    # conclui de novo)
    processo_reaberto: bool = False

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
    # Sem "Incluir Documento" ao abrir o processo (fluxo normal)
    processo_fechado: bool = False
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
        dados[COLUNA_DEMAIS_MARCADORES] = demais_marcadores(self.marcadores_atuais) or None
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
    # Último memo da APIS destinado à GEACS, como na árvore (interno; o
    # número vai em memo_apis_sei)
    memo_apis: DocArvore | None = None
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
            # Modelo com período por dependente: "555: 01/2024 a 06/2024; ..."
            'periodos_por_dependente': '; '.join(f'{m}: {p}' for m, p in dados_ui.periodos_por_dependente.items()) if dados_ui and dados_ui.periodos_por_dependente else None,
        }
        # Logo depois das colunas de resultado (até "erro")
        itens = list(dados.items())
        posicao = list(dados).index('erro') + 1
        return dict(itens[:posicao] + list(colunas_ui.items()) + itens[posicao:])


@dataclass
class RegistroAdcPdfAnt(RegistroBase):
    """Uma passagem pelo fluxo alternativo ADC PDF ANT AUT (main_geacs_adc_pdf_ant_aut.py) ou pelo fluxo
    PDF (main_geacs_adc_pdf_ant_man.py)."""

    # Planilhas na árvore (número SEI), PDFs anexados na passagem (nome na
    # árvore) e PDFs que já estavam na árvore (número SEI, retomada)
    planilhas_sei: list[str] = field(default_factory=list)
    pdfs_incluidos: list[str] = field(default_factory=list)
    pdfs_na_arvore: list[str] = field(default_factory=list)
    # PDFs de Anexo no modelo antigo (número SEI), a excluir manualmente
    pdfs_antigos_a_excluir: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {coluna: valor for coluna, valor in super().to_dict().items() if coluna not in _CAMPOS_SO_FLUXO_PRINCIPAL}


# Colunas que o fluxo DEPROC não grava na linha do processo: os resultados
# dos outros fluxos ficam como estão
_CAMPOS_FORA_DEPROC = _CAMPOS_SO_FLUXO_PRINCIPAL | {'processo_reaberto'}
# Os marcadores lidos na unidade da DEPROC não são os da GEACS: vão para
# colunas próprias (marcadores_deproc_* e tag_deproc_*), sem apagar as da GEACS
_COLUNAS_MARCADORES_DEPROC = {
    'marcadores_sei': 'marcadores_deproc_sei',
    'marcadores_adicionados': 'marcadores_deproc_adicionados',
    'marcadores_removidos': 'marcadores_deproc_removidos',
    'marcadores_finais': 'marcadores_deproc_finais',
}


@dataclass
class RegistroDeproc(RegistroBase):
    """Uma passagem pelo fluxo DEPROC (main_deproc_calcula_copa.py), na unidade da DEPROC."""

    # Instruções da APIS (mesmas colunas do fluxo normal)
    ult_memo_obtido: bool = False
    conteudo_ult_memo_obtido: bool = False
    memo_apis_sei: str | None = None
    memos_apis_geacs_sei: list[str] = field(default_factory=list)
    modelo_memo_apis: str | None = None

    # Memo DEPROC da GEACS na rodada e assinatura
    memo_deproc_geacs_sei: str | None = None
    memo_deproc_assinado: bool | None = None

    # Base DEPROC (aba Resultado): linhas do processo (coluna SEI), linhas
    # fora do período de apuração e atendimentos no relatório
    linhas_base_deproc: int | None = None
    linhas_fora_periodo_deproc: int | None = None
    atendimentos_deproc: int | None = None
    # Matrículas da base DEPROC que não estão no memo da APIS
    matriculas_divergentes_deproc: list[str] = field(default_factory=list)
    valor_total_coparticipacao: float | None = None
    valor_total_descontado: float | None = None
    valor_total_em_aberto: float | None = None

    # Relatório em PDF: anexado na passagem (nome na árvore) ou já na árvore
    relatorio_deproc_incluido: str | None = None
    relatorio_deproc_na_arvore: bool = False
    relatorio_deproc_sei: str | None = None

    # Memo de resultado da DEPROC à GEACS
    memo_deproc_resultado_criado: bool = False
    memo_deproc_resultado_inserido_bloco: bool = False
    memo_deproc_resultado_na_arvore: bool = False
    memo_deproc_resultado_sei: str | None = None

    # Internos (ver _CAMPOS_INTERNOS)
    memo_apis: DocArvore | None = None
    dados_ui: DadosUI | None = None

    def to_dict(self) -> dict:
        # Os marcadores da GEACS (tag_* e demais_marcadores) são de outra unidade
        dados = {
            _COLUNAS_MARCADORES_DEPROC.get(coluna, coluna): valor
            for coluna, valor in super().to_dict().items()
            if coluna not in _CAMPOS_FORA_DEPROC and not coluna.startswith('tag_') and coluna != COLUNA_DEMAIS_MARCADORES
        }
        dados.update(colunas_tags_deproc(self.marcadores_atuais))
        return dados


# Colunas que o fluxo de cancelar o memo DEPROC antigo não grava na linha do
# processo: a prox_acao, o fluxo e os marcadores são dos outros fluxos
_CAMPOS_FORA_CANC_MEMO_DEPROC_ANT = _CAMPOS_SO_FLUXO_PRINCIPAL | {
    'prox_acao',
    'fluxo',
    'processo_reaberto',
    'marcadores_sei',
    'marcadores_adicionados',
    'marcadores_removidos',
    'marcadores_finais',
}
# O erro deste fluxo vai para colunas próprias, sem apagar o dos outros
_COLUNAS_ERRO_CANC_MEMO_DEPROC_ANT = {'tipo_erro': 'canc_memo_deproc_ant_tipo_erro', 'erro': 'canc_memo_deproc_ant_erro'}


@dataclass
class RegistroCancMemoDeprocAnt(RegistroBase):
    """Uma passagem pelo fluxo de cancelar o memo DEPROC antigo
    (main_geacs_canc_memo_deproc_ant.py). Não altera a prox_acao."""

    # Sinalizador: o processo passou pelo fluxo (data e hora da passagem)
    canc_memo_deproc_ant_em: datetime | None = None
    canc_memo_deproc_ant_cancelado: bool = False
    # Memos cancelados: número SEI e nome na árvore
    canc_memo_deproc_ant_sei: list[str] = field(default_factory=list)
    canc_memo_deproc_ant_nome: list[str] = field(default_factory=list)
    # Memos DEPROC antigos não cancelados (número SEI): sem a opção de cancelar
    # ou sem data legível
    canc_memo_deproc_ant_nao_cancelados: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.canc_memo_deproc_ant_em = self.ultima_passagem

    def to_dict(self) -> dict:
        return {
            _COLUNAS_ERRO_CANC_MEMO_DEPROC_ANT.get(coluna, coluna): valor
            for coluna, valor in super().to_dict().items()
            if coluna not in _CAMPOS_FORA_CANC_MEMO_DEPROC_ANT and not coluna.startswith('tag_')
        }

    def para_log(self) -> dict:
        """Linha do resumo do log (com erro e próxima ação)."""
        acao = f'{len(self.canc_memo_deproc_ant_sei)} memo(s) DEPROC antigo(s) cancelado(s)' if self.canc_memo_deproc_ant_cancelado else 'Nenhum memo DEPROC antigo cancelado'
        return {'num_processo': self.num_processo, 'tipo_erro': self.tipo_erro, 'erro': self.erro, 'prox_acao': acao}


@dataclass
class RegistroResposta(RegistroBase):
    """Uma passagem por um fluxo de resposta (main_geacs_resp_apis.py,
    main_geacs_resp_disa.py e main_geacs_resp_deproc.py)."""

    # Marcador "Aguarda" com que o processo entrou no fluxo
    marcador_aguarda: str | None = None

    def to_dict(self) -> dict:
        return {coluna: valor for coluna, valor in super().to_dict().items() if coluna not in _CAMPOS_SO_FLUXO_PRINCIPAL | {'processo_reaberto'}}


@dataclass
class RegistroDeprocExcluirDocs(RegistroBase):
    """Uma passagem pelo fluxo de excluir os documentos da DEPROC
    (main_deproc_excluir_docs.py). Na planilha de controle, grava só a coluna
    própria deproc_excluir_docs (sem prox_acao, fluxo, erro e marcadores)."""

    # Documentos da DEPROC na árvore, excluídos e não excluídos (número SEI)
    docs_deproc: list[str] = field(default_factory=list)
    docs_excluidos: list[str] = field(default_factory=list)
    docs_nao_excluidos: list[str] = field(default_factory=list)

    def resumo_exclusao(self) -> str:
        partes = [self.ultima_passagem.strftime('%d/%m/%Y %H:%M')]
        if self.erro is None and not self.docs_deproc:
            partes.append('nenhum documento da DEPROC')
        if self.docs_excluidos:
            partes.append(f'{len(self.docs_excluidos)} excluído(s): {_juntar(self.docs_excluidos)}')
        if self.docs_nao_excluidos:
            partes.append(f'não excluído(s): {_juntar(self.docs_nao_excluidos)}')
        if self.erro is not None:
            partes.append(f'ERRO ({self.tipo_erro}): {self.erro}')
        return ' | '.join(partes)

    def to_dict(self) -> dict:
        return {
            'num_processo': self.num_processo,
            'ultima_passagem': self.ultima_passagem,
            'data_execucao': self.data_execucao,
            'deproc_excluir_docs': self.resumo_exclusao(),
        }

    def para_log(self) -> dict:
        """Linha do resumo do log (com erro e próxima ação)."""
        acao = f'DEPROC: {len(self.docs_excluidos)} documento(s) excluído(s)' if self.docs_excluidos else 'DEPROC: nenhum documento excluído'
        return {'num_processo': self.num_processo, 'tipo_erro': self.tipo_erro, 'erro': self.erro, 'prox_acao': acao}


@dataclass
class RegistroVerificarMarcadores(RegistroBase):
    """Uma passagem pelo fluxo de verificar os marcadores
    (main_geacs_verificar_marcadores.py). Na planilha de controle, grava só os
    marcadores: uma coluna tag_* por marcador válido na GEACS,
    demais_marcadores (os outros) e marcadores_finais; o erro vai para
    verificar_marcadores_erro. Não grava prox_acao, fluxo, tipo_erro e erro."""

    def to_dict(self) -> dict:
        dados = {
            'num_processo': self.num_processo,
            'ultima_passagem': self.ultima_passagem,
            'data_execucao': self.data_execucao,
            'verificar_marcadores_erro': f'{self.tipo_erro}: {self.erro}' if self.erro is not None else None,
        }
        # Sem conseguir ler os marcadores, as colunas deles ficam como estão
        if self.erro is None:
            dados['marcadores_finais'] = _juntar(self.marcadores_atuais)
            dados.update(colunas_tags(self.marcadores_atuais))
            dados[COLUNA_DEMAIS_MARCADORES] = demais_marcadores(self.marcadores_atuais) or None
        return dados

    def para_log(self) -> dict:
        """Linha do resumo do log (com erro e próxima ação)."""
        return {'num_processo': self.num_processo, 'tipo_erro': self.tipo_erro, 'erro': self.erro, 'prox_acao': 'Marcadores verificados'}
