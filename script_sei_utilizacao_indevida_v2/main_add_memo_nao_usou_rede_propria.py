import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from memorandos.MemoDisaUsoRede import MemoDisaUsoRede, UsoRedeBeneficiarios
from Registro import RegistroMainAddMemoNaoUsouRedePropria
from sei_automacao.auth.login import efetuar_login
from sei_automacao.documento import inserir_bloco_ass
from sei_automacao.driver import iniciar_driver
from sei_automacao.processo import (
    adicionar_marcador,
    incluir_doc_sei_memo,
    reabrir_processo,
)
from sei_automacao.processo.marcadores import checar_marcador_existe
from sei_automacao.ubiquo.busca import acessar_processo

load_dotenv()

SEI_LOGIN = os.getenv('SEI_LOGIN')
SEI_SENHA = os.getenv('SEI_SENHA')
SEI_ORGAO = os.getenv('SEI_ORGAO')

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

DIR_BASE = Path(__file__).resolve().parent.parent

DIR_DADOS = DIR_BASE / 'dados'

DIR_INPUTS = DIR_DADOS / 'inputs'
DIR_CONTROLE = DIR_DADOS / 'controle'
DIR_CONTROLE_MAIN = DIR_CONTROLE / 'main'
DIR_CONTROLE_MAIN_NAO_USOU_REDE_PROPRIA = (
    DIR_CONTROLE / 'main_add_memo_nao_usou_rede_propria'
)

DIR_LOG = DIR_BASE / 'logs'
DIR_LOG_MAIN_ADD_MEMO_NAO_USOU_REDE_PROPRIA = (
    DIR_LOG / 'main_add_memo_nao_usou_rede_propria'
)

for diretorio in [
    DIR_DADOS,
    DIR_INPUTS,
    DIR_CONTROLE,
    DIR_CONTROLE_MAIN_NAO_USOU_REDE_PROPRIA,
    DIR_LOG,
    DIR_LOG_MAIN_ADD_MEMO_NAO_USOU_REDE_PROPRIA,
]:
    diretorio.mkdir(parents=True, exist_ok=True)

ARQ_COMPILADO = (
    DIR_CONTROLE_MAIN / '_processos_processados-COMPILADO-2026_09_23.xlsx'
)
ARQ_USO_REDE_PROPRIA = (
    DIR_INPUTS / 'beneficiarios_atendidos_rede_propria-2026_09_23.xlsx'
)
ARQ_LOG = DIR_LOG_MAIN_ADD_MEMO_NAO_USOU_REDE_PROPRIA / f'{AGORA}_execucao.log'
ARQ_CONTROLE = (
    DIR_CONTROLE_MAIN_NAO_USOU_REDE_PROPRIA
    / f'{AGORA}_processos_add_memo_nao_uso_rede_propria.xlsx'
)

_TAG_AVALIADO_USO_REDE_PROPRIA = 'Script v2 - Avaliado Se Usou Rede Própria'
_TAG_MEMO_NAO_USOU_REDE_PROPRIA_ADD = (
    'Script v2 - Memo Não Usou Rede Propria Add'
)

_COLUNA_UTILIZOU = 'UTILIZOU A REDE PRÓPRIA?'
_RESPOSTAS_UTILIZOU = {'SIM': True, 'NÃO': False, 'NAO': False}

_VALORES_VERDADEIROS = frozenset({'true', 'verdadeiro', 'sim', 's', '1', 'x'})

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ARQ_LOG, encoding='utf-8'),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger()


class ErroAvaliacao(Exception):
    """Problema esperado nos dados de um processo (não é falha do script)."""


@dataclass(frozen=True)
class ResultadoConsulta:
    usaram: list[str]
    nao_usaram: list[str]
    nao_encontradas: list[str]


@dataclass(frozen=True)
class BasesUso:
    """Mapeia matrícula -> utilizou a rede própria.

    O valor é None quando a coluna de uso tem resposta diferente de
    SIM/NÃO para aquela matrícula.
    """

    titulares: dict[str, bool | None]
    dependentes: dict[str, bool | None]


def _normalizar_matricula(valor) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    mat = str(valor).strip().replace('-', '').replace('.', '').replace(' ', '')
    return mat or None


