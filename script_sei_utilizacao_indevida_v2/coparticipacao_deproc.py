"""Fluxo DEPROC: apuração da coparticipação a partir da base do MANTIS
(ARQ_BASE_DEPROC, aba "Resultado"), uma linha por item atendido.

Para cada processo: as linhas com SEI = número do processo, conferidas com
as matrículas do memo da APIS e filtradas pelo período de apuração de cada
beneficiário. As colunas do relatório e os totais seguem a aba "DE-PARA" da
mesma planilha (fixados aqui; a aba não é lida).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from mantis import Intervalo, interpretar_periodo
from rede_propria import ErroAvaliacao, normalizar_matricula, sem_dv, separar_matriculas_dependentes

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI

logger = logging.getLogger(__name__)

ABA_BASE_DEPROC = 'Resultado'

TITULAR = 'TITULAR'
DEPENDENTE = 'DEPENDENTE'

# Colunas da aba Resultado usadas (letra na planilha, citada na DE-PARA)
_COLUNAS_BASE = (
    'SEI',
    'MATRICULA_TITULAR',
    'MATRICULA_BENEFICIARIO',  # E
    'NOME_BENEFICIARIO',  # F
    'TITULAR_DEPENDENTE',  # G
    'DATA_ATENDIMENTO',  # I
    'COD_PRESTADOR',  # J
    'NOME_PRESTADOR',  # K
    'QUANTIDADE',  # O
    'GRUPO_COPARTICIPACAO',  # P
    'VALOR_APURADO_SISTEMA',  # U
    'VALOR_DESCONTADO_FOLHA',  # W
    'SALDO_APOS_COMPETENCIA',  # Y
    'CALCULO_COPARTICIPACAO',  # AI
    'SITUACAO',
)

SITUACAO_RATEIO_SALDO_NAO_QUITADO = 'APURADO, DESCONTADO PARCIALMENTE (RATEIO), SALDO NAO QUITADO'
SITUACAO_NAO_DESCONTADO_SALDO_NAO_QUITADO = 'APURADO, NAO DESCONTADO EM FOLHA, SALDO NAO QUITADO'

# Colunas do relatório (coluna "DE" da aba DE-PARA)
COL_MATRICULA = 'MATRÍCULA'
COL_NOME = 'NOME BENEFICIÁRIO'
COL_CATEGORIA = 'CATEGORIA'
COL_DATA = 'DATA ATENDIMENTO'
COL_PRESTADOR = 'PRESTADOR'
COL_PROCEDIMENTO = 'PROCEDIMENTO'
COL_QTDE = 'QTDE'
COL_VALOR = 'VALOR DA COPARTICIPAÇÃO'
COLUNAS_RELATORIO = (COL_MATRICULA, COL_NOME, COL_CATEGORIA, COL_DATA, COL_PRESTADOR, COL_PROCEDIMENTO, COL_QTDE, COL_VALOR)


class MatriculasDivergentes(ErroAvaliacao):
    """Matrícula da base DEPROC (no processo) que não está no memo da APIS."""

    def __init__(self, divergentes: list[str]):
        self.divergentes = divergentes
        super().__init__(f'Matrícula(s) da base DEPROC fora do memo da APIS: {", ".join(divergentes)}')


@dataclass(frozen=True)
class TotaisDeproc:
    coparticipacao: float
    descontado: float
    em_aberto: float


@dataclass(frozen=True)
class SubtotalBeneficiario:
    matricula: str
    categoria: str
    atendimentos: int
    valor: float


@dataclass(frozen=True)
class BeneficiarioDeproc:
    """Uma linha da tabela de valores do memo de resultado: o titular e cada
    dependente com linhas do processo na base DEPROC (em qualquer período).
    Dependente sem linha nenhuma não entra (sem nome na base). valor: soma
    dos atendimentos no período (0 se só tem linhas fora dele)."""

    matricula: str  # como exibida no memo
    nome: str
    categoria: str
    valor: float


@dataclass(frozen=True)
class ResultadoDeproc:
    linhas_processo: int
    linhas_fora_periodo: int
    # Uma linha por atendimento, nas colunas de COLUNAS_RELATORIO, ordenadas
    # por beneficiário (titular primeiro) e data
    atendimentos: pd.DataFrame
    subtotais: tuple[SubtotalBeneficiario, ...]
    totais: TotaisDeproc
    beneficiarios: tuple[BeneficiarioDeproc, ...] = ()

    @property
    def tem_coparticipacao(self) -> bool:
        """Há valor de coparticipação no período. Sem atendimento, ou só com
        atendimentos de valor 0 (isentos, cálculo impedido): não há relatório
        e o memo usa a redação sem coparticipação."""
        return not self.atendimentos.empty and round(self.totais.coparticipacao, 2) != 0


def carregar_base_deproc(arquivo: Path) -> pd.DataFrame:
    df = pd.read_excel(arquivo, sheet_name=ABA_BASE_DEPROC, usecols=list(_COLUNAS_BASE))
    df['SEI'] = df['SEI'].astype(str).str.strip()
    for coluna in ('MATRICULA_TITULAR', 'MATRICULA_BENEFICIARIO'):
        df[coluna] = df[coluna].map(normalizar_matricula)
    df['TITULAR_DEPENDENTE'] = df['TITULAR_DEPENDENTE'].astype(str).str.strip().str.upper()
    df['SITUACAO'] = df['SITUACAO'].fillna('').astype(str).str.strip()
    df['DATA_ATENDIMENTO'] = pd.to_datetime(df['DATA_ATENDIMENTO'], errors='coerce')
    logger.info(f'Base DEPROC carregada: {len(df)} linha(s), {df["SEI"].nunique()} processo(s) ({arquivo.name}, aba {ABA_BASE_DEPROC})')
    return df


def formatar_matricula_com_dv(matricula: str) -> str:
    """'33983721' -> '3398372-1' (a base DEPROC traz a matrícula com DV)."""
    return f'{matricula[:-1]}-{matricula[-1]}' if len(matricula) > 1 else matricula


def mesma_matricula(do_memo: str, da_base: str) -> bool:
    """A base DEPROC tem DV; o memo da APIS, com ou sem."""
    return do_memo in {da_base, sem_dv(da_base)}


def conferir_matriculas(linhas: pd.DataFrame, dados: DadosUI) -> list[str]:
    """Matrículas das linhas do processo que não batem com o memo da APIS
    (titular ou dependentes). Dependente do memo sem linha na base não é
    divergência: só não tem atendimento."""
    titular = normalizar_matricula(dados.matricula_titular)
    dependentes = separar_matriculas_dependentes(dados.matriculas_dependentes)

    categorias = set(linhas['TITULAR_DEPENDENTE']) - {TITULAR, DEPENDENTE}
    if categorias:
        raise ErroAvaliacao(f'Base DEPROC com TITULAR_DEPENDENTE desconhecido: {sorted(categorias)}')

    divergentes = []
    eh_titular = linhas['TITULAR_DEPENDENTE'] == TITULAR
    for matricula in sorted(set(linhas['MATRICULA_TITULAR']) | set(linhas.loc[eh_titular, 'MATRICULA_BENEFICIARIO'])):
        if not mesma_matricula(titular, matricula):
            divergentes.append(f'{matricula} (titular)')
    for matricula in sorted(set(linhas.loc[~eh_titular, 'MATRICULA_BENEFICIARIO'])):
        if not any(mesma_matricula(dependente, matricula) for dependente in dependentes):
            divergentes.append(f'{matricula} (dependente)')
    return divergentes


def _intervalos_por_linha(linhas: pd.DataFrame, dados: DadosUI) -> list[tuple[Intervalo, ...]]:
    """Período do titular para todos, exceto, no modelo com período por
    dependente, o dependente que tem o seu."""
    if dados.periodo_dependentes:
        raise ErroAvaliacao('Memo da APIS com período variável para dependentes: sem período de cada dependente para filtrar a base DEPROC')
    intervalos_titular = interpretar_periodo(dados.periodo_titular)
    periodos = {normalizar_matricula(m): interpretar_periodo(p, f'do dependente {m}') for m, p in (dados.periodos_por_dependente or {}).items()}

    def intervalos(linha) -> tuple[Intervalo, ...]:
        if linha.TITULAR_DEPENDENTE == DEPENDENTE:
            proprio = next((i for m, i in periodos.items() if mesma_matricula(m, linha.MATRICULA_BENEFICIARIO)), None)
            if proprio is not None:
                return proprio
        return intervalos_titular

    return [intervalos(linha) for linha in linhas.itertuples(index=False)]


def filtrar_periodo(linhas: pd.DataFrame, dados: DadosUI) -> pd.DataFrame:
    if linhas['DATA_ATENDIMENTO'].isna().any():
        raise ErroAvaliacao('Linha da base DEPROC do processo sem data de atendimento válida')
    dentro = [any(intervalo.contem(data.date()) for intervalo in intervalos) for data, intervalos in zip(linhas['DATA_ATENDIMENTO'], _intervalos_por_linha(linhas, dados), strict=True)]
    return linhas[dentro]


def _valores(linhas: pd.DataFrame, coluna: str) -> pd.Series:
    return pd.to_numeric(linhas[coluna], errors='coerce').fillna(0.0)


def _prestador(codigo, nome) -> str:
    nome = '' if pd.isna(nome) else str(nome).strip()
    if pd.isna(codigo):
        return nome
    codigo = str(int(codigo)) if isinstance(codigo, float) else str(codigo).strip()
    return f'{codigo} - {nome}' if nome else codigo


def montar_atendimentos(linhas: pd.DataFrame) -> pd.DataFrame:
    """Colunas do relatório, conforme a coluna "PARA" da aba DE-PARA."""
    df = pd.DataFrame({
        COL_MATRICULA: linhas['MATRICULA_BENEFICIARIO'].to_numpy(),
        COL_NOME: linhas['NOME_BENEFICIARIO'].fillna('').astype(str).str.strip().to_numpy(),
        COL_CATEGORIA: linhas['TITULAR_DEPENDENTE'].to_numpy(),
        COL_DATA: linhas['DATA_ATENDIMENTO'].to_numpy(),
        # COD_PRESTADOR - NOME_PRESTADOR (J e K concatenadas)
        COL_PRESTADOR: [_prestador(c, n) for c, n in zip(linhas['COD_PRESTADOR'], linhas['NOME_PRESTADOR'], strict=True)],
        COL_PROCEDIMENTO: linhas['GRUPO_COPARTICIPACAO'].fillna('').astype(str).str.strip().to_numpy(),
        COL_QTDE: pd.to_numeric(linhas['QUANTIDADE'], errors='coerce').fillna(0).astype(int).to_numpy(),
        # VALOR_APURADO_SISTEMA + CALCULO_COPARTICIPACAO (U + AI)
        COL_VALOR: (_valores(linhas, 'VALOR_APURADO_SISTEMA') + _valores(linhas, 'CALCULO_COPARTICIPACAO')).round(2).to_numpy(),
    })
    df['_ordem'] = (df[COL_CATEGORIA] != TITULAR).astype(int)
    return df.sort_values(['_ordem', COL_MATRICULA, COL_DATA], kind='stable').drop(columns='_ordem').reset_index(drop=True)


def calcular_totais(linhas: pd.DataFrame) -> TotaisDeproc:
    """Totais da aba DE-PARA:

    - coparticipação: VALOR_APURADO_SISTEMA + CALCULO_COPARTICIPACAO;
    - descontado: VALOR_APURADO_SISTEMA, exceto o das linhas com saldo não
      quitado, + VALOR_DESCONTADO_FOLHA das linhas "APURADO, DESCONTADO
      PARCIALMENTE (RATEIO), SALDO NAO QUITADO";
    - em aberto: CALCULO_COPARTICIPACAO + SALDO_APOS_COMPETENCIA das linhas
      com saldo não quitado (rateio ou "APURADO, NAO DESCONTADO EM FOLHA,
      SALDO NAO QUITADO").

    Nas linhas com saldo não quitado, VALOR_APURADO_SISTEMA = descontado +
    saldo: só a parte descontada conta como descontado (somar o apurado
    inteiro contaria o saldo duas vezes). Assim, descontado + em aberto =
    coparticipação."""
    apurado = _valores(linhas, 'VALOR_APURADO_SISTEMA')
    calculado = _valores(linhas, 'CALCULO_COPARTICIPACAO')
    rateio_nao_quitado = linhas['SITUACAO'] == SITUACAO_RATEIO_SALDO_NAO_QUITADO
    saldo_nao_quitado = linhas['SITUACAO'].isin([SITUACAO_RATEIO_SALDO_NAO_QUITADO, SITUACAO_NAO_DESCONTADO_SALDO_NAO_QUITADO])
    return TotaisDeproc(
        coparticipacao=round(float((apurado + calculado).sum()), 2),
        descontado=round(float(apurado[~saldo_nao_quitado].sum() + _valores(linhas, 'VALOR_DESCONTADO_FOLHA')[rateio_nao_quitado].sum()), 2),
        em_aberto=round(float(calculado.sum() + _valores(linhas, 'SALDO_APOS_COMPETENCIA')[saldo_nao_quitado].sum()), 2),
    )


def _subtotais(atendimentos: pd.DataFrame) -> tuple[SubtotalBeneficiario, ...]:
    """Soma por beneficiário (linha SUBTOTAL da DE-PARA), na ordem do relatório."""
    grupos = atendimentos.groupby([COL_MATRICULA, COL_CATEGORIA], sort=False)[COL_VALOR]
    return tuple(SubtotalBeneficiario(matricula, categoria, int(valores.count()), round(float(valores.sum()), 2)) for (matricula, categoria), valores in grupos)


def _nome_mais_frequente(nomes: pd.Series) -> str:
    nomes = nomes.fillna('').astype(str).str.strip()
    nomes = nomes[nomes != '']
    return nomes.value_counts().index[0] if not nomes.empty else ''


def _beneficiarios(linhas: pd.DataFrame, atendimentos: pd.DataFrame, dados: DadosUI) -> tuple[BeneficiarioDeproc, ...]:
    """Titular (sempre) e os dependentes com linhas do processo na base, com o
    nome da base e o valor no período. Titular sem linha: matrícula e nome do
    memo da APIS."""
    valores = atendimentos.groupby([COL_MATRICULA, COL_CATEGORIA])[COL_VALOR].sum()
    beneficiarios = []
    for (matricula, categoria), grupo in linhas.groupby(['MATRICULA_BENEFICIARIO', 'TITULAR_DEPENDENTE'], sort=True):
        valor = round(float(valores.get((matricula, categoria), 0.0)), 2)
        beneficiarios.append(BeneficiarioDeproc(formatar_matricula_com_dv(matricula), _nome_mais_frequente(grupo['NOME_BENEFICIARIO']), categoria, valor))
    if not any(b.categoria == TITULAR for b in beneficiarios):
        beneficiarios.append(BeneficiarioDeproc(dados.matricula_titular, dados.nome_titular, TITULAR, 0.0))
    return tuple(sorted(beneficiarios, key=lambda b: b.categoria != TITULAR))


def apurar_coparticipacao(base: pd.DataFrame, num_processo: str, dados: DadosUI) -> ResultadoDeproc:
    """Linhas do processo na base DEPROC, conferidas com as matrículas do memo
    da APIS e filtradas pelo período de apuração.

    Processo fora da base: ErroAvaliacao (a base pode não cobrir o processo).
    Matrícula divergente: MatriculasDivergentes."""
    linhas = base[base['SEI'] == str(num_processo).strip()]
    if linhas.empty:
        raise ErroAvaliacao('Processo não consta na base DEPROC (coluna SEI)')

    divergentes = conferir_matriculas(linhas, dados)
    if divergentes:
        raise MatriculasDivergentes(divergentes)

    no_periodo = filtrar_periodo(linhas, dados)
    atendimentos = montar_atendimentos(no_periodo)
    resultado = ResultadoDeproc(
        linhas_processo=len(linhas),
        linhas_fora_periodo=len(linhas) - len(no_periodo),
        atendimentos=atendimentos,
        subtotais=_subtotais(atendimentos),
        totais=calcular_totais(no_periodo),
        beneficiarios=_beneficiarios(linhas, atendimentos, dados),
    )
    totais = resultado.totais
    logger.info(
        f'Base DEPROC: {resultado.linhas_processo} linha(s) do processo, {resultado.linhas_fora_periodo} fora do período | '
        f'{len(atendimentos)} atendimento(s) | Coparticipação R$ {totais.coparticipacao:.2f} | '
        f'Descontado R$ {totais.descontado:.2f} | Em aberto R$ {totais.em_aberto:.2f}'
    )
    return resultado