def _combinar_respostas(atual: bool | None, nova: bool | None) -> bool | None:
    """Combina respostas de linhas repetidas da mesma matrícula.

    Qualquer SIM prevalece; resposta inválida prevalece sobre NÃO.
    """
    if atual is True or nova is True:
        return True
    if atual is None or nova is None:
        return None
    return False


def _carregar_uso(aba: str, coluna_matricula: str) -> dict[str, bool | None]:
    df = pd.read_excel(
        io=ARQ_USO_REDE_PROPRIA,
        sheet_name=aba,
        dtype={coluna_matricula: str, _COLUNA_UTILIZOU: str},
    )

    uso: dict[str, bool | None] = {}
    for matricula, resposta in zip(
        df[coluna_matricula], df[_COLUNA_UTILIZOU], strict=True
    ):
        if pd.isna(matricula) or not str(matricula).strip():
            continue
        mat = str(matricula).strip().replace('-', '')
        chave = str(resposta).strip().upper() if pd.notna(resposta) else ''
        valor = _RESPOSTAS_UTILIZOU.get(chave)
        uso[mat] = _combinar_respostas(uso.get(mat, False), valor)

    return uso


def _consultar_uso(
    matriculas: list[str],
    base: dict[str, bool | None],
    descricao: str,
) -> ResultadoConsulta:
    encontradas = [m for m in matriculas if m in base]
    nao_encontradas = [m for m in matriculas if m not in base]

    invalidas = [m for m in encontradas if base[m] is None]
    if invalidas:
        raise ErroAvaliacao(
            f'Matrícula(s) de {descricao} com resposta inválida em '
            f'"{_COLUNA_UTILIZOU}": {", ".join(invalidas)}'
        )

    resultado = ResultadoConsulta(
        usaram=[m for m in encontradas if base[m] is True],
        nao_usaram=[m for m in encontradas if base[m] is False],
        nao_encontradas=nao_encontradas,
    )
    logger.info(
        f'{descricao} pesquisados na base | '
        f'Usaram: {resultado.usaram} | '
        f'Não usaram: {resultado.nao_usaram} | '
        f'Não encontrados: {resultado.nao_encontradas}'
    )
    return resultado


def _para_bool(valor) -> bool:
    if pd.isna(valor):
        return False
    if isinstance(valor, str):
        return valor.strip().lower() in _VALORES_VERDADEIROS
    return bool(valor)


def _extrair_matriculas(linha: pd.Series) -> tuple[str | None, list[str]]:
    titular = _normalizar_matricula(linha['matricula_titular'])

    valor_deps = linha['matriculas_dependentes']
    dependentes = (
        [
            m
            for m in (
                _normalizar_matricula(p) for p in str(valor_deps).split(';')
            )
            if m
        ]
        if pd.notna(valor_deps)
        else []
    )
    return titular, dependentes


def _montar_memo(registro, matricula_titular: str):
    """Retorna o memo se o titular ou algum dependente NÃO usou a rede."""
    uso = UsoRedeBeneficiarios(
        matricula_titular=matricula_titular,
        tit_usou=registro.tit_usou,
        tit_nao_usou=registro.tit_nao_usou,
        deps_que_usaram=registro.deps_que_usaram,
        deps_que_nao_usaram=registro.deps_que_nao_usaram,
    )
    if not uso.alguem_nao_usou:
        return None
    return MemoDisaUsoRede(
        nome_signatario='Bruna Miiller Lavarini',
        cargo_signatario='Gerência de Auditoria e Contas da Saúde',
        uso=uso,
    )


def _avaliar_processo(driver, linha, bases: BasesUso, registro) -> None:
    num_processo = registro.num_processo
    registro.tag_processo_novo = _para_bool(linha['marcador_processo_novo'])
    registro.tag_processo_velho = _para_bool(linha['marcador_processo_velho'])

    if not registro.tag_processo_novo:
        if not registro.tag_processo_velho:
            raise ErroAvaliacao('Processo não marcado como novo nem velho')
        logger.info(f'{num_processo} - Processo velho, ainda não implementado')
        return

    acessar_processo(driver, num_processo)

    if checar_marcador_existe(driver, _TAG_AVALIADO_USO_REDE_PROPRIA):
        registro.tag_avaliado_se_usou_rede_propria = True

        if checar_marcador_existe(driver, _TAG_MEMO_NAO_USOU_REDE_PROPRIA_ADD):
            # _verificar_ja_tem_memo_nao_usou_rede()
            ...

        return

    matricula_titular, matriculas_dependentes = _extrair_matriculas(linha)
    if not matricula_titular:
        raise ErroAvaliacao('Não há matrícula de titular')

    tit = _consultar_uso([matricula_titular], bases.titulares, 'titular')
    deps = _consultar_uso(
        matriculas_dependentes, bases.dependentes, 'dependente'
    )

    registro.tit_usou = bool(tit.usaram)
    registro.tit_nao_usou = bool(tit.nao_usaram + tit.nao_encontradas)
    registro.deps_que_usaram = deps.usaram
    registro.deps_que_nao_usaram = deps.nao_usaram + deps.nao_encontradas

    reabrir_processo(driver)
    adicionar_marcador(driver, _TAG_AVALIADO_USO_REDE_PROPRIA)
    registro.tag_avaliado_se_usou_rede_propria = True

    memo = _montar_memo(registro, matricula_titular)
    if memo:
        incluir_doc_sei_memo(driver, **memo.para_kwargs_inserir_doc())
        inserir_bloco_ass(driver, 7707212)
        adicionar_marcador(driver, _TAG_MEMO_NAO_USOU_REDE_PROPRIA_ADD)
        registro.tag_memo_nao_usou_rede_propria_add = True


def _processar_linha(driver, linha: pd.Series, bases: BasesUso) -> dict:
    t_ini = datetime.now()
    num_processo = linha['num_processo']
    registro = RegistroMainAddMemoNaoUsouRedePropria(
        num_processo=num_processo,
        matricula_titular=linha['matricula_titular'],
        matriculas_dependentes=linha['matriculas_dependentes'],
    )
    logger.info(f'{num_processo} - PROCESSAMENTO INICIADO')

    try:
        _avaliar_processo(driver, linha, bases, registro)
    except ErroAvaliacao as e:
        registro.erro = str(e)
        logger.warning(f'{num_processo} - {registro.erro}')
    except Exception as e:
        registro.erro = str(e)
        logger.exception(f'{num_processo} - ERRO NO PROCESSAMENTO')
    finally:
        duracao = datetime.now() - t_ini
        logger.info(f'{num_processo} - PROCESSAMENTO FINALIZADO ({duracao})')

    return registro.to_dict()


def _salvar_resultado(registros_processados: list[dict]) -> None:
    if not registros_processados:
        return
    df = pd.DataFrame(registros_processados)
    df.to_excel(ARQ_CONTROLE, index=False)


def main():
    registros_processados: list[dict] = []
    driver = None
    t_ini_geral = datetime.now()

    try:
        logger.info('================= INÍCIO DA EXECUÇÃO =================')

        df_processos = pd.read_excel(
            io=ARQ_COMPILADO,
            sheet_name='FINAL',
            dtype={'matricula_titular': str, 'matriculas_dependentes': str},
        )
        bases = BasesUso(
            titulares=_carregar_uso(
                'UI 2025 EX-TITULARES', 'MATRICULAS TITULARES'
            ),
            dependentes=_carregar_uso(
                'UI 2025 EX-DEPENDENTES', 'MATRICULAS DEPENDENTES'
            ),
        )

        driver = iniciar_driver(driver_type='chrome')
        driver.maximize_window()
        driver.get('https://www.sei.mg.gov.br')
        efetuar_login(driver, SEI_LOGIN, SEI_SENHA, SEI_ORGAO)

        for _, linha in df_processos.iterrows():
            registros_processados.append(
                _processar_linha(driver, linha, bases)
            )

    except Exception:
        logger.exception('Erro crítico na execução do main')
        raise

    finally:
        _salvar_resultado(registros_processados)
        if driver is not None:
            driver.quit()
        duracao_geral = datetime.now() - t_ini_geral
        logger.info(f'Duração total da execução: {duracao_geral}')
        logger.info('================== FIM DA EXECUÇÃO ==================')


if __name__ == '__main__':
    main()
